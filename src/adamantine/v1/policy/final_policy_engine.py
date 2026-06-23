from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Iterable, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId


class FinalPolicyEngineState(str, Enum):
    """Stable AdamantineOS final policy engine states.

    This local engine merges already-locked evidence boundaries. It does not
    call external repositories and it never allows upstream evidence to become
    final approval by itself.
    """

    ALLOW_FINAL_ADAMANTINEOS_DECISION = "ALLOW_FINAL_ADAMANTINEOS_DECISION"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    DENY_MISSING_EVIDENCE = "DENY_MISSING_EVIDENCE"
    DENY_EVIDENCE_REJECTED = "DENY_EVIDENCE_REJECTED"
    DENY_AUTHORITY_BYPASS = "DENY_AUTHORITY_BYPASS"
    DENY_HANDOFF_BLOCKED = "DENY_HANDOFF_BLOCKED"
    DENY_REPLAY_GATE = "DENY_REPLAY_GATE"
    DENY_WALLET_POLICY_GATE = "DENY_WALLET_POLICY_GATE"
    DENY_HUMAN_GATE = "DENY_HUMAN_GATE"
    DENY_GATE_SHAPE_INVALID = "DENY_GATE_SHAPE_INVALID"
    DENY_CONTEXT_MISMATCH = "DENY_CONTEXT_MISMATCH"
    DENY_REASON_ID_INVALID = "DENY_REASON_ID_INVALID"
    DENY_SHIELD_V4_REQUIRED = "DENY_SHIELD_V4_REQUIRED"


@dataclass(frozen=True)
class LocalPolicyGateResult:
    """Deterministic local policy gate result for replay, wallet, and human gates."""

    gate: str
    passed: bool
    reason_id: ReasonId | str
    requires_human_review: bool = False


@dataclass(frozen=True)
class FinalPolicyEngineResult:
    """Final local AdamantineOS policy-engine result.

    `final_approval` can be true only after every evidence gate passes and every
    local gate passes in the locked order. Evidence gate ALLOW states are never
    final approval on their own.
    """

    state: FinalPolicyEngineState
    outcome: str
    reason_id: ReasonId | str
    final_approval: bool
    handoff_allowed: bool
    stopped_at: str
    evaluation_order: tuple[str, ...]
    dominant_reason_ids: tuple[str, ...]


_EVIDENCE_GATE_ORDER = (
    "shield",
    "wsqk_v2",
    "qid",
    "adaptive_core",
    "ai_gateway",
)
_LOCAL_GATE_ORDER = (
    "replay",
    "wallet_policy",
    "human",
)
_GATE_DENY_STATES = {
    "replay": FinalPolicyEngineState.DENY_REPLAY_GATE,
    "wallet_policy": FinalPolicyEngineState.DENY_WALLET_POLICY_GATE,
    "human": FinalPolicyEngineState.DENY_HUMAN_GATE,
}

_FORBIDDEN_AUTHORITY_KEYS = frozenset({
    "approved",
    "authority",
    "auto_approve",
    "broadcast",
    "bypass",
    "can_sign",
    "execute",
    "force_allow",
    "grant_execution",
    "human_approved",
    "override",
    "sign",
    "trusted",
    "wallet_signing_approval",
})
_NESTED_AUTHORITY_CONTAINERS = frozenset({
    "authority",
    "extra",
    "metadata",
    "override",
    "policy_override",
    "raw",
})
_ALLOWED_NORMALIZED_AUTHORITY_FIELDS = frozenset({"final_approval", "handoff_allowed"})
_CONTEXT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SHIELD_V4_REQUIRED_SCHEMA_VERSION = "shield.receipt.v2"
_SHIELD_V4_REQUIRED_CONTRACT_VERSION = 4
_SHIELD_V4_REQUIRED_POLICY_VERSION = "policy.v1"
_SHIELD_V4_REQUIRED_ALGORITHMS = frozenset({"classical-ed25519", "ml-dsa"})
_SHIELD_V4_REQUIRED_COMPONENT_IDS = frozenset({"adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai"})


