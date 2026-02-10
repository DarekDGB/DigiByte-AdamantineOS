from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v2 import parse_execution_request_envelope_v2
from adamantine.v1.execution.errors import EnvelopeError

NOW = 1770148800  # 2026-02-03T20:00:00Z


def _base() -> dict:
    return {
        "v": "execution_request_v2",
        "request_id": "req_1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "com.example.wallet",
            "session_id": "s1",
            "action": "send",
            "fields": {"asset": "DGB", "amount": "1"},
        },
        "authority": {"class": "user", "scope": {"policy_pack": "default"}},
        "timebox": {"issued_at": "2026-02-03T20:00:00Z", "expires_at": "2026-02-03T20:01:00Z"},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": {"v": "qid_session_v1", "dummy": True},
                "oracle": {"v": "adaptive_core_oracle_v3", "dummy": True},
                "shield": {"v": "shield_bundle_v3", "dummy": True},
            },
            "body": {"ui_confirmed": True},
        },
        "audit": {"platform": "ios", "client_version": "1.0.0"},
    }


def test_parse_ok_happy_path() -> None:
    env = _base()
    parsed = parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert parsed.request_id == "req_1"
    assert parsed.intent == "authorize"
    assert parsed.context.wallet_id == "w1"
    assert parsed.context.action == "send"
    assert isinstance(parsed.context.context_hash, str) and len(parsed.context.context_hash) == 64
    assert "v" in parsed.evidence_qid
    assert "v" in parsed.evidence_oracle
    assert "v" in parsed.evidence_shield
    assert parsed.body["ui_confirmed"] is True


def test_determinism_replay_same_input_same_context_hash() -> None:
    env = _base()
    p1 = parse_execution_request_envelope_v2(payload=env, now=NOW)
    p2 = parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert p1.context.context_hash == p2.context.context_hash


def test_reject_unknown_top_level_field() -> None:
    env = _base()
    env["surprise"] = 1
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_UNKNOWN_FIELD


def test_reject_version_mismatch() -> None:
    env = _base()
    env["v"] = "nope"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_VERSION_MISMATCH


def test_reject_payload_unknown_field() -> None:
    env = _base()
    env["payload"]["x"] = 1
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_UNKNOWN_FIELD


def test_reject_missing_evidence() -> None:
    env = _base()
    env["payload"].pop("evidence")
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_evidence_unknown_field() -> None:
    env = _base()
    env["payload"]["evidence"]["extra"] = {}
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_UNKNOWN_FIELD


def test_reject_missing_one_evidence_member() -> None:
    env = _base()
    env["payload"]["evidence"].pop("oracle")
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_empty_evidence_object() -> None:
    env = _base()
    env["payload"]["evidence"]["qid"] = {}
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_PAYLOAD_INVALID


def test_reject_timebox_expired() -> None:
    env = _base()
    now = NOW + 9999
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_EXPIRED


def test_reject_timebox_not_yet_valid() -> None:
    env = _base()
    now = NOW - 9999
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_NOT_YET_VALID


def test_reject_nonce_mode_not_single_use() -> None:
    env = _base()
    env["nonce"]["mode"] = "multi_use"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_NONCE_INVALID


def test_reject_context_fields_non_string_value() -> None:
    env = _base()
    env["context"]["fields"]["amount"] = 123  # must be str
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_audit_unknown_field() -> None:
    env = _base()
    env["audit"]["x"] = "nope"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id is ReasonId.DENY_UNKNOWN_FIELD
