from __future__ import annotations

import hashlib
import json

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session


def _canon_json_bytes(obj: object) -> bytes:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return s.encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _evidence_v2(*, response_payload: dict, proof_hash: str) -> dict:
    return {
        "v": "2",
        "kind": "qid_login_v2",
        "response_payload": response_payload,
        "proof_hash": proof_hash,
    }


def test_parse_qid_session_shape_b_denies_non_object_response_payload() -> None:
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload={"v": "2", "kind": "qid_login_v2", "response_payload": "nope"}, now=10)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_parse_qid_session_shape_b_denies_missing_address() -> None:
    rp = {"issued_at": 1, "expires_at": 999}
    proof_hash = _sha256_hex(_canon_json_bytes(dict(rp)))
    ev = _evidence_v2(response_payload=rp, proof_hash=proof_hash)
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=10)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_parse_qid_session_shape_b_denies_non_int_timestamps() -> None:
    rp = {"address": "addr1", "issued_at": "1", "expires_at": 999}
    proof_hash = _sha256_hex(_canon_json_bytes(dict(rp)))
    ev = _evidence_v2(response_payload=rp, proof_hash=proof_hash)
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=10)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_parse_qid_session_shape_b_denies_not_yet_valid() -> None:
    rp = {"address": "addr1", "issued_at": 50, "expires_at": 999}
    proof_hash = _sha256_hex(_canon_json_bytes(dict(rp)))
    ev = _evidence_v2(response_payload=rp, proof_hash=proof_hash)
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=10)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_NOT_YET_VALID


def test_parse_qid_session_shape_b_denies_expired() -> None:
    rp = {"address": "addr1", "issued_at": 1, "expires_at": 5}
    proof_hash = _sha256_hex(_canon_json_bytes(dict(rp)))
    ev = _evidence_v2(response_payload=rp, proof_hash=proof_hash)
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=10)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_EXPIRED


def test_parse_qid_session_shape_b_denies_missing_proof_hash() -> None:
    rp = {"address": "addr1", "issued_at": 1, "expires_at": 999}
    ev = {"v": "2", "kind": "qid_login_v2", "response_payload": rp, "proof_hash": ""}
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=10)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_parse_qid_session_shape_b_denies_proof_hash_mismatch() -> None:
    rp = {"address": "addr1", "issued_at": 1, "expires_at": 999}
    ev = _evidence_v2(response_payload=rp, proof_hash="0" * 64)
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=10)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_parse_qid_session_shape_b_contract_validation_failure_path_is_fail_closed() -> None:
    # issued_at/expires_at are ints and time-window check passes, but contract requires positive timestamps.
    rp = {"address": "addr1", "issued_at": 0, "expires_at": 10}
    proof_hash = _sha256_hex(_canon_json_bytes(dict(rp)))
    ev = _evidence_v2(response_payload=rp, proof_hash=proof_hash)

    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=ev, now=5)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF
