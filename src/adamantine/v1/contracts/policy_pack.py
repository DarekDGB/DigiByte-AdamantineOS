from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True, slots=True)
class PolicyPack:
    """
    Deterministic policy pack for evidence evaluation.

    SECURITY INVARIANTS:
    - Pure data: no environment reads, no time access, no IO.
    - Used to tune gates WITHOUT changing code (future mobile can ship packs).
    - Validation must be strict and fail-closed.

    v1 fields:
    - min_overall_score: minimum risk report score required to allow
    - allowed_external_reason_ids: allowlist for external reason IDs from oracles/adapters
    """
    min_overall_score: int = 85
    allowed_external_reason_ids: Tuple[str, ...] = ("ok",)

    def validate(self) -> None:
        if not isinstance(self.min_overall_score, int):
            raise ValueError("min_overall_score must be int")
        if not (0 <= self.min_overall_score <= 100):
            raise ValueError("min_overall_score must be in range 0..100")

        if not isinstance(self.allowed_external_reason_ids, tuple):
            raise ValueError("allowed_external_reason_ids must be tuple")

        if len(self.allowed_external_reason_ids) == 0:
            raise ValueError("allowed_external_reason_ids must not be empty")

        # Strict: entries must be non-empty str, unique
        seen: set[str] = set()
        for rid in self.allowed_external_reason_ids:
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError("allowed_external_reason_ids entries must be non-empty str")
            if rid in seen:
                raise ValueError("allowed_external_reason_ids must be unique")
            seen.add(rid)
