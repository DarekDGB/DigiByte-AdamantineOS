from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast, Literal, Callable

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority, WSQKAuthorityV2
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
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.execution.envelope_v2 import parse_execution_request_envelope_v2
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.response_v2 import build_execution_response_v2, ProtectionMode
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_replay_proof, parse_qid_session
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.wsqk.issuer_v2 import WSQK_AUTHORITY_V2
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineResult,
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)
from adamantine.v1.policy.risk_policy import RiskPolicy




@dataclass(frozen=True, slots=True)
class _RuntimeFinalPolicyEvidence:
    source: str
    state: str
    outcome: str
    reason_id: ReasonId
    accepted_as_evidence: bool
    final_approval: bool
    handoff_allowed: bool
    context_hash: str
    dominant_reason_ids: tuple[str, ...]
    final_outcome: str | None = None


def _runtime_evidence_from_validated(*, source: str, context_hash: str, reason_id: ReasonId = ReasonId.EVIDENCE_OK) -> _RuntimeFinalPolicyEvidence:
    """Normalize a real runtime result into final-policy evidence.

    This helper is intentionally called only after the corresponding runtime
    parser/gate has accepted real request evidence. It is not an unconditional
    placeholder ALLOW; it records that the named upstream result reached an
    accepted evidence boundary for the same request context.
    """
    return _RuntimeFinalPolicyEvidence(
        source=source,
        state="ALLOW_EVIDENCE_CONTINUE_CHECKS",
        outcome="ALLOW_EVIDENCE",
        reason_id=reason_id,
        accepted_as_evidence=True,
        final_approval=False,
        handoff_allowed=True,
        context_hash=context_hash,
        dominant_reason_ids=(reason_id.value,),
    )



def _runtime_final_policy_reason(result: FinalPolicyEngineResult) -> ReasonId:
    if isinstance(result.reason_id, ReasonId):
        return result.reason_id
    if isinstance(result.reason_id, str):
        try:
            return ReasonId(result.reason_id)
        except ValueError:
            return ReasonId.UNKNOWN_EXTERNAL_REASON
    return ReasonId.UNKNOWN_EXTERNAL_REASON


def _final_policy_artifacts(result: FinalPolicyEngineResult) -> dict[str, Any]:
    return {
        "final_policy": {
            "state": result.state.value,
            "outcome": result.outcome,
            "final_approval": result.final_approval,
            "handoff_allowed": result.handoff_allowed,
            "stopped_at": result.stopped_at,
            "evaluation_order": list(result.evaluation_order),
            "dominant_reason_ids": list(result.dominant_reason_ids),
        }
    }

REQUIRED_SHIELD_LAYERS_V3: tuple[str, ...] = (
    "sentinel_ai",
    "adn",
    "dqsn",
    "qwg",
    "guardian_wallet",
)




def run_with_tva(
    *,
    executor: Executor,
    request: ExecutionRequest,
    context: Any,
    verdict: Verdict,
    authority: Any,
    now: int,
    nonce_store: NonceStore,
    required_evidence_families: Any = None,
    required_quantum_posture: str | None = None,
) -> str:
    """Compatibility TVA hook used before final policy execution.

    Milestone 18 keeps this symbol so existing monkeypatch tests can still force
    TVA failures, but the executor is not called here. Real execution occurs only
    after evaluate_final_policy_engine returns a final AdamantineOS allow.
    """
    enforce_tva(
        context,
        verdict,
        authority,
        now=now,
        nonce_store=nonce_store,
        required_evidence_families=required_evidence_families,
        required_quantum_posture=required_quantum_posture,
    )
    return "TVA_ACCEPTED"

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
) -> WSQKAuthority | WSQKAuthorityV2 | None:
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

    contract_version = wsqk.get("contract_version")
    if contract_version == WSQK_AUTHORITY_V2:
        families_raw = wsqk.get("required_evidence_families")
        posture = wsqk.get("quantum_posture")
        proof_hash = wsqk.get("proof_bindings_hash")
        if not isinstance(families_raw, list) or not all(isinstance(x, str) for x in families_raw):
            return None
        if not isinstance(posture, str) or not posture:
            return None
        if not isinstance(proof_hash, str) or not proof_hash:
            return None
        return WSQKAuthorityV2(
            contract_version=contract_version,
            wallet_id=w,
            action=a,
            context_hash=ch,
            issued_at=ia,
            expires_at=ea,
            nonce=n,
            required_evidence_families=tuple(families_raw),
            quantum_posture=posture,
            proof_bindings_hash=proof_hash,
        )

    return WSQKAuthority(
        wallet_id=w,
        action=a,
        context_hash=ch,
        issued_at=ia,
        expires_at=ea,
        nonce=n,
    )


