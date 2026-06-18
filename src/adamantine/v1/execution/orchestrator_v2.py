from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast, Literal, Callable

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority, WSQKAuthorityV2
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
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
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import (
    ShieldReceiptVerificationResult,
    ShieldReceiptVerificationState,
    verify_shield_orchestrator_receipt,
)
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.wsqk.issuer_v2 import WSQK_AUTHORITY_V2
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineResult,
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)
from adamantine.v1.policy.risk_policy import RiskPolicy, ShieldRuntimeBoundary


AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE = "ai_gateway:not_required_for_runtime_path"
AI_GATEWAY_V2_RUNTIME_ADVISORY_POSTURE = (
    "AI Gateway is advisory/evidence-only in the v2 RuntimeHost path; this marker means "
    "the request did not enter through an AI Gateway ingress and cannot approve or deny execution."
)


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


def _runtime_evidence_from_boundary(
    *,
    source: str,
    context_hash: str,
    reason_id: ReasonId = ReasonId.EVIDENCE_OK,
    accepted: bool,
) -> _RuntimeFinalPolicyEvidence:
    """Normalize a real runtime boundary result into final-policy evidence.

    Milestone 18 Option 2 deliberately feeds the final policy engine real
    accept/reject outcomes from each live runtime boundary. A source that fails
    parsing, binding, posture, or structural checks is represented as rejected
    evidence at its own gate instead of being hidden behind an upstream return.
    """
    return _RuntimeFinalPolicyEvidence(
        source=source,
        state="ALLOW_EVIDENCE_CONTINUE_CHECKS" if accepted else "DENY_EVIDENCE_REJECTED",
        outcome="ALLOW_EVIDENCE" if accepted else "DENY",
        reason_id=reason_id,
        accepted_as_evidence=accepted,
        final_approval=False,
        handoff_allowed=accepted,
        context_hash=context_hash,
        dominant_reason_ids=(reason_id.value,),
    )


def _runtime_evidence_accepted(*, source: str, context_hash: str, reason_id: ReasonId = ReasonId.EVIDENCE_OK) -> _RuntimeFinalPolicyEvidence:
    return _runtime_evidence_from_boundary(source=source, context_hash=context_hash, reason_id=reason_id, accepted=True)


def _runtime_evidence_rejected(*, source: str, context_hash: str, reason_id: ReasonId) -> _RuntimeFinalPolicyEvidence:
    return _runtime_evidence_from_boundary(source=source, context_hash=context_hash, reason_id=reason_id, accepted=False)


def _runtime_evidence_from_shield_receipt(
    *,
    result: ShieldReceiptVerificationResult,
    expected_context_hash: str,
) -> _RuntimeFinalPolicyEvidence:
    """Normalize a Shield Orchestrator receipt verification result.

    AOS-M-002A locks the architecture choice without granting Shield final
    authority. Only a verified ALLOW receipt becomes accepted Shield evidence;
    DENY/HUMAN_REVIEW/invalid receipt states remain fail-closed at the Shield
    gate. Even accepted Shield evidence always has final_approval=False.
    """

    context_hash = result.context_hash if isinstance(result.context_hash, str) else expected_context_hash
    receipt_hash = result.receipt_hash if isinstance(result.receipt_hash, str) else "unverified"
    accepted = result.state is ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    return _RuntimeFinalPolicyEvidence(
        source=f"shield_orchestrator_receipt:{receipt_hash}",
        state=result.state.value if accepted else "DENY_EVIDENCE_REJECTED",
        outcome="ALLOW_EVIDENCE" if accepted else "DENY",
        reason_id=result.reason_id,
        accepted_as_evidence=accepted,
        final_approval=False,
        handoff_allowed=result.handoff_allowed if accepted else False,
        context_hash=context_hash,
        dominant_reason_ids=tuple(result.dominant_reason_ids) if accepted else (result.reason_id.value,),
        final_outcome=result.final_outcome,
    )


