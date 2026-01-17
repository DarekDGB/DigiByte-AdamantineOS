from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc


def test_context_hash_deterministic_with_sorted_fields() -> None:
    h1 = compute_context_hash(wallet_id="w1", action="SEND", fields={"b": "2", "a": "1"})
    h2 = compute_context_hash(wallet_id="w1", action="SEND", fields={"a": "1", "b": "2"})
    assert h1 == h2


def test_eqc_denies_missing_wallet_id() -> None:
    res = evaluate_eqc(wallet_id="", action="SEND", fields=None)
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_WALLET_ID.value in res.reason_ids


def test_eqc_denies_missing_action() -> None:
    res = evaluate_eqc(wallet_id="w1", action="", fields=None)
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_ACTION.value in res.reason_ids


def test_eqc_allows_when_required_fields_present() -> None:
    res = evaluate_eqc(wallet_id="w1", action="SEND", fields={"amount": "10"})
    assert res.verdict is Verdict.ALLOW
    assert res.reason_ids == ()
    assert isinstance(res.context_hash, str)
    assert len(res.context_hash) == 64
