from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations import verify_shield_orchestrator_receipt
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import ShieldReceiptVerificationState

CTX = "a" * 64
REQ = "req-milestone-16b-v3-2-contract"
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "shield_v3_integration"
    / "orchestrator_v3_2_receipt"
    / "component_baseline_receipt.json"
)
SHARED_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "shield_v3_integration"
    / "orchestrator_v3_2_receipt"
    / "shared_shield_orchestrator_receipt_v3_2_component_baseline.json"
)

EXPECTED_COMPONENTS = {
    "adn": {
        "reason_ids": {"ADN_OK_COORDINATION_ALLOW"},
        "evidence_families": {"defense_signal"},
    },
    "dqsn": {
        "reason_ids": {"DQSN_OK_NETWORK_ALLOW"},
        "evidence_families": {"network_observation"},
    },
    "guardian_wallet": {
        "reason_ids": {"GW_OK_HEALTHY_ALLOW"},
        "evidence_families": {"wallet_context"},
    },
    "qwg": {
        "reason_ids": {"QWG_OK_POSTURE_ALLOW"},
        "evidence_families": {"wallet_posture"},
    },
    "sentinel_ai": {
        "reason_ids": {"SNTL_OK_TELEMETRY_ALLOW"},
        "evidence_families": {"telemetry"},
    },
}


def _load_receipt() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def _rehash(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt = deepcopy(receipt)
    receipt["receipt_hash"] = ""
    receipt["receipt_hash"] = canonical_sha256(receipt)
    return receipt


def _verify(receipt: Any):
    return verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )


def test_milestone_16c_fixture_represents_all_five_shield_baseline_components() -> None:
    receipt = _load_receipt()
    components = {component["component_id"]: component for component in receipt["component_verdicts"]}

    assert set(components) == set(EXPECTED_COMPONENTS)
    for component_id, expected in EXPECTED_COMPONENTS.items():
        component = components[component_id]
        assert component["schema_version"] == "shield.verdict.v1"
        assert component["contract_version"] == 3
        assert component["request_id"] == REQ
        assert component["context_hash"] == CTX
        assert component["decision"] == "ALLOW"
        assert component["fail_closed"] is True
        assert set(component["reason_ids"]) == expected["reason_ids"]
        assert set(component["evidence_families"]) == expected["evidence_families"]


def test_milestone_16c_shared_orchestrator_fixture_is_accepted_as_evidence_only() -> None:
    receipt = json.loads(SHARED_FIXTURE.read_text())

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id="req-milestone-16c-shared-vector",
    )

    assert result.state == ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"


def test_milestone_16c_component_baseline_receipt_is_accepted_as_evidence_only() -> None:
    result = _verify(_load_receipt())

    assert result.state == ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.dominant_reason_ids == ("ORCH_OK_ALL_COMPONENTS_ALLOW",)


def test_milestone_16c_every_raw_component_verdict_is_rejected_as_bypass() -> None:
    receipt = _load_receipt()

    for raw_component in receipt["component_verdicts"]:
        result = _verify(raw_component)

        assert result.state == ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS
        assert result.accepted_as_evidence is False
        assert result.final_approval is False


def test_milestone_16c_missing_component_from_v3_2_receipt_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"] = [
        component for component in receipt["component_verdicts"] if component["component_id"] != "qwg"
    ]
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)
    assert result.accepted_as_evidence is False


def test_milestone_16c_duplicate_component_from_v3_2_receipt_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][-1] = deepcopy(receipt["component_verdicts"][0])
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_milestone_16c_unknown_component_from_v3_2_receipt_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["component_id"] = "unknown_component"
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_milestone_16c_mixed_legacy_and_v3_2_components_fail_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0] = {
        "component_id": "legacy_component",
        "verdict": "ALLOW",
        "reason_ids": ["LEGACY_OK"],
    }
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


def test_milestone_16c_unknown_component_reason_id_from_rehashed_receipt_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["reason_ids"] = ["UNKNOWN_COMPONENT_REASON"]
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)
    assert result.accepted_as_evidence is False


def test_milestone_16c_unknown_component_evidence_family_from_rehashed_receipt_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["evidence_families"] = ["unknown_component_family"]
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)
    assert result.accepted_as_evidence is False


def test_milestone_16c_skipped_component_from_rehashed_receipt_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["decision"] = "SKIPPED"
    receipt = _rehash(receipt)

    result = _verify(receipt)

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)
    assert result.accepted_as_evidence is False
