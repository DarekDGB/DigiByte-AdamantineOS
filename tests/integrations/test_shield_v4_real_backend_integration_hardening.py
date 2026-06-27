from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import (
    ShieldV4ReceiptVerificationState,
    verify_shield_v4_orchestrator_receipt,
)
from adamantine.v1.integrations.shield_v4_real_crypto_backend import (
    encode_binary_signature_material,
    make_real_crypto_signature_verifier,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "adamantine"
    / "v1"
    / "fixtures"
    / "shield_v4"
    / "full_multi_repo_v4_real_backend_allow_flow.json"
)


class FixtureRealVerifierBackend:
    """Deterministic real-backend verifier double for V4.8G fixture evidence.

    This backend uses explicit b64u binary material and non-TEST key identifiers.
    It exists only to prove AdamantineOS real-backend verifier wiring without
    vendoring liboqs or introducing production secrets.
    """

    backend_name = "shield-v4.8g-fixture-real-verifier"
    backend_version = "contract-test-double;no-production-secrets"
    supported_algorithms = ("classical-ed25519", "ml-dsa")

    def _signature_for_public(self, *, algorithm: str, public_key: str, message: bytes) -> str:
        raw = hashlib.sha256(
            b"shield-v4.8g-real-backend|"
            + algorithm.encode("utf-8")
            + b"|"
            + public_key.encode("utf-8")
            + b"|"
            + message
        ).digest()
        return encode_binary_signature_material(raw, field="signature")

    def verify_signature(self, *, algorithm: str, public_key: str, message: bytes, signature: str) -> bool:
        return signature == self._signature_for_public(algorithm=algorithm, public_key=public_key, message=message)


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def real_verifier():
    return make_real_crypto_signature_verifier(FixtureRealVerifierBackend())


def verify_fixture(receipt: dict[str, Any] | None = None):
    fixture = load_fixture()
    return verify_shield_v4_orchestrator_receipt(
        fixture["receipt"] if receipt is None else receipt,
        expected_context_hash=fixture["expected_context_hash"],
        expected_request_id=fixture["expected_request_id"],
        trusted_key_registry=fixture["trusted_key_registry"],
        verification_time=fixture["verification_time"],
        minimum_key_registry_version=2,
        signature_verifier=real_verifier(),
    )


def test_v48g_adamantineos_verifies_real_backend_fixture_as_evidence_only() -> None:
    fixture = load_fixture()
    result = verify_fixture()

    assert fixture["author_attribution"] == "DarekDGB"
    assert fixture["schema_version"] == "shield.v4.8g.real_backend_fixture.v1"
    assert result.state == ShieldV4ReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.request_id == fixture["expected_request_id"]
    assert result.context_hash == fixture["expected_context_hash"]
    assert result.verification_summary is not None
    assert result.verification_summary["orchestrator"]["verified_algorithms"] == ["classical-ed25519", "ml-dsa"]
    assert [item["component_id"] for item in result.verification_summary["components"]] == [
        "adn",
        "dqsn",
        "guardian_wallet",
        "qwg",
        "sentinel_ai",
    ]


def test_v48g_adamantineos_real_fixture_uses_b64u_and_no_test_only_material() -> None:
    fixture = load_fixture()
    registry_entries = fixture["trusted_key_registry"]["entries"]
    all_signatures = list(fixture["receipt"]["signature_bundle"]["signatures"])
    for component in fixture["receipt"]["component_verdicts"]:
        all_signatures.extend(component["signature_bundle"]["signatures"])
        assert component["metadata"]["real_backend_contract"] == "b64u-signature-material"

    assert len(registry_entries) == 12
    for entry in registry_entries:
        assert not entry["key_id"].startswith("test-")
        assert "test-only" not in entry["public_key"].lower()
        assert entry["public_key"].startswith("b64u:")
    for signature in all_signatures:
        assert signature["signature"].startswith("b64u:")
        assert not signature["key_id"].startswith("test-")


def test_v48g_r4_adamantineos_rejects_unconfigured_signature_backend_for_real_fixture() -> None:
    fixture = load_fixture()
    result = verify_shield_v4_orchestrator_receipt(
        fixture["receipt"],
        expected_context_hash=fixture["expected_context_hash"],
        expected_request_id=fixture["expected_request_id"],
        trusted_key_registry=fixture["trusted_key_registry"],
        verification_time=fixture["verification_time"],
        minimum_key_registry_version=2,
    )

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("SIGNATURE_BACKEND_NOT_CONFIGURED",)
    assert result.final_approval is False


def test_v48g_adamantineos_rejects_missing_mldsa_and_tampered_real_signature() -> None:
    fixture = load_fixture()
    missing_mldsa = copy.deepcopy(fixture["receipt"])
    missing_mldsa["component_verdicts"][0]["signature_bundle"]["signatures"] = [
        sig
        for sig in missing_mldsa["component_verdicts"][0]["signature_bundle"]["signatures"]
        if sig["algorithm"] == "classical-ed25519"
    ]
    missing_result = verify_fixture(missing_mldsa)
    assert missing_result.verified is False
    assert missing_result.final_approval is False
    assert missing_result.state in {
        ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT,
        ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_POLICY,
    }

    tampered = copy.deepcopy(fixture["receipt"])
    tampered["signature_bundle"]["signatures"][1]["signature"] = encode_binary_signature_material(
        b"tampered-real-backend-signature",
        field="signature",
    )
    tampered_result = verify_fixture(tampered)
    assert tampered_result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert tampered_result.dominant_reason_ids == ("signature verification failed",)


def test_v48g_adamantineos_real_backend_rejects_truthy_non_bool_verify_result() -> None:
    class NonBoolBackend(FixtureRealVerifierBackend):
        def verify_signature(self, *, algorithm: str, public_key: str, message: bytes, signature: str) -> object:
            return 1

    fixture = load_fixture()
    result = verify_shield_v4_orchestrator_receipt(
        fixture["receipt"],
        expected_context_hash=fixture["expected_context_hash"],
        expected_request_id=fixture["expected_request_id"],
        trusted_key_registry=fixture["trusted_key_registry"],
        verification_time=fixture["verification_time"],
        minimum_key_registry_version=2,
        signature_verifier=make_real_crypto_signature_verifier(NonBoolBackend()),
    )

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("signature verifier failed closed",)
    assert result.final_approval is False
