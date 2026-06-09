from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from adamantine.v1.contracts.reason_ids import ReasonId


AI_GATEWAY_HANDOFF_V1 = "ai_gateway_handoff_v1"
AI_GATEWAY_RECEIPT_V1 = "ai_gateway_receipt_v1"
AI_GATEWAY_OUTPUT_V1 = "ai_gateway_output_v1"
RECEIPT_DETERMINISM_PROFILE_V1 = "canonical_sha256_no_time_v1"

_HANDOFF_FIELDS = frozenset(
    {
        "handoff_version",
        "adapter",
        "task_type",
        "policy_decision",
        "reason_id",
        "envelope_hash",
        "output_hash",
        "context_hash",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "receipt_version",
        "gateway_version",
        "adapter_id",
        "adapter_version",
        "envelope_hash",
        "output_hash",
        "policy_decision",
        "reason_id",
        "created_from_contract",
        "determinism_profile",
    }
)
_ALLOWED_POLICY_DECISIONS = frozenset({"accepted", "rejected"})
_HEX = frozenset("0123456789abcdef")


class AIGatewayPolicyEvidenceState(str, Enum):
    """Stable AI Gateway policy evidence states.

    AI Gateway is an ingress evidence source only. It can continue checks or
    deny, but it can never grant final AdamantineOS approval by itself.
    """

    ALLOW_EVIDENCE_CONTINUE_CHECKS = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    DENY_AI_GATEWAY_REJECTED = "DENY_AI_GATEWAY_REJECTED"
    DENY_MISSING_HANDOFF = "DENY_MISSING_HANDOFF"
    DENY_MISSING_RECEIPT = "DENY_MISSING_RECEIPT"
    DENY_UNSUPPORTED_INPUT = "DENY_UNSUPPORTED_INPUT"
    DENY_SCHEMA_INVALID = "DENY_SCHEMA_INVALID"
    DENY_UNKNOWN_FIELD = "DENY_UNKNOWN_FIELD"
    DENY_INVALID_HASH = "DENY_INVALID_HASH"
    DENY_CONTEXT_HASH_MISMATCH = "DENY_CONTEXT_HASH_MISMATCH"
    DENY_RECEIPT_MISMATCH = "DENY_RECEIPT_MISMATCH"
    DENY_RAW_AI_OUTPUT = "DENY_RAW_AI_OUTPUT"
    DENY_EARLIER_GATE_DENIED = "DENY_EARLIER_GATE_DENIED"
    DENY_HIDDEN_AUTHORITY_FIELD = "DENY_HIDDEN_AUTHORITY_FIELD"


@dataclass(frozen=True)
class AIGatewayPolicyEvidenceResult:
    """Normalized AI Gateway evidence for the future policy engine."""

    source: str
    state: AIGatewayPolicyEvidenceState
    outcome: str
    reason_id: ReasonId | str
    accepted_as_evidence: bool
    final_approval: bool
    handoff_allowed: bool
    adapter: str | None
    task_type: str | None
    policy_decision: str | None
    context_hash: str | None
    envelope_hash: str | None
    output_hash: str | None
    gateway_version: str | None
    adapter_version: str | None
    dominant_reason_ids: tuple[str, ...]
    handoff: Mapping[str, Any] | None = None
    receipt: Mapping[str, Any] | None = None


def _reason_text(reason_id: ReasonId | str) -> str:
    return reason_id.value if isinstance(reason_id, ReasonId) else str(reason_id)


