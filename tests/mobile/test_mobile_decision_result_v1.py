from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.result import EQCResult
from adamantine.v1.mobile.result_builder_v1 import build_mobile_decision_result_v1


def test_mobile_decision_result_allow() -> None:
    eqc = EQCResult.allow(context_hash="a" * 64)
    out = build_mobile_decision_result_v1(eqc=eqc, request_id="r1")
    assert out["v"] == "mobile_decision_result_v1"
    assert out["verdict"] == "allow"
    assert out["reason_code"] == "APPROVED"
    assert out["context_hash"] == "a" * 64
    assert isinstance(out["_snapshot_sha256"], str)


def test_mobile_decision_result_deny_maps_reason() -> None:
    eqc = EQCResult(verdict=Verdict.DENY, context_hash="a" * 64, reason_ids=(ReasonId.EQC_CONFLICTING_EVIDENCE,))
    out = build_mobile_decision_result_v1(eqc=eqc, request_id="r1")
    assert out["verdict"] == "deny"
    assert out["reason_code"] == "SECURITY_POLICY_BLOCK"
    assert isinstance(out["_snapshot_sha256"], str)


def test_mobile_decision_result_determinism_same_input_same_hash() -> None:
    eqc = EQCResult(verdict=Verdict.DENY, context_hash="a" * 64, reason_ids=(ReasonId.EQC_MISSING_SHIELD_BUNDLE,))
    out1 = build_mobile_decision_result_v1(eqc=eqc, request_id="r1")
    out2 = build_mobile_decision_result_v1(eqc=eqc, request_id="r1")
    assert out1 == out2