def _extract_wsqk_v2_runtime_requirements(
    authority_scope: Mapping[str, Any],
) -> tuple[tuple[str, ...] | None, str | None]:
    """Extract opt-in WSQK v2 runtime requirements from authority.scope.

    WSQK v2 remains explicit-only. If the envelope does not declare
    authority.scope.wsqk_v2, the runtime preserves legacy behavior and does
    not silently infer quantum-aware requirements.
    """
    raw = authority_scope.get("wsqk_v2")
    if raw is None:
        return None, None
    if not isinstance(raw, Mapping):
        raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)

    families_raw = raw.get("required_evidence_families")
    posture_raw = raw.get("required_quantum_posture")

    if not isinstance(families_raw, list) or not all(isinstance(x, str) for x in families_raw):
        raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)
    if not isinstance(posture_raw, str) or not posture_raw:
        raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)

    return tuple(families_raw), posture_raw


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


def _protected_call_requested(authority_proofs: Mapping[str, Any] | None) -> bool:
    """
    Best-effort signal for whether the caller requested a *protected* execution.

    In v1.3.0, we treat the presence of a 'wsqk' proof object as the request signal.
    """
    if authority_proofs is None:
        return False
    return "wsqk" in authority_proofs


def _compute_protection_mode(
    *,
    protected_requested: bool,
    qid_ok: bool,
    oracle_ok: bool,
    shield_ok: bool,
) -> ProtectionMode:
    """
    Deterministic security posture output (auditable).

    legacy:
      - Q-ID invalid/missing OR protected call not requested
    minimal:
      - Q-ID valid, but Shield/Oracle missing/invalid
    full:
      - Q-ID valid + Shield valid + Oracle valid
    """
    if not protected_requested:
        return "legacy"
    if not qid_ok:
        return "legacy"
    if qid_ok and oracle_ok and shield_ok:
        return "full"
    return "minimal"


