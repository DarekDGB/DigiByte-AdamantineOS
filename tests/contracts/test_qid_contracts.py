import pytest
from adamantine.v1.contracts.qid import QIDSessionProof


def test_valid_qid_session_passes():
    proof = QIDSessionProof(
        subject="did:example:123",
        issued_at=100,
        expires_at=200,
        proof_hash="abc123",
    )
    proof.validate(now=150)


def test_expired_session_denied():
    proof = QIDSessionProof(
        subject="did:example:123",
        issued_at=100,
        expires_at=200,
        proof_hash="abc123",
    )
    with pytest.raises(ValueError):
        proof.validate(now=250)


def test_empty_subject_denied():
    proof = QIDSessionProof(
        subject="",
        issued_at=100,
        expires_at=200,
        proof_hash="abc123",
    )
    with pytest.raises(ValueError):
        proof.validate(now=150)
