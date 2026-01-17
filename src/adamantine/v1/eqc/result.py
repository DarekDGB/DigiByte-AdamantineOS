from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict


@dataclass(frozen=True, slots=True)
class EQCResult:
    """
    EQC output: decision only.
    - Does not execute
    - Does not grant authority
    """
    verdict: Verdict
    reason_ids: tuple[str, ...]
    context_hash: str

    @staticmethod
    def allow(*, context_hash: str) -> "EQCResult":
        return EQCResult(verdict=Verdict.ALLOW, reason_ids=(), context_hash=context_hash)

    @staticmethod
    def deny(*, context_hash: str, reasons: tuple[ReasonId, ...]) -> "EQCResult":
        return EQCResult(
            verdict=Verdict.DENY,
            reason_ids=tuple(r.value for r in reasons),
            context_hash=context_hash,
        )
