import hashlib
import json

import pytest

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash

from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.contracts.reason_ids import ReasonId


def test_parse_qid_session_accepts_valid_payload() -> None:
    now = 150
    payload = bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "abc123",
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
        "extra": "ignored",
    })
    proof = parse_qid_session(payload=payload, now=now)
    assert proof.subject == "did:example:123"




def test_parse_qid_session_shape_a_denies_proof_hash_mismatch() -> None:
    now = 150
    payload = bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "placeholder",
        "context_hash": "c" * 64,
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    })
    payload["proof_hash"] = "0" * 64

    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=now)

    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF

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
    payload = bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "abc123",
    })
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=now)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_EXPIRED


def _canon_json_bytes(obj: object) -> bytes:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return s.encode("utf-8")


def test_parse_qid_session_accepts_qid_evidence_v2() -> None:
    now = 150
    response_payload = {
        "type": "login_response",
        "service_id": "svc",
        "nonce": "n",
        "address": "DGB1-ADDRESS",
        "pubkey": "PUB",
        "require": "legacy",
        "version": "1",
        "issued_at": 100,
        "expires_at": 200,
    }
    proof_hash = hashlib.sha256(_canon_json_bytes(response_payload)).hexdigest()

    evidence = {
        "v": "2",
        "kind": "qid_login_v2",
        "login_uri": "qid://login?x=1",
        "response_payload": response_payload,
        "signature": "sig",
        "subject": "DGB1-ADDRESS",
        "proof_hash": proof_hash,
    }

    proof = parse_qid_session(payload=evidence, now=now)
    assert proof.subject == "DGB1-ADDRESS"
    assert proof.issued_at == 100
    assert proof.expires_at == 200
    assert proof.proof_hash == proof_hash


def test_parse_qid_session_denies_qid_evidence_v2_hash_mismatch() -> None:
    now = 150
    response_payload = {
        "type": "login_response",
        "service_id": "svc",
        "nonce": "n",
        "address": "DGB1-ADDRESS",
        "pubkey": "PUB",
        "require": "legacy",
        "version": "1",
        "issued_at": 100,
        "expires_at": 200,
    }

    evidence = {
        "v": "2",
        "kind": "qid_login_v2",
        "login_uri": "qid://login?x=1",
        "response_payload": response_payload,
        "signature": "sig",
        "subject": "DGB1-ADDRESS",
        "proof_hash": "00" * 32,  # wrong
    }

    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=evidence, now=now)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF
