from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from adamantine.v1.contracts.combined_context_hash import (
    CombinedContextHashError,
    compute_combined_context_hash,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
    ShieldReceiptAdapterResult,
    ShieldReceiptAdapterState,
    adapt_shield_orchestrator_receipt,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import (
    ShieldReceiptVerificationResult,
    ShieldReceiptVerificationState,
    verify_shield_orchestrator_receipt,
)


class ShieldV3AdapterHarnessState(str, Enum):
    """Stable Level 2 fixture-only Shield v3 adapter harness states."""

    ALLOW_EVIDENCE_CONTINUE_CHECKS = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    DENY_DOMINATES_BLOCK = "DENY_DOMINATES_BLOCK"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    REJECTED_CONTEXT_CONTRACT = "REJECTED_CONTEXT_CONTRACT"
    REJECTED_RECEIPT_VERIFICATION = "REJECTED_RECEIPT_VERIFICATION"
    REJECTED_ADAPTER_MAPPING = "REJECTED_ADAPTER_MAPPING"
    REJECTED_BOUNDARY_INCONSISTENCY = "REJECTED_BOUNDARY_INCONSISTENCY"


@dataclass(frozen=True)
class ShieldV3AdapterHarnessResult:
    """Deterministic Level 2 fixture-only harness result.

    This result connects the AdamantineOS combined context hash boundary, the
    Shield receipt verifier, and the Shield receipt adapter. It is intentionally
    fixture-only and never imports or calls live Shield repositories.
    """

    state: ShieldV3AdapterHarnessState
    reason_id: ReasonId
    context_hash: str | None
    request_id: str | None
    accepted_as_evidence: bool
    final_approval: bool
    final_outcome: str | None
    handoff_allowed: bool
    dominant_reason_ids: tuple[str, ...]
    verification: ShieldReceiptVerificationResult | None = None
    adapter: ShieldReceiptAdapterResult | None = None


def _request_id_from_context(context_payload: Any) -> str | None:
    if isinstance(context_payload, Mapping) and isinstance(context_payload.get("request_id"), str):
        return str(context_payload["request_id"])
    return None


def _rejected(
    *,
    state: ShieldV3AdapterHarnessState,
    reason_id: ReasonId,
    context_hash: str | None,
    request_id: str | None,
    dominant_reason: str,
    verification: ShieldReceiptVerificationResult | None = None,
    adapter: ShieldReceiptAdapterResult | None = None,
) -> ShieldV3AdapterHarnessResult:
    return ShieldV3AdapterHarnessResult(
        state=state,
        reason_id=reason_id,
        context_hash=context_hash,
        request_id=request_id,
        accepted_as_evidence=False,
        final_approval=False,
        final_outcome=None,
        handoff_allowed=False,
        dominant_reason_ids=(dominant_reason,),
        verification=verification,
        adapter=adapter,
    )


def _adapter_state_matches_verifier(
    verification: ShieldReceiptVerificationResult,
    adapter: ShieldReceiptAdapterResult,
) -> bool:
    if verification.state == ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS:
        return adapter.state == ShieldReceiptAdapterState.SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS
    if verification.state == ShieldReceiptVerificationState.VERIFIED_DENY_DOMINATES:
        return adapter.state == ShieldReceiptAdapterState.SHIELD_BLOCK_DENY_DOMINATES
    if verification.state == ShieldReceiptVerificationState.VERIFIED_HUMAN_REVIEW_REQUIRED:
        return adapter.state == ShieldReceiptAdapterState.SHIELD_REVIEW_REQUIRED
    return False


def run_shield_v3_adapter_harness(
    *,
    combined_context_payload: Any,
    shield_receipt: Any,
    rejected_receipt_hashes: Iterable[str] = (),
) -> ShieldV3AdapterHarnessResult:
    """Run the Level 2 fixture-only AdamantineOS Shield v3 adapter harness.

    The harness uses only local AdamantineOS contracts. It computes the combined
    context hash, verifies the supplied Orchestrator-style receipt against that
    hash and request ID, then maps the verified receipt through the adapter.

    A verified Shield ALLOW is evidence only. This function never returns final
    approval and never performs live Shield Orchestrator integration.
    """

    request_id = _request_id_from_context(combined_context_payload)
    try:
        context_hash = compute_combined_context_hash(combined_context_payload)
    except CombinedContextHashError as exc:
        return _rejected(
            state=ShieldV3AdapterHarnessState.REJECTED_CONTEXT_CONTRACT,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            context_hash=None,
            request_id=request_id,
            dominant_reason=f"COMBINED_CONTEXT_HASH_CONTRACT_REJECTED:{exc}",
        )

    verification = verify_shield_orchestrator_receipt(
        shield_receipt,
        expected_context_hash=context_hash,
        expected_request_id=str(combined_context_payload["request_id"]),
        rejected_receipt_hashes=rejected_receipt_hashes,
    )

    if not verification.verified:
        return _rejected(
            state=ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION,
            reason_id=verification.reason_id,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason=verification.state.value,
            verification=verification,
        )

    adapter = adapt_shield_orchestrator_receipt(shield_receipt, expected_context_hash=context_hash)
    if not adapter.accepted_as_evidence:
        return _rejected(
            state=ShieldV3AdapterHarnessState.REJECTED_ADAPTER_MAPPING,
            reason_id=adapter.adapter_reason_id,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason=adapter.state.value,
            verification=verification,
            adapter=adapter,
        )

    if not _adapter_state_matches_verifier(verification, adapter):
        return _rejected(
            state=ShieldV3AdapterHarnessState.REJECTED_BOUNDARY_INCONSISTENCY,
            reason_id=ReasonId.EQC_CONFLICTING_EVIDENCE,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason="VERIFIER_ADAPTER_STATE_MISMATCH",
            verification=verification,
            adapter=adapter,
        )

    if adapter.final_approval or verification.final_approval:
        return _rejected(
            state=ShieldV3AdapterHarnessState.REJECTED_BOUNDARY_INCONSISTENCY,
            reason_id=ReasonId.EQC_CONFLICTING_EVIDENCE,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason="SHIELD_EVIDENCE_CANNOT_GRANT_FINAL_APPROVAL",
            verification=verification,
            adapter=adapter,
        )

    if verification.final_outcome == "DENY":
        state = ShieldV3AdapterHarnessState.DENY_DOMINATES_BLOCK
        reason_id = ReasonId.DENY_POLICY
    elif verification.final_outcome == "HUMAN_REVIEW_REQUIRED":
        state = ShieldV3AdapterHarnessState.HUMAN_REVIEW_REQUIRED
        reason_id = ReasonId.DENY_AUTHORITY_INSUFFICIENT
    else:
        state = ShieldV3AdapterHarnessState.ALLOW_EVIDENCE_CONTINUE_CHECKS
        reason_id = ReasonId.EVIDENCE_OK

    return ShieldV3AdapterHarnessResult(
        state=state,
        reason_id=reason_id,
        context_hash=context_hash,
        request_id=request_id,
        accepted_as_evidence=True,
        final_approval=False,
        final_outcome=verification.final_outcome,
        handoff_allowed=verification.handoff_allowed and adapter.handoff_allowed,
        dominant_reason_ids=verification.dominant_reason_ids,
        verification=verification,
        adapter=adapter,
    )