def _shield_runtime_boundary_artifact(
    *,
    policy: RiskPolicy,
    receipt_result: ShieldReceiptVerificationResult,
    route_status: str,
) -> dict[str, Any]:
    return {
        "shield_runtime_boundary": {
            "mode": policy.shield_runtime_boundary.value,
            "receipt_state": receipt_result.state.value,
            "verified": receipt_result.verified,
            "accepted_as_evidence": (
                receipt_result.state is ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
            ),
            "final_approval": False,
            "handoff_allowed": receipt_result.handoff_allowed,
            "receipt_hash": receipt_result.receipt_hash,
            "route_status": route_status,
        }
    }



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
    artifact = {
        "state": result.state.value,
        "outcome": result.outcome,
        "final_approval": result.final_approval,
        "handoff_allowed": result.handoff_allowed,
        "stopped_at": result.stopped_at,
        "evaluation_order": list(result.evaluation_order),
        "dominant_reason_ids": list(result.dominant_reason_ids),
    }
    return {"final_policy": artifact}


def _reject_branch_invariant_result(result: FinalPolicyEngineResult) -> FinalPolicyEngineResult:
    """Fail closed if a reject branch ever receives an unexpected engine ALLOW.

    Milestone 18 N8 hardening: reject branches must not silently diverge from
    the final policy engine. If future refactors accidentally feed data that
    makes the engine return ALLOW while the branch is already handling a reject,
    the runtime response is coerced to an explicit DENY invariant violation.
    """
    if result.state is not FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION:
        return result
    return FinalPolicyEngineResult(
        state=FinalPolicyEngineState.DENY_GATE_SHAPE_INVALID,
        outcome="DENY",
        reason_id=ReasonId.DENY_POLICY,
        final_approval=False,
        handoff_allowed=False,
        stopped_at="reject_branch_final_policy_invariant",
        evaluation_order=result.evaluation_order,
        dominant_reason_ids=("FINAL_POLICY_UNEXPECTED_ALLOW_ON_REJECT_BRANCH",),
    )


def _final_policy_denied_response_v2(
    *,
    req: Any,
    pol: RiskPolicy,
    final_policy: FinalPolicyEngineResult,
    protected_requested: bool,
    qid_ok: bool,
    oracle_ok: bool,
    shield_ok: bool,
    tva_allowed: bool = False,
    eqc_allowed: bool = False,
    wsqk_allowed: bool = False,
    nonce_consumed: bool = False,
    artifacts: dict[str, Any] | None = None,
    include_final_policy_artifact: bool = True,
) -> dict[str, Any]:
    original_state = final_policy.state
    final_policy = _reject_branch_invariant_result(final_policy)
    final_reason = _runtime_final_policy_reason(final_policy)
    merged_artifacts = _final_policy_artifacts(final_policy) if include_final_policy_artifact else {}
    if original_state is FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION:
        merged_artifacts["final_policy_invariant"] = {
            "status": "fail_closed",
            "reason": "reject_branch_received_unexpected_allow",
            "original_state": original_state.value,
        }
    if artifacts:
        merged_artifacts.update(artifacts)
    return build_execution_response_v2(
        request_id=req.request_id,
        intent=req.intent,
        action=req.context.action,
        context_hash=req.context.context_hash,
        status="deny",
        reason_id=final_reason,
        protection_mode=_compute_protection_mode(
            protected_requested=protected_requested,
            qid_ok=qid_ok,
            oracle_ok=oracle_ok,
            shield_ok=shield_ok,
        ),
        tva_allowed=tva_allowed,
        eqc_allowed=eqc_allowed,
        wsqk_allowed=wsqk_allowed,
        issued_at=req.issued_at,
        expires_at=req.expires_at,
        max_skew_seconds=req.max_skew_seconds,
        timebox_valid=True,
        nonce_store=req.nonce_store,
        nonce_value=req.nonce_value,
        nonce_consumed=nonce_consumed,
        qid_present=True,
        qid_valid=qid_ok,
        shield_present=True,
        shield_valid=shield_ok,
        oracle_present=True,
        oracle_valid=oracle_ok,
        policy_mode=pol.resilience_mode.value,
        override_allowed=False,
        policy_reason_id=final_reason,
        artifacts=merged_artifacts,
    )


