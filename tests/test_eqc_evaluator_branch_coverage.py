from __future__ import annotations

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

NOW = 1706918400


def _session(*, now: int, issued_at_delta: int = -10, ttl: int = 60) -> QIDSessionProof:
    """Minimal VALID QIDSessionProof for evaluator branches (matches current contract)."""
    return QIDSessionProof(
        subject="w1",
        issued_at=now + issued_at_delta,
        expires_at=now + issued_at_delta + ttl,
        proof_hash="b" * 64,
        device_binding=None,
        issuer_version="v1",
    )


def _oracle(*, ctx_hash: str, now: int, overall_score: int) -> AdaptiveCoreOracleV3:
    rs = RiskSignal(source="ac", severity=10, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    rs.validate()
    report = RiskReport(
        context_hash=ctx_hash,
        signals=(rs,),
        overall_score=overall_score,
        generated_at=now - 1,
        oracle_version="v3",
        external_source_id="src",
    )
    report.validate(now=now)
    oracle = AdaptiveCoreOracleV3(
        context_hash=ctx_hash,
        issued_at=now - 10,
        expires_at=now + 10,
        report=report,
    )
    oracle.validate(now=now)
    return oracle


def _shield_ok(*, ctx_hash: str, now: int) -> ShieldBundleV3:
    sig = ShieldSignal(source=ShieldSource.SENTINEL, severity=1, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    sig.validate()
    shield = ShieldBundleV3(
        context_hash=ctx_hash,
        bundle_id="b1",
        issued_at=now - 10,
        expires_at=now + 10,
        required_layers=(
            "sentinel_ai",
            "adn",
            "dqsn",
            "qwg",
            "guardian_wallet",
        ),
        signals=(sig,),
    )
    shield.validate()
    return shield


def test_eqc_v1_metrics_increment_on_missing_now() -> None:
    metrics = InMemoryMetrics()
    out = evaluate_eqc(wallet_id="w1", action="send", now=None, metrics=metrics)  # type: ignore[arg-type]

    assert out.verdict.value == "DENY"
    assert ReasonId.EQC_MISSING_NOW.value in out.reason_ids

    snap = metrics.snapshot()
    assert snap.get(ReasonId.EQC_MISSING_NOW.value, 0) == 1


def test_eqc_v2_oracle_report_context_hash_mismatch() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"a": "1"})

    session = _session(now=now)

    # Oracle report context_hash mismatch triggers EQC_RISK_CONTEXT_HASH_MISMATCH
    oracle = _oracle(ctx_hash=("c" * 64), now=now, overall_score=95)
    shield = _shield_ok(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields={"a": "1"},
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids[0] == ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH.value


def test_eqc_v2_oracle_validate_failure_maps_to_invalid_risk_report() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)

    # Make oracle invalid via timebox (issued_at > expires_at)
    rs = RiskSignal(source="ac", severity=10, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    rs.validate()
    report = RiskReport(
        context_hash=ctx_hash,
        signals=(rs,),
        overall_score=95,
        generated_at=now - 1,
        oracle_version="v3",
        external_source_id="src",
    )
    report.validate(now=now)

    bad_oracle = AdaptiveCoreOracleV3(
        context_hash=ctx_hash,
        issued_at=now + 10,
        expires_at=now - 10,
        report=report,
    )

    shield = _shield_ok(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields=None,
        session=session,
        oracle=bad_oracle,
        shield=shield,
        now=now,
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids[0] == ReasonId.EQC_INVALID_RISK_REPORT.value


def test_eqc_v2_score_below_threshold() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)

    policy = RiskPolicy(min_overall_score=90)
    policy.validate()

    oracle = _oracle(ctx_hash=ctx_hash, now=now, overall_score=10)  # below threshold
    shield = _shield_ok(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields=None,
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
        policy=policy,
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids[0] == ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value


def test_eqc_v2_shield_invalid_bundle() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, overall_score=95)

    # invalid: missing required layers
    sig = ShieldSignal(source=ShieldSource.SENTINEL, severity=1, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    sig.validate()
    bad_shield = ShieldBundleV3(
        context_hash=ctx_hash,
        bundle_id="b2",
        issued_at=now - 10,
        expires_at=now + 10,
        required_layers=(),
        signals=(sig,),
    )

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields=None,
        session=session,
        oracle=oracle,
        shield=bad_shield,
        now=now,
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids[0] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value


def test_eqc_v2_shield_context_hash_mismatch() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, overall_score=95)

    shield = _shield_ok(ctx_hash=("d" * 64), now=now)  # mismatch vs computed ctx_hash

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields=None,
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids[0] == ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH.value


def test_eqc_v2_shield_stale_window() -> None:
    now = NOW
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields=None)
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, overall_score=95)
    shield = _shield_ok(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="w1",
        action="send",
        fields=None,
        session=session,
        oracle=oracle,
        shield=shield,
        now=shield.expires_at,  # stale boundary
    )
    assert out.verdict.value == "DENY"
    assert out.reason_ids[0] == ReasonId.EQC_SHIELD_STALE.value


def test_eqc_v2_final_presence_reasons_after_valid_evidence() -> None:
    """Covers late fail-closed branch: wallet_id missing BUT evidence checks pass."""
    now = NOW

    ctx_hash = compute_context_hash(wallet_id="", action="send", fields={"x": "1"})
    session = _session(now=now)
    oracle = _oracle(ctx_hash=ctx_hash, now=now, overall_score=95)
    shield = _shield_ok(ctx_hash=ctx_hash, now=now)

    out = evaluate_eqc_v2(
        wallet_id="",
        action="send",
        fields={"x": "1"},
        session=session,
        oracle=oracle,
        shield=shield,
        now=now,
    )
    assert out.verdict.value == "DENY"
    # Presence failure is reported after evidence checks complete
    assert out.reason_ids[0] == ReasonId.EQC_MISSING_WALLET_ID.value


def test_eqc_v2_metrics_increment_multiple_reasons() -> None:
    metrics = InMemoryMetrics()
    out = evaluate_eqc_v2(wallet_id="", action="", now=None, metrics=metrics)  # type: ignore[arg-type]

    assert out.verdict.value == "DENY"

    snap = metrics.snapshot()
    assert snap.get(ReasonId.EQC_MISSING_WALLET_ID.value, 0) == 1
    assert snap.get(ReasonId.EQC_MISSING_ACTION.value, 0) == 1
    assert snap.get(ReasonId.EQC_MISSING_NOW.value, 0) == 1
