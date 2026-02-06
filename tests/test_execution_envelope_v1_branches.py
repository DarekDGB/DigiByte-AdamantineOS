from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.obs.metrics import Metrics


class RecordingMetrics(Metrics):
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, reason_id: str) -> None:
        if not isinstance(reason_id, str) or not reason_id:
            return
        self.counts[reason_id] = self.counts.get(reason_id, 0) + 1


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
            "action": "send",
            "fields": {"asset": "DGB", "amount": "1"},
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

    m = RecordingMetrics()
    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now, metrics=m)

    assert e.value.reason_id is ReasonId.DENY_VERSION_MISMATCH
    assert m.counts.get(ReasonId.DENY_VERSION_MISMATCH.value, 0) == 1


def test_reject_timebox_not_str_fields() -> None:
    now = 1706990400
    env = _base()
    env["timebox"]["issued_at"] = 123  # type: ignore[assignment]

    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)

    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID


def test_reject_timebox_invalid_isoformat() -> None:
    now = 1706990400
    env = _base()
    env["timebox"]["issued_at"] = "not-a-date"

    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)

    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID


def test_reject_timebox_missing_timezone() -> None:
    now = 1706990400
    env = _base()
    env["timebox"]["issued_at"] = "2026-02-03T20:00:00"  # no Z / tz

    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=now)

    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID
