from __future__ import annotations

import pytest

from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.eqc.evaluator import evaluate_eqc_v2
from adamantine.v1.eqc.result import EQCResult
from adamantine.v1.mobile.result_builder_v1 import build_mobile_decision_result_v1


def test_eqc_v2_denies_when_session_missing() -> None:
    res = evaluate_eqc_v2(wallet_id="w1", action="sign", now=1000, session=None)
    assert res.verdict.value == "DENY"
    assert ReasonId.EQC_MISSING_QID_SESSION in res.reason_ids


def test_eqc_v2_denies_when_session_not_yet_valid() -> None:
    sess = QIDSessionProof(subject="s", issued_at=2000, expires_at=3000, proof_hash="ph")
    res = evaluate_eqc_v2(wallet_id="w1", action="sign", now=1500, session=sess)
    assert res.verdict.value == "DENY"
    assert ReasonId.EQC_QID_SESSION_NOT_YET_VALID in res.reason_ids


def test_eqc_v2_denies_when_session_expired() -> None:
    sess = QIDSessionProof(subject="s", issued_at=1000, expires_at=1100, proof_hash="ph")
    res = evaluate_eqc_v2(wallet_id="w1", action="sign", now=1100, session=sess)
    assert res.verdict.value == "DENY"
    assert ReasonId.EQC_QID_SESSION_EXPIRED in res.reason_ids


def test_eqc_v2_denies_when_session_contract_invalid() -> None:
    # within time window but invalid proof data => session.validate() raises
    sess = QIDSessionProof(subject="", issued_at=1000, expires_at=2000, proof_hash="ph")
    res = evaluate_eqc_v2(wallet_id="w1", action="sign", now=1500, session=sess)
    assert res.verdict.value == "DENY"
    assert ReasonId.EQC_INVALID_QID_PROOF in res.reason_ids


def test_mobile_result_builder_rejects_blank_request_id() -> None:
    # hits src/adamantine/v1/mobile/result_builder_v1.py line 32
    eqc = EQCResult.allow(context_hash="0" * 64)
    with pytest.raises(ValueError, match="request_id must be non-empty"):
        build_mobile_decision_result_v1(eqc=eqc, request_id="   ")
