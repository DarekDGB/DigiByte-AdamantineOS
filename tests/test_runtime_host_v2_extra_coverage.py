from __future__ import annotations

from typing import Any, Dict

import pytest

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import _default_policy
from adamantine.v2.runtime_host.host import RuntimeHostV2, run_mobile_execution_call_v2


def test_run_mobile_execution_call_v2_rejects_non_int_now() -> None:
    with pytest.raises(TypeError):
        run_mobile_execution_call_v2(  # type: ignore[arg-type]
            payload={},
            now="nope",
            executor=RecordingExecutor(),
            nonce_store=InMemoryNonceStore(),
            policy=_default_policy(),
        )


def test_run_mobile_execution_call_v2_passes_through_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    import adamantine.v2.runtime_host.host as host

    captured: Dict[str, Any] = {}

    def _fake_orchestrator_v2(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(host, "orchestrate_execution_v2", _fake_orchestrator_v2)

    payload = {"x": 1}
    ex = RecordingExecutor()
    ns = InMemoryNonceStore()
    pol = _default_policy()

    out = run_mobile_execution_call_v2(payload=payload, now=9, executor=ex, nonce_store=ns, policy=pol)
    assert out == {"status": "ok"}
    assert captured["payload"] == payload
    assert captured["now"] == 9
    assert captured["executor"] is ex
    assert captured["nonce_store"] is ns
    assert captured["policy"] is pol


def test_runtime_host_v2_handle_calls_run_mobile_execution_call_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    import adamantine.v2.runtime_host.host as host

    called: Dict[str, Any] = {}

    def _fake_run(**kwargs: Any) -> Dict[str, Any]:
        called.update(kwargs)
        return {"handled": True}

    monkeypatch.setattr(host, "run_mobile_execution_call_v2", _fake_run)

    rh = RuntimeHostV2(executor=RecordingExecutor(), nonce_store=InMemoryNonceStore(), policy=_default_policy())
    out = rh.handle(payload={"p": 1}, now=7)
    assert out == {"handled": True}
    assert called["payload"] == {"p": 1}
    assert called["now"] == 7
