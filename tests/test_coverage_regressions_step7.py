from __future__ import annotations

import pytest

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash

from adamantine.errors import TVAError
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore, NonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.execution.executor import Executor
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v1.wsqk.issuer import WSQKIssueRequest, issue_wsqk_authority


# -----------------------------
# Contracts: Q-ID (qid.py)
# -----------------------------
def test_qid_contract_covers_fail_closed_branches() -> None:
    now = 150

    # now must be int
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", 100, 200, "h").validate(now="x")  # type: ignore[arg-type]

    # subject must be non-empty
    with pytest.raises(ValueError):
        QIDSessionProof("", 100, 200, "h").validate(now=now)

    # proof_hash must be non-empty
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", 100, 200, "").validate(now=now)

    # issued_at/expires_at must be int
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", "100", 200, "h").validate(now=now)  # type: ignore[arg-type]

    # timestamps must be positive
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", 0, 200, "h").validate(now=now)

    # expires_at must be > issued_at
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", 200, 200, "h").validate(now=now)

    # session validity window
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", 100, 200, "h").validate(now=250)

    # device_binding type enforcement
    with pytest.raises(ValueError):
        QIDSessionProof("did:x", 100, 200, "h", device_binding=123).validate(now=now)  # type: ignore[arg-type]


# -----------------------------
# Contracts: Risk (risk.py)
# -----------------------------
def test_risk_contract_covers_fail_closed_branches() -> None:
    # RiskSignal source non-empty
    with pytest.raises(ValueError):
        RiskSignal(source="", severity=1, reason_ids=("ok",)).validate()

    # RiskSignal severity bounds
    with pytest.raises(ValueError):
        RiskSignal(source="ac", severity=101, reason_ids=("ok",)).validate()

    # RiskSignal reason_ids must be tuple
    with pytest.raises(ValueError):
        RiskSignal(source="ac", severity=1, reason_ids=["ok"]).validate()  # type: ignore[arg-type]

    # RiskSignal reason_ids elements must be non-empty str
    with pytest.raises(ValueError):
        RiskSignal(source="ac", severity=1, reason_ids=("",)).validate()

    now = 200
    sig = RiskSignal(source="ac", severity=1, reason_ids=("ok",))

    # RiskReport now must be int
    with pytest.raises(ValueError):
        RiskReport("h", (sig,), 90, 150).validate(now="x")  # type: ignore[arg-type]

    # context_hash non-empty
    with pytest.raises(ValueError):
        RiskReport("", (sig,), 90, 150).validate(now=now)

    # overall_score bounds/type
    with pytest.raises(ValueError):
        RiskReport("h", (sig,), "90", 150).validate(now=now)  # type: ignore[arg-type]

    # generated_at positive
    with pytest.raises(ValueError):
        RiskReport("h", (sig,), 90, 0).validate(now=now)

    # generated_at cannot be in future
    with pytest.raises(ValueError):
        RiskReport("h", (sig,), 90, 999).validate(now=now)

    # signals must be tuple
    with pytest.raises(ValueError):
        RiskReport("h", [sig], 90, 150).validate(now=now)  # type: ignore[arg-type]

    # signals must contain RiskSignal instances
    with pytest.raises(ValueError):
        RiskReport("h", ("not-a-signal",), 90, 150).validate(now=now)  # type: ignore[arg-type]


