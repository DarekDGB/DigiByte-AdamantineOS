from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution import orchestrator_v1 as o1
from adamantine.v1.execution import orchestrator_v2 as o2
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy


def _v1_min_payload() -> dict[str, Any]:
    # Minimal shape that still exercises orchestrator_v1 fail-closed behavior.
    # This intentionally DOES NOT include wsqk proof, and may fail earlier validation.
    return {
        "v": "execution_request_v1",
        "request_id": "req-1",
        "context": {"action": "SEND"},
        "authority": {"proofs": {}},
        "payload": {},
    }


def test_orchestrator_v1_missing_wsqk_is_fail_closed() -> None:
    # v1 can return error (not deny) when the request is invalid / missing required parts.
    resp = o1.orchestrate_execution_v1(
        payload=_v1_min_payload(),
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] in ("deny", "error")
    # If it denies, it should be the authority/WSQK family; if it errors, schema invalid is acceptable.
    assert resp["reason_id"] in (
        ReasonId.DENY_AUTHORITY_INVALID.value,
        ReasonId.DENY_SCHEMA_INVALID.value,
    )


def test_orchestrator_v1_outer_adapter_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hit orchestrator_v1 outer "except AdapterError" block (lines ~265-267)
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "boom")

    monkeypatch.setattr(o1, "parse_execution_request_envelope_v1", boom, raising=True)

    resp = o1.orchestrate_execution_v1(
        payload={"request_id": "req-x", "context": {"action": "SEND"}},
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "error"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_v2_outer_adapter_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hit orchestrator_v2 outer AdapterError catch
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "boom")

    monkeypatch.setattr(o2, "parse_execution_request_envelope_v2", boom, raising=True)

    resp = o2.orchestrate_execution_v2(
        payload={"request_id": "req-x", "intent": "authorize", "context": {"action": "send"}},
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_v2_outer_generic_exception_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hit orchestrator_v2 bottom "except Exception"
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(o2, "parse_execution_request_envelope_v2", boom, raising=True)

    resp = o2.orchestrate_execution_v2(
        payload={"request_id": "req-x", "intent": "authorize", "context": {"action": "send"}},
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "error"
    assert resp["reason_id"] == ReasonId.DENY_SCHEMA_INVALID.value