def _deny(
    *,
    state: AIGatewayPolicyEvidenceState,
    reason_id: ReasonId | str,
    adapter: str | None = None,
    task_type: str | None = None,
    policy_decision: str | None = None,
    context_hash: str | None = None,
    envelope_hash: str | None = None,
    output_hash: str | None = None,
    gateway_version: str | None = None,
    adapter_version: str | None = None,
    dominant_reason_ids: tuple[str, ...] | None = None,
    handoff: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> AIGatewayPolicyEvidenceResult:
    reason = _reason_text(reason_id)
    return AIGatewayPolicyEvidenceResult(
        source="ai_gateway",
        state=state,
        outcome="DENY",
        reason_id=reason_id,
        accepted_as_evidence=False,
        final_approval=False,
        handoff_allowed=False,
        adapter=adapter,
        task_type=task_type,
        policy_decision=policy_decision,
        context_hash=context_hash,
        envelope_hash=envelope_hash,
        output_hash=output_hash,
        gateway_version=gateway_version,
        adapter_version=adapter_version,
        dominant_reason_ids=dominant_reason_ids or (reason,),
        handoff=handoff,
        receipt=receipt,
    )


def _contains_forbidden_authority_field(value: Any) -> bool:
    forbidden = {
        "allow",
        "approve",
        "approved",
        "authority",
        "authorization",
        "bypass",
        "final_approval",
        "grant_execution",
        "handoff_allowed",
        "override",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in forbidden:
                return True
            if _contains_forbidden_authority_field(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_authority_field(item) for item in value)
    return False


def _extract_earlier_denies(prior_gate_results: Sequence[Any] | None) -> tuple[str, ...]:
    if prior_gate_results is None:
        return ()
    denies: list[str] = []
    for result in prior_gate_results:
        outcome = getattr(result, "outcome", None)
        reason_id = getattr(result, "reason_id", None)
        if isinstance(result, Mapping):
            outcome = result.get("outcome", outcome)
            reason_id = result.get("reason_id", reason_id)
        if outcome == "DENY":
            denies.append(_reason_text(reason_id or ReasonId.DENY_POLICY))
    return tuple(denies)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in _HEX for ch in value)


def _unknown_fields(data: Mapping[str, Any], allowed: frozenset[str]) -> tuple[str, ...]:
    return tuple(key for key in data if key not in allowed)


def _missing_fields(data: Mapping[str, Any], required: frozenset[str]) -> tuple[str, ...]:
    return tuple(key for key in required if key not in data or data[key] is None)


def _looks_like_raw_ai_output(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return (
        value.get("contract_version") == AI_GATEWAY_OUTPUT_V1
        or "output_payload" in value
        or "model_output" in value
        or "raw_model_output" in value
    )


def _validate_handoff_shape(
    handoff: Any,
    *,
    expected_context_hash: str,
) -> AIGatewayPolicyEvidenceResult | None:
    if handoff is None:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_MISSING_HANDOFF,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )
    if _looks_like_raw_ai_output(handoff):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_RAW_AI_OUTPUT,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )
    if not isinstance(handoff, Mapping):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_UNSUPPORTED_INPUT,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )
    if _contains_forbidden_authority_field(handoff):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            handoff=handoff,
        )
    if _unknown_fields(handoff, _HANDOFF_FIELDS):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_UNKNOWN_FIELD,
            reason_id=ReasonId.DENY_UNKNOWN_FIELD,
            handoff=handoff,
        )
    if _missing_fields(handoff, _HANDOFF_FIELDS):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            handoff=handoff,
        )
    if handoff.get("handoff_version") != AI_GATEWAY_HANDOFF_V1:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_VERSION_MISMATCH,
            handoff=handoff,
        )
    if handoff.get("policy_decision") not in _ALLOWED_POLICY_DECISIONS:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_POLICY,
            handoff=handoff,
        )
    for field in ("adapter", "task_type", "reason_id"):
        if not _is_non_empty_string(handoff.get(field)):
            return _deny(
                state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
                reason_id=ReasonId.DENY_SCHEMA_INVALID,
                handoff=handoff,
            )
    if not _is_sha256_hex(handoff.get("envelope_hash")):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_INVALID_HASH,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            handoff=handoff,
        )
    if not _is_sha256_hex(handoff.get("output_hash")):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_INVALID_HASH,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            handoff=handoff,
        )
    context_hash = handoff.get("context_hash")
    if not _is_sha256_hex(context_hash):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_INVALID_HASH,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            context_hash=context_hash if isinstance(context_hash, str) else None,
            handoff=handoff,
        )
    if context_hash != expected_context_hash:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
            reason_id=ReasonId.DENY_POLICY,
            adapter=str(handoff.get("adapter")),
            task_type=str(handoff.get("task_type")),
            policy_decision=str(handoff.get("policy_decision")),
            context_hash=context_hash,
            envelope_hash=str(handoff.get("envelope_hash")),
            output_hash=str(handoff.get("output_hash")),
            handoff=handoff,
        )
    return None


def _validate_receipt_shape(receipt: Any) -> AIGatewayPolicyEvidenceResult | None:
    if receipt is None:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_MISSING_RECEIPT,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )
    if not isinstance(receipt, Mapping):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_UNSUPPORTED_INPUT,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )
    if _contains_forbidden_authority_field(receipt):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            receipt=receipt,
        )
    if _unknown_fields(receipt, _RECEIPT_FIELDS):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_UNKNOWN_FIELD,
            reason_id=ReasonId.DENY_UNKNOWN_FIELD,
            receipt=receipt,
        )
    if _missing_fields(receipt, _RECEIPT_FIELDS):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            receipt=receipt,
        )
    if receipt.get("receipt_version") != AI_GATEWAY_RECEIPT_V1:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_VERSION_MISMATCH,
            receipt=receipt,
        )
    if receipt.get("created_from_contract") != AI_GATEWAY_OUTPUT_V1:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_VERSION_MISMATCH,
            receipt=receipt,
        )
    if receipt.get("determinism_profile") != RECEIPT_DETERMINISM_PROFILE_V1:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            receipt=receipt,
        )
    if receipt.get("policy_decision") not in _ALLOWED_POLICY_DECISIONS:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
            reason_id=ReasonId.DENY_POLICY,
            receipt=receipt,
        )
    for field in ("gateway_version", "adapter_id", "adapter_version", "reason_id"):
        if not _is_non_empty_string(receipt.get(field)):
            return _deny(
                state=AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID,
                reason_id=ReasonId.DENY_SCHEMA_INVALID,
                receipt=receipt,
            )
    if not _is_sha256_hex(receipt.get("envelope_hash")):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_INVALID_HASH,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            receipt=receipt,
        )
    if not _is_sha256_hex(receipt.get("output_hash")):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_INVALID_HASH,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            receipt=receipt,
        )
    return None


