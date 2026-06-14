from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations import verify_shield_orchestrator_receipt
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import ShieldReceiptVerificationState

CTX = "a" * 64
REQ = "req-verified-1"


def _receipt(
    final_outcome: str = "ALLOW",
    *,
    request_id: str = REQ,
    context_hash: str = CTX,
    component_verdicts: list[dict[str, Any]] | None = None,
    handoff_allowed: bool | None = None,
) -> dict[str, Any]:
    if handoff_allowed is None:
        handoff_allowed = final_outcome == "ALLOW"
    reason = {
        "ALLOW": "ORCH_OK_ALL_COMPONENTS_ALLOW",
        "DENY": "ORCH_DENY_DOMINATES",
        "HUMAN_REVIEW_REQUIRED": "ORCH_HUMAN_REVIEW_REQUIRED",
    }[final_outcome]
    if component_verdicts is None:
        component_verdicts = [
            {
                "component_id": "guardian_wallet",
                "verdict": final_outcome,
                "reason_ids": [reason],
            }
        ]
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": request_id,
        "context_hash": context_hash,
        "component_verdicts": component_verdicts,
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


def test_verifier_accepts_allow_only_as_evidence_and_never_final_approval() -> None:
    result = verify_shield_orchestrator_receipt(_receipt("ALLOW"), expected_context_hash=CTX, expected_request_id=REQ)

    assert result.state == ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.context_hash == CTX
    assert result.request_id == REQ
    assert result.receipt_hash is not None
    assert result.handoff_allowed is True
    assert result.dominant_reason_ids == ("ORCH_OK_ALL_COMPONENTS_ALLOW",)
    assert result.receipt is not None


def test_verifier_accepts_deny_as_dominant_blocking_evidence() -> None:
    result = verify_shield_orchestrator_receipt(_receipt("DENY"), expected_context_hash=CTX, expected_request_id=REQ)

    assert result.state == ShieldReceiptVerificationState.VERIFIED_DENY_DOMINATES
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "DENY"
    assert result.handoff_allowed is False


