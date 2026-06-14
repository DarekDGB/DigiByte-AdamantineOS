from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
    ShieldReceiptAdapterState,
    adapt_shield_orchestrator_receipt,
)

CTX = "a" * 64


def _receipt(final_outcome: str = "ALLOW", *, handoff_allowed: bool | None = None) -> dict[str, Any]:
    if handoff_allowed is None:
        handoff_allowed = final_outcome == "ALLOW"
    reason = {
        "ALLOW": "ORCH_OK_ALL_COMPONENTS_ALLOW",
        "DENY": "ORCH_DENY_DOMINATES",
        "HUMAN_REVIEW_REQUIRED": "ORCH_HUMAN_REVIEW_REQUIRED",
    }[final_outcome]
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": "req-1",
        "context_hash": CTX,
        "component_verdicts": [{"component_id": "guardian_wallet", "verdict": final_outcome}],
        "final_outcome": final_outcome,
        "dominant_reason_ids": [reason],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": handoff_allowed,
            "handoff_reason": reason,
        },
        "fail_closed": True,
    }
    base["receipt_hash"] = canonical_sha256(base)
    return base


def test_adapter_maps_allow_only_to_continue_checks_not_final_approval() -> None:
    result = adapt_shield_orchestrator_receipt(_receipt("ALLOW"), expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS
    assert result.adapter_reason_id == ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.handoff_allowed is True
    assert result.context_hash == CTX
    assert result.dominant_reason_ids == ("ORCH_OK_ALL_COMPONENTS_ALLOW",)
    assert result.receipt is not None


def test_adapter_maps_deny_to_block_and_never_handoff_allow() -> None:
    result = adapt_shield_orchestrator_receipt(_receipt("DENY"), expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_BLOCK_DENY_DOMINATES
    assert result.adapter_reason_id == ReasonId.DENY_POLICY
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "DENY"
    assert result.handoff_allowed is False
    assert result.dominant_reason_ids == ("ORCH_DENY_DOMINATES",)


def test_adapter_maps_human_review_to_review_required() -> None:
    result = adapt_shield_orchestrator_receipt(_receipt("HUMAN_REVIEW_REQUIRED"), expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_REVIEW_REQUIRED
    assert result.adapter_reason_id == ReasonId.DENY_AUTHORITY_INSUFFICIENT
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "HUMAN_REVIEW_REQUIRED"
    assert result.handoff_allowed is False
    assert result.dominant_reason_ids == ("ORCH_HUMAN_REVIEW_REQUIRED",)


def test_adapter_rejects_raw_component_bypass_without_throwing_allow_path() -> None:
    result = adapt_shield_orchestrator_receipt(
        {"schema_version": "shield.verdict.v1", "decision": "ALLOW"},
        expected_context_hash=CTX,
    )

    assert result.state == ShieldReceiptAdapterState.SHIELD_REJECTED_RAW_COMPONENT_BYPASS
    assert result.adapter_reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.final_outcome is None
    assert result.handoff_allowed is False
    assert result.receipt is None


def test_adapter_rejects_context_mismatch_with_stable_state() -> None:
    result = adapt_shield_orchestrator_receipt(_receipt("ALLOW"), expected_context_hash="b" * 64)

    assert result.state == ShieldReceiptAdapterState.SHIELD_REJECTED_CONTEXT_MISMATCH
    assert result.adapter_reason_id == ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.context_hash == CTX
    assert result.dominant_reason_ids == ("SHIELD_REJECTED_CONTEXT_MISMATCH",)


def test_adapter_rejects_tampered_receipt_with_stable_state() -> None:
    receipt = _receipt("ALLOW")
    receipt["receipt_hash"] = "b" * 64

    result = adapt_shield_orchestrator_receipt(receipt, expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_REJECTED_TAMPERED_RECEIPT
    assert result.adapter_reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.context_hash == CTX


def test_adapter_rejects_invalid_shape_fail_closed() -> None:
    result = adapt_shield_orchestrator_receipt(["not", "a", "receipt"], expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_REJECTED_INVALID_RECEIPT
    assert result.adapter_reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.context_hash is None


def test_adapter_rejects_deny_or_human_review_attempting_handoff_allow() -> None:
    deny = adapt_shield_orchestrator_receipt(_receipt("DENY", handoff_allowed=True), expected_context_hash=CTX)
    review = adapt_shield_orchestrator_receipt(_receipt("HUMAN_REVIEW_REQUIRED", handoff_allowed=True), expected_context_hash=CTX)

    assert deny.state == ShieldReceiptAdapterState.SHIELD_REJECTED_INVALID_RECEIPT
    assert review.state == ShieldReceiptAdapterState.SHIELD_REJECTED_INVALID_RECEIPT
    assert deny.accepted_as_evidence is False
    assert review.accepted_as_evidence is False
    assert deny.final_approval is False
    assert review.final_approval is False


def test_adapter_rejects_receipt_with_invalid_hash_field() -> None:
    receipt = _receipt("ALLOW")
    receipt["context_hash"] = "bad"

    result = adapt_shield_orchestrator_receipt(receipt, expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_REJECTED_INVALID_RECEIPT
    assert result.context_hash == "bad"
    assert result.accepted_as_evidence is False


def test_adapter_classifies_typed_shield_receipt_errors_without_message_substrings() -> None:
    from adamantine.v1.contracts.shield_orchestrator_receipt import (
        DirectComponentVerdictError,
        ShieldReceiptContextMismatchError,
        ShieldReceiptHashMismatchError,
    )
    from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import _classify_validation_error

    assert _classify_validation_error(DirectComponentVerdictError("typed-only raw bypass")) == ShieldReceiptAdapterState.SHIELD_REJECTED_RAW_COMPONENT_BYPASS
    assert _classify_validation_error(ShieldReceiptContextMismatchError("typed-only context failure")) == ShieldReceiptAdapterState.SHIELD_REJECTED_CONTEXT_MISMATCH
    assert _classify_validation_error(ShieldReceiptHashMismatchError("typed-only receipt digest failure")) == ShieldReceiptAdapterState.SHIELD_REJECTED_TAMPERED_RECEIPT


def test_adapter_preserves_legacy_plain_value_error_message_fallbacks() -> None:
    from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import _classify_validation_error

    assert _classify_validation_error(ValueError("legacy direct Shield component wording")) == ShieldReceiptAdapterState.SHIELD_REJECTED_RAW_COMPONENT_BYPASS
    assert _classify_validation_error(ValueError("legacy context mismatch wording")) == ShieldReceiptAdapterState.SHIELD_REJECTED_CONTEXT_MISMATCH
    assert _classify_validation_error(ValueError("legacy hash mismatch wording")) == ShieldReceiptAdapterState.SHIELD_REJECTED_TAMPERED_RECEIPT
