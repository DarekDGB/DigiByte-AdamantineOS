from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3


def _ok_signal(source: ShieldSource) -> ShieldSignal:
    return ShieldSignal(
        source=source,
        severity=10,
        reason_ids=(ReasonId.EVIDENCE_OK.value,),
    )


def test_shield_v3_accepts_valid_bundle() -> None:
    ctx = "a" * 64
    bundle = ShieldBundleV3(
        bundle_id="b1",
        context_hash=ctx,
        issued_at=90,
        expires_at=200,
        required_layers=("qwg", "guardian_wallet"),
        signals=(
            _ok_signal(ShieldSource.QWG),
            _ok_signal(ShieldSource.GUARDIAN),
        ),
    )
    bundle.validate()  # should not raise


def test_shield_v3_rejects_invalid_time_window() -> None:
    ctx = "a" * 64
    bundle = ShieldBundleV3(
        bundle_id="b1",
        context_hash=ctx,
        issued_at=200,
        expires_at=100,
        required_layers=("qwg",),
        signals=(
            _ok_signal(ShieldSource.QWG),
        ),
    )
    with pytest.raises(ValueError):
        bundle.validate()


def test_shield_v3_rejects_empty_signals() -> None:
    ctx = "a" * 64
    bundle = ShieldBundleV3(
        bundle_id="b1",
        context_hash=ctx,
        issued_at=90,
        expires_at=200,
        required_layers=("qwg",),
        signals=(),
    )
    with pytest.raises(ValueError):
        bundle.validate()
