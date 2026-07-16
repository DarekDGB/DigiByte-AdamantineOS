from __future__ import annotations

from typing import Any, Protocol

from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.execution.executor import Executor
from adamantine.v1.policy.risk_policy import RiskPolicy


class RuntimeClock(Protocol):
    """
    Runtime-supplied clock.

    Hard rule: Adamantine must never call time() internally.
    Runtime provides deterministic `now` explicitly (e.g. unix seconds).
    """

    def now(self) -> int:  # pragma: no cover
        ...


class RuntimeNonceStoreProvider(Protocol):
    """
    Runtime supplies the nonce store implementation.

    Nonce lifecycle is a runtime responsibility (persistence, atomic consume, etc).
    Adamantine only consumes via injected store interface.
    """

    def nonce_store(self) -> NonceStore:  # pragma: no cover
        ...


class RuntimeExecutorProvider(Protocol):
    """
    Runtime supplies the executor implementation.

    Executor is the ONLY component allowed to perform wallet actions.
    (Sign/broadcast/state updates live outside Adamantine.)
    """

    def executor(self) -> Executor:  # pragma: no cover
        ...


class RuntimePolicyProvider(Protocol):
    """
    Optional runtime-supplied policy configuration.

    If omitted, Adamantine may use safe defaults (deny-by-default still holds).
    """

    def policy(self) -> RiskPolicy:  # pragma: no cover
        ...


class RuntimeServices(
    RuntimeClock,
    RuntimeNonceStoreProvider,
    RuntimeExecutorProvider,
    Protocol,
):
    """
    Combined runtime service surface required to embed Adamantine safely.

    Notes:
    - NO UI
    - NO keys
    - NO network
    - NO storage inside Adamantine
    - runtime owns side-effects; Adamantine remains pure policy evaluation
    """

    # Protocol composition only
    pass


class AdamantineRuntimeAdapter(Protocol):
    """
    Runtime <-> Adamantine adapter (interface only).

    Purpose:
    - Provide a single embedding surface for wallet runtimes
    - Keep Adamantine pure + deterministic
    - Prevent accidental coupling to wallet execution concerns

    This protocol intentionally does NOT define any wallet operations.
    It only defines policy evaluation entrypoints.

    Implementations MUST:
    - validate inputs deny-by-default
    - supply explicit `now`
    - prefer RuntimeHostV2/orchestrator_v2 for live execution
    - never route live execution around the final policy engine
    - never raise (return execution_response_v1 fail-closed instead)
    """

    def evaluate_mobile_execution_call_v1(self, *, payload: Any) -> dict[str, Any]:  # pragma: no cover
        """
        Evaluate legacy `mobile_execution_call_v1` envelope and return `execution_response_v1`.

        - `payload` is untrusted input from runtime/mobile boundary.
        - Output must be deterministic for identical inputs (incl. injected now).
        """
        ...
