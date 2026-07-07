from __future__ import annotations

import copy
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import (
    COMPONENT_ROLES,
    DEFAULT_STANDARD_PROFILE_BY_ALGORITHM,
    ORCHESTRATOR_RECEIPT_DOMAIN,
    receipt_hash,
    signed_payload_hash,
    unsigned_receipt_payload,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import ShieldV4ReceiptVerificationState, verify_shield_v4_orchestrator_receipt
from adamantine.v1.integrations.shield_v4_real_crypto_backend import (
    build_real_crypto_signature_input,
    decode_binary_signature_material,
    encode_binary_signature_material,
    make_real_crypto_signature_verifier,
)

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "src" / "adamantine" / "v1" / "fixtures" / "shield_v4" / "full_multi_repo_v4_allow_flow.json"
ORCHESTRATOR_ROLE = "shield_orchestrator"


class IntegratedRealVerifierBackend:
    backend_name = "fixture-real-verifier-backend"
    backend_version = "v4.8g-test"
    supported_algorithms = ("classical-ed25519", "ml-dsa", "fn-dsa")

    def verify_signature(self, *, algorithm: str, public_key: str, message: bytes, signature: str) -> bool:
        public_key_bytes = decode_binary_signature_material(public_key, field="public_key")
        expected = _real_signature(public_key_bytes, algorithm=algorithm, message=message)
        return hmac.compare_digest(signature, expected)


def _real_public_key(*, role: str, algorithm: str, key_version: int) -> str:
    return encode_binary_signature_material(
        f"shield-v4.8g-real-public-key|{role}|{algorithm}|{key_version}".encode("utf-8"),
        field="public_key",
    )


def _real_signature(public_key_bytes: bytes, *, algorithm: str, message: bytes) -> str:
    digest = hashlib.sha512(b"shield-v4.8g-real-signature|" + algorithm.encode("utf-8") + b"|" + public_key_bytes + b"|" + message).digest()
    return encode_binary_signature_material(digest, field="signature")


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _realize_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    realized = copy.deepcopy(dict(registry))
    realized["entries"] = [copy.deepcopy(entry) for entry in registry["entries"]]
    for key in realized["entries"]:
        if key["key_id"].startswith("test-"):
            key["key_id"] = "prod-" + key["key_id"][len("test-") :]
        key["public_key"] = _real_public_key(role=key["role"], algorithm=key["algorithm"], key_version=key["key_version"])
    return realized


def _key_for(registry: dict[str, Any], *, role: str, algorithm: str, key_version: int) -> dict[str, Any]:
    for key in registry["entries"]:
        if (key["role"], key["algorithm"], key["key_version"]) == (role, algorithm, key_version):
            return key
    raise AssertionError(f"missing key for {role} {algorithm} v{key_version}")


def _resign_bundle_with_real_material(bundle: dict[str, Any], *, role: str, registry: dict[str, Any]) -> None:
    for entry in bundle["signatures"]:
        key = _key_for(registry, role=role, algorithm=entry["algorithm"], key_version=entry["key_version"])
        entry["key_id"] = key["key_id"]
        message = build_real_crypto_signature_input(
            algorithm=entry["algorithm"],
            standard_profile=entry["standard_profile"],
            domain_tag=entry["domain_tag"],
            signed_payload_hash=entry["signed_payload_hash"],
            key_id=entry["key_id"],
            key_version=entry["key_version"],
        )
        public_key_bytes = decode_binary_signature_material(key["public_key"], field="public_key")
        entry["signature"] = _real_signature(public_key_bytes, algorithm=entry["algorithm"], message=message)


def _realize_receipt_and_registry() -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
    fixture = _load_fixture()
    receipt = copy.deepcopy(fixture["receipt"])
    registry = _realize_registry(fixture["trusted_key_registry"])
    for component in receipt["component_verdicts"]:
        _resign_bundle_with_real_material(
            component["signature_bundle"],
            role=COMPONENT_ROLES[component["component_id"]],
            registry=registry,
        )
    unsigned_receipt = unsigned_receipt_payload(receipt)
    receipt["receipt_hash"] = receipt_hash(unsigned_receipt)
    receipt["signed_payload_hash"] = signed_payload_hash(domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN, payload=unsigned_receipt)
    for entry in receipt["signature_bundle"]["signatures"]:
        entry["signed_payload_hash"] = receipt["signed_payload_hash"]
    _resign_bundle_with_real_material(receipt["signature_bundle"], role=ORCHESTRATOR_ROLE, registry=registry)
    return receipt, registry, fixture["expected_context_hash"], fixture["expected_request_id"], fixture["verification_time"]


def test_v48g_adamantineos_verifies_real_backend_receipt_interface_contract() -> None:
    receipt, registry, expected_context_hash, expected_request_id, verification_time = _realize_receipt_and_registry()
    result = verify_shield_v4_orchestrator_receipt(
        receipt,
        expected_context_hash=expected_context_hash,
        expected_request_id=expected_request_id,
        trusted_key_registry=registry,
        verification_time=verification_time,
        signature_verifier=make_real_crypto_signature_verifier(IntegratedRealVerifierBackend()),
    )

    assert result.state == ShieldV4ReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.verification_summary is not None
    assert result.verification_summary["orchestrator"]["verified_algorithms"] == ["classical-ed25519", "ml-dsa"]
    assert [item["component_id"] for item in result.verification_summary["components"]] == ["adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai"]
    assert all(key["public_key"].startswith("b64u:") and not key["key_id"].startswith("test-") for key in registry["entries"])


def test_v48g_adamantineos_real_backend_e2e_rejects_receipt_signature_splice_fail_closed() -> None:
    receipt, registry, expected_context_hash, expected_request_id, verification_time = _realize_receipt_and_registry()
    receipt["signature_bundle"]["signatures"][1]["signature"] = receipt["component_verdicts"][0]["signature_bundle"]["signatures"][1]["signature"]
    result = verify_shield_v4_orchestrator_receipt(
        receipt,
        expected_context_hash=expected_context_hash,
        expected_request_id=expected_request_id,
        trusted_key_registry=registry,
        verification_time=verification_time,
        signature_verifier=make_real_crypto_signature_verifier(IntegratedRealVerifierBackend()),
    )

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("signature verification failed",)
