from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations import verify_shield_orchestrator_receipt
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import ShieldReceiptVerificationState

CTX = "a" * 64
REQ = "req-verified-1"


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


def _component_verdicts(*, decisions: dict[str, str] | None = None, request_id: str = REQ, context_hash: str = CTX) -> list[dict[str, Any]]:
    merged = {component_id: "ALLOW" for component_id in COMPONENT_IDS}
    if decisions:
        merged.update(decisions)
    return [
        {
            "component_id": component_id,
            "contract_version": 3,
            "schema_version": "shield.verdict.v1",
            "request_id": request_id,
            "context_hash": context_hash,
            "decision": merged[component_id],
            "reason_ids": [REASON_BY_COMPONENT_DECISION[component_id][merged[component_id]]],
            "evidence_hash": "b" * 64,
            "evidence_families": [EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
            "metadata": {},
            "fail_closed": True,
        }
        for component_id in COMPONENT_IDS
    ]


def _receipt(
    final_outcome: str = "ALLOW",
    *,
    request_id: str = REQ,
    context_hash: str = CTX,
    component_verdicts: list[dict[str, Any]] | None = None,
    handoff_allowed: bool | None = None,
) -> dict[str, Any]:
    decisions: dict[str, str] = {}
    if final_outcome == "DENY":
        decisions["guardian_wallet"] = "DENY"
    elif final_outcome == "HUMAN_REVIEW_REQUIRED":
        decisions["guardian_wallet"] = "ESCALATE"
    if component_verdicts is None:
        component_verdicts = _component_verdicts(decisions=decisions, request_id=request_id, context_hash=context_hash)
    component_decisions = {
        str(component["component_id"]): str(component.get("decision", "ALLOW"))
        for component in component_verdicts
        if isinstance(component, dict) and isinstance(component.get("component_id"), str)
    }
    outcome, reason, default_handoff = _classify(component_decisions or {"guardian_wallet": final_outcome})
    if handoff_allowed is None:
        handoff_allowed = default_handoff
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": request_id,
        "context_hash": context_hash,
        "component_verdicts": component_verdicts,
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


def _legacy_receipt(final_outcome: str = "ALLOW") -> dict[str, Any]:
    reason = {
        "ALLOW": "ORCH_OK_ALL_COMPONENTS_ALLOW",
        "DENY": "ORCH_DENY_DOMINATES",
        "HUMAN_REVIEW_REQUIRED": "ORCH_HUMAN_REVIEW_REQUIRED",
    }[final_outcome]
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": REQ,
        "context_hash": CTX,
        "component_verdicts": [
            {"component_id": "guardian_wallet", "verdict": final_outcome, "reason_ids": [reason]}
        ],
        "final_outcome": final_outcome,
        "dominant_reason_ids": [reason],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": final_outcome == "ALLOW",
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
    receipt = _receipt("ALLOW")
    receipt["component_verdicts"][2]["metadata"] = {"final_approval": True}
    receipt["receipt_hash"] = ""
    receipt["receipt_hash"] = canonical_sha256(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
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
    receipt = _receipt("DENY")
    receipt["final_outcome"] = "ALLOW"
    receipt["dominant_reason_ids"] = ["ORCH_OK_ALL_COMPONENTS_ALLOW"]
    receipt["adamantineos_handoff"] = {
        "handoff_allowed": True,
        "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW",
    }
    receipt["receipt_hash"] = ""
    receipt["receipt_hash"] = canonical_sha256(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
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


def test_verifier_rejects_legacy_receipt_components_as_unverified_evidence() -> None:
    result = verify_shield_orchestrator_receipt(
        _legacy_receipt("ALLOW"),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.verified is False
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_component_verdict_validator_rejects_non_list_boundary_shape() -> None:
    receipt = _receipt("ALLOW")
    receipt["component_verdicts"] = None
    receipt["receipt_hash"] = ""
    receipt["receipt_hash"] = canonical_sha256(receipt)

    result = verify_shield_orchestrator_receipt(receipt, expected_context_hash=CTX, expected_request_id=REQ)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("REJECTED_INVALID_RECEIPT",)


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