def _receipt_matches_handoff(
    handoff: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> bool:
    return (
        receipt.get("adapter_id") == handoff.get("adapter")
        and receipt.get("envelope_hash") == handoff.get("envelope_hash")
        and receipt.get("output_hash") == handoff.get("output_hash")
        and receipt.get("policy_decision") == handoff.get("policy_decision")
        and receipt.get("reason_id") == handoff.get("reason_id")
    )


def normalize_ai_gateway_policy_evidence(
    *,
    handoff: Any,
    receipt: Any,
    expected_context_hash: str,
    prior_gate_results: Sequence[Any] | None = None,
) -> AIGatewayPolicyEvidenceResult:
    """Normalize AI Gateway handoff/receipt evidence for policy use.

    This boundary intentionally does not import or trust the external AI Gateway
    package. It validates the stable handoff/receipt shape observed in the
    external contracts, rejects raw AI output, and returns evidence-only policy
    results for the future AdamantineOS policy engine.
    """

    earlier_denies = _extract_earlier_denies(prior_gate_results)
    if earlier_denies:
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_EARLIER_GATE_DENIED,
            reason_id=earlier_denies[0],
            dominant_reason_ids=earlier_denies,
        )

    if not _is_sha256_hex(expected_context_hash):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_INVALID_HASH,
            reason_id=ReasonId.DENY_POLICY,
        )

    handoff_error = _validate_handoff_shape(
        handoff,
        expected_context_hash=expected_context_hash,
    )
    if handoff_error is not None:
        return handoff_error

    receipt_error = _validate_receipt_shape(receipt)
    if receipt_error is not None:
        return receipt_error

    assert isinstance(handoff, Mapping)
    assert isinstance(receipt, Mapping)

    if not _receipt_matches_handoff(handoff, receipt):
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            adapter=str(handoff.get("adapter")),
            task_type=str(handoff.get("task_type")),
            policy_decision=str(handoff.get("policy_decision")),
            context_hash=str(handoff.get("context_hash")),
            envelope_hash=str(handoff.get("envelope_hash")),
            output_hash=str(handoff.get("output_hash")),
            gateway_version=str(receipt.get("gateway_version")),
            adapter_version=str(receipt.get("adapter_version")),
            handoff=handoff,
            receipt=receipt,
        )

    if handoff["policy_decision"] == "rejected":
        reason_id = str(handoff["reason_id"])
        return _deny(
            state=AIGatewayPolicyEvidenceState.DENY_AI_GATEWAY_REJECTED,
            reason_id=reason_id,
            adapter=str(handoff["adapter"]),
            task_type=str(handoff["task_type"]),
            policy_decision="rejected",
            context_hash=str(handoff["context_hash"]),
            envelope_hash=str(handoff["envelope_hash"]),
            output_hash=str(handoff["output_hash"]),
            gateway_version=str(receipt["gateway_version"]),
            adapter_version=str(receipt["adapter_version"]),
            handoff=handoff,
            receipt=receipt,
        )

    return AIGatewayPolicyEvidenceResult(
        source="ai_gateway",
        state=AIGatewayPolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS,
        outcome="ALLOW_EVIDENCE",
        reason_id=ReasonId.EVIDENCE_OK,
        accepted_as_evidence=True,
        final_approval=False,
        handoff_allowed=True,
        adapter=str(handoff["adapter"]),
        task_type=str(handoff["task_type"]),
        policy_decision="accepted",
        context_hash=str(handoff["context_hash"]),
        envelope_hash=str(handoff["envelope_hash"]),
        output_hash=str(handoff["output_hash"]),
        gateway_version=str(receipt["gateway_version"]),
        adapter_version=str(receipt["adapter_version"]),
        dominant_reason_ids=(ReasonId.EVIDENCE_OK.value,),
        handoff=handoff,
        receipt=receipt,
    )
