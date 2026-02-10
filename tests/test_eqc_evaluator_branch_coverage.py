from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.shield import ShieldSignal
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc, evaluate_eqc_v2
from adamantine.v1.obs.metrics import InMemoryMetrics
from adamantine.v1.policy.risk_policy import RiskPolicy


NOW = 100


def _session(*, now: int, issued_at_delta: int = -10, ttl: int = 60) -> QIDSessionProof:
    """
    Build a minimal VALID QIDSessionProof for evaluator branches.
    """
    return QIDSessionProof(
        subject="w1",
        issued_at=now + issued_at_delta,
        expires_at=now + issued_at_delta + ttl,
        session_id="sid",
        pqc_algo="ML-DSA",
        pqc_pub="p" * 16,
        pqc_sig="s" * 16,
        nonce="n1",
    )


def _risk_report(*, ctx_hash: str, score: int = 95, generated_at: int = 10) -> RiskReport:
    sig = RiskSignal(source="ac", severity=10, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    sig.validate()
    rr = RiskReport(
        context_hash=ctx_hash,
        signals=(sig,),
        overall_score=score,
        generated_at=generated_at,
        oracle_version="v3",
        external_source_id="src",
    )
    rr.validate(now=NOW)
    return rr


def _oracle(*, ctx_hash: str, report_ctx_hash: str | None = None, issued_at: int = 50, expires_at: int = 150) -> AdaptiveCoreOracleV3:
    rr = _risk_report(ctx_hash=report_ctx_hash or ctx_hash, score=95, generated_at=10)
    o = AdaptiveCoreOracleV3(
        context_hash=ctx_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        report=rr,
    )
    # oracle.validate is called by evaluator; we keep this valid by default.
    return o


def _shield_ok(*, ctx_hash: str, issued_at: int = 50, expires_at: int = 150) -> ShieldBundleV3:
    s1 = ShieldSignal(layer="guardian_wallet", signal_id="gw-1", reason_ids=(ReasonId.EVIDENCE_OK.value,), facts={})
    s2 = ShieldSignal(layer="qwg", signal_id="qwg-1", reason_ids=(ReasonId.EVIDENCE_OK.value,), facts={})
    # Sorted by (layer, signal_id): guardian_wallet < qwg
    s1.validate()
    s2.validate()
    b = ShieldBundleV3(
        context_hash=ctx_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        required_layers=("sentinel_ai", "adn", "dqsn", "qwg", "guardian_wallet"),
        signals=(s1, s2),
        bundle_id="b1",
    )
    # shield.validate is called by evaluator; keep valid by default.
    return b


def test_eqc_v1_metrics_increment_on_missing_now() -> None:
    metrics = InMemoryMetrics()
    out = evaluate_eqc(wallet_id="w1", action="send", now=None, metrics=metrics)  # type: ignore[arg-type]
    assert out.verdict.value == "DENY"
    assert ReasonId.EQC_MISSING_NOW.value in out.reason_ids
    assert metrics.counters.get(ReasonId.EQC_MISSING_NOW.value, 0) == 1


def test_eqc_v2_oracle_report_context_hash_mismatch() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"a": "1"})
    session = _session(now=now)

    # report.context_hash != computed ctx_hash => EQC_RISK_CONTEXT_HASH_MISMATCH
    oracle = _oracle(ctx_hash=ctx_hash, report_ctx_hash=("b" * 64))
    shield = _shield_ok(ctx_hash=ctx_hash)

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
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH.value,)


def test_eqc_v2_oracle_validate_failure_maps_to_invalid_risk_report() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)

    # Make oracle.validate fail by invalid timebox.
    oracle = _oracle(ctx_hash=ctx_hash, issued_at=200, expires_at=100)
    shield = _shield_ok(ctx_hash=ctx_hash)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_INVALID_RISK_REPORT.value,)


def test_eqc_v2_score_below_threshold() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)

    # overall_score below default threshold (85)
    rr = _risk_report(ctx_hash=ctx_hash, score=10, generated_at=10)
    oracle = AdaptiveCoreOracleV3(context_hash=ctx_hash, issued_at=50, expires_at=150, report=rr)
    shield = _shield_ok(ctx_hash=ctx_hash)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value,)


def test_eqc_v2_shield_invalid_bundle() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash)

    s1 = ShieldSignal(layer="guardian_wallet", signal_id="gw-1", reason_ids=(ReasonId.EVIDENCE_OK.value,), facts={})
    s2 = ShieldSignal(layer="qwg", signal_id="qwg-1", reason_ids=(ReasonId.EVIDENCE_OK.value,), facts={})
    s1.validate()
    s2.validate()

    # Invalid required_layers order -> shield.validate() raises -> EQC_INVALID_SHIELD_BUNDLE
    bad_shield = ShieldBundleV3(
        context_hash=ctx_hash,
        issued_at=50,
        expires_at=150,
        required_layers=("qwg", "guardian_wallet"),  # unsorted -> invalid
        signals=(s1, s2),
        bundle_id="b1",
    )

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=bad_shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_INVALID_SHIELD_BUNDLE.value,)


def test_eqc_v2_shield_context_hash_mismatch() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash)

    shield = _shield_ok(ctx_hash=("c" * 64))  # mismatch

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH.value,)


def test_eqc_v2_shield_stale_window() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash)

    # stale: issued_at > now
    shield = _shield_ok(ctx_hash=ctx_hash, issued_at=200, expires_at=300)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=RiskPolicy(),
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_SHIELD_STALE.value,)


def test_eqc_v2_final_presence_reasons_after_valid_evidence() -> None:
    """
    Covers the late fail-closed branch:
      - wallet_id missing
      - BUT evidence checks all pass (so we hit the final `if reasons:` block)
    """
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="", action="send", fields={"x": "1"})

    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash)
    shield = _shield_ok(ctx_hash=ctx_hash)

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
    assert out.verdict.value == "DENY"
    assert out.reason_ids == (ReasonId.EQC_MISSING_WALLET_ID.value,)


def test_eqc_v2_metrics_increment_multiple_reasons() -> None:
    metrics = InMemoryMetrics()
    out = evaluate_eqc_v2(wallet_id="", action="", now=None, metrics=metrics)  # type: ignore[arg-type]
    assert out.verdict.value == "DENY"
    assert metrics.counters.get(ReasonId.EQC_MISSING_WALLET_ID.value, 0) == 1
    assert metrics.counters.get(ReasonId.EQC_MISSING_ACTION.value, 0) == 1
    assert metrics.counters.get(ReasonId.EQC_MISSING_NOW.value, 0) == 1
