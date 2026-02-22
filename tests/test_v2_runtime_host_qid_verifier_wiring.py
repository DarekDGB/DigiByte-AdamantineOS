from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import Executor
from adamantine.v2.runtime_host import host as host_mod


class _NoopExecutor(Executor):
    def execute(self, *, request, context, now: int) -> dict:  # type: ignore[override]
        return {"ok": True}


def test_run_mobile_execution_call_v2_passes_qid_verifier(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def _fake_orchestrator(*, payload: Any, now: int, executor: Executor, nonce_store, qid_verifier=None, policy=None):  # type: ignore[no-untyped-def]
        seen["qid_verifier"] = qid_verifier
        return {"status": "deny", "reason_id": "X"}

    monkeypatch.setattr(host_mod, "orchestrate_execution_v2", _fake_orchestrator)

    def _verifier(evidence_qid: Mapping[str, Any]) -> None:
        return None

    out = host_mod.run_mobile_execution_call_v2(
        payload={"v": "execution_request_v2"},
        now=123,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        qid_verifier=_verifier,
    )
    assert out["status"] == "deny"
    assert seen["qid_verifier"] is _verifier


def test_runtime_host_v2_handle_passes_qid_verifier(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def _fake_orchestrator(*, payload: Any, now: int, executor: Executor, nonce_store, qid_verifier=None, policy=None):  # type: ignore[no-untyped-def]
        seen["qid_verifier"] = qid_verifier
        return {"status": "deny", "reason_id": "X"}

    monkeypatch.setattr(host_mod, "orchestrate_execution_v2", _fake_orchestrator)

    def _verifier(evidence_qid: Mapping[str, Any]) -> None:
        return None

    h = host_mod.RuntimeHostV2(
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=None,
        qid_verifier=_verifier,
    )
    out = h.handle(payload={"v": "execution_request_v2"}, now=123)
    assert out["status"] == "deny"
    assert seen["qid_verifier"] is _verifier