def _is_context_hash(value: Any) -> bool:
    return isinstance(value, str) and _CONTEXT_HASH_RE.fullmatch(value) is not None


def _truthy_authority_value(value: Any) -> bool:
    return value not in (False, None, "", (), [], {})


def _contains_forbidden_authority_mapping(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in _FORBIDDEN_AUTHORITY_KEYS and _truthy_authority_value(child):
                return True
            if _contains_forbidden_authority_mapping(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_authority_mapping(item) for item in value)
    elif isinstance(value, set):
        return any(_contains_forbidden_authority_mapping(item) for item in value)
    return False


def _object_authority_items(evidence: Any) -> Mapping[str, Any]:
    data: dict[str, Any] = {}
    dict_data = getattr(evidence, "__dict__", None)
    if isinstance(dict_data, Mapping):
        for key, value in dict_data.items():
            if isinstance(key, str):
                data[key] = value

    slots = getattr(type(evidence), "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)
    for key in slots:
        if isinstance(key, str) and hasattr(evidence, key):
            data[key] = getattr(evidence, key)
    return data


def _contains_forbidden_authority_signal(evidence: Any) -> bool:
    """Detect authority-shaped data that should never reach final policy.

    Adapter boundaries should reject hidden authority fields first. 16G adds this
    final fail-closed guard so a normalized-looking evidence object cannot smuggle
    signing, execution, override, or trust authority into the final policy engine.
    Standard normalized fields such as ``final_approval`` and ``handoff_allowed``
    are handled by explicit engine checks and are not treated as hidden fields.
    """

    if isinstance(evidence, Mapping):
        return _contains_forbidden_authority_mapping(evidence)

    data = _object_authority_items(evidence)
    if not data:
        return False

    for key, value in data.items():
        if key in _ALLOWED_NORMALIZED_AUTHORITY_FIELDS:
            continue
        if key in _FORBIDDEN_AUTHORITY_KEYS and _truthy_authority_value(value):
            return True
        if isinstance(value, (Mapping, list, tuple, set)) and _contains_forbidden_authority_mapping(value):
            return True
    return False


def _reason_text(reason_id: ReasonId | str) -> str:
    return reason_id.value if isinstance(reason_id, ReasonId) else str(reason_id)


def _valid_reason(reason_id: Any) -> ReasonId | None:
    if isinstance(reason_id, ReasonId):
        return reason_id
    if isinstance(reason_id, str) and reason_id.strip():
        try:
            return ReasonId(reason_id)
        except ValueError:
            return None
    return None


def _safe_reason(reason_id: ReasonId | str, fallback: ReasonId = ReasonId.UNKNOWN_EXTERNAL_REASON) -> ReasonId:
    return _valid_reason(reason_id) or fallback


def _first_reason(value: Any, fallback: ReasonId | str) -> ReasonId | str:
    reasons = getattr(value, "dominant_reason_ids", None)
    if isinstance(reasons, Iterable) and not isinstance(reasons, (str, bytes)):
        for reason in reasons:
            if isinstance(reason, str) and reason.strip():
                return _safe_reason(reason)
    reason_id = getattr(value, "reason_id", None)
    if isinstance(reason_id, (ReasonId, str)):
        return _safe_reason(reason_id)
    return fallback


def _dominant_reasons(value: Any, fallback: ReasonId | str) -> tuple[str, ...]:
    reasons = getattr(value, "dominant_reason_ids", None)
    if isinstance(reasons, Iterable) and not isinstance(reasons, (str, bytes)):
        collected = tuple(_safe_reason(reason).value for reason in reasons if isinstance(reason, str) and reason.strip())
        if collected:
            return collected
    return (_reason_text(_first_reason(value, fallback)),)


def _result(
    *,
    state: FinalPolicyEngineState,
    outcome: str,
    reason_id: ReasonId | str,
    stopped_at: str,
    evaluation_order: tuple[str, ...],
    dominant_reason_ids: tuple[str, ...] | None = None,
    final_approval: bool = False,
    handoff_allowed: bool = False,
) -> FinalPolicyEngineResult:
    return FinalPolicyEngineResult(
        state=state,
        outcome=outcome,
        reason_id=reason_id,
        final_approval=final_approval,
        handoff_allowed=handoff_allowed,
        stopped_at=stopped_at,
        evaluation_order=evaluation_order,
        dominant_reason_ids=dominant_reason_ids or (_reason_text(reason_id),),
    )


def _field_equals_human_review(value: Any) -> bool:
    raw = value.value if isinstance(value, Enum) else value
    return raw == FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED.value


def _evidence_indicates_human_review(evidence: Any) -> bool:
    return any(
        _field_equals_human_review(getattr(evidence, field, None))
        for field in ("state", "outcome", "final_outcome")
    )


def _verified_algorithms(summary: Any) -> frozenset[str]:
    algorithms = frozenset(
        str(algorithm)
        for algorithm in getattr(summary, "get", lambda _key, _default=None: _default)("verified_algorithms", ())
        if isinstance(algorithm, str) and algorithm.strip()
    )
    return algorithms


def _summary_satisfies_required_algorithms(summary: Any) -> bool:
    satisfied = isinstance(summary, Mapping) and _SHIELD_V4_REQUIRED_ALGORITHMS.issubset(_verified_algorithms(summary))
    return satisfied


def _component_summaries_satisfy_v4(components: Any) -> bool:
    component_ids: set[str] = set()
    summaries_ok = isinstance(components, Iterable) and not isinstance(components, (str, bytes, Mapping))
    if summaries_ok:
        for component in components:
            if not isinstance(component, Mapping) or not _summary_satisfies_required_algorithms(component):
                summaries_ok = False
                break
            component_id = component.get("component_id")
            if not isinstance(component_id, str):
                summaries_ok = False
                break
            component_ids.add(component_id)
    return summaries_ok and frozenset(component_ids) == _SHIELD_V4_REQUIRED_COMPONENT_IDS


def _shield_v4_requirement_failure(evidence: Any) -> str | None:
    receipt = getattr(evidence, "receipt", None)
    summary = getattr(evidence, "verification_summary", None)
    failure: str | None = None
    if getattr(evidence, "verified", False) is not True:
        failure = "SHIELD_V4_VERIFIED_RESULT_REQUIRED"
    elif not isinstance(receipt, Mapping):
        failure = "SHIELD_V4_RECEIPT_REQUIRED"
    elif (
        receipt.get("schema_version") != _SHIELD_V4_REQUIRED_SCHEMA_VERSION
        or receipt.get("contract_version") != _SHIELD_V4_REQUIRED_CONTRACT_VERSION
    ):
        failure = "SHIELD_V4_DOWNGRADE_REJECTED"
    elif not isinstance(summary, Mapping):
        failure = "SHIELD_V4_VERIFICATION_SUMMARY_REQUIRED"
    elif summary.get("policy_version") != _SHIELD_V4_REQUIRED_POLICY_VERSION:
        failure = "SHIELD_V4_POLICY_REQUIRED"
    elif not _summary_satisfies_required_algorithms(summary.get("orchestrator")):
        failure = "SHIELD_V4_ORCHESTRATOR_SIGNATURE_SUMMARY_REQUIRED"
    elif not _component_summaries_satisfy_v4(summary.get("components")):
        failure = "SHIELD_V4_COMPONENT_SIGNATURE_SUMMARY_REQUIRED"
    return failure


def _evaluate_evidence_gate(
    *,
    gate: str,
    evidence: Any,
    evaluation_order: tuple[str, ...],
    expected_context_hash: str,
    shield_v4_required: bool = False,
) -> FinalPolicyEngineResult | None:
    if evidence is None:
        return _result(
            state=FinalPolicyEngineState.DENY_MISSING_EVIDENCE,
            outcome="DENY",
            reason_id=ReasonId.DENY_POLICY,
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(f"MISSING_EVIDENCE:{gate}",),
        )

    if _truthy_authority_value(getattr(evidence, "final_approval", False)):
        return _result(
            state=FinalPolicyEngineState.DENY_AUTHORITY_BYPASS,
            outcome="DENY",
            reason_id=ReasonId.DENY_AUTHORITY_INVALID,
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(f"UPSTREAM_FINAL_APPROVAL_BYPASS:{gate}",),
        )

    if _contains_forbidden_authority_signal(evidence):
        return _result(
            state=FinalPolicyEngineState.DENY_AUTHORITY_BYPASS,
            outcome="DENY",
            reason_id=ReasonId.DENY_AUTHORITY_INVALID,
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(f"HIDDEN_AUTHORITY_BYPASS:{gate}",),
        )

    if getattr(evidence, "accepted_as_evidence", False) is not True:
        return _result(
            state=FinalPolicyEngineState.DENY_EVIDENCE_REJECTED,
            outcome="DENY",
            reason_id=_first_reason(evidence, ReasonId.DENY_POLICY),
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=_dominant_reasons(evidence, ReasonId.DENY_POLICY),
        )

    if gate == "shield" and shield_v4_required:
        shield_v4_failure = _shield_v4_requirement_failure(evidence)
        if shield_v4_failure is not None:
            return _result(
                state=FinalPolicyEngineState.DENY_SHIELD_V4_REQUIRED,
                outcome="DENY",
                reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
                stopped_at="shield",
                evaluation_order=evaluation_order,
                dominant_reason_ids=(shield_v4_failure,),
            )

    if getattr(evidence, "handoff_allowed", False) is not True:
        return _result(
            state=FinalPolicyEngineState.DENY_HANDOFF_BLOCKED,
            outcome="DENY",
            reason_id=_first_reason(evidence, ReasonId.DENY_POLICY),
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=_dominant_reasons(evidence, ReasonId.DENY_POLICY),
        )

    evidence_context_hash = getattr(evidence, "context_hash", None)
    if evidence_context_hash != expected_context_hash:
        return _result(
            state=FinalPolicyEngineState.DENY_CONTEXT_MISMATCH,
            outcome="DENY",
            reason_id=ReasonId.EQC_CONFLICTING_EVIDENCE,
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(f"CONTEXT_MISMATCH:{gate}",),
        )

    if _evidence_indicates_human_review(evidence):
        return _result(
            state=FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED,
            outcome="HUMAN_REVIEW_REQUIRED",
            reason_id=_first_reason(evidence, ReasonId.DENY_AUTHORITY_INSUFFICIENT),
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=_dominant_reasons(evidence, ReasonId.DENY_AUTHORITY_INSUFFICIENT),
            final_approval=False,
            handoff_allowed=False,
        )


    return None


def _evaluate_local_gate(
    *,
    gate: str,
    gate_result: LocalPolicyGateResult | None,
    evaluation_order: tuple[str, ...],
) -> FinalPolicyEngineResult | None:
    if not isinstance(gate_result, LocalPolicyGateResult) or gate_result.gate != gate:
        return _result(
            state=FinalPolicyEngineState.DENY_GATE_SHAPE_INVALID,
            outcome="DENY",
            reason_id=ReasonId.DENY_POLICY,
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(f"INVALID_LOCAL_GATE:{gate}",),
        )

    if not gate_result.passed:
        return _result(
            state=_GATE_DENY_STATES[gate],
            outcome="DENY",
            reason_id=gate_result.reason_id,
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(_reason_text(_safe_reason(gate_result.reason_id)),),
        )

    if gate_result.requires_human_review:
        return _result(
            state=FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED,
            outcome="HUMAN_REVIEW_REQUIRED",
            reason_id=_safe_reason(gate_result.reason_id),
            stopped_at=gate,
            evaluation_order=evaluation_order,
            dominant_reason_ids=(_reason_text(_safe_reason(gate_result.reason_id)),),
        )

    return None


def evaluate_final_policy_engine(
    *,
    shield: Any,
    wsqk_v2: Any,
    qid: Any,
    adaptive_core: Any,
    ai_gateway: Any,
    replay: LocalPolicyGateResult,
    wallet_policy: LocalPolicyGateResult,
    human: LocalPolicyGateResult,
    expected_context_hash: str,
    shield_v4_required: bool = False,
) -> FinalPolicyEngineResult:
    """Evaluate the locked local AdamantineOS final policy order.

    Order is fixed:
    Shield -> WSQK v2 -> Q-ID -> Adaptive Core -> AI Gateway -> replay ->
    wallet policy -> human gate -> final AdamantineOS decision.

    This function consumes normalized evidence boundary results. It does not
    import external repositories, call live multi-repo code, or promote any
    evidence-only ALLOW into final approval before local gates pass.

    ``expected_context_hash`` is required. Omitting it is impossible at the
    signature level, and passing a malformed value fails closed before any
    evidence gate can become trusted.

    When ``shield_v4_required`` is true, the Shield gate must be a verified
    Shield v4 receipt-verifier result with v4 receipt schema, policy,
    Orchestrator signature summary, and all five component signature summaries.
    A normalized v3 Shield result cannot satisfy this mode.
    """

    if not _is_context_hash(expected_context_hash):
        return _result(
            state=FinalPolicyEngineState.DENY_CONTEXT_MISMATCH,
            outcome="DENY",
            reason_id=ReasonId.EQC_CONFLICTING_EVIDENCE,
            stopped_at="expected_context_hash",
            evaluation_order=("expected_context_hash",),
            dominant_reason_ids=("EXPECTED_CONTEXT_HASH_REQUIRED",),
        )

    if type(shield_v4_required) is not bool:
        return _result(
            state=FinalPolicyEngineState.DENY_SHIELD_V4_REQUIRED,
            outcome="DENY",
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            stopped_at="shield_v4_required",
            evaluation_order=("shield_v4_required",),
            dominant_reason_ids=("SHIELD_V4_REQUIRED_MODE_INVALID",),
        )

    evidence_by_gate = {
        "shield": shield,
        "wsqk_v2": wsqk_v2,
        "qid": qid,
        "adaptive_core": adaptive_core,
        "ai_gateway": ai_gateway,
    }
    visited: tuple[str, ...] = ()
    for gate in _EVIDENCE_GATE_ORDER:
        visited = (*visited, gate)
        failure = _evaluate_evidence_gate(
            gate=gate,
            evidence=evidence_by_gate[gate],
            evaluation_order=visited,
            expected_context_hash=expected_context_hash,
            shield_v4_required=shield_v4_required,
        )
        if failure is not None:
            return failure

    local_by_gate = {
        "replay": replay,
        "wallet_policy": wallet_policy,
        "human": human,
    }
    for gate in _LOCAL_GATE_ORDER:
        visited = (*visited, gate)
        failure = _evaluate_local_gate(
            gate=gate,
            gate_result=local_by_gate[gate],
            evaluation_order=visited,
        )
        if failure is not None:
            return failure

    return _result(
        state=FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION,
        outcome="ALLOW",
        reason_id=ReasonId.OK_ALLOW,
        stopped_at="final_adamantineos_decision",
        evaluation_order=(*visited, "final_adamantineos_decision"),
        dominant_reason_ids=(ReasonId.OK_ALLOW.value,),
        final_approval=True,
        handoff_allowed=True,
    )
