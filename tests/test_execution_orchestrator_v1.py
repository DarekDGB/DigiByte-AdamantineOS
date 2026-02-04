from __future__ import annotations

from typing import Any

from adamantine.v1.execution.orchestrator_v1 import orchestrate_execution_v1
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore


def _minimal_payload() -> dict[str, Any]:
    return {
        "v": "execution_request_v1",
        "request_id": "req-1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "app",
            "session_id": "s1",
            "action": "SEND",
            "fields": {"amount": "1"},
        },
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "issued_at": 100,
            "expires_at": 200,
            "nonce": "n1",
            "context_hash": "x" * 64,
        },
        "timebox": {
            "issued_at": "2026-02-03T20:00:00Z",
            "expires_at": "2026-02-03T20:01:00Z",
        },
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {"ui_confirmed": True},
        "audit": {"platform": "ios"},
        "evidence": {},  # missing evidence → deny
    }


def test_orchestrator_never_raises() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    resp = orchestrate_execution_v1(
        payload=_minimal_payload(),
        now=150,
        executor=executor,
        nonce_store=store,
    )

    assert isinstance(resp, dict)
    assert resp["status"] in {"deny", "error"}


def test_executor_not_called_on_deny() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    resp = orchestrate_execution_v1(
        payload=_minimal_payload(),
        now=150,
        executor=executor,
        nonce_store=store,
    )

    assert resp["status"] != "allow"
    assert executor.called is False


def test_determinism_same_input_same_output() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    payload = _minimal_payload()

    r1 = orchestrate_execution_v1(
        payload=payload,
        now=150,
        executor=executor,
        nonce_store=store,
    )
    r2 = orchestrate_execution_v1(
        payload=payload,
        now=150,
        executor=executor,
        nonce_store=store,
    )

    assert r1 == r2


def test_error_path_returns_error_status() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    bad_payload: dict[str, Any] = {}

    resp = orchestrate_execution_v1(
        payload=bad_payload,
        now=150,
        executor=executor,
        nonce_store=store,
    )

    assert resp["status"] == "error"
    assert executor.called is False
