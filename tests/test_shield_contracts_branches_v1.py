from __future__ import annotations

import pytest

from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry, ShieldSignal


def test_shield_signal_rejects_non_str_source() -> None:
    sig = ShieldSignal(source=123, severity=10, reason_ids=("R1",))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sig.validate()


def test_shield_signal_rejects_empty_reason_id() -> None:
    sig = ShieldSignal(source="sentinel", severity=10, reason_ids=("",))
    with pytest.raises(ValueError):
        sig.validate()


def test_external_reason_map_entry_rejects_empty_external_id() -> None:
    ent = ExternalReasonMapEntry(external_id="", internal_reason_id="DENY_POLICY")
    with pytest.raises(ValueError):
        ent.validate()


def test_external_reason_map_entry_rejects_empty_internal_reason_id() -> None:
    ent = ExternalReasonMapEntry(external_id="ok", internal_reason_id="")
    with pytest.raises(ValueError):
        ent.validate()


def test_external_reason_map_rejects_non_entry_items() -> None:
    bad = ExternalReasonMap(entries=("not-an-entry",))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        bad.validate()