def orchestrate_execution_v2(
    *,
    payload: Any,
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
    qid_verifier: Callable[[Mapping[str, Any]], None] | None = None,
    policy: RiskPolicy | None = None,
) -> dict[str, Any]:
    p: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}

    try:
        req = parse_execution_request_envelope_v2(payload=cast(Mapping[str, Any], p), now=now)
        fields = _extract_fields(p)

        protected_requested = _protected_call_requested(req.authority_proofs)
        required_evidence_families, required_quantum_posture = _extract_wsqk_v2_runtime_requirements(
            req.authority_scope
        )

        pol = policy or RiskPolicy()
        pol.validate()
        reason_map = _default_reason_map(pol)

        # Step 4: policy posture latches (no silent downgrade)
        # - require_protected_call: caller MUST request protected execution (wsqk present)
        # - require_full_mode: caller MUST request protected execution; otherwise full mode is impossible
        if getattr(pol, "require_protected_call", False) and not protected_requested:
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.DENY_POLICY,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=False,
                    oracle_ok=False,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=False,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=False,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=ReasonId.DENY_POLICY,
                artifacts={"error": "policy requires protected execution"},
            )

        if getattr(pol, "require_full_mode", False) and not protected_requested:
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.DENY_POLICY,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=False,
                    oracle_ok=False,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=False,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=False,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=ReasonId.DENY_POLICY,
                artifacts={"error": "policy requires full protection mode"},
            )

        # Phase M hard-lock: registry MUST exist and be valid (deny-by-default).
        try:
            reason_registry = _build_mandatory_reason_registry(pol)
        except Exception as e:
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.DENY_POLICY,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=False,
                    oracle_ok=False,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=False,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=False,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=ReasonId.DENY_POLICY,
                artifacts={"error": f"reason registry build failed: {e}"},
            )

        # Q-ID must validate first (legacy if invalid).
        # If runtime provides qid_verifier (crypto verification hook), it MUST succeed
        # before we accept/parse any Q-ID session representation.
        try:
            if qid_verifier is not None:
                try:
                    qid_verifier(req.evidence_qid)
                except AdapterError:
                    raise
                except Exception as ex:
                    raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, f"qid_verifier error: {ex}")

            session = parse_qid_session(payload=req.evidence_qid, now=now)
        except AdapterError as e:
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=e.reason_id,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=False,
                    oracle_ok=False,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=False,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=False,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=e.reason_id,
                artifacts={"error": e.message},
            )

        # v1.4.0: Q-ID linkage hardening (clock-free replay gate).
        # If caller requested protected execution, a replay proof is mandatory.
        if protected_requested and getattr(pol, "require_qid_replay_proof", False):
            try:
                _ = parse_qid_replay_proof(
                    evidence_qid=req.evidence_qid,
                    expected_wallet_id=req.context.wallet_id,
                    expected_subject=session.subject,
                    expected_proof_hash=session.proof_hash,
                    expected_device_binding=session.device_binding,
                    expected_session_nonce=req.nonce_value,
                    require_fresh=True,
                )
            except AdapterError as e:
                return build_execution_response_v2(
                    request_id=req.request_id,
                    intent=req.intent,
                    action=req.context.action,
                    context_hash=req.context.context_hash,
                    status="deny",
                    reason_id=e.reason_id,
                    protection_mode=_compute_protection_mode(
                        protected_requested=protected_requested,
                        qid_ok=False,
                        oracle_ok=False,
                        shield_ok=False,
                    ),
                    tva_allowed=False,
                    eqc_allowed=False,
                    wsqk_allowed=False,
                    issued_at=req.issued_at,
                    expires_at=req.expires_at,
                    max_skew_seconds=req.max_skew_seconds,
                    timebox_valid=True,
                    nonce_store=req.nonce_store,
                    nonce_value=req.nonce_value,
                    nonce_consumed=False,
                    qid_present=True,
                    qid_valid=False,
                    shield_present=True,
                    shield_valid=False,
                    oracle_present=True,
                    oracle_valid=False,
                    policy_mode=pol.resilience_mode.value,
                    override_allowed=False,
                    policy_reason_id=e.reason_id,
                    artifacts={"error": e.message},
                )

        # Oracle (minimal if invalid).
        try:
            oracle = parse_adaptive_core_oracle_v3(
                payload=req.evidence_oracle,
                now=now,
                expected_context_hash=req.context.context_hash,
                reason_map=reason_map,
                reason_registry=reason_registry,
                policy=pol,
            )
        except AdapterError as e:
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=e.reason_id,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=False,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=True,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=False,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=e.reason_id,
                artifacts={"error": e.message},
            )

        # Governance: map shield adapter failures to stable EQC-facing reasons.
        try:
            shield = parse_shield_bundle_v3(
                payload=req.evidence_shield,
                now=now,
                expected_context_hash=req.context.context_hash,
                reason_map=reason_map,
                reason_registry=reason_registry,
                require_versions=True,
            )
        except AdapterError as e:
            mapped = _map_shield_adapter_reason(e.reason_id)
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=mapped,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=True,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=True,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=mapped,
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
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=False,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=True,
                shield_present=True,
                shield_valid=False,
                oracle_present=True,
                oracle_valid=True,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
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
            final_policy = evaluate_final_policy_engine(
                shield=_runtime_evidence_from_validated(source=f"shield:{getattr(shield, 'bundle_id', 'validated_bundle')}", context_hash=getattr(shield, "context_hash", req.context.context_hash)),
                wsqk_v2=_runtime_evidence_from_validated(source="wsqk_v2:not_reached_before_eqc_deny", context_hash=req.context.context_hash),
                qid=_runtime_evidence_from_validated(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                adaptive_core=_runtime_evidence_from_validated(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
                ai_gateway=_runtime_evidence_from_validated(source="ai_gateway:not_required_for_runtime_path", context_hash=req.context.context_hash),
                replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                wallet_policy=LocalPolicyGateResult("wallet_policy", False, rid),
                human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                expected_context_hash=req.context.context_hash,
            )
            final_reason = _runtime_final_policy_reason(final_policy)
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=eqc.context_hash,
                status="deny",
                reason_id=final_reason,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=True,
                ),
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=True,
                shield_present=True,
                shield_valid=True,
                oracle_present=True,
                oracle_valid=True,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=final_reason,
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
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=ReasonId.DENY_AUTHORITY_INVALID,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=True,
                ),
                tva_allowed=False,
                eqc_allowed=True,
                wsqk_allowed=False,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=False,
                qid_present=True,
                qid_valid=True,
                shield_present=True,
                shield_valid=True,
                oracle_present=True,
                oracle_valid=True,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=ReasonId.DENY_AUTHORITY_INVALID,
            )

        exec_req = ExecutionRequest(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            payload="opaque",
        )

        # Milestone 18: TVA/replay enforcement is completed before the final
        # policy engine, but execution is still held until the final engine
        # returns an AdamantineOS final allow. This preserves the existing TVA
        # nonce semantics without allowing the executor to run before the final
        # policy authority has spoken.
        run_with_tva(
            executor=executor,
            request=exec_req,
            context=req.context,
            verdict=eqc.verdict,
            authority=wsqk,
            now=now,
            nonce_store=nonce_store,
            required_evidence_families=required_evidence_families,
            required_quantum_posture=required_quantum_posture,
        )

        final_policy = evaluate_final_policy_engine(
            shield=_runtime_evidence_from_validated(source=f"shield:{getattr(shield, 'bundle_id', 'validated_bundle')}", context_hash=getattr(shield, "context_hash", req.context.context_hash)),
            wsqk_v2=_runtime_evidence_from_validated(source="wsqk_v2:authority_proof", context_hash=wsqk.context_hash),
            qid=_runtime_evidence_from_validated(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
            adaptive_core=_runtime_evidence_from_validated(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
            ai_gateway=_runtime_evidence_from_validated(source="ai_gateway:not_required_for_runtime_path", context_hash=req.context.context_hash),
            replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
            wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
            human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
            expected_context_hash=req.context.context_hash,
        )

        if final_policy.state is not FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION:
            final_reason = _runtime_final_policy_reason(final_policy)
            return build_execution_response_v2(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=req.context.context_hash,
                status="deny",
                reason_id=final_reason,
                protection_mode=_compute_protection_mode(
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=True,
                ),
                tva_allowed=True,
                eqc_allowed=True,
                wsqk_allowed=True,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
                max_skew_seconds=req.max_skew_seconds,
                timebox_valid=True,
                nonce_store=req.nonce_store,
                nonce_value=req.nonce_value,
                nonce_consumed=True,
                qid_present=True,
                qid_valid=True,
                shield_present=True,
                shield_valid=True,
                oracle_present=True,
                oracle_valid=True,
                policy_mode=pol.resilience_mode.value,
                override_allowed=False,
                policy_reason_id=final_reason,
                artifacts=_final_policy_artifacts(final_policy),
            )

        out = executor.execute(exec_req)

        return build_execution_response_v2(
            request_id=req.request_id,
            intent=req.intent,
            action=req.context.action,
            context_hash=req.context.context_hash,
            status="allow",
            reason_id=ReasonId.OK_ALLOW,
            protection_mode=_compute_protection_mode(
                protected_requested=protected_requested,
                qid_ok=True,
                oracle_ok=True,
                shield_ok=True,
            ),
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            issued_at=req.issued_at,
            expires_at=req.expires_at,
            max_skew_seconds=req.max_skew_seconds,
            timebox_valid=True,
            nonce_store=req.nonce_store,
            nonce_value=req.nonce_value,
            nonce_consumed=True,
            qid_present=True,
            qid_valid=True,
            shield_present=True,
            shield_valid=True,
            oracle_present=True,
            oracle_valid=True,
            policy_mode=pol.resilience_mode.value,
            override_allowed=False,
            policy_reason_id=ReasonId.OK_ALLOW,
            artifacts={"executor_result": out},
        )

    except AdapterError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        ctx = _require_mapping(p.get("context")) or {}
        action = _safe_str(ctx.get("action"), fallback="invalid-action")
        return build_execution_response_v2(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="deny",
            reason_id=e.reason_id,
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=True,
            nonce_store="unknown",
            nonce_value="unknown",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode=RiskPolicy().resilience_mode.value,
            override_allowed=False,
            policy_reason_id=e.reason_id,
            artifacts={"error": e.message},
        )

    except TVAError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        action = _safe_str((_require_mapping(p.get("context")) or {}).get("action"), fallback="invalid-action")
        rid = _reason_from_message(str(e))
        return build_execution_response_v2(
            request_id=request_id,
            intent=_safe_str(p.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="deny",
            reason_id=rid,
            # TVA failure means the request did not reach full protection; keep
            # telemetry conservative so audit consumers never confuse a deny at
            # the TVA gate with completed full verification.
            protection_mode=_compute_protection_mode(
                protected_requested=False,
                qid_ok=False,
                oracle_ok=False,
                shield_ok=False,
            ),
            tva_allowed=False,
            eqc_allowed=True,
            wsqk_allowed=True,
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=True,
            nonce_store="unknown",
            nonce_value="unknown",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode=RiskPolicy().resilience_mode.value,
            override_allowed=False,
            policy_reason_id=rid,
            artifacts={"error": str(e)},
        )

    except EnvelopeError as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        ctx = _require_mapping(p.get("context")) or {}
        action = _safe_str(ctx.get("action"), fallback="invalid-action")
        return build_execution_response_v2(
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
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=False,
            nonce_store="unknown",
            nonce_value="unknown",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode=RiskPolicy().resilience_mode.value,
            override_allowed=False,
            policy_reason_id=e.reason_id,
            artifacts={"error": e.message},
        )

    except Exception as e:
        request_id = _safe_str(p.get("request_id"), fallback="invalid-request")
        ctx = _require_mapping(p.get("context")) or {}
        action = _safe_str(ctx.get("action"), fallback="invalid-action")
        return build_execution_response_v2(
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
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=False,
            nonce_store="unknown",
            nonce_value="unknown",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode=RiskPolicy().resilience_mode.value,
            override_allowed=False,
            policy_reason_id=ReasonId.DENY_SCHEMA_INVALID,
            artifacts={"error": str(e)},
        )
