from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


def run_mobile_execution_call_v2(
    *,
    payload: Any,
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
    qid_verifier: Callable[[Mapping[str, Any]], None] | None = None,
    policy: RiskPolicy | None = None,
) -> dict[str, Any]:
    """
    Reference Runtime Host entrypoint (MobileExecutionCall v2).

    This is intentionally a THIN wrapper:
    - runtime provides payload + now (explicit injection)
    - host injects executor + nonce_store (+ optional policy + required qid_verifier for Q-ID v2 evidence)
    - orchestrator_v2 is the single decision authority
    - host MUST NOT mutate decision, reason_id, context_hash, or protection_mode

    Security note:
    - qid_verifier may be None only so the orchestrator can return a
      deterministic fail-closed response. Any call carrying Q-ID v2
      evidence must inject a real verifier supplied by the integrator.
    """
    if type(now) is not int:
        raise TypeError("now must be int (unix seconds)")

    return orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=executor,
        nonce_store=nonce_store,
        qid_verifier=qid_verifier,
        policy=policy,
    )


@dataclass(slots=True)
class RuntimeHostV2:
    """
    Reference host object integrators can copy.

    Stores injected dependencies and exposes a single deterministic entrypoint.
    """
    executor: Executor
    nonce_store: NonceStore
    policy: RiskPolicy | None = None
    # None is a deterministic fail-closed configuration for Q-ID v2 evidence.
    qid_verifier: Callable[[Mapping[str, Any]], None] | None = None

    def handle(self, *, payload: Any, now: int) -> dict[str, Any]:
        return run_mobile_execution_call_v2(
            payload=payload,
            now=now,
            executor=self.executor,
            nonce_store=self.nonce_store,
            qid_verifier=self.qid_verifier,
            policy=self.policy,
        )
