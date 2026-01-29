from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPolicy:
    """
    Deterministic risk policy config.

    This is intentionally small at first:
    - no environment reads
    - no runtime mutation
    - pure value object

    It will be injected into EQC later (Step 5) to avoid hard-coded thresholds.
    """

    min_overall_score: int = 85

    def validate(self) -> None:
        if not isinstance(self.min_overall_score, int):
            raise ValueError("min_overall_score must be int")
        if not (0 <= self.min_overall_score <= 100):
            raise ValueError("min_overall_score must be in range 0..100")