REQUIRED_SHIELD_LAYERS_V3: tuple[str, ...] = (
    "sentinel_ai",
    "adn",
    "dqsn",
    "qwg",
    "guardian_wallet",
)

_RECEIPT_COMPONENT_TO_SHIELD_SOURCE: dict[str, ShieldSource] = {
    "sentinel_ai": ShieldSource.SENTINEL,
    "adn": ShieldSource.ADN,
    "dqsn": ShieldSource.DQSN,
    "qwg": ShieldSource.QWG,
    "guardian_wallet": ShieldSource.GUARDIAN,
}


def _shield_bundle_from_verified_receipt(
    *,
    result: ShieldReceiptVerificationResult,
    issued_at: int,
    expires_at: int,
) -> ShieldBundleV3:
    """Internalize a verified Shield Orchestrator receipt for EQC only.

    AOS-M-002B keeps the external production boundary receipt-only. This helper
    does not parse legacy bundle evidence and does not grant final approval; it
    converts the already-verified receipt into AdamantineOS's existing internal
    ShieldBundleV3 evidence model so EQC, TVA, and the final policy engine can
    run the normal continuation route.
    """

    if result.state is not ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS:
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt must be verified ALLOW evidence")
    if not result.verified or not result.accepted_as_evidence or result.final_approval:
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt verification flags are not evidence-only")
    if not result.handoff_allowed:
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt handoff is not allowed")
    if not isinstance(result.receipt, Mapping):
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt body is missing")
    if not isinstance(result.context_hash, str) or not result.context_hash:
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt context hash missing")
    if not isinstance(result.receipt_hash, str) or not result.receipt_hash:
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt hash missing")

    raw_components = result.receipt.get("component_verdicts")
    if not isinstance(raw_components, list):
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt component verdicts missing")

    source_by_layer: dict[str, ShieldSignal] = {}
    for component in raw_components:
        if not isinstance(component, Mapping):
            raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt component verdict invalid")
        component_id = component.get("component_id")
        decision = component.get("decision")
        if not isinstance(component_id, str) or component_id not in _RECEIPT_COMPONENT_TO_SHIELD_SOURCE:
            raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt component_id invalid")
        if decision != "ALLOW":
            raise AdapterError(ReasonId.EQC_CONFLICTING_EVIDENCE, "Shield receipt component decision is not ALLOW")
        source_by_layer[component_id] = ShieldSignal(
            source=_RECEIPT_COMPONENT_TO_SHIELD_SOURCE[component_id],
            severity=0,
            reason_ids=(ReasonId.EVIDENCE_OK.value,),
        )

    if set(source_by_layer) != set(_RECEIPT_COMPONENT_TO_SHIELD_SOURCE):
        raise AdapterError(ReasonId.EQC_INVALID_SHIELD_BUNDLE, "Shield receipt missing required component evidence")

    bundle = ShieldBundleV3(
        bundle_id=f"shield_orchestrator_receipt:{result.receipt_hash}",
        context_hash=result.context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        required_layers=REQUIRED_SHIELD_LAYERS_V3,
        signals=tuple(source_by_layer[layer] for layer in REQUIRED_SHIELD_LAYERS_V3),
    )
    bundle.validate()
    return bundle



_BOUND_HUMAN_CONFIRMATION_FIELD = "ui_confirmed"
_BOUND_HUMAN_CONFIRMATION_TRUE = "true"


