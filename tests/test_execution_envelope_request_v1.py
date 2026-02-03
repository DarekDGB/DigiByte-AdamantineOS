from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError


def _base(now: int) -> dict:
    return {
        "v": "execution_request_v1",
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
        "payload": {"ui_confirmed": True},
        "audit": {"platform": "ios", "client_version": "0.1.0"},
    }


def test_parse_ok_happy_path() -> None:
    now = 1706990400  # 2024-02-03T20:00:00Z (fixed deterministic now)
    env = _base(now)
    parsed = parse_execution_request_envelope_v1(payload=env, now=now)
    assert parsed.request_id == "req_1"
    assert parsed.intent == "authorize"
    assert parsed.context.wallet_id == "w1"
    assert parsed.context.action == "send"
    assert isinstance(parsed.context.context_hash, str) and len(parsed.context.context_hash) == 64


def test_reject_unknown_top_level_field() -> None:
    now = 1706990400
    env = _base(now)
    env["surprise"] = 1
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_UNKNOWN_FIELD


def test_reject_version_mismatch() -> None:
    now = 1706990400
    env = _base(now)
    env["v"] = "nope"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_VERSION_MISMATCH


def test_reject_timebox_expired() -> None:
    env = _base(now=0)
    # now far after expiry
    now = 1706990400 + 9999
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_EXPIRED


def test_reject_timebox_not_yet_valid() -> None:
    env = _base(now=0)
    # now before issued_at
    now = 1706990400 - 9999
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_NOT_YET_VALID


def test_reject_nonce_mode_not_single_use() -> None:
    now = 1706990400
    env = _base(now)
    env["nonce"]["mode"] = "multi_use"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_NONCE_INVALID


def test_reject_context_fields_non_string_value() -> None:
    now = 1706990400
    env = _base(now)
    env["context"]["fields"]["amount"] = 123  # must be str in v1
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_audit_unknown_field() -> None:
    now = 1706990400
    env = _base(now)
    env["audit"]["x"] = "nope"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_UNKNOWN_FIELD
