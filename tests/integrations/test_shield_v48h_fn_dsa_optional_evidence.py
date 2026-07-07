from __future__ import annotations

import copy
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import (
    COMPONENT_ROLES,
    DEFAULT_STANDARD_PROFILE_BY_ALGORITHM,
    FN_DSA,
    ShieldV4ReceiptContractError,
    default_standard_profile_for_algorithm,
    ML_DSA,
    ORCHESTRATOR_RECEIPT_DOMAIN,
    REQUIRED_ALGORITHMS,
    receipt_hash,
    signed_payload_hash,
    unsigned_receipt_payload,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import (
    KEY_REGISTRY_SCHEMA_VERSION,
    ORCHESTRATOR_ROLE,
    ShieldV4ReceiptVerificationState,
    _VerifierRejection,
    _normalise_component_signature_result,
    _verify_bundle,
    _verify_test_only_signature,
    load_trusted_shield_v4_key_registry,
    verify_shield_v4_orchestrator_receipt,
)

FIXTURES = Path(__file__).resolve().parents[2] / "src" / "adamantine" / "v1" / "fixtures" / "shield_v4"
FN_DSA_PROFILE = "fips206-draft-falcon1024-v1"


def _load_flow_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _verify_flow(flow: dict[str, Any], receipt: dict[str, Any] | None = None):
    candidate = receipt or flow["receipt"]
    return verify_shield_v4_orchestrator_receipt(
        candidate,
        expected_context_hash=flow["expected_context_hash"],
        expected_request_id=flow["expected_request_id"],
        trusted_key_registry=flow["trusted_key_registry"],
        verification_time=flow["verification_time"],
        signature_verifier=_verify_test_only_signature,
    )


def _resign_orchestrator_receipt(receipt: dict[str, Any]) -> None:
    unsigned = unsigned_receipt_payload(receipt)
    receipt["receipt_hash"] = receipt_hash(unsigned)
    payload_hash = signed_payload_hash(domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN, payload=unsigned)
    receipt["signed_payload_hash"] = payload_hash
    signatures: list[dict[str, Any]] = []
    for existing in receipt["signature_bundle"]["signatures"]:
        algorithm = existing["algorithm"]
        standard_profile = DEFAULT_STANDARD_PROFILE_BY_ALGORITHM[algorithm]
        key_id = f"test-shield_orchestrator-{algorithm}-v1"
        key_version = 1
        public_key = f"TEST-ONLY-PUBLIC-shield_orchestrator-{algorithm}-v1"
        signatures.append(
            {
                "algorithm": algorithm,
                "standard_profile": standard_profile,
                "key_id": key_id,
                "key_version": key_version,
                "signed_payload_hash": payload_hash,
                "domain_tag": ORCHESTRATOR_RECEIPT_DOMAIN,
                "signature": hmac.new(
                    public_key.encode("utf-8"),
                    f"{ORCHESTRATOR_RECEIPT_DOMAIN}|{payload_hash}|{algorithm}|{standard_profile}|{key_id}|{key_version}".encode(
                        "utf-8"
                    ),
                    "sha256",
                ).hexdigest(),
            }
        )
    receipt["signature_bundle"] = {
        "schema_version": "shield.signature_bundle.v1",
        "policy_version": "policy.v1",
        "signatures": signatures,
    }


def _component_fn_dsa_signature(receipt: dict[str, Any], component_index: int = 0) -> dict[str, Any]:
    for entry in receipt["component_verdicts"][component_index]["signature_bundle"]["signatures"]:
        if entry["algorithm"] == FN_DSA:
            return entry
    raise AssertionError("fixture did not contain component FN-DSA signature")


def _orchestrator_signature(receipt: dict[str, Any], algorithm: str) -> dict[str, Any]:
    for entry in receipt["signature_bundle"]["signatures"]:
        if entry["algorithm"] == algorithm:
            return entry
    raise AssertionError(f"fixture did not contain {algorithm} signature")


def test_v48h_adamantineos_accepts_fn_dsa_absent_and_valid_fn_dsa_present() -> None:
    no_fn_flow = _load_flow_fixture("full_multi_repo_v4_allow_flow.json")
    no_fn_result = _verify_flow(no_fn_flow)
    assert no_fn_result.state == ShieldV4ReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert no_fn_result.reason_id == ReasonId.EVIDENCE_OK
    assert no_fn_result.final_approval is False
    assert no_fn_result.verification_summary is not None
    assert no_fn_result.verification_summary["orchestrator"]["verified_algorithms"] == list(REQUIRED_ALGORITHMS)

    fn_flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    fn_result = _verify_flow(fn_flow)
    assert fn_result.state == ShieldV4ReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert fn_result.reason_id == ReasonId.EVIDENCE_OK
    assert fn_result.verified is True
    assert fn_result.accepted_as_evidence is True
    assert fn_result.final_approval is False
    assert fn_result.verification_summary is not None
    assert fn_result.verification_summary["orchestrator"]["verified_algorithms"] == ["classical-ed25519", ML_DSA, FN_DSA]
    assert FN_DSA_PROFILE in fn_result.verification_summary["orchestrator"]["verified_standard_profiles"]
    assert all(FN_DSA in component["verified_algorithms"] for component in fn_result.verification_summary["components"])


@pytest.mark.parametrize("algorithm", ["classical-ed25519", ML_DSA])
def test_v48h_fn_dsa_cannot_rescue_required_orchestrator_signature_failure(algorithm: str) -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    _orchestrator_signature(receipt, algorithm)["signature"] = "0" * 64

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


@pytest.mark.parametrize("algorithm", ["classical-ed25519", ML_DSA])
def test_v48h_fn_dsa_cannot_rescue_required_component_signature_failure(algorithm: str) -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    for entry in receipt["component_verdicts"][0]["signature_bundle"]["signatures"]:
        if entry["algorithm"] == algorithm:
            entry["signature"] = "0" * 64
            break
    _resign_orchestrator_receipt(receipt)

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_v48h_present_invalid_fn_dsa_is_denied_even_when_required_signatures_are_valid() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    _component_fn_dsa_signature(receipt)["signature"] = "0" * 64
    _resign_orchestrator_receipt(receipt)

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_v48h_fn_dsa_wrong_key_role_is_denied() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    _component_fn_dsa_signature(receipt)["key_id"] = "test-shield_orchestrator-fn-dsa-v1"
    _resign_orchestrator_receipt(receipt)

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_KEY_REGISTRY
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("trusted key not found",)
    assert result.final_approval is False


@pytest.mark.parametrize("bad_profile", ["fips206-draft-falcon512-v1", "fips204-ml-dsa-65-v1"])
def test_v48h_unsupported_or_flipped_fn_dsa_standard_profile_is_denied(bad_profile: str) -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    _orchestrator_signature(receipt, FN_DSA)["standard_profile"] = bad_profile

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_v48h_fn_dsa_present_requires_matching_trust_registry_key() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    registry = copy.deepcopy(flow["trusted_key_registry"])
    registry["entries"] = [entry for entry in registry["entries"] if entry["algorithm"] != FN_DSA]

    result = verify_shield_v4_orchestrator_receipt(
        flow["receipt"],
        expected_context_hash=flow["expected_context_hash"],
        expected_request_id=flow["expected_request_id"],
        trusted_key_registry=registry,
        verification_time=flow["verification_time"],
        signature_verifier=_verify_test_only_signature,
    )

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_KEY_REGISTRY
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("trusted key not found",)
    assert result.final_approval is False


def test_v48h_duplicate_fn_dsa_entry_is_denied() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    receipt["signature_bundle"]["signatures"].append(copy.deepcopy(_orchestrator_signature(receipt, FN_DSA)))

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_v48h_fn_dsa_cross_receipt_or_cross_role_splice_is_denied() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    _component_fn_dsa_signature(receipt)["signature"] = _orchestrator_signature(receipt, FN_DSA)["signature"]
    _resign_orchestrator_receipt(receipt)

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_INVALID
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_v48h_component_signature_results_cannot_falsely_claim_or_hide_fn_dsa() -> None:
    no_fn_flow = _load_flow_fixture("full_multi_repo_v4_allow_flow.json")
    claimed = copy.deepcopy(no_fn_flow["receipt"])
    claimed["component_signature_results"][0]["verified_algorithms"] = ["classical-ed25519", ML_DSA, FN_DSA]
    _resign_orchestrator_receipt(claimed)
    claimed_result = _verify_flow(no_fn_flow, claimed)
    assert claimed_result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_POLICY
    assert claimed_result.dominant_reason_ids == ("component signature result mismatch",)

    fn_flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    hidden = copy.deepcopy(fn_flow["receipt"])
    hidden["component_signature_results"][0]["verified_algorithms"] = ["classical-ed25519", ML_DSA]
    _resign_orchestrator_receipt(hidden)
    hidden_result = _verify_flow(fn_flow, hidden)
    assert hidden_result.state == ShieldV4ReceiptVerificationState.REJECTED_SIGNATURE_POLICY
    assert hidden_result.dominant_reason_ids == ("component signature result mismatch",)
    assert hidden_result.final_approval is False


def test_v48h_fn_dsa_different_payload_hash_is_denied() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])
    _orchestrator_signature(receipt, FN_DSA)["signed_payload_hash"] = hashlib.sha256(b"different-receipt").hexdigest()

    result = _verify_flow(flow, receipt)

    assert result.state == ShieldV4ReceiptVerificationState.REJECTED_TAMPERED_RECEIPT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_v48h_profile_and_component_result_private_edges_are_fail_closed() -> None:
    flow = _load_flow_fixture("full_multi_repo_v4_fn_dsa_allow_flow.json")
    receipt = copy.deepcopy(flow["receipt"])

    assert default_standard_profile_for_algorithm(FN_DSA) == FN_DSA_PROFILE
    with pytest.raises(ShieldV4ReceiptContractError, match="unsupported Shield v4 signature algorithm"):
        default_standard_profile_for_algorithm("pqc-falcon")

    unsupported_component_result = copy.deepcopy(receipt)
    unsupported_component_result["component_signature_results"][0]["verified_algorithms"] = [
        "classical-ed25519",
        ML_DSA,
        "pqc-falcon",
    ]
    _resign_orchestrator_receipt(unsupported_component_result)
    unsupported_result = _verify_flow(flow, unsupported_component_result)
    assert unsupported_result.state == ShieldV4ReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert unsupported_result.final_approval is False

    registry = load_trusted_shield_v4_key_registry(flow["trusted_key_registry"])
    bad_profile_bundle = copy.deepcopy(receipt["signature_bundle"])
    for entry in bad_profile_bundle["signatures"]:
        if entry["algorithm"] == FN_DSA:
            entry["standard_profile"] = "fips206-draft-falcon512-v1"
            break
    with pytest.raises(_VerifierRejection, match="unsupported Shield v4 signature standard_profile"):
        _verify_bundle(
            bad_profile_bundle,
            expected_signed_payload_hash=receipt["signed_payload_hash"],
            expected_domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN,
            required_role=ORCHESTRATOR_ROLE,
            registry=registry,
            verification_time=flow["verification_time"],
            artifact_not_before=receipt["not_before"],
            artifact_not_after=receipt["not_after"],
            signature_verifier=_verify_test_only_signature,
        )

    with pytest.raises(_VerifierRejection, match="component signature result mismatch"):
        _normalise_component_signature_result(
            {
                "component_id": "adn",
                "component_role": COMPONENT_ROLES["adn"],
                "verified": True,
                "verified_algorithms": "classical-ed25519",
                "signature_policy": "policy.v1",
            }
        )

    assert KEY_REGISTRY_SCHEMA_VERSION == flow["trusted_key_registry"]["schema_version"]
