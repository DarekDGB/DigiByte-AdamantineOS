from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
    ShieldReceiptAdapterState,
    adapt_shield_orchestrator_receipt,
)

CTX = "a" * 64


COMPONENT_IDS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")
REASON_BY_COMPONENT_DECISION = {
    "adn": {
        "ALLOW": "ADN_OK_COORDINATION_ALLOW",
        "ESCALATE": "ADN_ESCALATE_POLICY_REVIEW",
        "DENY": "ADN_DENY_DEFENSE_TRIGGERED",
        "ERROR": "ADN_ERROR_INVALID_VERDICT",
    },
    "dqsn": {
        "ALLOW": "DQSN_OK_NETWORK_ALLOW",
        "ESCALATE": "DQSN_ESCALATE_QUANTUM_SIGNAL",
        "DENY": "DQSN_DENY_NETWORK_RISK",
        "ERROR": "DQSN_ERROR_INVALID_VERDICT",
    },
    "guardian_wallet": {
        "ALLOW": "GW_OK_HEALTHY_ALLOW",
        "ESCALATE": "GW_ESCALATE_QID_REQUIRED",
        "DENY": "GW_DENY_POLICY_BLOCKED",
        "ERROR": "GW_ERROR_INVALID_VERDICT",
    },
    "qwg": {
        "ALLOW": "QWG_OK_POSTURE_ALLOW",
        "ESCALATE": "QWG_ESCALATE_QUANTUM_POSTURE",
        "DENY": "QWG_DENY_KEY_RISK",
        "ERROR": "QWG_ERROR_INVALID_VERDICT",
    },
    "sentinel_ai": {
        "ALLOW": "SNTL_OK_TELEMETRY_ALLOW",
        "ESCALATE": "SNTL_ESCALATE_THREAT_REVIEW",
        "DENY": "SNTL_DENY_THREAT_DETECTED",
        "ERROR": "SNTL_ERROR_AI_OUTPUT_UNTRUSTED",
    },
}
EVIDENCE_FAMILY_BY_COMPONENT = {
    "adn": "defense_signal",
    "dqsn": "network_observation",
    "guardian_wallet": "wallet_context",
    "qwg": "wallet_posture",
    "sentinel_ai": "telemetry",
}


def _classify(decisions: dict[str, str]) -> tuple[str, str, bool]:
    values = list(decisions.values())
    if "DENY" in values:
        return "DENY", "ORCH_DENY_DOMINATES", False
    if "ERROR" in values:
        return "DENY", "ORCH_ERROR_INVALID_COMPONENT_VERDICT", False
    if "ESCALATE" in values:
        return "HUMAN_REVIEW_REQUIRED", "ORCH_HUMAN_REVIEW_ESCALATE_PRESENT", False
    return "ALLOW", "ORCH_OK_ALL_COMPONENTS_ALLOW", True


def _component_verdicts(decisions: dict[str, str] | None = None) -> list[dict[str, Any]]:
    merged = {component_id: "ALLOW" for component_id in COMPONENT_IDS}
    if decisions:
        merged.update(decisions)
    return [
        {
            "component_id": component_id,
            "contract_version": 3,
            "schema_version": "shield.verdict.v1",
            "request_id": "req-1",
            "context_hash": CTX,
            "decision": merged[component_id],
            "reason_ids": [REASON_BY_COMPONENT_DECISION[component_id][merged[component_id]]],
            "evidence_hash": "b" * 64,
            "evidence_families": [EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
            "metadata": {},
            "fail_closed": True,
        }
        for component_id in COMPONENT_IDS
    ]


def _receipt(final_outcome: str = "ALLOW", *, handoff_allowed: bool | None = None) -> dict[str, Any]:
    decisions: dict[str, str] = {}
    if final_outcome == "DENY":
        decisions["guardian_wallet"] = "DENY"
    elif final_outcome == "HUMAN_REVIEW_REQUIRED":
        decisions["guardian_wallet"] = "ESCALATE"
    outcome, reason, default_handoff = _classify({component_id: decisions.get(component_id, "ALLOW") for component_id in COMPONENT_IDS})
    if handoff_allowed is None:
        handoff_allowed = default_handoff
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": "req-1",
        "context_hash": CTX,
        "component_verdicts": _component_verdicts(decisions),
        "final_outcome": outcome,
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


def _legacy_receipt() -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": "req-1",
        "context_hash": CTX,
        "component_verdicts": [{"component_id": "guardian_wallet", "verdict": "ALLOW"}],
        "final_outcome": "ALLOW",
        "dominant_reason_ids": ["ORCH_OK_ALL_COMPONENTS_ALLOW"],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": True,
            "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW",
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
    assert result.dominant_reason_ids == ("ORCH_HUMAN_REVIEW_ESCALATE_PRESENT",)


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


def test_adapter_rejects_legacy_receipt_components_as_unverified_evidence() -> None:
    result = adapt_shield_orchestrator_receipt(_legacy_receipt(), expected_context_hash=CTX)

    assert result.state == ShieldReceiptAdapterState.SHIELD_REJECTED_RAW_COMPONENT_BYPASS
    assert result.adapter_reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.handoff_allowed is False


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
