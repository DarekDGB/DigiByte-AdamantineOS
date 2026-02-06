from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError

NOW = 1770148800  # 2026-02-03T20:00:00Z


def _base() -> dict:
    return {
        "v": "execution_request_v1",
        "request_id": "req_guard",
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


def test_reject_timebox_expires_at_not_greater_than_issued_at() -> None:
    env = _base()
    # Same value -> invalid (must be strictly greater)
    env["timebox"]["expires_at"] = env["timebox"]["issued_at"]

    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=NOW)

    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID


def test_reject_timebox_negative_skew_seconds() -> None:
    env = _base()
    env["timebox"]["max_skew_seconds"] = -1

    with pytest.raises(EnvelopeError) as e:
        parse_execution_request_envelope_v1(payload=env, now=NOW)

    assert e.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID
