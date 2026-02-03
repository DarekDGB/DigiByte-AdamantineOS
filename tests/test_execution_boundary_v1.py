from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.boundary import handle_execution_request_v1, run_with_tva
from adamantine.v1.execution.executor import RecordingExecutor

NOW = 1770148800  # 2026-02-03T20:00:00Z


def test_execution_never_called_when_tva_fails() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    req = ExecutionRequest(wallet_id="w1", action="SEND", payload="opaque")
    ctx = ExecutionContext(wallet_id="w1", action="SEND", context_hash="abc123")

    # Authority does NOT match context_hash -> TVA must fail
    auth = WSQKAuthority(
        wallet_id="w1",
        action="SEND",
        context_hash="wrong",
        issued_at=100,
        expires_at=200,
        nonce="n1",
    )

    with pytest.raises(TVAError) as e:
        run_with_tva(
            executor=executor,
            request=req,
            context=ctx,
            verdict=Verdict.ALLOW,
            authority=auth,
            now=150,
            nonce_store=store,
        )

    assert str(e.value) == ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value
    assert executor.called is False
    assert executor.last_request is None


def test_execution_called_only_when_tva_passes() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    req = ExecutionRequest(wallet_id="w1", action="SEND", payload="opaque")
    ctx = ExecutionContext(wallet_id="w1", action="SEND", context_hash="abc123")

    auth = WSQKAuthority(
        wallet_id="w1",
        action="SEND",
        context_hash="abc123",
        issued_at=100,
        expires_at=200,
        nonce="unique",
    )

    out = run_with_tva(
        executor=executor,
        request=req,
        context=ctx,
        verdict=Verdict.ALLOW,
        authority=auth,
        now=150,
        nonce_store=store,
    )

    assert out == "EXECUTED"
    assert executor.called is True
    assert executor.last_request == req


def _valid_envelope_request() -> dict:
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
    }


def test_envelope_boundary_denies_valid_requests_until_wired() -> None:
    resp = handle_execution_request_v1(raw=_valid_envelope_request(), now=NOW)
    assert resp["v"] == "execution_response_v1"
    assert resp["request_id"] == "req_1"
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_NOT_WIRED.value
    assert resp["decision"]["allowed"] is False


def test_envelope_boundary_denies_invalid_schema_with_reason_id() -> None:
    bad = _valid_envelope_request()
    bad["surprise"] = 1
    resp = handle_execution_request_v1(raw=bad, now=NOW)
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_UNKNOWN_FIELD.value
    assert resp["decision"]["allowed"] is False


def test_envelope_boundary_echoes_request_id_when_available_on_error() -> None:
    bad = {"v": "execution_request_v1", "request_id": "req_echo"}  # incomplete
    resp = handle_execution_request_v1(raw=bad, now=NOW)
    assert resp["request_id"] == "req_echo"
    assert resp["status"] == "deny"
