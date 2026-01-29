from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class RiskSignal:
    """
    Minimal, typed risk signal from an external source.
    """

    source: str
    severity: int
    reason_ids: Tuple[str, ...]

    def validate(self) -> None:
        if not self.source:
            raise ValueError("source must be non-empty")

        if not isinstance(self.severity, int) or not (0 <= self.severity <= 100):
            raise ValueError("severity must be int in range 0..100")

        if not isinstance(self.reason_ids, tuple):
            raise ValueError("reason_ids must be tuple")

        if not self.reason_ids:
            raise ValueError("reason_ids must not be empty")

        for r in self.reason_ids:
            if not isinstance(r, str) or not r:
                raise ValueError("each reason_id must be non-empty str")


@dataclass(frozen=True)
class RiskReport:
    """
    Immutable risk report bound to a specific execution context.
    """

    context_hash: str
    signals: Tuple[RiskSignal, ...]
    overall_score: int
    generated_at: int
    oracle_version: str | None = None
    external_source_id: str | None = None

    def validate(self, *, now: int) -> None:
        if not isinstance(now, int):
            raise ValueError("now must be int")

        if not self.context_hash:
            raise ValueError("context_hash must be non-empty")

        if not isinstance(self.overall_score, int) or not (0 <= self.overall_score <= 100):
            raise ValueError("overall_score must be int in range 0..100")

        if not isinstance(self.generated_at, int) or self.generated_at <= 0:
            raise ValueError("generated_at must be positive int")

        if self.generated_at > now:
            raise ValueError("generated_at cannot be in the future")

        if not isinstance(self.signals, tuple):
            raise ValueError("signals must be tuple")

        for signal in self.signals:
            if not isinstance(signal, RiskSignal):
                raise ValueError("signals must contain RiskSignal instances")
            signal.validate()
