from __future__ import annotations

import pytest

from adamantine.v1.contracts.shield_orchestrator_receipt import (
    canonical_sha256,
    reject_direct_component_verdict,
    validate_shield_orchestrator_receipt,
)

CTX = "a" * 64


def receipt(final_outcome: str = "ALLOW", handoff_allowed: bool = True) -> dict[str, object]:
    base = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": "req-1",
        "context_hash": CTX,
        "component_verdicts": [{"component_id": "guardian_wallet"}],
        "final_outcome": final_outcome,
        "dominant_reason_ids": ["ORCH_OK_ALL_COMPONENTS_ALLOW"],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": handoff_allowed,
            "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW",
        },
        "fail_closed": True,
    }
    base["receipt_hash"] = canonical_sha256(base)
    return base


def test_adamantine_accepts_only_valid_orchestrator_receipt():
    good = receipt()
    assert validate_shield_orchestrator_receipt(good, expected_context_hash=CTX) == good


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
