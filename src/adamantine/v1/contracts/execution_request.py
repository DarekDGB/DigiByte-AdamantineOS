from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """
    Execution request contract (foundation).

    This is the minimal, explicit input needed to attempt execution.
    It is NOT an execution implementation.

    payload is an opaque string at foundation stage.
    Future versions may replace this with structured types.
    """
    wallet_id: str
    action: str
    payload: str