def _bound_human_confirmation_gate(
    *,
    payload_body: Mapping[str, Any],
    context_fields: Mapping[str, str] | None,
) -> LocalPolicyGateResult:
    """Require the UI confirmation signal to be bound into context_hash.

    AOS-RT-001: payload.body.ui_confirmed is an untrusted runtime flag on
    its own. It is accepted only when the same confirmation value is present
    in context.fields, which is part of the deterministic context_hash that
    WSQK, Q-ID, Adaptive Core, and Shield evidence are expected to bind to.
    """

    payload_confirmed = payload_body.get(_BOUND_HUMAN_CONFIRMATION_FIELD) is True
    bound_confirmed = (context_fields or {}).get(_BOUND_HUMAN_CONFIRMATION_FIELD) == _BOUND_HUMAN_CONFIRMATION_TRUE
    accepted = payload_confirmed and bound_confirmed
    return LocalPolicyGateResult(
        "human",
        accepted,
        ReasonId.EVIDENCE_OK if accepted else ReasonId.DENY_AUTHORITY_INSUFFICIENT,
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
    if type(ia) is not int or type(ea) is not int:
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


def _is_qid_v2_login_evidence(evidence_qid: Mapping[str, Any]) -> bool:
    return evidence_qid.get("v") == "2" and evidence_qid.get("kind") == "qid_login_v2"


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

        # Q-ID must validate first. If Q-ID rejects, the final policy engine
        # now receives that real rejected source instead of being bypassed.
        # T-1 hardening: Q-ID v2 proof_hash proves integrity only, not issuer
        # authenticity. Any Q-ID v2 login evidence MUST provide an external
        # verifier before Adamantine parses or trusts it. This is independent of
        # WSQK/protected-mode presence; missing verifier is fail-closed.
        try:
            if _is_qid_v2_login_evidence(req.evidence_qid) and qid_verifier is None:
                raise AdapterError(
                    ReasonId.QID_AUTHENTICITY_VERIFIER_MISSING,
                    "qid_verifier is required for Q-ID v2 evidence",
                )
            if qid_verifier is not None:
                try:
                    qid_verifier(req.evidence_qid)
                except AdapterError:
                    raise
                except Exception as ex:
                    raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, f"qid_verifier error: {ex}")

            session = parse_qid_session(payload=req.evidence_qid, now=now)
        except AdapterError as e:
            final_policy = evaluate_final_policy_engine(
                shield=_runtime_evidence_accepted(source="shield:not_reached_before_qid_reject", context_hash=req.context.context_hash),
                wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_qid_reject", context_hash=req.context.context_hash),
                qid=_runtime_evidence_rejected(source="qid:rejected", context_hash=req.context.context_hash, reason_id=e.reason_id),
                adaptive_core=_runtime_evidence_accepted(source="adaptive_core:not_reached_before_qid_reject", context_hash=req.context.context_hash),
                ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                expected_context_hash=req.context.context_hash,
            )
            return _final_policy_denied_response_v2(
                req=req,
                pol=pol,
                final_policy=final_policy,
                protected_requested=protected_requested,
                qid_ok=False,
                oracle_ok=False,
                shield_ok=False,
                artifacts={"error": e.message},
                include_final_policy_artifact=False,
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
                final_policy = evaluate_final_policy_engine(
                    shield=_runtime_evidence_accepted(source="shield:not_reached_before_qid_replay_reject", context_hash=req.context.context_hash),
                    wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_qid_replay_reject", context_hash=req.context.context_hash),
                    qid=_runtime_evidence_rejected(source="qid:replay_rejected", context_hash=req.context.context_hash, reason_id=e.reason_id),
                    adaptive_core=_runtime_evidence_accepted(source="adaptive_core:not_reached_before_qid_replay_reject", context_hash=req.context.context_hash),
                    ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                    replay=LocalPolicyGateResult("replay", False, e.reason_id),
                    wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                    human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                    expected_context_hash=req.context.context_hash,
                )
                return _final_policy_denied_response_v2(
                    req=req,
                    pol=pol,
                    final_policy=final_policy,
                    protected_requested=protected_requested,
                    qid_ok=False,
                    oracle_ok=False,
                    shield_ok=False,
                    artifacts={"error": e.message},
                )

        # Oracle / Adaptive Core evidence. Rejections are now passed through
        # the final policy engine as adaptive_core evidence failures.
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
            final_policy = evaluate_final_policy_engine(
                shield=_runtime_evidence_accepted(source="shield:not_reached_before_oracle_reject", context_hash=req.context.context_hash),
                wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_oracle_reject", context_hash=req.context.context_hash),
                qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                adaptive_core=_runtime_evidence_rejected(source="adaptive_core:oracle_v3_rejected", context_hash=req.context.context_hash, reason_id=e.reason_id),
                ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                expected_context_hash=req.context.context_hash,
            )
            return _final_policy_denied_response_v2(
                req=req,
                pol=pol,
                final_policy=final_policy,
                protected_requested=protected_requested,
                qid_ok=True,
                oracle_ok=False,
                shield_ok=False,
                artifacts={"error": e.message},
                include_final_policy_artifact=False,
            )

        shield_runtime_artifact: dict[str, Any] | None = None
        shield_evidence_for_policy: _RuntimeFinalPolicyEvidence

        if pol.shield_runtime_boundary is ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2:
            receipt_result = verify_shield_orchestrator_receipt(
                req.evidence_shield,
                expected_context_hash=req.context.context_hash,
                expected_request_id=req.request_id,
                rejected_receipt_hashes=pol.rejected_shield_receipt_hashes,
            )
            shield_evidence_for_policy = _runtime_evidence_from_shield_receipt(
                result=receipt_result,
                expected_context_hash=req.context.context_hash,
            )

            if not shield_evidence_for_policy.accepted_as_evidence:
                final_policy = evaluate_final_policy_engine(
                    shield=shield_evidence_for_policy,
                    wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_shield_receipt_reject", context_hash=req.context.context_hash),
                    qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                    adaptive_core=_runtime_evidence_accepted(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
                    ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                    replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                    wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                    human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                    expected_context_hash=req.context.context_hash,
                )
                return _final_policy_denied_response_v2(
                    req=req,
                    pol=pol,
                    final_policy=final_policy,
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=False,
                    artifacts=_shield_runtime_boundary_artifact(
                        policy=pol,
                        receipt_result=receipt_result,
                        route_status="receipt_rejected_at_orchestrator_only_boundary",
                    ),
                    include_final_policy_artifact=False,
                )

            shield = _shield_bundle_from_verified_receipt(
                result=receipt_result,
                issued_at=req.issued_at,
                expires_at=req.expires_at,
            )
            shield_runtime_artifact = _shield_runtime_boundary_artifact(
                policy=pol,
                receipt_result=receipt_result,
                route_status="receipt_verified_runtime_route_wired",
            )

        else:
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
                final_policy = evaluate_final_policy_engine(
                    shield=_runtime_evidence_rejected(source="shield:bundle_rejected", context_hash=req.context.context_hash, reason_id=mapped),
                    wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_shield_reject", context_hash=req.context.context_hash),
                    qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                    adaptive_core=_runtime_evidence_accepted(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
                    ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                    replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                    wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                    human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                    expected_context_hash=req.context.context_hash,
                )
                return _final_policy_denied_response_v2(
                    req=req,
                    pol=pol,
                    final_policy=final_policy,
                    protected_requested=protected_requested,
                    qid_ok=True,
                    oracle_ok=True,
                    shield_ok=False,
                    artifacts={
                        "shield_adapter_reason": e.reason_id.value,
                        "shield_adapter_message": e.message,
                    },
                    include_final_policy_artifact=False,
                )
            shield_evidence_for_policy = _runtime_evidence_accepted(
                source=f"shield:{getattr(shield, 'bundle_id', 'validated_bundle')}",
                context_hash=getattr(shield, "context_hash", req.context.context_hash),
            )
        if tuple(shield.required_layers) != REQUIRED_SHIELD_LAYERS_V3:
            expected = list(REQUIRED_SHIELD_LAYERS_V3)
            got = list(shield.required_layers)
            missing = [x for x in expected if x not in got]
            extra = [x for x in got if x not in expected]
            final_policy = evaluate_final_policy_engine(
                shield=_runtime_evidence_rejected(source=f"shield:{getattr(shield, 'bundle_id', 'validated_bundle')}:required_layers", context_hash=getattr(shield, "context_hash", req.context.context_hash), reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE),
                wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_shield_layer_reject", context_hash=req.context.context_hash),
                qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                adaptive_core=_runtime_evidence_accepted(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
                ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                expected_context_hash=req.context.context_hash,
            )
            return _final_policy_denied_response_v2(
                req=req,
                pol=pol,
                final_policy=final_policy,
                protected_requested=protected_requested,
                qid_ok=True,
                oracle_ok=True,
                shield_ok=False,
                artifacts={
                    "shield_required_layers_expected": expected,
                    "shield_required_layers_got": got,
                    "shield_required_layers_missing": missing,
                    "shield_required_layers_extra": extra,
                },
                include_final_policy_artifact=False,
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
                shield=shield_evidence_for_policy,
                wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:not_reached_before_eqc_deny", context_hash=req.context.context_hash),
                qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                adaptive_core=_runtime_evidence_accepted(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
                ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                wallet_policy=LocalPolicyGateResult("wallet_policy", False, rid),
                human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                expected_context_hash=req.context.context_hash,
            )
            return _final_policy_denied_response_v2(
                req=req,
                pol=pol,
                final_policy=final_policy,
                protected_requested=protected_requested,
                qid_ok=True,
                oracle_ok=True,
                shield_ok=True,
                eqc_allowed=False,
                artifacts={
                    "evidence": {"qid": True, "oracle": True, "shield": True},
                    **(shield_runtime_artifact or {}),
                },
                include_final_policy_artifact=False,
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
            final_policy = evaluate_final_policy_engine(
                shield=shield_evidence_for_policy,
                wsqk_v2=_runtime_evidence_rejected(source="wsqk_v2:authority_proof_rejected", context_hash=req.context.context_hash, reason_id=ReasonId.DENY_AUTHORITY_INVALID),
                qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
                adaptive_core=_runtime_evidence_accepted(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
                ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
                replay=LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
                wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
                human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
                expected_context_hash=req.context.context_hash,
            )
            return _final_policy_denied_response_v2(
                req=req,
                pol=pol,
                final_policy=final_policy,
                protected_requested=protected_requested,
                qid_ok=True,
                oracle_ok=True,
                shield_ok=True,
                eqc_allowed=True,
                artifacts={"error": "wsqk authority rejected", **(shield_runtime_artifact or {})},
                include_final_policy_artifact=True,
            )

        exec_req = ExecutionRequest(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            payload="opaque",
        )

        payload_body = _require_mapping((_require_mapping(p.get("payload")) or {}).get("body")) or {}
        human_gate = _bound_human_confirmation_gate(
            payload_body=payload_body,
            context_fields=fields,
        )

        # Milestone 18 Option 2: TVA/replay is a real local gate into the
        # final policy engine. A replay/TVA failure is represented as replay
        # gate failure and denied by the engine before execution.
        try:
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
            replay_gate = LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK)
            tva_ok = True
            nonce_was_consumed = True
        except TVAError as e:
            replay_reason = _reason_from_message(str(e))
            replay_gate = LocalPolicyGateResult("replay", False, replay_reason)
            tva_ok = False
            nonce_was_consumed = False

        final_policy = evaluate_final_policy_engine(
            shield=shield_evidence_for_policy,
            wsqk_v2=_runtime_evidence_accepted(source="wsqk_v2:authority_proof", context_hash=wsqk.context_hash),
            qid=_runtime_evidence_accepted(source=f"qid:{getattr(session, 'subject', 'validated_session')}", context_hash=req.context.context_hash),
            adaptive_core=_runtime_evidence_accepted(source="adaptive_core:oracle_v3", context_hash=getattr(oracle, "context_hash", req.context.context_hash)),
            ai_gateway=_runtime_evidence_accepted(source=AI_GATEWAY_V2_RUNTIME_ADVISORY_SOURCE, context_hash=req.context.context_hash),
            replay=replay_gate,
            wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
            human=human_gate,
            expected_context_hash=req.context.context_hash,
        )

        if final_policy.state is not FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION:
            return _final_policy_denied_response_v2(
                req=req,
                pol=pol,
                final_policy=final_policy,
                protected_requested=protected_requested,
                qid_ok=tva_ok,
                oracle_ok=tva_ok,
                shield_ok=tva_ok,
                tva_allowed=tva_ok,
                eqc_allowed=True,
                wsqk_allowed=True,
                nonce_consumed=nonce_was_consumed,
                artifacts=shield_runtime_artifact,
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
            artifacts={"executor_result": out, **(shield_runtime_artifact or {})},
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
