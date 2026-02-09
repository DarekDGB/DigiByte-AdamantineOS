from __future__ import annotations

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.evaluator import evaluate_eqc_v2
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.policy.risk_policy import RiskPolicy


def _valid_session(*, now: int) -> QIDSessionProof:
    return QIDSessionProof(
        subject="did:example:123",
        issued_at=now - 50,
        expires_at=now + 50,
        proof_hash="proofhash123",
        device_binding="device-1",
        issuer_version="qid-v0",
    )


def _valid_oracle(*, context_hash: str, now: int, score: int = 90) -> AdaptiveCoreOracleV3:
    sig = RiskSignal(source="adaptive-core", severity=10, reason_ids=("ok",))
    report = RiskReport(
        context_hash=context_hash,
        signals=(sig,),
        overall_score=score,
        generated_at=now - 10,
        oracle_version="ac-v3",
        external_source_id="rpt-1",
    )
    return AdaptiveCoreOracleV3(
        context_hash=context_hash,
        issued_at=now - 20,
        expires_at=now + 20,
        report=report,
    )


def _shield_ok(*, context_hash: str, now: int) -> ShieldBundleV3:
    s1 = ShieldSignal(source=ShieldSource.QWG, severity=10, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    s2 = ShieldSignal(source=ShieldSource.GUARDIAN, severity=10, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    return ShieldBundleV3(
        bundle_id="b1",
        context_hash=context_hash,
        issued_at=now - 10,
        expires_at=now + 10,
        required_layers=("qwg", "guardian_wallet"),
        signals=(s2, s1),  # order not important internally; adapter enforces ordering externally
    )


def _shield_deny(*, context_hash: str, now: int) -> ShieldBundleV3:
    s1 = ShieldSignal(source=ShieldSource.QWG, severity=90, reason_ids=(ReasonId.DENY_POLICY.value,))
    return ShieldBundleV3(
        bundle_id="b1",
        context_hash=context_hash,
        issued_at=now - 10,
        expires_at=now + 10,
        required_layers=("qwg",),
        signals=(s1,),
    )


def test_eqc_v2_denies_missing_oracle() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    res = evaluate_eqc_v2(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        oracle=None,
        shield=_shield_ok(context_hash=ctx_hash, now=now),
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_ORACLE.value in res.reason_ids


def test_eqc_v2_denies_missing_shield_bundle() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    res = evaluate_eqc_v2(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        oracle=_valid_oracle(context_hash=ctx_hash, now=now, score=90),
        shield=None,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_SHIELD_BUNDLE.value in res.reason_ids


def test_eqc_v2_denies_conflicting_shield_evidence() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    res = evaluate_eqc_v2(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        oracle=_valid_oracle(context_hash=ctx_hash, now=now, score=90),
        shield=_shield_deny(context_hash=ctx_hash, now=now),
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_CONFLICTING_EVIDENCE.value in res.reason_ids


def test_eqc_v2_allows_when_all_evidence_present_and_ok() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields={"amount": "10"})
    res = evaluate_eqc_v2(
        wallet_id="w1",
        action="SEND",
        fields={"amount": "10"},
        session=_valid_session(now=now),
        oracle=_valid_oracle(context_hash=ctx_hash, now=now, score=90),
        shield=_shield_ok(context_hash=ctx_hash, now=now),
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert res.verdict is Verdict.ALLOW
    assert res.reason_ids == ()
    assert isinstance(res.context_hash, str)
    assert len(res.context_hash) == 64
