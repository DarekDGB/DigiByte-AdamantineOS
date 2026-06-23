from __future__ import annotations

import copy
import hmac
import json
from pathlib import Path

from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import (
    ORCHESTRATOR_RECEIPT_DOMAIN,
    receipt_hash,
    signed_payload_hash,
    unsigned_receipt_payload,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import (
    ShieldV4ReceiptVerificationState,
    verify_shield_v4_orchestrator_receipt,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "adamantine"
    / "v1"
    / "fixtures"
    / "shield_v4"
    / "full_multi_repo_v4_allow_flow.json"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def verify_fixture(receipt: dict, fixture: dict, **overrides):
    params = {
        "expected_context_hash": fixture["expected_context_hash"],
        "expected_request_id": fixture["expected_request_id"],
        "trusted_key_registry": fixture["trusted_key_registry"],
        "verification_time": fixture["verification_time"],
    }
    params.update(overrides)
    return verify_shield_v4_orchestrator_receipt(receipt, **params)



def resign_orchestrator_receipt(receipt: dict) -> None:
    unsigned = unsigned_receipt_payload(receipt)
    receipt["receipt_hash"] = receipt_hash(unsigned)
    payload_hash = signed_payload_hash(domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN, payload=unsigned)
    receipt["signed_payload_hash"] = payload_hash
    signatures = []
    for algorithm in ("classical-ed25519", "ml-dsa"):
        key_id = f"test-shield_orchestrator-{algorithm}-v1"
        public_key = f"TEST-ONLY-PUBLIC-shield_orchestrator-{algorithm}-v1"
        signatures.append(
            {
                "algorithm": algorithm,
                "key_id": key_id,
                "key_version": 1,
                "signed_payload_hash": payload_hash,
                "domain_tag": ORCHESTRATOR_RECEIPT_DOMAIN,
                "signature": hmac.new(
                    public_key.encode("utf-8"),
                    f"{ORCHESTRATOR_RECEIPT_DOMAIN}|{payload_hash}|{algorithm}|{key_id}|1".encode("utf-8"),
                    "sha256",
                ).hexdigest(),
            }
        )
    receipt["signature_bundle"] = {"schema_version": "shield.signature_bundle.v1", "policy_version": "policy.v1", "signatures": signatures}


def test_adamantineos_accepts_full_multi_repo_shield_v4_allow_flow_as_evidence_only() -> None:
    fixture = load_fixture()
    result = verify_fixture(fixture["receipt"], fixture)

    assert fixture["author_attribution"] == "DarekDGB"
    assert result.state == ShieldV4ReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.handoff_allowed is True
    assert result.verification_summary is not None
    assert result.verification_summary["orchestrator"]["verified_algorithms"] == ["classical-ed25519", "ml-dsa"]
    assert [item["component_id"] for item in result.verification_summary["components"]] == [
        "adn",
        "dqsn",
        "guardian_wallet",
        "qwg",
        "sentinel_ai",
    ]


def test_adamantineos_rejects_full_multi_repo_missing_component_signature() -> None:
    fixture = load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    receipt["component_verdicts"][0]["signature_bundle"]["signatures"] = receipt["component_verdicts"][0]["signature_bundle"]["signatures"][:1]
    resign_orchestrator_receipt(receipt)

    result = verify_fixture(receipt, fixture)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.final_approval is False


def test_adamantineos_rejects_full_multi_repo_wrong_component_key() -> None:
    fixture = load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    receipt["component_verdicts"][0]["signature_bundle"]["signatures"][0]["key_id"] = "test-shield_component_qwg-classical-ed25519-v1"
    resign_orchestrator_receipt(receipt)

    result = verify_fixture(receipt, fixture)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_KEY_REGISTRY
    assert result.final_approval is False


def test_adamantineos_rejects_full_multi_repo_wrong_context_hash() -> None:
    fixture = load_fixture()
    result = verify_fixture(fixture["receipt"], fixture, expected_context_hash="b" * 64)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_CONTEXT_MISMATCH
    assert result.final_approval is False


def test_adamantineos_rejects_full_multi_repo_v3_downgrade_attempt() -> None:
    fixture = load_fixture()
    v3 = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "context_hash": fixture["expected_context_hash"],
        "request_id": fixture["expected_request_id"],
    }

    result = verify_fixture(v3, fixture)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_DOWNGRADE
    assert result.final_approval is False


def test_adamantineos_rejects_full_multi_repo_tampered_receipt_and_replay() -> None:
    fixture = load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    receipt["signature_bundle"]["signatures"][0]["signature"] = "0" * 64
    assert verify_fixture(receipt, fixture).state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID

    receipt_hash_tamper = copy.deepcopy(fixture["receipt"])
    receipt_hash_tamper["receipt_hash"] = "0" * 64
    assert verify_fixture(receipt_hash_tamper, fixture).state == ShieldV4ReceiptVerificationState.REJECTED_TAMPERED_RECEIPT

    signed_payload_hash_tamper = copy.deepcopy(fixture["receipt"])
    signed_payload_hash_tamper["signed_payload_hash"] = "0" * 64
    assert verify_fixture(signed_payload_hash_tamper, fixture).state == ShieldV4ReceiptVerificationState.REJECTED_TAMPERED_RECEIPT

    replay = verify_fixture(fixture["receipt"], fixture, seen_request_ids={fixture["expected_request_id"]})
    assert replay.state == ShieldV4ReceiptVerificationState.REJECTED_REPLAY_RISK
