from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.reason_ids import ReasonId


@dataclass(frozen=True)
class EnvelopeError(ValueError):
    """
    Fail-closed execution envelope error with explicit ReasonId.

    Used for mobile -> Adamantine request/response envelope validation.
    """

    reason_id: ReasonId
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.reason_id.value}: {self.message}"
