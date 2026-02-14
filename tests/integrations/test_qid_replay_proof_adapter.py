import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_replay_proof


def _evidence(replay: dict | None) -> dict:
    base = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "proofhash123",
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    }
    if replay is not None:
        base["replay_proof"] = replay
    return base


def test_parse_qid_replay_proof_accepts_valid() -> None:
    rp = {
        "proof_version": "qid-replay-v1",
        "wallet_id": "w1",
        "subject": "did:example:123",
        "proof_hash": "proofhash123",
        "device_binding": "device-1",
        "session_nonce": "n1",
        "registry_commitment": "reg-commit-1",
        "fresh": True,
    }
    out = parse_qid_replay_proof(
        evidence_qid=_evidence(rp),
        expected_wallet_id="w1",
        expected_subject="did:example:123",
        expected_proof_hash="proofhash123",
        expected_device_binding="device-1",
        expected_session_nonce="n1",
    )
    assert out.wallet_id == "w1"


def test_parse_qid_replay_proof_missing_denies() -> None:
    with pytest.raises(AdapterError) as e:
        parse_qid_replay_proof(
            evidence_qid=_evidence(None),
            expected_wallet_id="w1",
            expected_subject="did:example:123",
            expected_proof_hash="proofhash123",
            expected_device_binding="device-1",
            expected_session_nonce="n1",
        )
    assert e.value.reason_id is ReasonId.QID_REPLAY_PROOF_MISSING


def test_parse_qid_replay_proof_nonce_replay_denies() -> None:
    rp = {
        "proof_version": "qid-replay-v1",
        "wallet_id": "w1",
        "subject": "did:example:123",
        "proof_hash": "proofhash123",
        "device_binding": "device-1",
        "session_nonce": "n1",
        "registry_commitment": "reg-commit-1",
        "fresh": False,
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_replay_proof(
            evidence_qid=_evidence(rp),
            expected_wallet_id="w1",
            expected_subject="did:example:123",
            expected_proof_hash="proofhash123",
            expected_device_binding="device-1",
            expected_session_nonce="n1",
            require_fresh=True,
        )
    assert e.value.reason_id is ReasonId.QID_NONCE_REPLAY
