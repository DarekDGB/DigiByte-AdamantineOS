from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.shield_orchestrator_receipt import (
    _classify_component_verdicts,
    canonical_sha256,
    reject_direct_component_verdict,
    validate_shield_orchestrator_receipt,
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


def receipt(final_outcome: str = "ALLOW", handoff_allowed: bool | None = None) -> dict[str, object]:
    decisions: dict[str, str] = {}
    if final_outcome == "DENY":
        decisions["guardian_wallet"] = "DENY"
    elif final_outcome == "HUMAN_REVIEW_REQUIRED":
        decisions["guardian_wallet"] = "ESCALATE"
    outcome, reason, default_handoff = _classify({component_id: decisions.get(component_id, "ALLOW") for component_id in COMPONENT_IDS})
    if handoff_allowed is None:
        handoff_allowed = default_handoff
    base: dict[str, object] = {
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


def legacy_receipt() -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": "req-1",
        "context_hash": CTX,
        "component_verdicts": [{"component_id": "guardian_wallet"}],
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


def test_adamantine_accepts_only_valid_orchestrator_receipt():
    good = receipt()
    assert validate_shield_orchestrator_receipt(good, expected_context_hash=CTX) == good






def test_adamantine_receipt_hash_vector_stays_stable_with_strict_json_nan_lock():
    item = receipt()

    assert item["receipt_hash"] == "c282da0d9aa6587116271012f82b2399974c0cbfd82dcb7a9545bcb957b4bdfc"
    assert canonical_sha256({"ok": True, "n": 1, "s": "DigiByte"}) == "57191193452bcc05c491b175f9778d9aab8d1d6829fcf55756f1e0ea77967c14"


def test_adamantine_receipt_hash_rejects_non_finite_json_numbers():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="Out of range float values"):
            canonical_sha256({"non_finite": value})


def test_classification_mirrors_orchestrator_skipped_to_deny_for_parity():
    verdicts = _component_verdicts()
    verdicts[0]["decision"] = "SKIPPED"

    outcome, reason_ids, handoff = _classify_component_verdicts(verdicts)

    assert outcome == "DENY"
    assert reason_ids == ["ORCH_ERROR_MISSING_REQUIRED_VERDICT"]
    assert handoff == {
        "handoff_allowed": False,
        "handoff_reason": "ORCH_ERROR_MISSING_REQUIRED_VERDICT",
    }


def test_skipped_component_still_rejected_before_classification():
    item = receipt()
    item["component_verdicts"][0]["decision"] = "SKIPPED"  # type: ignore[index]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="component verdict invalid"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_legacy_receipt_component_summary():
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(legacy_receipt(), expected_context_hash=CTX)


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": "shield.verdict.v1", "decision": "ALLOW"},
        {"decision": "ALLOW"},
    ],
)
def test_adamantine_rejects_direct_component_bypass(payload):
    with pytest.raises(ValueError):
        reject_direct_component_verdict(payload)
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(payload, expected_context_hash=CTX)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r.pop("request_id"),
        lambda r: r.__setitem__("schema_version", "unknown"),
        lambda r: r.__setitem__("contract_version", 4),
        lambda r: r.__setitem__("fail_closed", False),
        lambda r: r.__setitem__("context_hash", "b" * 64),
        lambda r: r.__setitem__("final_outcome", "MAYBE"),
        lambda r: r.__setitem__("component_verdicts", []),
        lambda r: r.__setitem__("dominant_reason_ids", []),
        lambda r: r.__setitem__("adamantineos_handoff", []),
        lambda r: r.__setitem__("adamantineos_handoff", {"handoff_allowed": True}),
        lambda r: r.__setitem__("adamantineos_handoff", {"handoff_allowed": "yes", "handoff_reason": "ORCH"}),
        lambda r: r.__setitem__("adamantineos_handoff", {"handoff_allowed": True, "handoff_reason": ""}),
        lambda r: r.__setitem__("receipt_hash", "b" * 64),
    ],
)
def test_adamantine_rejects_malformed_or_tampered_receipts(mutator):
    item = receipt()
    mutator(item)
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_deny_and_human_review_handoff():
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(receipt("DENY", True), expected_context_hash=CTX)
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(receipt("HUMAN_REVIEW_REQUIRED", True), expected_context_hash=CTX)


def test_adamantine_rejects_uppercase_top_level_context_hash_even_with_valid_receipt_hash():
    item = receipt()
    item["context_hash"] = CTX.upper()
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="lowercase sha256 hex"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_uppercase_expected_context_hash():
    with pytest.raises(ValueError, match="lowercase sha256 hex"):
        validate_shield_orchestrator_receipt(receipt(), expected_context_hash=CTX.upper())


def test_adamantine_rejects_uppercase_receipt_hash():
    item = receipt()
    item["receipt_hash"] = str(item["receipt_hash"]).upper()

    with pytest.raises(ValueError, match="lowercase sha256 hex"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_uppercase_component_context_hash_even_with_valid_receipt_hash():
    item = receipt()
    item["component_verdicts"][0]["context_hash"] = CTX.upper()  # type: ignore[index]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="component verdict invalid"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_uppercase_component_evidence_hash_even_with_valid_receipt_hash():
    item = receipt()
    item["component_verdicts"][0]["evidence_hash"] = ("b" * 64).upper()  # type: ignore[index]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="component verdict invalid"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_bad_input_hash_paths_fail_closed():
    with pytest.raises(ValueError):
        canonical_sha256("bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        reject_direct_component_verdict("bad")  # type: ignore[arg-type]
    bad = receipt()
    bad["context_hash"] = "g" * 64
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(bad, expected_context_hash=CTX)
    short_hash = receipt()
    short_hash["context_hash"] = "bad"
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(short_hash, expected_context_hash=CTX)
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(receipt(), expected_context_hash="g" * 64)
    bad_receipt_hash = receipt()
    bad_receipt_hash["receipt_hash"] = "g" * 64
    with pytest.raises(ValueError):
        validate_shield_orchestrator_receipt(bad_receipt_hash, expected_context_hash=CTX)


def test_adamantine_accepts_component_metadata_without_authority_tokens():
    item = receipt()
    item["component_verdicts"][0]["metadata"] = {"safe_note": "observed"}  # type: ignore[index]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    assert validate_shield_orchestrator_receipt(item, expected_context_hash=CTX) == item


def test_adamantine_rejects_component_context_mismatch_inside_receipt():
    item = receipt()
    item["component_verdicts"][0]["context_hash"] = "c" * 64  # type: ignore[index]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="component verdict invalid"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_non_canonical_component_order():
    item = receipt()
    item["component_verdicts"] = list(reversed(item["component_verdicts"]))  # type: ignore[arg-type]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="canonical v3.2 order"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)


def test_adamantine_rejects_dominant_reason_mismatch_against_components():
    item = receipt("DENY")
    item["dominant_reason_ids"] = ["ORCH_OK_ALL_COMPONENTS_ALLOW"]
    item["receipt_hash"] = ""
    item["receipt_hash"] = canonical_sha256(item)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="dominant_reason_ids"):
        validate_shield_orchestrator_receipt(item, expected_context_hash=CTX)
