from __future__ import annotations

from dataclasses import dataclass
from adamantine.v1.contracts.reason_ids import ReasonId


@dataclass(frozen=True)
class AdapterError(ValueError):
    """
    Fail-closed adapter error with explicit ReasonId.
    """

    reason_id: ReasonId
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.reason_id.value}: {self.message}"
