from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import (
    ShieldReceiptAuthorityBypassError,
    ShieldReceiptComponentVerdictError,
    DirectComponentVerdictError,
    ShieldReceiptContextMismatchError,
    ShieldReceiptHashMismatchError,
    ShieldReceiptOutcomeMismatchError,
    reject_direct_component_verdict,
    validate_shield_orchestrator_receipt,
)


class ShieldReceiptVerificationState(str, Enum):
    """Stable AdamantineOS Shield Orchestrator receipt verification states."""

    VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS = "VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS"
    VERIFIED_DENY_DOMINATES = "VERIFIED_DENY_DOMINATES"
    VERIFIED_HUMAN_REVIEW_REQUIRED = "VERIFIED_HUMAN_REVIEW_REQUIRED"
    REJECTED_INVALID_RECEIPT = "REJECTED_INVALID_RECEIPT"
    REJECTED_CONTEXT_MISMATCH = "REJECTED_CONTEXT_MISMATCH"
    REJECTED_REQUEST_MISMATCH = "REJECTED_REQUEST_MISMATCH"
    REJECTED_TAMPERED_RECEIPT = "REJECTED_TAMPERED_RECEIPT"
    REJECTED_RAW_COMPONENT_BYPASS = "REJECTED_RAW_COMPONENT_BYPASS"
    REJECTED_AUTHORITY_BYPASS = "REJECTED_AUTHORITY_BYPASS"
    REJECTED_REPLAY_RISK = "REJECTED_REPLAY_RISK"


@dataclass(frozen=True)
class ShieldReceiptVerificationResult:
    """Fail-closed verification result for external Shield Orchestrator evidence."""

    state: ShieldReceiptVerificationState
    reason_id: ReasonId
    verified: bool
    accepted_as_evidence: bool
    final_approval: bool
    final_outcome: str | None
    context_hash: str | None
    request_id: str | None
    receipt_hash: str | None
    handoff_allowed: bool
    dominant_reason_ids: tuple[str, ...]
    receipt: Mapping[str, Any] | None = None




def _string_or_none(payload: Any, key: str) -> str | None:
    if isinstance(payload, Mapping) and isinstance(payload.get(key), str):
        return str(payload[key])
    return None


def _rejected(
    *,
    state: ShieldReceiptVerificationState,
    reason_id: ReasonId,
    payload: Any,
    dominant_reason: str | None = None,
) -> ShieldReceiptVerificationResult:
    return ShieldReceiptVerificationResult(
        state=state,
        reason_id=reason_id,
        verified=False,
        accepted_as_evidence=False,
        final_approval=False,
        final_outcome=None,
        context_hash=_string_or_none(payload, "context_hash"),
        request_id=_string_or_none(payload, "request_id"),
        receipt_hash=_string_or_none(payload, "receipt_hash"),
        handoff_allowed=False,
        dominant_reason_ids=(dominant_reason or state.value,),
        receipt=None,
    )


def _classify_base_error(exc: ValueError) -> tuple[ShieldReceiptVerificationState, ReasonId]:
    if isinstance(exc, DirectComponentVerdictError):
        return ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    if isinstance(exc, ShieldReceiptContextMismatchError):
        return ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH, ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    if isinstance(exc, ShieldReceiptHashMismatchError):
        return ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    if isinstance(exc, ShieldReceiptAuthorityBypassError):
        return ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    if isinstance(exc, ShieldReceiptOutcomeMismatchError):
        return ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS, ReasonId.EQC_CONFLICTING_EVIDENCE
    if isinstance(exc, ShieldReceiptComponentVerdictError):
        return ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT, ReasonId.EQC_INVALID_SHIELD_BUNDLE

    # Legacy fallback for older callers that may still raise plain ValueError.
    # Typed contract exceptions above are the authoritative classification path.
    message = str(exc).lower()
    if "direct shield component" in message:
        return ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    if "context mismatch" in message:
        return ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH, ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    if "hash mismatch" in message:
        return ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    return ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT, ReasonId.EQC_INVALID_SHIELD_BUNDLE



def verify_shield_orchestrator_receipt(
    receipt: Any,
    *,
    expected_context_hash: str,
    expected_request_id: str,
    rejected_receipt_hashes: Iterable[str] = (),
) -> ShieldReceiptVerificationResult:
    """Verify external Shield Orchestrator evidence without importing live Shield code.

    This boundary treats Shield output as evidence only. Even a verified ALLOW never
    becomes AdamantineOS final approval; it can only continue to later checks.
    Replay state is injected by the caller so the verifier remains deterministic and
    has no hidden global authority.
    """

    try:
        reject_direct_component_verdict(receipt)
        valid = validate_shield_orchestrator_receipt(receipt, expected_context_hash=expected_context_hash)
    except ValueError as exc:
        state, reason_id = _classify_base_error(exc)
        dominant_reason = None
        if isinstance(exc, ShieldReceiptOutcomeMismatchError):
            dominant_reason = "DENY_MUST_DOMINATE"
        elif isinstance(exc, ShieldReceiptComponentVerdictError):
            dominant_reason = "COMPONENT_VERDICTS_INVALID"
        return _rejected(state=state, reason_id=reason_id, payload=receipt, dominant_reason=dominant_reason)

    if not isinstance(expected_request_id, str) or not expected_request_id.strip():
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            payload=valid,
            dominant_reason="EXPECTED_REQUEST_ID_INVALID",
        )

    if valid["request_id"] != expected_request_id:
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_REQUEST_MISMATCH,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            payload=valid,
        )

    receipt_hash = str(valid["receipt_hash"])
    if receipt_hash in set(rejected_receipt_hashes):
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_REPLAY_RISK,
            reason_id=ReasonId.EQC_SHIELD_STALE,
            payload=valid,
        )


    final_outcome = str(valid["final_outcome"])
    handoff_allowed = bool(valid["adamantineos_handoff"]["handoff_allowed"])
    dominant_reason_ids = tuple(str(reason_id) for reason_id in valid["dominant_reason_ids"])

    if final_outcome == "DENY":
        state = ShieldReceiptVerificationState.VERIFIED_DENY_DOMINATES
        reason_id = ReasonId.DENY_POLICY
    elif final_outcome == "HUMAN_REVIEW_REQUIRED":
        state = ShieldReceiptVerificationState.VERIFIED_HUMAN_REVIEW_REQUIRED
        reason_id = ReasonId.DENY_AUTHORITY_INSUFFICIENT
    else:
        state = ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
        reason_id = ReasonId.EVIDENCE_OK

    return ShieldReceiptVerificationResult(
        state=state,
        reason_id=reason_id,
        verified=True,
        accepted_as_evidence=True,
        final_approval=False,
        final_outcome=final_outcome,
        context_hash=str(valid["context_hash"]),
        request_id=str(valid["request_id"]),
        receipt_hash=receipt_hash,
        handoff_allowed=handoff_allowed,
        dominant_reason_ids=dominant_reason_ids,
        receipt=valid,
    )
