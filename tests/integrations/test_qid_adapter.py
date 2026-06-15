from typing import Any

import pytest

from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import (
    compute_qid_shape_a_proof_hash,
    compute_qid_v2_response_payload_proof_hash,
    parse_qid_session,
)
from adamantine.v1.contracts.reason_ids import ReasonId


def bind_shape_a_proof_hash(payload: dict[str, Any]) -> dict[str, Any]:
    bound = dict(payload)
    bound["proof_hash"] = compute_qid_shape_a_proof_hash(
        qid_iface_version=bound["qid_iface_version"],
        subject=bound["subject"],
        issued_at=bound["issued_at"],
        expires_at=bound["expires_at"],
        context_hash=bound.get("context_hash"),
        device_binding=bound.get("device_binding"),
        issuer_version=bound.get("issuer_version"),
    )
    replay_proof = bound.get("replay_proof")
    if isinstance(replay_proof, dict):
        bound["replay_proof"] = {**replay_proof, "proof_hash": bound["proof_hash"]}
    return bound


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
        "context_hash": "c" * 64,
    }
    proof_hash = compute_qid_v2_response_payload_proof_hash(response_payload)

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
    assert proof.context_hash == "c" * 64


def test_parse_qid_session_denies_qid_evidence_v2_missing_context_hash() -> None:
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
    proof_hash = compute_qid_v2_response_payload_proof_hash(response_payload)

    evidence = {
        "v": "2",
        "kind": "qid_login_v2",
        "login_uri": "qid://login?x=1",
        "response_payload": response_payload,
        "signature": "sig",
        "subject": "DGB1-ADDRESS",
        "proof_hash": proof_hash,
    }

    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=evidence, now=now)

    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


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
        "context_hash": "c" * 64,
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
