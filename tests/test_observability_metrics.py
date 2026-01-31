from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.obs.metrics import InMemoryMetrics, NullMetrics
from adamantine.v1.policy.risk_policy import RiskPolicy


def test_inmemory_metrics_counts_only_reason_ids() -> None:
    m = InMemoryMetrics()
    m.inc("A")
    m.inc("A")
    m.inc("B")
    snap = m.snapshot()
    assert snap == {"A": 2, "B": 1}

    # Ensure no payload storage fields exist (deny-by-default leakage)
    assert not hasattr(m, "payload")
    assert not hasattr(m, "request")
    assert not hasattr(m, "context")


def test_null_metrics_is_safe_noop() -> None:
    m = NullMetrics()
    m.inc("ANY")
    assert m.snapshot() == {}


def test_metrics_increment_on_eqc_deny() -> None:
    now = 200
    m = InMemoryMetrics()

    # Missing everything -> should deny + count missing reasons
    res = evaluate_eqc(wallet_id="", action="", now=now, metrics=m)
    snap = m.snapshot()

    assert res.verdict.value == "DENY"
    assert snap.get(ReasonId.EQC_MISSING_WALLET_ID.value, 0) >= 1
    assert snap.get(ReasonId.EQC_MISSING_ACTION.value, 0) >= 1
    # NOTE: session/risk missing will also be counted due to fail-closed gate
    assert snap.get(ReasonId.EQC_MISSING_QID_SESSION.value, 0) >= 1


def test_metrics_increment_on_qid_adapter_error() -> None:
    now = 200
    m = InMemoryMetrics()

    with pytest.raises(AdapterError):
        parse_qid_session(payload={"qid_iface_version": "qid-session-v0"}, now=now, metrics=m)

    snap = m.snapshot()
    assert snap.get(ReasonId.EQC_INVALID_QID_PROOF.value, 0) >= 1


def test_metrics_increment_on_risk_adapter_unknown_reason() -> None:
    now = 200
    m = InMemoryMetrics()
    expected_hash = "a" * 64

    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": expected_hash,
        "generated_at": 190,
        "overall_score": 90,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["NEW_REASON"]}],
    }

    with pytest.raises(AdapterError):
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
            metrics=m,
        )

    snap = m.snapshot()
    assert snap.get(ReasonId.UNKNOWN_EXTERNAL_REASON.value, 0) >= 1
