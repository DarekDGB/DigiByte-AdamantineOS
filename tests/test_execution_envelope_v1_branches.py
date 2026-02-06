from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.obs.metrics import Metrics


def _base() -> dict:
    return {
        "v": "execution_request_v1",
        "request_id": "req_1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "com.example.wallet",
            "session_id": "s1",
            "action": "SEND",
            "fields": {"amount": "1", "to": "DGB1"},
        },
        "authority": {"class": "user", "scope": {"policy_pack": "default"}},
        "timebox": {"issued_at": "2026-02-03T20:00:00Z", "expires_at": "2026-02-03T20:01:00Z"},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {"ui_confirmed": True},
        "audit": {"platform": "ios", "client_version": "0.1.0"},
    }


def test_metrics_increment_on_fail_path() -> None:
    now = 1706990400
    env = _base()
    env["v"] = "nope"

    m = Metrics()
    with pytest.raises(EnvelopeError):
        parse_execution_request_envelope_v1(payload=env, now=now, metrics=m)

    snap = m.snapshot()
    assert snap.get(ReasonId.DENY_VERSION_MISMATCH.value, 0) >= 1


def test_reject_payload_not_mapping() -> None:
    now = 1706990400
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=["nope"], now=now)  # type: ignore[arg-type]
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_nonempty_str_required() -> None:
    now = 1706990400
    env = _base()
    env["request_id"] = ""
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_timebox_not_str_fields() -> None:
    now = 1706990400
    env = _base()
    env["timebox"]["issued_at"] = 123  # type: ignore[assignment]
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_timebox_invalid_isoformat() -> None:
    now = 1706990400
    env = _base()
    env["timebox"]["issued_at"] = "not-a-date"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_timebox_missing_timezone() -> None:
    now = 1706990400
    env = _base()
    env["timebox"]["issued_at"] = "2026-02-03T20:00:00"  # no Z / tz
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_now_not_int() -> None:
    env = _base()
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now="1706990400")  # type: ignore[arg-type]
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_reject_context_fields_bad_key() -> None:
    now = 1706990400
    env = _base()
    env["context"]["fields"][""] = "x"  # empty key -> invalid
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)
    assert e.value.reason_id is ReasonId.DENY_SCHEMA_INVALID
