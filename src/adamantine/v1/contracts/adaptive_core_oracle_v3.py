from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.risk import RiskReport


@dataclass(frozen=True, slots=True)
class AdaptiveCoreOracleV3:
    """
    Internalized Adaptive Core oracle evidence (post-parse, post-mapping).

    Evidence-only:
      - never grants allow by itself
      - deterministic, context-bound, time-boxed
    """
    context_hash: str
    issued_at: int
    expires_at: int
    report: RiskReport

    def validate(self, *, now: int) -> None:
        if not isinstance(now, int):
            raise ValueError("now must be int")

        if not isinstance(self.context_hash, str) or not self.context_hash.strip():
            raise ValueError("context_hash must be non-empty str")

        if not isinstance(self.issued_at, int) or not isinstance(self.expires_at, int):
            raise ValueError("issued_at/expires_at must be int")

        if self.expires_at < self.issued_at:
            raise ValueError("expires_at must be >= issued_at")

        # Freshness enforcement is policy-driven; contract validation only enforces structure.
        if not isinstance(self.report, RiskReport):
            raise ValueError("report must be RiskReport")

        self.report.validate(now=now)
