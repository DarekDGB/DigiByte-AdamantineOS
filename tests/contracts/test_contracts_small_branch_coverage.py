from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry, ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3


def _reason_map() -> ExternalReasonMap:
    m = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BAD", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )
    m.validate()
    return m


def test_policy_pack_validate_hits_missing_line() -> None:
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("OK",),
        external_reason_map=_reason_map(),
    )
    pack.validate()


def test_shield_bundle_v3_validate_success_and_fail_paths() -> None:
    sig = ShieldSignal(
        source=ShieldSource.GUARDIAN,
        severity=50,
        reason_ids=(ReasonId.EVIDENCE_OK.value,),
    )
    sig.validate()

    bundle = ShieldBundleV3(
        bundle_id="b1",
        context_hash="a" * 64,
        issued_at=100,
        expires_at=200,
        required_layers=("guardian_wallet",),
        signals=(sig,),
    )
    bundle.validate()

    bad = ShieldBundleV3(
        bundle_id="b1",
        context_hash="a" * 64,
        issued_at=200,
        expires_at=100,
        required_layers=("guardian_wallet",),
        signals=(sig,),
    )
    with pytest.raises(ValueError):
        bad.validate()

    bad2 = ShieldBundleV3(
        bundle_id="b1",
        context_hash="a" * 64,
        issued_at=100,
        expires_at=200,
        required_layers=(),
        signals=(sig,),
    )
    with pytest.raises(ValueError):
        bad2.validate()

    bad3 = ShieldBundleV3(
        bundle_id="b1",
        context_hash="a" * 64,
        issued_at=100,
        expires_at=200,
        required_layers=("guardian_wallet",),
        signals=(),
    )
    with pytest.raises(ValueError):
        bad3.validate()


def test_adaptive_core_oracle_v3_validate_branches() -> None:
    rs = RiskSignal(source="ac", severity=10, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    rs.validate()

    report = RiskReport(
        context_hash="a" * 64,
        signals=(rs,),
        overall_score=95,
        generated_at=100,
        oracle_version="v3",
        external_source_id="src",
    )
    report.validate(now=200)

    oracle = AdaptiveCoreOracleV3(
        context_hash="a" * 64,
        issued_at=150,
        expires_at=250,
        report=report,
    )
    oracle.validate(now=200)

    # Fail branch: oracle time window invalid
    bad = AdaptiveCoreOracleV3(
        context_hash="a" * 64,
        issued_at=250,
        expires_at=200,
        report=report,
    )
    with pytest.raises(ValueError):
        bad.validate(now=200)

    # Guaranteed fail branch (contract-level): report generated_at cannot be in the future
    future_report = RiskReport(
        context_hash="a" * 64,
        signals=(rs,),
        overall_score=95,
        generated_at=999,  # future relative to now=200
        oracle_version="v3",
        external_source_id="src",
    )
    with pytest.raises(ValueError):
        future_report.validate(now=200)
