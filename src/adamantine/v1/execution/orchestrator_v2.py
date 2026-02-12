from __future__ import annotations

from typing import Any, Mapping, cast

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.eqc.evaluator import evaluate_eqc_v2
from adamantine.v1.execution.boundary import run_with_tva
from adamantine.v1.execution.envelope_v2 import parse_execution_request_envelope_v2
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.policy.risk_policy import RiskPolicy


REQUIRED_SHIELD_LAYERS_V3: tuple[str, ...] = (
    "sentinel_ai",
    "adn",
    "dqsn",
    "qwg",
    "guardian_wallet",
)


def _safe_str(value: Any, *, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def _reason_from_message(msg: str) -> ReasonId:
    try:
        return ReasonId(msg)
    except Exception:
        return ReasonId.DENY_SCHEMA_INVALID


def _coerce_reason_id(value: Any) -> ReasonId:
    if isinstance(value, ReasonId):
        return value
    if isinstance(value, str) and value:
        try:
            return ReasonId(value)
        except Exception:
            return ReasonId.DENY_SCHEMA_INVALID
    return ReasonId.DENY_SCHEMA_INVALID


def _require_mapping(obj: Any) -> Mapping[str, Any] | None:
    if obj is None:
        return None
    if not isinstance(obj, Mapping):
        return None
    return cast(Mapping[str, Any], obj)


def _extract_fields(original_payload: Mapping[str, Any]) -> dict[str, str] | None:
    ctx = _require_mapping(original_payload.get("context"))
    if ctx is None:
        return None
    fields = _require_mapping(ctx.get("fields"))
    if fields is None:
        return None
    out: dict[str, str] = {}
    for k, v in fields.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _extract_wsqk_authority(
    *,
    wallet_id: str,
    action: str,
    context_hash: str,
    nonce_value: str,
    issued_at: int,
    expires_at: int,
    authority_proofs: Mapping[str, Any] | None,
) -> WSQKAuthority | None:
    if authority_proofs is None:
        return None

    wsqk = _require_mapping(authority_proofs.get("wsqk"))
    if wsqk is None:
        return None

    w = wsqk.get("wallet_id")
    a = wsqk.get("action")
    ch = wsqk.get("context_hash")
    ia = wsqk.get("issued_at")
    ea = wsqk.get("expires_at")
    n = wsqk.get("nonce")

    if not isinstance(w, str) or not w:
        return None
    if not isinstance(a, str) or not a:
        return None
    if not isinstance(ch, str) or not ch:
        return None
    if not isinstance(ia, int) or not isinstance(ea, int):
        return None
    if not isinstance(n, str) or not n:
        return None

    if w != wallet_id or a != action or ch != context_hash:
        return None
    if n != nonce_value:
        return None
    if ia != issued_at or ea != expires_at:
        return None

    return WSQKAuthority(
        wallet_id=w,
        action=a,
        context_hash=ch,
        issued_at=ia,
        expires_at=ea,
        nonce=n,
    )


def _default_reason_map(policy: RiskPolicy) -> Any:
    if policy.policy_pack is not None:
        return policy.policy_pack.external_reason_map
    return PolicyPack().external_reason_map


def _build_mandatory_reason_registry(policy: RiskPolicy) -> ExternalReasonRegistryV1:
    """
    Phase M hard-lock:
    - ExternalReasonRegistryV1 is mandatory for orchestrator_v2.
    - For now we derive allowlists from policy pack allowlist (single source of truth).
    - Future: split per-layer allowlists (contract bump + tests).
    """
    allowed = tuple(policy.effective_allowed_external_reason_ids())
    if len(allowed) == 0:
        raise ValueError("policy must provide non-empty allowed external reason ids")

    shield_allowlists = tuple(
        ExternalReasonLayerAllowlist(layer=layer, allowed_external_reason_ids=allowed)
        for layer in REQUIRED_SHIELD_LAYERS_V3
    )

    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=allowed,
        shield_layer_allowlists=shield_allowlists,
    )
    reg.validate()
    return reg


def _map_shield_adapter_reason(rid: ReasonId) -> ReasonId:
    """Map shield adapter failures to stable, wallet-facing reasons.

    Governance:
    - Structural invalidity in shield payloads should surface as EQC_INVALID_SHIELD_BUNDLE
      (so callers don't see generic adapter internals).
    - External reason disallow/unmapped reasons remain UNKNOWN_EXTERNAL_REASON.
    """

    if rid in (ReasonId.DENY_ADAPTER_INVALID, ReasonId.DENY_VERSION_MISMATCH):
        return ReasonId.EQC_INVALID_SHIELD_BUNDLE
    return rid


