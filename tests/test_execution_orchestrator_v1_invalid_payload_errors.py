from __future__ import annotations

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v1 import orchestrate_execution_v1


def test_orchestrator_returns_error_on_non_mapping_payload() -> None:
    now = 1706990400

    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = RiskPolicy(min_overall_score=85, policy_pack=PolicyPack())

    resp = orchestrate_execution_v1(
        payload="not-a-dict",  # type: ignore[arg-type]
        now=now,
        executor=executor,
        nonce_store=store,
        policy=policy,
    )

    assert resp["status"] == "error"
    assert isinstance(resp.get("reason_id"), str) and resp["reason_id"]
    assert executor.called is False
