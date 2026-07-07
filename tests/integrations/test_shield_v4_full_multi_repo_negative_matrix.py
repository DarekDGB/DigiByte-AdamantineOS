from __future__ import annotations

import copy
import hashlib
import hmac
import json
from pathlib import Path

from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import (
    COMPONENT_VERDICT_DOMAIN,
    DEFAULT_STANDARD_PROFILE_BY_ALGORITHM,
    ORCHESTRATOR_RECEIPT_DOMAIN,
    receipt_hash,
    signed_payload_hash,
    unsigned_receipt_payload,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import (
    ShieldV4ReceiptVerificationState,
    _verify_test_only_signature,
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

COMPONENT_ROLES = {
    "adn": "shield_component_adn",
    "dqsn": "shield_component_dqsn",
    "guardian_wallet": "shield_component_guardian_wallet",
    "qwg": "shield_component_qwg",
    "sentinel_ai": "shield_component_sentinel_ai",
}
COMPONENT_SIGNATURE_PREFIXES = {
    "adn": "TEST-ONLY-ADN-SIGNATURE",
    "dqsn": "TEST-ONLY-DQSN-SIGNATURE",
    "guardian_wallet": "TEST-ONLY-GUARDIAN-WALLET-SIGNATURE",
    "qwg": "TEST-ONLY-QWG-SIGNATURE",
    "sentinel_ai": "TEST-ONLY-SENTINEL-AI-SIGNATURE",
}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def verify_fixture(receipt: dict, fixture: dict, **overrides):
    params = {
        "expected_context_hash": fixture["expected_context_hash"],
        "expected_request_id": fixture["expected_request_id"],
        "trusted_key_registry": fixture["trusted_key_registry"],
        "verification_time": fixture["verification_time"],
        "signature_verifier": _verify_test_only_signature,
    }
    params.update(overrides)
    return verify_shield_v4_orchestrator_receipt(receipt, **params)


def optional_component_signature(component: dict, algorithm: str = "fn-dsa") -> dict:
    component_id = str(component["component_id"])
    role = COMPONENT_ROLES[component_id]
    key_id = f"test-{role}-{algorithm}-v1"
    public_key = f"TEST-ONLY-PUBLIC-{role}-{algorithm}-v1"
    signed_hash = str(component["signed_payload_hash"])
    standard_profile = DEFAULT_STANDARD_PROFILE_BY_ALGORITHM[algorithm]
    return {
        "algorithm": algorithm,
        "standard_profile": standard_profile,
        "key_id": key_id,
        "key_version": 1,
        "signed_payload_hash": signed_hash,
        "domain_tag": COMPONENT_VERDICT_DOMAIN,
        "signature": hashlib.sha256(
            f"{COMPONENT_SIGNATURE_PREFIXES[component_id]}\n{public_key}\n{algorithm}\n{standard_profile}\n{signed_hash}".encode("utf-8")
        ).hexdigest(),
    }


def optional_orchestrator_signature(receipt: dict, algorithm: str = "fn-dsa") -> dict:
    key_id = f"test-shield_orchestrator-{algorithm}-v1"
    public_key = f"TEST-ONLY-PUBLIC-shield_orchestrator-{algorithm}-v1"
    signed_hash = str(receipt["signed_payload_hash"])
    standard_profile = DEFAULT_STANDARD_PROFILE_BY_ALGORITHM[algorithm]
    return {
        "algorithm": algorithm,
        "standard_profile": standard_profile,
        "key_id": key_id,
        "key_version": 1,
        "signed_payload_hash": signed_hash,
        "domain_tag": ORCHESTRATOR_RECEIPT_DOMAIN,
        "signature": hmac.new(
            public_key.encode("utf-8"),
            f"{ORCHESTRATOR_RECEIPT_DOMAIN}|{signed_hash}|{algorithm}|{standard_profile}|{key_id}|1".encode("utf-8"),
            "sha256",
        ).hexdigest(),
    }


def resign_orchestrator_receipt(receipt: dict) -> None:
    unsigned = unsigned_receipt_payload(receipt)
    receipt["receipt_hash"] = receipt_hash(unsigned)
    payload_hash = signed_payload_hash(domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN, payload=unsigned)
    receipt["signed_payload_hash"] = payload_hash
    signatures = []
    for algorithm in ("classical-ed25519", "ml-dsa"):
        standard_profile = DEFAULT_STANDARD_PROFILE_BY_ALGORITHM[algorithm]
        key_id = f"test-shield_orchestrator-{algorithm}-v1"
        public_key = f"TEST-ONLY-PUBLIC-shield_orchestrator-{algorithm}-v1"
        signatures.append(
            {
                "algorithm": algorithm,
                "standard_profile": standard_profile,
                "key_id": key_id,
                "key_version": 1,
                "signed_payload_hash": payload_hash,
                "domain_tag": ORCHESTRATOR_RECEIPT_DOMAIN,
                "signature": hmac.new(
                    public_key.encode("utf-8"),
                    f"{ORCHESTRATOR_RECEIPT_DOMAIN}|{payload_hash}|{algorithm}|{standard_profile}|{key_id}|1".encode("utf-8"),
                    "sha256",
                ).hexdigest(),
            }
        )
    receipt["signature_bundle"] = {
        "schema_version": "shield.signature_bundle.v1",
        "policy_version": "policy.v1",
        "signatures": signatures,
    }


def refresh_hashes_without_resigning(receipt: dict) -> None:
    unsigned = unsigned_receipt_payload(receipt)
    receipt["receipt_hash"] = receipt_hash(unsigned)
    receipt["signed_payload_hash"] = signed_payload_hash(domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN, payload=unsigned)


def test_v48b_adamantineos_rejects_required_ml_dsa_stripped_even_with_optional_fn_dsa() -> None:
    fixture = load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    receipt["signature_bundle"]["signatures"] = [
        entry for entry in receipt["signature_bundle"]["signatures"] if entry["algorithm"] == "classical-ed25519"
    ]
    receipt["signature_bundle"]["signatures"].append(optional_orchestrator_signature(receipt))

    result = verify_fixture(receipt, fixture)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.final_approval is False


def test_v48b_adamantineos_rejects_component_required_ml_dsa_stripped_even_with_optional_fn_dsa() -> None:
    fixture = load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    component = receipt["component_verdicts"][0]
    component["signature_bundle"]["signatures"] = [
        entry for entry in component["signature_bundle"]["signatures"] if entry["algorithm"] == "classical-ed25519"
    ]
    component["signature_bundle"]["signatures"].append(optional_component_signature(component))
    resign_orchestrator_receipt(receipt)

    result = verify_fixture(receipt, fixture)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.final_approval is False


def test_v48b_adamantineos_rejects_duplicate_component_algorithm_and_domain_replay() -> None:
    fixture = load_fixture()
    duplicate = copy.deepcopy(fixture["receipt"])
    duplicate["component_verdicts"][0]["signature_bundle"]["signatures"].append(
        copy.deepcopy(duplicate["component_verdicts"][0]["signature_bundle"]["signatures"][0])
    )
    resign_orchestrator_receipt(duplicate)
    assert verify_fixture(duplicate, fixture).state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT

    domain_replay = copy.deepcopy(fixture["receipt"])
    domain_replay["component_verdicts"][0]["signature_bundle"]["signatures"][0]["domain_tag"] = ORCHESTRATOR_RECEIPT_DOMAIN
    resign_orchestrator_receipt(domain_replay)
    assert verify_fixture(domain_replay, fixture).state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT


def test_v48b_adamantineos_rejects_revoked_key_out_of_window_key_and_registry_rollback() -> None:
    fixture = load_fixture()

    revoked = copy.deepcopy(fixture["trusted_key_registry"])
    revoked["entries"][0]["status"] = "revoked"
    assert verify_fixture(fixture["receipt"], fixture, trusted_key_registry=revoked).state == ShieldV4ReceiptVerificationState.REJECTED_KEY_REGISTRY

    narrow = copy.deepcopy(fixture["trusted_key_registry"])
    narrow["entries"][0]["not_before"] = "2026-06-21T00:01:00Z"
    narrow["entries"][0]["not_after"] = "2026-06-21T00:03:00Z"
    assert verify_fixture(fixture["receipt"], fixture, trusted_key_registry=narrow).state == ShieldV4ReceiptVerificationState.REJECTED_KEY_REGISTRY

    rollback = verify_fixture(fixture["receipt"], fixture, minimum_key_registry_version=2)
    assert rollback.state == ShieldV4ReceiptVerificationState.REJECTED_KEY_REGISTRY
    assert rollback.final_approval is False


def test_v48b_adamantineos_rejects_cross_receipt_signature_splice() -> None:
    fixture = load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    receipt["request_id"] = "req-v4-spliced-from-another-receipt"
    refresh_hashes_without_resigning(receipt)

    result = verify_fixture(receipt, fixture, expected_request_id="req-v4-spliced-from-another-receipt")

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_TAMPERED_RECEIPT
    assert result.final_approval is False


def test_v48b_adamantineos_rejects_canonicalization_divergence_and_authority_injection() -> None:
    fixture = load_fixture()
    null_injection = copy.deepcopy(fixture["receipt"])
    null_injection["adamantineos_handoff"]["ambiguous"] = None
    result = verify_fixture(null_injection, fixture)
    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT

    authority = copy.deepcopy(fixture["receipt"])
    authority["adamantineos_handoff"]["final_approval"] = True
    resign_orchestrator_receipt(authority)
    result = verify_fixture(authority, fixture)
    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_AUTHORITY_BYPASS
    assert result.final_approval is False
