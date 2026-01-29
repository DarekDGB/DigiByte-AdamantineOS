import pytest

from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.contracts.reason_ids import ReasonId


def test_parse_qid_session_accepts_valid_payload() -> None:
    now = 150
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "abc123",
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
        "extra": "ignored",
    }
    proof = parse_qid_session(payload=payload, now=now)
    assert proof.subject == "did:example:123"


def test_parse_qid_session_denies_missing_version() -> None:
    now = 150
    payload = {
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "abc123",
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=now)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_parse_qid_session_denies_expired() -> None:
    now = 250
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "abc123",
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=now)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_EXPIRED