def orchestrate_execution_v2(
    *,
    payload: Any,
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
    policy: RiskPolicy | None = None,
) -> dict[str, Any]:
    p: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}

    try:
        req = parse_execution_request_envelope_v2(payload=cast(Mapping[str, Any], p), now=now)
        fields = _extract_fields(p)

        pol = policy or RiskPolicy()
        pol.validate()
        reason_map = _default_reason_map(pol)

        # Phase M hard-lock: registry MUST exist and be valid (deny-by-default).
        try:
            reason_registry = _build_mandatory_reason_registry(pol)
        except Exception as e:
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.DENY_POLICY,
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
                artifacts={"error": f"reason registry build failed: {e}"},
            )

        session = parse_qid_session(payload=req.evidence_qid, now=now)

        oracle = parse_adaptive_core_oracle_v3(
            payload=req.evidence_oracle,
            now=now,
            expected_context_hash=req.context.context_hash,
            reason_map=reason_map,
            reason_registry=reason_registry,
            policy=pol,
        )

        # Governance: map shield adapter failures to stable EQC-facing reasons.
        try:
            shield = parse_shield_bundle_v3(
                payload=req.evidence_shield,
                now=now,
                expected_context_hash=req.context.context_hash,
                reason_map=reason_map,
                reason_registry=reason_registry,
            )
        except AdapterError as e:
            mapped = _map_shield_adapter_reason(e.reason_id)
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=mapped,
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
                artifacts={
                    "shield_adapter_reason": e.reason_id.value,
                    "shield_adapter_message": e.message,
                },
            )

        if tuple(shield.required_layers) != REQUIRED_SHIELD_LAYERS_V3:
            expected = list(REQUIRED_SHIELD_LAYERS_V3)
            got = list(shield.required_layers)
            missing = [x for x in expected if x not in got]
            extra = [x for x in got if x not in expected]
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
                artifacts={
                    "shield_required_layers_expected": expected,
                    "shield_required_layers_got": got,
                    "shield_required_layers_missing": missing,
                    "shield_required_layers_extra": extra,
                },
            )

        eqc = evaluate_eqc_v2(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            fields=fields,
            session=session,
            oracle=oracle,
            shield=shield,
            now=now,
            policy=pol,
        )

        if eqc.verdict is not Verdict.ALLOW:
            rid = _coerce_reason_id(eqc.reason_ids[0] if eqc.reason_ids else ReasonId.DENY_SCHEMA_INVALID.value)
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=eqc.context_hash,
                status="deny",
                reason_id=rid,
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
                artifacts={"evidence": {"qid": True, "oracle": True, "shield": True}},
            )

        wsqk = _extract_wsqk_authority(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            context_hash=req.context.context_hash,
            nonce_value=req.nonce_value,
            issued_at=req.issued_at,
            expires_at=req.expires_at,
            authority_proofs=req.authority_proofs,
        )
        if wsqk is None:
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.DENY_AUTHORITY_INVALID,
                tva_allowed=False,
                eqc_allowed=True,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
            )

        exec_req = ExecutionRequest(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            payload="opaque",
        )

        out = run_with_tva(
            executor=executor,
            request=exec_req,
            context=req.context,
            verdict=eqc.verdict,
            authority=wsqk,
            now=now,
            nonce_store=nonce_store,
        )

        return build_execution_response_v1(
            request_id=req.request_id,
            intent=req.intent,
            action=req.context.action,
            context_hash=req.context.context_hash,
            status="allow",
            reason_id=ReasonId.OK_ALLOW,
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=True,
            timebox_valid=True,
            artifacts={"executor_result": out},
        )

    except AdapterError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        ctx = _require_mapping(p.get("context")) or {}
        action = _safe_str(ctx.get("action"), fallback="invalid-action")
        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="deny",
            reason_id=e.reason_id,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=True,
            artifacts={"error": e.message},
        )

    except TVAError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        action = _safe_str((_require_mapping(p.get("context")) or {}).get("action"), fallback="invalid-action")
        rid = _reason_from_message(str(e))
        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="deny",
            reason_id=rid,
            tva_allowed=False,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=False,
            timebox_valid=True,
            artifacts={"error": str(e)},
        )

    except EnvelopeError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        ctx = _require_mapping(p.get("context")) or {}
        action = _safe_str(ctx.get("action"), fallback="invalid-action")
        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="error",
            reason_id=e.reason_id,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": e.message},
        )

    except Exception as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        ctx = _require_mapping(p.get("context")) or {}
        action = _safe_str(ctx.get("action"), fallback="invalid-action")
        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="error",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": str(e)},
        )
