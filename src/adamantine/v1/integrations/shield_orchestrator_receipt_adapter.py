from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import (
    DirectComponentVerdictError,
    ShieldReceiptContextMismatchError,
    ShieldReceiptHashMismatchError,
    reject_direct_component_verdict,
    validate_shield_orchestrator_receipt,
)


class ShieldReceiptAdapterState(str, Enum):
    """Stable AdamantineOS Level 2 Shield receipt adapter states."""

    SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS = "SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS"
    SHIELD_BLOCK_DENY_DOMINATES = "SHIELD_BLOCK_DENY_DOMINATES"
    SHIELD_REVIEW_REQUIRED = "SHIELD_REVIEW_REQUIRED"
    SHIELD_REJECTED_INVALID_RECEIPT = "SHIELD_REJECTED_INVALID_RECEIPT"
    SHIELD_REJECTED_CONTEXT_MISMATCH = "SHIELD_REJECTED_CONTEXT_MISMATCH"
    SHIELD_REJECTED_RAW_COMPONENT_BYPASS = "SHIELD_REJECTED_RAW_COMPONENT_BYPASS"
    SHIELD_REJECTED_TAMPERED_RECEIPT = "SHIELD_REJECTED_TAMPERED_RECEIPT"


@dataclass(frozen=True)
class ShieldReceiptAdapterResult:
    """Fail-closed AdamantineOS handoff result for a Shield Orchestrator receipt."""

    state: ShieldReceiptAdapterState
    adapter_reason_id: ReasonId
    accepted_as_evidence: bool
    final_approval: bool
    final_outcome: str | None
    dominant_reason_ids: tuple[str, ...]
    context_hash: str | None
    handoff_allowed: bool
    receipt: Mapping[str, Any] | None = None


def _rejected(
    *,
    state: ShieldReceiptAdapterState,
    adapter_reason_id: ReasonId,
    message_reason: str,
    context_hash: str | None = None,
) -> ShieldReceiptAdapterResult:
    return ShieldReceiptAdapterResult(
        state=state,
        adapter_reason_id=adapter_reason_id,
        accepted_as_evidence=False,
        final_approval=False,
        final_outcome=None,
        dominant_reason_ids=(message_reason,),
        context_hash=context_hash,
        handoff_allowed=False,
        receipt=None,
    )


def _classify_validation_error(exc: ValueError) -> ShieldReceiptAdapterState:
    if isinstance(exc, DirectComponentVerdictError):
        return ShieldReceiptAdapterState.SHIELD_REJECTED_RAW_COMPONENT_BYPASS
    if isinstance(exc, ShieldReceiptContextMismatchError):
        return ShieldReceiptAdapterState.SHIELD_REJECTED_CONTEXT_MISMATCH
    if isinstance(exc, ShieldReceiptHashMismatchError):
        return ShieldReceiptAdapterState.SHIELD_REJECTED_TAMPERED_RECEIPT

    # Legacy fallback for older callers that may still raise plain ValueError.
    message = str(exc).lower()
    if "direct shield component" in message or "component verdict" in message:
        return ShieldReceiptAdapterState.SHIELD_REJECTED_RAW_COMPONENT_BYPASS
    if "context mismatch" in message:
        return ShieldReceiptAdapterState.SHIELD_REJECTED_CONTEXT_MISMATCH
    if "hash mismatch" in message:
        return ShieldReceiptAdapterState.SHIELD_REJECTED_TAMPERED_RECEIPT
    return ShieldReceiptAdapterState.SHIELD_REJECTED_INVALID_RECEIPT


def _reason_for_rejected_state(state: ShieldReceiptAdapterState) -> ReasonId:
    if state == ShieldReceiptAdapterState.SHIELD_REJECTED_CONTEXT_MISMATCH:
        return ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    return ReasonId.EQC_INVALID_SHIELD_BUNDLE


def adapt_shield_orchestrator_receipt(
    receipt: Any,
    *,
    expected_context_hash: str,
) -> ShieldReceiptAdapterResult:
    """Map a Shield Orchestrator receipt into a fail-closed AdamantineOS adapter state.

    This Level 2 boundary intentionally does not import live Shield packages and never
    produces final approval. A valid Shield ALLOW can only become
    SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS.
    """

    try:
        reject_direct_component_verdict(receipt)
    except ValueError as exc:
        state = _classify_validation_error(exc)
        return _rejected(
            state=state,
            adapter_reason_id=_reason_for_rejected_state(state),
            message_reason=state.value,
        )

    try:
        valid = validate_shield_orchestrator_receipt(receipt, expected_context_hash=expected_context_hash)
    except ValueError as exc:
        state = _classify_validation_error(exc)
        context_hash = receipt.get("context_hash") if isinstance(receipt, Mapping) and isinstance(receipt.get("context_hash"), str) else None
        return _rejected(
            state=state,
            adapter_reason_id=_reason_for_rejected_state(state),
            message_reason=state.value,
            context_hash=context_hash,
        )

    outcome = valid["final_outcome"]
    dominant_reason_ids = tuple(str(reason_id) for reason_id in valid["dominant_reason_ids"])
    handoff = valid["adamantineos_handoff"]
    handoff_allowed = bool(handoff["handoff_allowed"])

    if outcome == "DENY":
        state = ShieldReceiptAdapterState.SHIELD_BLOCK_DENY_DOMINATES
        adapter_reason_id = ReasonId.DENY_POLICY
    elif outcome == "HUMAN_REVIEW_REQUIRED":
        state = ShieldReceiptAdapterState.SHIELD_REVIEW_REQUIRED
        adapter_reason_id = ReasonId.DENY_AUTHORITY_INSUFFICIENT
    else:
        state = ShieldReceiptAdapterState.SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS
        adapter_reason_id = ReasonId.EVIDENCE_OK

    return ShieldReceiptAdapterResult(
        state=state,
        adapter_reason_id=adapter_reason_id,
        accepted_as_evidence=True,
        final_approval=False,
        final_outcome=str(outcome),
        dominant_reason_ids=dominant_reason_ids,
        context_hash=str(valid["context_hash"]),
        handoff_allowed=handoff_allowed,
        receipt=valid,
    )
