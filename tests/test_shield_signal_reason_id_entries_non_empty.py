from __future__ import annotations

import pytest

from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource


def test_shield_signal_rejects_blank_reason_id_entry() -> None:
    sig = ShieldSignal(
        source=ShieldSource.SENTINEL,
        severity=10,
        reason_ids=(" ",),  # blank -> should fail-closed
    )

    with pytest.raises(ValueError) as e:
        sig.validate()

    assert "reason_id entries must be non-empty str" in str(e.value)
