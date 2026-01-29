import pytest
from adamantine.v1.contracts.risk import RiskSignal, RiskReport


def test_valid_risk_report_passes():
    signal = RiskSignal(
        source="adaptive-core",
        severity=10,
        reason_ids=("ok",),
    )
    report = RiskReport(
        context_hash="hash123",
        signals=(signal,),
        overall_score=90,
        generated_at=100,
    )
    report.validate(now=150)


def test_invalid_score_denied():
    signal = RiskSignal(
        source="adaptive-core",
        severity=10,
        reason_ids=("ok",),
    )
    report = RiskReport(
        context_hash="hash123",
        signals=(signal,),
        overall_score=150,
        generated_at=100,
    )
    with pytest.raises(ValueError):
        report.validate(now=150)


def test_empty_reason_ids_denied():
    signal = RiskSignal(
        source="adaptive-core",
        severity=10,
        reason_ids=(),
    )
    with pytest.raises(ValueError):
        signal.validate()
