from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import (
    ExternalReasonMap,
    ExternalReasonMapEntry,
    ShieldSignal,
    ShieldSource,
)


def test_shield_signal_validates_internal_reason_ids() -> None:
    sig = ShieldSignal(
        source=ShieldSource.SENTINEL,
        severity=10,
        reason_ids=(ReasonId.EQC_INVALID_QID_PROOF.value,),
    )
    sig.validate()


def test_shield_signal_rejects_unknown_reason_id() -> None:
    sig = ShieldSignal(source=ShieldSource.DQSN, severity=10, reason_ids=("NOT_A_REASON",))
    with pytest.raises(ValueError):
        sig.validate()


def test_shield_signal_rejects_severity_out_of_range() -> None:
    sig = ShieldSignal(
        source=ShieldSource.ADN,
        severity=101,
        reason_ids=(ReasonId.EQC_INVALID_RISK_REPORT.value,),
    )
    with pytest.raises(ValueError):
        sig.validate()


def test_external_reason_map_entry_validates_internal_reason_id() -> None:
    e = ExternalReasonMapEntry(external_id="EXT_OK", internal_reason_id=ReasonId.EQC_INVALID_RISK_REPORT.value)
    e.validate()


def test_external_reason_map_entry_rejects_invalid_internal_reason_id() -> None:
    e = ExternalReasonMapEntry(external_id="EXT_BAD", internal_reason_id="NOPE")
    with pytest.raises(ValueError):
        e.validate()


def test_external_reason_map_requires_unique_external_ids() -> None:
    m = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="A", internal_reason_id=ReasonId.EQC_INVALID_RISK_REPORT.value),
            ExternalReasonMapEntry(external_id="A", internal_reason_id=ReasonId.EQC_INVALID_QID_PROOF.value),
        )
    )
    with pytest.raises(ValueError):
        m.validate()


def test_external_reason_map_lookup_is_deterministic() -> None:
    m = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="A", internal_reason_id=ReasonId.EQC_INVALID_RISK_REPORT.value),
            ExternalReasonMapEntry(external_id="B", internal_reason_id=ReasonId.EQC_INVALID_QID_PROOF.value),
        )
    )
    m.validate()
    assert m.lookup("A") == ReasonId.EQC_INVALID_RISK_REPORT.value
    assert m.lookup("B") == ReasonId.EQC_INVALID_QID_PROOF.value
    assert m.lookup("C") is None
    assert m.lookup("") is None
