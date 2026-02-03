from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.reason_ids import ReasonId


@dataclass
class EnvelopeError(ValueError):
    """
    Fail-closed execution envelope error with explicit ReasonId.

    NOTE: Must NOT be frozen. pytest/contextlib may set __traceback__ on the
    exception instance during propagation.
    """

    reason_id: ReasonId
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.reason_id.value}: {self.message}"
