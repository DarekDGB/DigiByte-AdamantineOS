"""Deprecated internal compatibility orchestrator for execution_request_v1.

AOS-RT-004 lock:
- This module is retained only for legacy fixture compatibility and regression tests.
- It is not a public production entrypoint and is not exported from
  ``adamantine.v1.execution``.
- New wallet/runtime integrations must use the v2 runtime host and
  ``orchestrator_v2`` final decision boundary.
- Direct production imports of this module are unsupported.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, cast

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)
from adamantine.v1.policy.risk_policy import RiskPolicy


ORCHESTRATOR_V1_DEPRECATED_INTERNAL_ONLY = True
ORCHESTRATOR_V1_PUBLIC_ENTRYPOINT = False


class _V1FinalPolicyEvidence:
    __slots__ = (
        "source",
        "state",
        "outcome",
        "reason_id",
        "accepted_as_evidence",
        "final_approval",
        "handoff_allowed",
        "context_hash",
        "dominant_reason_ids",
    )

    def __init__(self, *, source: str, context_hash: str, reason_id: ReasonId = ReasonId.EVIDENCE_OK) -> None:
        self.source = source
        self.state = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
        self.outcome = "ALLOW_EVIDENCE"
        self.reason_id = reason_id
        self.accepted_as_evidence = True
        self.final_approval = False
        self.handoff_allowed = True
        self.context_hash = context_hash
        self.dominant_reason_ids = (reason_id.value,)


def _v1_runtime_evidence(*, source: str, context_hash: str) -> _V1FinalPolicyEvidence:
    return _V1FinalPolicyEvidence(source=source, context_hash=context_hash)


def _v1_final_policy_artifacts(result: object) -> dict[str, Any]:
    return {
        "final_policy": {
            "state": getattr(getattr(result, "state", None), "value", str(getattr(result, "state", "unknown"))),
            "outcome": getattr(result, "outcome", "unknown"),
            "final_approval": getattr(result, "final_approval", False),
            "handoff_allowed": getattr(result, "handoff_allowed", False),
            "stopped_at": getattr(result, "stopped_at", "unknown"),
            "evaluation_order": list(getattr(result, "evaluation_order", ())),
            "dominant_reason_ids": list(getattr(result, "dominant_reason_ids", ())),
        }
    }


def _v1_final_policy_reason(result: object) -> ReasonId:
    reason = getattr(result, "reason_id", ReasonId.UNKNOWN_EXTERNAL_REASON)
    if isinstance(reason, ReasonId):
        return reason
    if isinstance(reason, str):
        try:
            return ReasonId(reason)
        except ValueError:
            return ReasonId.UNKNOWN_EXTERNAL_REASON
    return ReasonId.UNKNOWN_EXTERNAL_REASON


def _safe_str(value: Any, *, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def _reason_from_message(msg: str) -> ReasonId:
    """
    TVAError messages are reason-id strings.
    Fall back to DENY_SCHEMA_INVALID if not recognized.
    """
    try:
        return ReasonId(msg)
    except Exception:
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
    # Envelope parser already validated these as str->str.
    out: dict[str, str] = {}
    for k, v in fields.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _is_qid_v2_login_evidence(qid_raw: Mapping[str, Any]) -> bool:
    return qid_raw.get("v") == "2" and qid_raw.get("kind") == "qid_login_v2"


def _extract_evidence(req_payload: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    """
    Evidence is carried inside the intent payload as:
      payload.evidence.qid
      payload.evidence.risk
    """
    ev = _require_mapping(req_payload.get("evidence"))
    if ev is None:
        return None, None

    qid = _require_mapping(ev.get("qid"))
    risk = _require_mapping(ev.get("risk"))
    return qid, risk


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
    """
    WSQK authority MUST be provided externally via authority.proofs.wsqk.
    Adamantine must not mint authority implicitly.
    """
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

    # Fail-closed: all must be present and correct types
    if not isinstance(w, str) or not w:
        return None
    if not isinstance(a, str) or not a:
        return None
    if not isinstance(ch, str) or not ch:
        return None
    if type(ia) is not int or type(ea) is not int:
        return None
    if not isinstance(n, str) or not n:
        return None

    # Binding: must match envelope context + nonce/timebox
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


def orchestrate_execution_v1(
    *,
    payload: Any,  # <- critical: accept Any so we never raise on bad caller types
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
    qid_verifier: Callable[[Mapping[str, Any]], None] | None = None,
    policy: RiskPolicy | None = None,
) -> dict[str, Any]:
    """
    Deprecated internal compatibility path for execution_request_v1.

    AOS-RT-004 lock:
    - retained for legacy fixtures and regression tests only
    - not exported as a public production runtime surface
    - new integrations must use the v2 runtime host / orchestrator_v2 path

    Invariants:
    - Always returns execution_response_v1
    - Never raises
    - Deny-by-default
    - ALLOW path: EQC -> WSQK(proof) -> TVA -> final policy -> executor
    """
    # Fail-closed: normalize payload for safe error handling in ALL exception paths.
    p: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}

    try:
        req = parse_execution_request_envelope_v1(payload=cast(Mapping[str, Any], p), now=now)
        fields = _extract_fields(p)

        pol = policy or RiskPolicy()
        pol.validate()

        # Evidence is carried inside the intent payload
        qid_raw, risk_raw = _extract_evidence(req.payload)

        session = None
        if qid_raw is not None:
            if _is_qid_v2_login_evidence(qid_raw) and qid_verifier is None:
                raise AdapterError(
                    ReasonId.QID_AUTHENTICITY_VERIFIER_MISSING,
                    "qid_verifier is required for Q-ID v2 evidence",
                )
            if qid_verifier is not None:
                try:
                    qid_verifier(qid_raw)
                except AdapterError:
                    raise
                except Exception as ex:
                    raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, f"qid_verifier error: {ex}")
            session = parse_qid_session(payload=qid_raw, now=now)

        risk = None
        if risk_raw is not None:
            risk = parse_risk_report(
                payload=risk_raw,
                now=now,
                expected_context_hash=req.context.context_hash,
                policy=pol,
            )

        eqc = evaluate_eqc(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            fields=fields,
            session=session,
            risk=risk,
            now=now,
            policy=pol,
        )

        if eqc.verdict is not Verdict.ALLOW:
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=eqc.context_hash,
                status="deny",
                reason_id=eqc.reason_ids[0],
                protection_mode="legacy",
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
            )

        # WSQK authority must be present as an external proof
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
                protection_mode="legacy",
                tva_allowed=False,
                eqc_allowed=True,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
            )

        # ExecutionRequest is intentionally opaque at foundation stage
        exec_req = ExecutionRequest(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            payload="opaque",
        )

        enforce_tva(
            req.context,
            eqc.verdict,
            wsqk,
            now=now,
            nonce_store=nonce_store,
        )

        final_policy = evaluate_final_policy_engine(
            shield=_v1_runtime_evidence(source="v1:no_shield_contract", context_hash=req.context.context_hash),
            wsqk_v2=_v1_runtime_evidence(source="v1:wsqk_authority", context_hash=wsqk.context_hash),
            qid=_v1_runtime_evidence(source="v1:qid_session" if session is not None else "v1:qid_absent_allowed", context_hash=req.context.context_hash),
            adaptive_core=_v1_runtime_evidence(source="v1:risk_report" if risk is not None else "v1:risk_absent_allowed", context_hash=req.context.context_hash),
            ai_gateway=_v1_runtime_evidence(source="v1:ai_gateway_not_required", context_hash=req.context.context_hash),
            replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
            wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
            human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
            expected_context_hash=req.context.context_hash,
        )
        if final_policy.state is not FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION:
            final_reason = _v1_final_policy_reason(final_policy)
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=final_reason,
                protection_mode="legacy",
                tva_allowed=True,
                eqc_allowed=True,
                wsqk_allowed=True,
                nonce_consumed=True,
                timebox_valid=True,
                artifacts=_v1_final_policy_artifacts(final_policy),
            )

        out = executor.execute(exec_req)

        return build_execution_response_v1(
            request_id=req.request_id,
            intent=req.intent,
            action=req.context.action,
            context_hash=req.context.context_hash,
            status="allow",
            reason_id=ReasonId.OK_ALLOW,
            protection_mode="legacy",
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=True,
            timebox_valid=True,
            artifacts={"executor_result": out},
        )

    except AdapterError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        action = _safe_str((_require_mapping(p.get("context")) or {}).get("action"), fallback="invalid-action")
        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="error",
            reason_id=e.reason_id,
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
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
            protection_mode="legacy",
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
            protection_mode="legacy",
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
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": str(e)},
        )
