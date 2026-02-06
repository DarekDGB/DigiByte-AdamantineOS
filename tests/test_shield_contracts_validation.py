from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry, ShieldSignal, ShieldSource


def test_external_reason_map_validate_requires_non_empty_entries() -> None:
    m = ExternalReasonMap(entries=tuple())
    with pytest.raises(ValueError) as e:
        m.validate()
    assert "entries must be a non-empty tuple" in str(e.value)


def test_external_reason_map_validate_rejects_duplicate_external_ids() -> None:
    m = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="x", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="x", internal_reason_id=ReasonId.DENY_SCHEMA_INVALID.value),
        )
    )
    with pytest.raises(ValueError) as e:
        m.validate()
    assert "external_id must be unique" in str(e.value)


def test_external_reason_map_entry_requires_valid_internal_reason_id() -> None:
    bad = ExternalReasonMapEntry(external_id="x", internal_reason_id="NOT_A_REASON")
    with pytest.raises(ValueError) as e:
        bad.validate()
    assert "internal_reason_id is not a valid ReasonId" in str(e.value)


def test_shield_signal_reason_ids_must_be_non_empty_unique_and_valid() -> None:
    s = ShieldSignal(source=ShieldSource.ADAPTIVE_CORE, severity=10, reason_ids=tuple())
    with pytest.raises(ValueError) as e1:
        s.validate()
    assert "reason_ids must be a non-empty tuple" in str(e1.value)

    dup = ShieldSignal(
        source=ShieldSource.ADAPTIVE_CORE,
        severity=10,
        reason_ids=(ReasonId.DENY_POLICY.value, ReasonId.DENY_POLICY.value),
    )
    with pytest.raises(ValueError) as e2:
        dup.validate()
    assert "reason_ids must be unique" in str(e2.value)

    bad = ShieldSignal(source=ShieldSource.ADAPTIVE_CORE, severity=10, reason_ids=("NOT_A_REASON",))
    with pytest.raises(ValueError) as e3:
        bad.validate()
    assert "not a valid internal ReasonId" in str(e3.value)