# -----------------------------
# EQC: cover remaining branches (evaluator.py)
# -----------------------------
def test_eqc_covers_time_branches_and_validation_failures() -> None:
    now = 200
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)

    # session not yet valid
    session_future = QIDSessionProof("did:x", issued_at=300, expires_at=400, proof_hash="h")
    risk_ok = RiskReport(ctx_hash, (RiskSignal("ac", 1, ("ok",)),), 90, generated_at=150)
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=session_future,
        risk=risk_ok,
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_QID_SESSION_NOT_YET_VALID.value in res.reason_ids

    # session expired
    session_expired = QIDSessionProof("did:x", issued_at=100, expires_at=150, proof_hash="h")
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=session_expired,
        risk=risk_ok,
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_QID_SESSION_EXPIRED.value in res.reason_ids

    # invalid qid proof (contract validate raises)
    session_bad = QIDSessionProof("did:x", issued_at=100, expires_at=300, proof_hash="")
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=session_bad,
        risk=risk_ok,
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_INVALID_QID_PROOF.value in res.reason_ids

    # invalid risk report (contract validate raises)
    session_ok = QIDSessionProof("did:x", issued_at=100, expires_at=300, proof_hash="h", context_hash=ctx_hash)
    risk_bad = RiskReport(ctx_hash, (RiskSignal("", 1, ("ok",)),), 90, generated_at=150)
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=session_ok,
        risk=risk_bad,
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_INVALID_RISK_REPORT.value in res.reason_ids


# -----------------------------
# Adapters: Q-ID (qid_adapter.py)
# -----------------------------
def test_qid_adapter_covers_error_branches() -> None:
    # now must be int
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload={}, now="x")  # type: ignore[arg-type]
    assert e.value.reason_id is ReasonId.EQC_MISSING_NOW

    # payload must be mapping
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload="nope", now=100)  # type: ignore[arg-type]
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF

    # issued_at/expires_at must be int
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:x",
        "issued_at": "100",
        "expires_at": 200,
        "proof_hash": "h",
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=150)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF

    # not yet valid
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:x",
        "issued_at": 200,
        "expires_at": 300,
        "proof_hash": "h",
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=150)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_NOT_YET_VALID

    # device_binding invalid (empty)
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:x",
        "issued_at": 100,
        "expires_at": 300,
        "proof_hash": "h",
        "device_binding": "",
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=150)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF

    # issuer_version invalid type
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:x",
        "issued_at": 100,
        "expires_at": 300,
        "proof_hash": "h",
        "issuer_version": 123,
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=150)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF

    # contract validation failure path (timestamps non-positive)
    payload = bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:x",
        "issued_at": 0,
        "expires_at": 300,
        "proof_hash": "h",
    })
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=payload, now=150)
    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


# -----------------------------
# Adapters: Adaptive Core (adaptive_core_adapter.py)
# -----------------------------
def test_adaptive_core_adapter_covers_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 200
    expected_hash = "a" * 64

    # now must be int
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload={},
            now="x",  # type: ignore[arg-type]
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_MISSING_NOW

    # expected_context_hash must be non-empty str
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload={},
            now=now,
            expected_context_hash="",
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # payload must be mapping
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload="nope",  # type: ignore[arg-type]
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # missing iface
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload={"context_hash": expected_hash},
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # generated_at invalid
    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": expected_hash,
        "generated_at": 0,
        "overall_score": 90,
        "signals": [{"source": "ac", "severity": 1, "reason_ids": ["ok"]}],
    }
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # generated_at in the future
    payload["generated_at"] = 999
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # overall_score invalid
    payload["generated_at"] = 150
    payload["overall_score"] = 1000
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # signals must be sequence (not str/bytes)
    payload["overall_score"] = 90
    payload["signals"] = "nope"
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # signals must not be empty
    payload["signals"] = []
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # signal must be mapping
    payload["signals"] = ["not-mapping"]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # signal source invalid
    payload["signals"] = [{"source": "", "severity": 1, "reason_ids": ["ok"]}]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # signal severity invalid
    payload["signals"] = [{"source": "ac", "severity": 999, "reason_ids": ["ok"]}]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # reason_ids must be sequence
    payload["signals"] = [{"source": "ac", "severity": 1, "reason_ids": "nope"}]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # reason_id element invalid (empty str)
    payload["signals"] = [{"source": "ac", "severity": 1, "reason_ids": [""]}]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # unknown external reason -> fail-closed
    payload["signals"] = [{"source": "ac", "severity": 1, "reason_ids": ["NEW_REASON"]}]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON

    # trigger RiskSignal.validate failure path (empty reason_ids list)
    payload["signals"] = [{"source": "ac", "severity": 1, "reason_ids": []}]
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # oracle_version wrong type
    payload["signals"] = [{"source": "ac", "severity": 1, "reason_ids": ["ok"]}]
    payload["oracle_version"] = 123
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # external_source_id wrong type
    payload["oracle_version"] = "ac-v0"
    payload["external_source_id"] = 123
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

    # cover adapter's RiskReport.validate exception branch via monkeypatch
    payload["external_source_id"] = "rpt-1"
    payload["oracle_version"] = "ac-v0"
    real_validate = RiskReport.validate

    def _boom(self: RiskReport, *, now: int) -> None:
        raise ValueError("boom")

    monkeypatch.setattr(RiskReport, "validate", _boom)
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
        )
    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT
    monkeypatch.setattr(RiskReport, "validate", real_validate)


