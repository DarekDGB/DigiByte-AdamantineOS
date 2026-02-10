from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v2 import parse_execution_request_envelope_v2
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.obs.metrics import InMemoryMetrics

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


def test_envelope_v2_metrics_inc_path_is_hit() -> None:
    m = InMemoryMetrics()
    with pytest.raises(EnvelopeError):
        parse_execution_request_envelope_v2(payload=_base(), now="not-int", metrics=m)  # type: ignore[arg-type]
    assert sum(m.snapshot().values()) >= 1


def test_envelope_v2_rejects_payload_not_mapping() -> None:
    m = InMemoryMetrics()
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload="nope", now=NOW, metrics=m)  # type: ignore[arg-type]
    assert e.value.reason_id == ReasonId.DENY_SCHEMA_INVALID
    assert sum(m.snapshot().values()) >= 1


def test_envelope_v2_rejects_nonempty_str_fields() -> None:
    env = _base()
    env["request_id"] = ""
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_SCHEMA_INVALID


def test_envelope_v2_rejects_timebox_empty_iso_string() -> None:
    env = _base()
    env["timebox"]["issued_at"] = ""
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_TIMEBOX_INVALID


def test_envelope_v2_rejects_timebox_invalid_iso_format() -> None:
    env = _base()
    env["timebox"]["issued_at"] = "not-iso"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_TIMEBOX_INVALID


def test_envelope_v2_rejects_timebox_missing_timezone() -> None:
    env = _base()
    env["timebox"]["issued_at"] = "2026-02-03T20:00:00"  # no Z / offset
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_TIMEBOX_INVALID


def test_envelope_v2_rejects_context_fields_key_empty() -> None:
    env = _base()
    env["context"]["fields"] = {"": "x"}
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_SCHEMA_INVALID


def test_envelope_v2_rejects_expires_at_before_or_equal_issued_at() -> None:
    env = _base()
    env["timebox"]["issued_at"] = "2026-02-03T20:00:00Z"
    env["timebox"]["expires_at"] = "2026-02-03T20:00:00Z"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_TIMEBOX_INVALID


def test_envelope_v2_rejects_negative_or_non_int_skew() -> None:
    env = _base()
    env["timebox"]["max_skew_seconds"] = "nope"
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v2(payload=env, now=NOW)
    assert e.value.reason_id == ReasonId.DENY_TIMEBOX_INVALID
