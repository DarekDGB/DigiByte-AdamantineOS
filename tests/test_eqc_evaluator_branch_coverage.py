from __future__ import annotations

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc, evaluate_eqc_v2
from adamantine.v1.obs.metrics import InMemoryMetrics
from adamantine.v1.policy.risk_policy import RiskPolicy


def _session(*, now: int, issued_at_delta: int = -10, ttl: int = 60) -> QIDSessionProof:
    return QIDSessionProof(
        binding_hash="b" * 64,
        pqc_algo="ML-DSA",
        pqc_pub="p" * 16,
        pqc_sig="s" * 16,
        issued_at=now + issued_at_delta,
        expires_at=now + issued_at_delta + ttl,
        nonce="n1",
        session_id="sid",
    )


def _risk_report(*, ctx_hash: str, score: int, now: int) -> RiskReport:
    sig = RiskSignal(source="ac", severity=1, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    return RiskReport(
        context_hash=ctx_hash,
        signals=(sig,),
        overall_score=score,
        generated_at=now - 1,
        oracle_version="v3",
        external_source_id="src",
    )


def _oracle(*, ctx_hash: str, now: int, score: int = 99, expires_in: int = 60) -> AdaptiveCoreOracleV3:
    rr = _risk_report(ctx_hash=ctx_hash, score=score, now=now)
    return AdaptiveCoreOracleV3(
        context_hash=ctx_hash,
        issued_at=now - 1,
        expires_at=now + expires_in,
        report=rr,
    )


def _shield(
    *,
    ctx_hash: str,
    now: int,
    expires_in: int = 60,
    required_layers: tuple[str, ...] = ("sentinel_ai",),
    reason_ids: tuple[str, ...] = (ReasonId.EVIDENCE_OK.value,),
) -> ShieldBundleV3:
    sig = ShieldSignal(
        layer="sentinel_ai",
        source=ShieldSource.SHIELD,
        signal_id="s1",
        reason_ids=reason_ids,
        facts={"ok": True},
    )
    return ShieldBundleV3(
        bundle_id="b1",
        context_hash=ctx_hash,
        required_layers=required_layers,
        signals=(sig,),
        issued_at=now - 1,
        expires_at=now + expires_in,
    )


def test_eqc_v1_metrics_increment_on_missing_now() -> None:
    metrics = InMemoryMetrics()
    out = evaluate_eqc(wallet_id="w1", action="send", now=None, metrics=metrics)  # type: ignore[arg-type]
    assert out.verdict.value == "deny"
    snap = metrics.snapshot()
    assert snap.get(ReasonId.EQC_MISSING_NOW.value, 0) == 1


def test_eqc_v2_oracle_report_context_hash_mismatch() -> None:
    now = 100
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"a": "1"})
    session = _session(now=now)

    # Oracle binds to a *different* context hash => EQC_RISK_CONTEXT_HASH_MISMATCH
    oracle = _oracle(ctx_hash="b" * 64, now=now, score=99)
    shield = _shield(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields={"a": "1"},
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH.value


def test_eqc_v2_oracle_validate_failure_maps_to_invalid_risk_report() -> None:
    now = 100
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)

    rr = _risk_report(ctx_hash=ctx_hash, score=99, now=now)
    # issued_at >= expires_at => oracle.validate raises
    bad_oracle = AdaptiveCoreOracleV3(context_hash=ctx_hash, issued_at=200, expires_at=100, report=rr)
    shield = _shield(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=bad_oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_INVALID_RISK_REPORT.value


def test_eqc_v2_score_below_threshold() -> None:
    now = 100
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, score=1)  # below default threshold
    shield = _shield(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),  # default min_overall_score=85
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value


def test_eqc_v2_shield_invalid_bundle() -> None:
    now = 100
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, score=99)

    # required_layers empty => shield.validate raises
    bad_shield = _shield(ctx_hash=ctx_hash, now=now, required_layers=())
    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=bad_shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value


def test_eqc_v2_shield_context_hash_mismatch() -> None:
    now = 100
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, score=99)

    shield = _shield(ctx_hash="c" * 64, now=now)
    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH.value


def test_eqc_v2_shield_stale_window() -> None:
    now = 100
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, score=99)

    # expires_at <= now => stale
    shield = _shield(ctx_hash=ctx_hash, now=now, expires_in=0)
    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_SHIELD_STALE.value


def test_eqc_v2_final_presence_reasons_after_valid_evidence() -> None:
    """
    Covers the late fail-closed branch:
      - wallet_id missing
      - BUT evidence checks all pass (so we hit the final `if reasons:` block)
    """
    now = 100

    # wallet_id empty affects ctx_hash; bind oracle+shield to the same ctx_hash.
    ctx_hash = compute_context_hash(wallet_id="", action="send", fields={"x": "1"})
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, score=99)
    shield = _shield(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="",
        action="send",
        fields={"x": "1"},
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "deny"
    assert out.reason_ids[0] == ReasonId.EQC_MISSING_WALLET_ID.value


def test_eqc_v2_metrics_increment_multiple_reasons() -> None:
    metrics = InMemoryMetrics()
    out = evaluate_eqc_v2(wallet_id="", action="", now=None, metrics=metrics)  # type: ignore[arg-type]
    assert out.verdict.value == "deny"

    snap = metrics.snapshot()
    assert snap.get(ReasonId.EQC_MISSING_WALLET_ID.value, 0) == 1
    assert snap.get(ReasonId.EQC_MISSING_ACTION.value, 0) == 1
    assert snap.get(ReasonId.EQC_MISSING_NOW.value, 0) == 1
