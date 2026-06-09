from __future__ import annotations

from dataclasses import replace

from adamantine.v1.contracts.authority import WSQKAuthorityV2
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.wsqk_v2_policy_evidence import (
    WSQKV2PolicyEvidenceState,
    normalize_wsqk_v2_policy_evidence,
)
from adamantine.v1.wsqk.issuer_v2 import WSQK_AUTHORITY_V2, WSQKIssueRequestV2, issue_wsqk_authority_v2

WALLET = "wallet-darek"
ACTION = "sign_transaction"
CTX = "a" * 64
NOW = 1_760_000_000
NONCE = "nonce-wsqk-v2-001"


def _request(**overrides: object) -> WSQKIssueRequestV2:
    data: dict[str, object] = {
        "wallet_id": WALLET,
        "action": ACTION,
        "context_hash": CTX,
        "now": NOW,
        "ttl_seconds": 300,
        "nonce": NONCE,
        "required_evidence_families": ("pqc_signature", "classical_signature"),
        "quantum_posture": "hybrid_required",
    }
    data.update(overrides)
    return WSQKIssueRequestV2(**data)  # type: ignore[arg-type]


def _run(value: object, **overrides: str):
    expected = {
        "expected_wallet_id": WALLET,
        "expected_action": ACTION,
        "expected_context_hash": CTX,
    }
    expected.update(overrides)
    return normalize_wsqk_v2_policy_evidence(value, **expected)


def test_wsqk_issue_request_success_becomes_evidence_only() -> None:
    result = _run(_request())

    assert result.source == "wsqk_v2"
    assert result.state == WSQKV2PolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.handoff_allowed is True
    assert result.wallet_id == WALLET
    assert result.action == ACTION
    assert result.context_hash == CTX
    assert result.nonce == NONCE
    assert result.quantum_posture == "hybrid_required"
    assert result.required_evidence_families == ("classical_signature", "pqc_signature")
    assert result.proof_bindings_hash is not None
    assert result.dominant_reason_ids == (ReasonId.EVIDENCE_OK.value,)
    assert result.authority is not None
    assert result.authority.contract_version == WSQK_AUTHORITY_V2


def test_wsqk_authority_object_success_becomes_evidence_only() -> None:
    authority = issue_wsqk_authority_v2(_request())

    result = _run(authority)

    assert result.state == WSQKV2PolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.authority == authority


def test_wsqk_request_mapping_success_is_supported() -> None:
    result = _run(
        {
            "wallet_id": WALLET,
            "action": ACTION,
            "context_hash": CTX,
            "now": NOW,
            "ttl_seconds": 300,
            "nonce": NONCE,
            "required_evidence_families": ["pqc_signature", "classical_signature"],
            "quantum_posture": "hybrid_required",
        }
    )

    assert result.state == WSQKV2PolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.required_evidence_families == ("classical_signature", "pqc_signature")
    assert result.final_approval is False


def test_wsqk_authority_mapping_success_is_supported() -> None:
    authority = issue_wsqk_authority_v2(_request())

    result = _run(
        {
            "contract_version": authority.contract_version,
            "wallet_id": authority.wallet_id,
            "action": authority.action,
            "context_hash": authority.context_hash,
            "issued_at": authority.issued_at,
            "expires_at": authority.expires_at,
            "nonce": authority.nonce,
            "required_evidence_families": list(authority.required_evidence_families),
            "quantum_posture": authority.quantum_posture,
            "proof_bindings_hash": authority.proof_bindings_hash,
        }
    )

    assert result.state == WSQKV2PolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.accepted_as_evidence is True
    assert isinstance(result.authority, WSQKAuthorityV2)


def test_wsqk_missing_wallet_becomes_structured_deny_reason() -> None:
    result = _run(_request(wallet_id=""))

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED
    assert result.outcome == "DENY"
    assert result.reason_id == ReasonId.WSQK_MISSING_WALLET_ID.value
    assert result.dominant_reason_ids == (ReasonId.WSQK_MISSING_WALLET_ID.value,)
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.authority is None


def test_wsqk_unknown_evidence_family_denies_with_explicit_reason() -> None:
    result = _run(_request(required_evidence_families=("classical_signature", "unknown_family")))

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED
    assert result.reason_id == ReasonId.WSQK_V2_UNKNOWN_EVIDENCE_FAMILY.value
    assert result.handoff_allowed is False
    assert result.final_approval is False


def test_wsqk_invalid_quantum_posture_denies_with_explicit_reason() -> None:
    result = _run(_request(quantum_posture="future_magic"))

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED
    assert result.reason_id == ReasonId.WSQK_V2_INVALID_QUANTUM_POSTURE.value
    assert result.accepted_as_evidence is False


def test_wsqk_unsupported_boolean_input_fails_closed() -> None:
    result = _run(True)

    assert result.state == WSQKV2PolicyEvidenceState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id == ReasonId.DENY_WSQK
    assert result.dominant_reason_ids == (ReasonId.DENY_WSQK.value,)
    assert result.final_approval is False


