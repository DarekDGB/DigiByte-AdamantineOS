from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.wsqk.issuer_v2 import (
    WSQK_AUTHORITY_V2,
    WSQKIssueRequestV2,
    canonical_required_evidence_families,
    compute_wsqk_v2_proof_bindings_hash,
    issue_wsqk_authority_v2,
)


def _request(**overrides: object) -> WSQKIssueRequestV2:
    values: dict[str, object] = {
        "wallet_id": "wallet-1",
        "action": "SEND",
        "context_hash": "ctx-hash",
        "now": 1_700_000_000,
        "ttl_seconds": 300,
        "nonce": "nonce-1",
        "required_evidence_families": ["qid_hybrid", "pqc_signature"],
        "quantum_posture": "hybrid_required",
    }
    values.update(overrides)
    return WSQKIssueRequestV2(**values)  # type: ignore[arg-type]


def test_wsqk_v2_issuer_creates_expected_authority() -> None:
    authority = issue_wsqk_authority_v2(_request())

    assert authority.contract_version == WSQK_AUTHORITY_V2
    assert authority.wallet_id == "wallet-1"
    assert authority.action == "SEND"
    assert authority.context_hash == "ctx-hash"
    assert authority.issued_at == 1_700_000_000
    assert authority.expires_at == 1_700_000_300
    assert authority.nonce == "nonce-1"
    assert authority.required_evidence_families == ("pqc_signature", "qid_hybrid")
    assert authority.quantum_posture == "hybrid_required"
    assert len(authority.proof_bindings_hash) == 64


def test_wsqk_v2_required_evidence_families_sorted_set_hash_stability() -> None:
    authority_a = issue_wsqk_authority_v2(
        _request(required_evidence_families=["qid_hybrid", "pqc_signature", "qid_hybrid"])
    )
    authority_b = issue_wsqk_authority_v2(
        _request(required_evidence_families=["pqc_signature", "qid_hybrid"])
    )

    assert authority_a.required_evidence_families == ("pqc_signature", "qid_hybrid")
    assert authority_a.required_evidence_families == authority_b.required_evidence_families
    assert authority_a.proof_bindings_hash == authority_b.proof_bindings_hash


def test_wsqk_v2_hash_changes_when_actual_canonical_set_changes() -> None:
    authority_a = issue_wsqk_authority_v2(
        _request(required_evidence_families=["pqc_signature", "qid_hybrid"])
    )
    authority_b = issue_wsqk_authority_v2(
        _request(required_evidence_families=["classical_signature", "pqc_signature", "qid_hybrid"])
    )

    assert authority_a.required_evidence_families != authority_b.required_evidence_families
    assert authority_a.proof_bindings_hash != authority_b.proof_bindings_hash


def test_wsqk_v2_compute_hash_uses_canonical_family_order() -> None:
    left = compute_wsqk_v2_proof_bindings_hash(
        contract_version=WSQK_AUTHORITY_V2,
        wallet_id="wallet-1",
        action="SEND",
        context_hash="ctx-hash",
        issued_at=1,
        expires_at=2,
        nonce="n",
        required_evidence_families=["qid_hybrid", "pqc_signature"],
        quantum_posture="hybrid_required",
    )
    right = compute_wsqk_v2_proof_bindings_hash(
        contract_version=WSQK_AUTHORITY_V2,
        wallet_id="wallet-1",
        action="SEND",
        context_hash="ctx-hash",
        issued_at=1,
        expires_at=2,
        nonce="n",
        required_evidence_families=["pqc_signature", "qid_hybrid", "pqc_signature"],
        quantum_posture="hybrid_required",
    )

    assert left == right


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("wallet_id", "", ReasonId.WSQK_MISSING_WALLET_ID),
        ("action", "", ReasonId.WSQK_MISSING_ACTION),
        ("context_hash", "", ReasonId.WSQK_MISSING_CONTEXT_HASH),
        ("now", object(), ReasonId.WSQK_MISSING_NOW),
        ("ttl_seconds", object(), ReasonId.WSQK_INVALID_TTL),
        ("ttl_seconds", 0, ReasonId.WSQK_INVALID_TTL),
        ("nonce", "", ReasonId.WSQK_INVALID_NONCE),
        ("quantum_posture", "revoked", ReasonId.DENY_AUTHORITY_INSUFFICIENT),
    ],
)
def test_wsqk_v2_issuer_rejects_invalid_core_fields(field: str, value: object, reason: ReasonId) -> None:
    with pytest.raises(TVAError) as exc:
        issue_wsqk_authority_v2(_request(**{field: value}))

    assert str(exc.value) == reason.value


@pytest.mark.parametrize(
    "families",
    [
        "qid_hybrid",
        None,
        [],
        ["qid_hybrid", 123],
        ["qid_hybrid", ""],
        ["qid_hybrid", "unknown_family"],
    ],
)
def test_wsqk_v2_canonical_families_reject_invalid_inputs(families: object) -> None:
    with pytest.raises(TVAError) as exc:
        canonical_required_evidence_families(families)  # type: ignore[arg-type]

    assert str(exc.value) == ReasonId.DENY_AUTHORITY_INVALID.value


def test_wsqk_v2_canonical_families_accept_tuple_and_trim_values() -> None:
    assert canonical_required_evidence_families((" qid_hybrid ", "pqc_signature")) == (
        "pqc_signature",
        "qid_hybrid",
    )