def test_verifier_accepts_human_review_as_review_required_evidence() -> None:
    result = verify_shield_orchestrator_receipt(
        _receipt("HUMAN_REVIEW_REQUIRED"),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.VERIFIED_HUMAN_REVIEW_REQUIRED
    assert result.reason_id == ReasonId.DENY_AUTHORITY_INSUFFICIENT
    assert result.verified is True
    assert result.final_approval is False
    assert result.final_outcome == "HUMAN_REVIEW_REQUIRED"
    assert result.handoff_allowed is False


def test_verifier_rejects_raw_component_verdict_bypass() -> None:
    result = verify_shield_orchestrator_receipt(
        {"schema_version": "shield.verdict.v1", "decision": "ALLOW"},
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.verified is False
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.dominant_reason_ids == ("REJECTED_RAW_COMPONENT_BYPASS",)


def test_verifier_rejects_context_mismatch() -> None:
    result = verify_shield_orchestrator_receipt(_receipt("ALLOW"), expected_context_hash="b" * 64, expected_request_id=REQ)

    assert result.state == ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH
    assert result.reason_id == ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    assert result.context_hash == CTX
    assert result.request_id == REQ
    assert result.receipt_hash is not None
    assert result.handoff_allowed is False


def test_verifier_rejects_tampered_receipt_hash() -> None:
    receipt = _receipt("ALLOW")
    receipt["receipt_hash"] = "b" * 64

    result = verify_shield_orchestrator_receipt(receipt, expected_context_hash=CTX, expected_request_id=REQ)

    assert result.state == ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.context_hash == CTX
    assert result.request_id == REQ
    assert result.receipt_hash == "b" * 64


def test_verifier_rejects_invalid_shape() -> None:
    result = verify_shield_orchestrator_receipt(["not", "receipt"], expected_context_hash=CTX, expected_request_id=REQ)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.context_hash is None
    assert result.request_id is None
    assert result.receipt_hash is None


def test_verifier_rejects_invalid_expected_request_id() -> None:
    result = verify_shield_orchestrator_receipt(_receipt("ALLOW"), expected_context_hash=CTX, expected_request_id=" ")

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("EXPECTED_REQUEST_ID_INVALID",)
    assert result.request_id == REQ


def test_verifier_rejects_request_mismatch_to_stop_receipt_reuse() -> None:
    result = verify_shield_orchestrator_receipt(_receipt("ALLOW"), expected_context_hash=CTX, expected_request_id="other-req")

    assert result.state == ShieldReceiptVerificationState.REJECTED_REQUEST_MISMATCH
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.request_id == REQ
    assert result.accepted_as_evidence is False


def test_verifier_rejects_injected_replay_risk_without_global_state() -> None:
    receipt = _receipt("ALLOW")

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
        rejected_receipt_hashes=(receipt["receipt_hash"],),
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_REPLAY_RISK
    assert result.reason_id == ReasonId.EQC_SHIELD_STALE
    assert result.receipt_hash == receipt["receipt_hash"]
    assert result.final_approval is False


def test_verifier_rejects_nested_authority_bypass_inside_component_verdict() -> None:
    component = {
        "component_id": "guardian_wallet",
        "verdict": "ALLOW",
        "reason_ids": ["ORCH_OK_ALL_COMPONENTS_ALLOW"],
        "final_approval": True,
    }

    result = verify_shield_orchestrator_receipt(
        _receipt("ALLOW", component_verdicts=[component]),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_verifier_rejects_invalid_component_verdict_shape() -> None:
    component = {
        "component_id": "guardian_wallet",
        "verdict": "ALLOW",
        "reason_ids": [],
    }

    result = verify_shield_orchestrator_receipt(
        _receipt("ALLOW", component_verdicts=[component]),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)
    assert result.accepted_as_evidence is False


def test_verifier_rejects_nested_non_mapping_component_verdict() -> None:
    result = verify_shield_orchestrator_receipt(
        _receipt("ALLOW", component_verdicts=["bad-component"]),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_verifier_rejects_empty_component_id() -> None:
    result = verify_shield_orchestrator_receipt(
        _receipt(
            "ALLOW",
            component_verdicts=[{"component_id": " ", "verdict": "ALLOW", "reason_ids": ["OK"]}],
        ),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_verifier_rejects_blank_component_reason_id() -> None:
    result = verify_shield_orchestrator_receipt(
        _receipt(
            "ALLOW",
            component_verdicts=[{"component_id": "guardian_wallet", "verdict": "ALLOW", "reason_ids": [""]}],
        ),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_verifier_rejects_component_deny_hidden_under_final_allow() -> None:
    component = {
        "component_id": "guardian_wallet",
        "verdict": "DENY",
        "reason_ids": ["GUARDIAN_DENY"],
    }

    result = verify_shield_orchestrator_receipt(
        _receipt("ALLOW", component_verdicts=[component]),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS
    assert result.reason_id == ReasonId.EQC_CONFLICTING_EVIDENCE
    assert result.dominant_reason_ids == ("DENY_MUST_DOMINATE",)


def test_verifier_rejects_empty_component_verdict_list() -> None:
    result = verify_shield_orchestrator_receipt(
        _receipt("ALLOW", component_verdicts=[]),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE


def test_verifier_rejects_unknown_component_verdict_value() -> None:
    result = verify_shield_orchestrator_receipt(
        _receipt(
            "ALLOW",
            component_verdicts=[{"component_id": "guardian_wallet", "verdict": "MAYBE", "reason_ids": ["BAD"]}],
        ),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_component_verdict_validator_rejects_non_list_boundary_shape() -> None:
    from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import _validate_component_verdicts

    assert _validate_component_verdicts({"component_verdicts": None}) is False


def test_verifier_classifies_typed_shield_receipt_errors_without_message_substrings() -> None:
    from adamantine.v1.contracts.shield_orchestrator_receipt import (
        DirectComponentVerdictError,
        ShieldReceiptContextMismatchError,
        ShieldReceiptHashMismatchError,
    )
    from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import _classify_base_error

    raw_state, raw_reason = _classify_base_error(DirectComponentVerdictError("typed-only raw bypass"))
    context_state, context_reason = _classify_base_error(ShieldReceiptContextMismatchError("typed-only context failure"))
    hash_state, hash_reason = _classify_base_error(ShieldReceiptHashMismatchError("typed-only receipt digest failure"))

    assert raw_state == ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS
    assert raw_reason == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert context_state == ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH
    assert context_reason == ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    assert hash_state == ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT
    assert hash_reason == ReasonId.EQC_INVALID_SHIELD_BUNDLE
