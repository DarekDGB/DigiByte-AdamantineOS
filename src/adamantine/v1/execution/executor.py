from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.execution_request import ExecutionRequest


class Executor:
    """
    Execution boundary interface.

    Implementations perform real actions (sign, broadcast, etc).
    Foundation stage: interface only.

    Security invariant: any concrete Executor is outside this repository and
    must be independently reviewed. It must execute only after AdamantineOS
    returns a final allow decision and must never reinterpret external evidence
    as signing/broadcast authority.
    """

    def execute(self, req: ExecutionRequest) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class RecordingExecutor(Executor):
    """
    Test helper executor that records calls.

    This allows us to prove in tests that execution is never reached
    when TVA fails.
    """
    called: bool = False
    last_request: ExecutionRequest | None = None

    def execute(self, req: ExecutionRequest) -> str:
        self.called = True
        self.last_request = req
        return "EXECUTED"