def test_wsqk_malformed_authority_mapping_fails_closed() -> None:
    result = _run(
        {
            "contract_version": WSQK_AUTHORITY_V2,
            "wallet_id": WALLET,
            "action": ACTION,
            "context_hash": CTX,
            "issued_at": "not-int",
            "expires_at": NOW + 300,
            "nonce": NONCE,
            "required_evidence_families": ["classical_signature"],
            "quantum_posture": "classical_only",
            "proof_bindings_hash": "b" * 64,
        }
    )

    assert result.state == WSQKV2PolicyEvidenceState.DENY_UNSUPPORTED_INPUT
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_wsqk_wallet_mismatch_denies_before_later_gates() -> None:
    authority = issue_wsqk_authority_v2(_request())

    result = _run(authority, expected_wallet_id="other-wallet")

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WALLET_MISMATCH
    assert result.reason_id == ReasonId.TVA_AUTHORITY_WALLET_MISMATCH
    assert result.wallet_id == WALLET
    assert result.authority == authority
    assert result.final_approval is False


def test_wsqk_action_mismatch_denies() -> None:
    authority = issue_wsqk_authority_v2(_request())

    result = _run(authority, expected_action="broadcast_transaction")

    assert result.state == WSQKV2PolicyEvidenceState.DENY_ACTION_MISMATCH
    assert result.reason_id == ReasonId.TVA_AUTHORITY_ACTION_MISMATCH
    assert result.action == ACTION
    assert result.final_approval is False


def test_wsqk_context_hash_mismatch_denies() -> None:
    authority = issue_wsqk_authority_v2(_request())

    result = _run(authority, expected_context_hash="b" * 64)

    assert result.state == WSQKV2PolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH
    assert result.reason_id == ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH
    assert result.context_hash == CTX
    assert result.final_approval is False


def test_wsqk_contract_version_mismatch_denies() -> None:
    authority = replace(issue_wsqk_authority_v2(_request()), contract_version="WSQK_AUTHORITY_V3")

    result = _run(authority)

    assert result.state == WSQKV2PolicyEvidenceState.DENY_CONTRACT_VERSION_MISMATCH
    assert result.reason_id == ReasonId.DENY_WSQK
    assert result.final_approval is False


def test_wsqk_proof_hash_tampering_denies() -> None:
    authority = replace(issue_wsqk_authority_v2(_request()), proof_bindings_hash="b" * 64)

    result = _run(authority)

    assert result.state == WSQKV2PolicyEvidenceState.DENY_PROOF_BINDINGS_HASH_MISMATCH
    assert result.reason_id == ReasonId.TVA_WSQK_V2_PROOF_BINDINGS_HASH_MISMATCH
    assert result.proof_bindings_hash == "b" * 64
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_wsqk_invalid_families_inside_authority_denies_with_explicit_reason() -> None:
    authority = replace(issue_wsqk_authority_v2(_request()), required_evidence_families=("unknown_family",))

    result = _run(authority)

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED
    assert result.reason_id == ReasonId.WSQK_V2_UNKNOWN_EVIDENCE_FAMILY.value
    assert result.required_evidence_families == ("unknown_family",)
    assert result.final_approval is False


def test_wsqk_partial_mapping_without_required_shape_fails_closed() -> None:
    result = _run({"wallet_id": WALLET})

    assert result.state == WSQKV2PolicyEvidenceState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id == ReasonId.DENY_WSQK
    assert result.final_approval is False


def test_wsqk_authority_mapping_with_string_family_reaches_structured_deny() -> None:
    authority = issue_wsqk_authority_v2(_request(required_evidence_families=("classical_signature",)))

    result = _run(
        {
            "contract_version": authority.contract_version,
            "wallet_id": authority.wallet_id,
            "action": authority.action,
            "context_hash": authority.context_hash,
            "issued_at": authority.issued_at,
            "expires_at": authority.expires_at,
            "nonce": authority.nonce,
            "required_evidence_families": "classical_signature",
            "quantum_posture": authority.quantum_posture,
            "proof_bindings_hash": authority.proof_bindings_hash,
        }
    )

    assert result.state == WSQKV2PolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.required_evidence_families == ("classical_signature",)
    assert result.final_approval is False


def test_wsqk_authority_mapping_with_non_iterable_family_fails_closed() -> None:
    authority = issue_wsqk_authority_v2(_request(required_evidence_families=("classical_signature",)))

    result = _run(
        {
            "contract_version": authority.contract_version,
            "wallet_id": authority.wallet_id,
            "action": authority.action,
            "context_hash": authority.context_hash,
            "issued_at": authority.issued_at,
            "expires_at": authority.expires_at,
            "nonce": authority.nonce,
            "required_evidence_families": 7,
            "quantum_posture": authority.quantum_posture,
            "proof_bindings_hash": authority.proof_bindings_hash,
        }
    )

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED
    assert result.reason_id == ReasonId.WSQK_V2_INVALID_EVIDENCE_FAMILIES.value
    assert result.required_evidence_families == ()
    assert result.final_approval is False


def test_wsqk_request_mapping_error_becomes_structured_deny() -> None:
    result = _run(
        {
            "wallet_id": WALLET,
            "action": ACTION,
            "context_hash": CTX,
            "now": NOW,
            "ttl_seconds": 0,
            "nonce": NONCE,
            "required_evidence_families": ["classical_signature"],
            "quantum_posture": "classical_only",
        }
    )

    assert result.state == WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED
    assert result.reason_id == ReasonId.WSQK_INVALID_TTL.value
    assert result.accepted_as_evidence is False