# -----------------------------
# Policy validation (risk_policy.py)
# -----------------------------
def test_policy_validate_covers_invalid_modes() -> None:
    with pytest.raises(ValueError):
        RiskPolicy(min_overall_score="x").validate()  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        RiskPolicy(unknown_reason_mode="BAD").validate()  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        RiskPolicy(resilience_mode="BAD").validate()  # type: ignore[arg-type]


# -----------------------------
# WSQK issuer errors (issuer.py)
# -----------------------------
def test_wsqk_issuer_covers_error_branches() -> None:
    # missing wallet_id
    with pytest.raises(TVAError) as e:
        issue_wsqk_authority(
            WSQKIssueRequest(wallet_id="", action="A", context_hash="h", now=1, ttl_seconds=1, nonce="n")
        )
    assert str(e.value) == ReasonId.WSQK_MISSING_WALLET_ID.value

    # missing action
    with pytest.raises(TVAError) as e:
        issue_wsqk_authority(
            WSQKIssueRequest(wallet_id="w", action="", context_hash="h", now=1, ttl_seconds=1, nonce="n")
        )
    assert str(e.value) == ReasonId.WSQK_MISSING_ACTION.value

    # missing context_hash
    with pytest.raises(TVAError) as e:
        issue_wsqk_authority(
            WSQKIssueRequest(wallet_id="w", action="A", context_hash="", now=1, ttl_seconds=1, nonce="n")
        )
    assert str(e.value) == ReasonId.WSQK_MISSING_CONTEXT_HASH.value

    # now not convertible to int
    with pytest.raises(TVAError) as e:
        issue_wsqk_authority(
            WSQKIssueRequest(wallet_id="w", action="A", context_hash="h", now="x", ttl_seconds=1, nonce="n")  # type: ignore[arg-type]
        )
    assert str(e.value) == ReasonId.WSQK_MISSING_NOW.value


# -----------------------------
# Interfaces: NotImplementedError lines
# -----------------------------
def test_nonce_store_interface_raises_not_implemented() -> None:
    store = NonceStore()
    with pytest.raises(NotImplementedError):
        store.check_and_mark("w", "n", 1)


def test_executor_interface_raises_not_implemented() -> None:
    ex = Executor()
    with pytest.raises(NotImplementedError):
        ex.execute(req=None)  # type: ignore[arg-type]


# -----------------------------
# TVA invalid nonce branch (tva_gate.py line 78)
# -----------------------------
def test_tva_denies_empty_nonce() -> None:
    ctx = ExecutionContext(wallet_id="w1", action="SEND", context_hash="h")

    # Issue a valid authority first (WSQK enforces nonce validity).
    auth_ok = issue_wsqk_authority(
        WSQKIssueRequest(wallet_id="w1", action="SEND", context_hash="h", now=100, ttl_seconds=10, nonce="n1")
    )

    # Create an authority with an empty/whitespace nonce to reach TVA's nonce validation branch.
    auth_bad = type(auth_ok)(
        wallet_id=auth_ok.wallet_id,
        action=auth_ok.action,
        context_hash=auth_ok.context_hash,
        issued_at=auth_ok.issued_at,
        expires_at=auth_ok.expires_at,
        nonce=" ",
    )

    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, auth_bad, now=105, nonce_store=InMemoryNonceStore())

    assert str(e.value) == ReasonId.TVA_INVALID_NONCE.value
