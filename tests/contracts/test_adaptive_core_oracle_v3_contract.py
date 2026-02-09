from __future__ import annotations

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.risk import RiskReport, RiskSignal


def _valid_report(*, ctx: str, generated_at: int = 100) -> RiskReport:
    sig = RiskSignal(source="ac", severity=10, reason_ids=("ok",))
    return RiskReport(
        context_hash=ctx,
        signals=(sig,),
        overall_score=90,
        generated_at=generated_at,
        oracle_version="ac-v3",
        external_source_id="ac-1",
    )


def test_oracle_v3_accepts_valid_contract() -> None:
    ctx = "a" * 64
    oracle = AdaptiveCoreOracleV3(
        context_hash=ctx,
        issued_at=90,
        expires_at=200,
        report=_valid_report(ctx=ctx),
    )
    oracle.validate(now=100)  # should not raise


def test_oracle_v3_rejects_invalid_time_window() -> None:
    ctx = "a" * 64
    oracle = AdaptiveCoreOracleV3(
        context_hash=ctx,
        issued_at=200,
        expires_at=100,
        report=_valid_report(ctx=ctx),
    )
    with pytest.raises(ValueError):
        oracle.validate(now=150)


def test_oracle_v3_rejects_future_generated_report() -> None:
    ctx = "a" * 64
    oracle = AdaptiveCoreOracleV3(
        context_hash=ctx,
        issued_at=90,
        expires_at=300,
        report=_valid_report(ctx=ctx, generated_at=200),
    )
    with pytest.raises(ValueError):
        oracle.validate(now=150)
