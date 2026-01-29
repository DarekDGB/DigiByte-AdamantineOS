from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId


def test_reason_ids_are_unique() -> None:
    values = [r.value for r in ReasonId]
    assert len(values) == len(set(values))


def test_integration_reason_ids_exist() -> None:
    # Smoke test: these must exist for later fail-closed wiring.
    assert ReasonId.EQC_MISSING_NOW.value == "EQC_MISSING_NOW"
    assert ReasonId.EQC_MISSING_QID_SESSION.value == "EQC_MISSING_QID_SESSION"
    assert ReasonId.EQC_MISSING_RISK_REPORT.value == "EQC_MISSING_RISK_REPORT"
    assert ReasonId.UNKNOWN_EXTERNAL_REASON.value == "UNKNOWN_EXTERNAL_REASON"
