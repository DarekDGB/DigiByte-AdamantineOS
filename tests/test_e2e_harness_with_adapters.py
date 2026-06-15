from __future__ import annotations

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash
import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.execution.boundary import run_with_tva
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v1.wsqk.issuer import WSQKIssueRequest, issue_wsqk_authority


def _qid_payload(*, issued_at: int, expires_at: int, context_hash: str | None = None) -> dict:
    return bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "proof_hash": "proofhash123",
        "context_hash": context_hash,
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    })


def _risk_payload(*, context_hash: str, generated_at: int, overall_score: int, reason_ids: list[str]) -> dict:
    return {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": context_hash,
        "generated_at": generated_at,
        "overall_score": overall_score,
        "signals": [
            {"source": "adaptive-core", "severity": 10, "reason_ids": reason_ids},
        ],
        "oracle_version": "ac-v0",
        "external_source_id": "rpt-1",
    }


def test_e2e_allows_and_executes_with_valid_evidence() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10", "to": "DGB1"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.ALLOW

    auth = issue_wsqk_authority(
        WSQKIssueRequest(
            wallet_id=wallet_id,
            action=action,
            context_hash=eqc.context_hash,
            now=now,
            ttl_seconds=30,
            nonce="nonce-1",
        )
    )

    store = InMemoryNonceStore()
    executor = RecordingExecutor()

    ctx = ExecutionContext(wallet_id=wallet_id, action=action, context_hash=eqc.context_hash)
    req = ExecutionRequest(wallet_id=wallet_id, action=action, payload="payload-v0")

    out = run_with_tva(
        executor=executor,
        request=req,
        context=ctx,
        verdict=eqc.verdict,
        authority=auth,
        now=now,
        nonce_store=store,
    )

    assert out == "EXECUTED"
    assert executor.called is True
    assert executor.last_request == req


def test_e2e_denies_on_unknown_external_reason() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["NEW_REASON"]),
            now=now,
            expected_context_hash=ctx_hash,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )
    assert e.value.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON


def test_e2e_denies_on_score_below_threshold() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=80, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.DENY
    assert ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value in eqc.reason_ids


def test_tva_nonce_replay_denies_second_execution() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.ALLOW

    auth = issue_wsqk_authority(
        WSQKIssueRequest(
            wallet_id=wallet_id,
            action=action,
            context_hash=eqc.context_hash,
            now=now,
            ttl_seconds=30,
            nonce="nonce-replay",
        )
    )

    ctx = ExecutionContext(wallet_id=wallet_id, action=action, context_hash=eqc.context_hash)
    store = InMemoryNonceStore()

    enforce_tva(ctx, Verdict.ALLOW, auth, now=now, nonce_store=store)

    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, auth, now=now, nonce_store=store)

    assert str(e.value) == ReasonId.TVA_NONCE_REPLAY.value


# --- Step 20.1 additions: time window, evidence, context mismatch, determinism ---


def test_e2e_denies_on_expired_session() -> None:
    now = 200
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=199), now=now)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_EXPIRED


def test_e2e_denies_on_future_session() -> None:
    now = 200
    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=_qid_payload(issued_at=250, expires_at=350), now=now)
    assert e.value.reason_id is ReasonId.EQC_QID_SESSION_NOT_YET_VALID


def test_e2e_denies_on_risk_context_mismatch() -> None:
    now = 200
    expected = "a" * 64
    actual = "b" * 64

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_risk_payload(context_hash=actual, generated_at=190, overall_score=90, reason_ids=["ok"]),
            now=now,
            expected_context_hash=expected,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )
    assert e.value.reason_id is ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH


def test_e2e_denies_when_missing_qid_evidence() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=None,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_QID_SESSION.value in eqc.reason_ids


def test_e2e_denies_when_missing_risk_evidence() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)
    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=None,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_RISK_REPORT.value in eqc.reason_ids


def test_e2e_determinism_same_inputs_same_result() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10", "to": "DGB1"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc1 = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    eqc2 = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )

    assert eqc1.context_hash == eqc2.context_hash
    assert eqc1.verdict is eqc2.verdict
    assert eqc1.reason_ids == eqc2.reason_ids


# --- Step 20.2 additions: hostile adapter evidence shapes ---


def test_e2e_denies_on_invalid_qid_missing_proof_hash() -> None:
    now = 200
    bad = _qid_payload(issued_at=150, expires_at=250)
    bad.pop("proof_hash", None)

    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=bad, now=now)

    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_e2e_denies_on_invalid_qid_wrong_types() -> None:
    now = 200
    bad = _qid_payload(issued_at=150, expires_at=250)
    bad["issued_at"] = "150"  # wrong type
    bad["expires_at"] = "250"  # wrong type

    with pytest.raises(AdapterError) as e:
        parse_qid_session(payload=bad, now=now)

    assert e.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_e2e_denies_on_invalid_risk_missing_overall_score() -> None:
    now = 200
    expected = "a" * 64
    payload = _risk_payload(context_hash=expected, generated_at=190, overall_score=90, reason_ids=["ok"])
    payload.pop("overall_score", None)

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )

    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_e2e_denies_on_invalid_risk_wrong_overall_score_type() -> None:
    now = 200
    expected = "a" * 64
    payload = _risk_payload(context_hash=expected, generated_at=190, overall_score=90, reason_ids=["ok"])
    payload["overall_score"] = "90"  # wrong type

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )

    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_e2e_denies_on_invalid_risk_generated_at_in_future() -> None:
    now = 200
    expected = "a" * 64
    payload = _risk_payload(context_hash=expected, generated_at=250, overall_score=90, reason_ids=["ok"])  # future

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )

    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_e2e_denies_on_invalid_risk_empty_signals() -> None:
    now = 200
    expected = "a" * 64
    payload = _risk_payload(context_hash=expected, generated_at=190, overall_score=90, reason_ids=["ok"])
    payload["signals"] = []

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )

    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


# --- Step 20.3 additions: governance locks (no custom ExternalReasonMap construction) ---


def test_e2e_unknown_reason_denied_under_deny_explicit_policy() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}
    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["NOT_ALLOWED"]),
            now=now,
            expected_context_hash=ctx_hash,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )
    assert e.value.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON


def test_e2e_unmapped_external_reason_is_denied() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}
    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_risk_payload(
                context_hash=ctx_hash,
                generated_at=190,
                overall_score=90,
                reason_ids=["UNMAPPED_REASON_999"],
            ),
            now=now,
            expected_context_hash=ctx_hash,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )

    assert e.value.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON


def test_e2e_reason_map_is_required_when_policy_not_provided() -> None:
    now = 200
    expected = "a" * 64

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_risk_payload(
                context_hash=expected,
                generated_at=190,
                overall_score=90,
                reason_ids=["ok"],
            ),
            now=now,
            expected_context_hash=expected,
            reason_map=None,
            policy=None,
        )

    assert e.value.reason_id is ReasonId.EQC_INVALID_RISK_REPORT

def test_e2e_reason_ordering_for_basic_presence_failures_is_stable() -> None:
    now = 200
    action = "SEND"
    fields = {"amount": "10"}

    wallet_id = ""

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )

    assert eqc.verdict is Verdict.DENY
    assert eqc.reason_ids == (ReasonId.EQC_MISSING_WALLET_ID.value,)


def test_e2e_reason_ordering_wallet_and_action_missing_is_stable() -> None:
    now = 200
    wallet_id = ""
    action = ""
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )

    assert eqc.verdict is Verdict.DENY
    assert eqc.reason_ids == (
        ReasonId.EQC_MISSING_WALLET_ID.value,
        ReasonId.EQC_MISSING_ACTION.value,
    )


def test_e2e_adapters_cannot_grant_authority_via_injected_fields() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10", "to": "DGB1"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    qid = _qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash)
    qid["verdict"] = "ALLOW"
    qid["authority"] = {"class": "admin", "scope": {"policy_pack": "root"}}

    riskp = _risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"])
    riskp["allow"] = True
    riskp["tva"] = {"bypass": True}
    riskp["wsqk"] = {"nonce": "steal-me"}

    session = parse_qid_session(payload=qid, now=now)
    risk = parse_risk_report(
        payload=riskp,
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )

    assert eqc.verdict is Verdict.ALLOW
    assert eqc.reason_ids == ()

def test_e2e_no_execution_without_valid_tva_authority() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10", "to": "DGB1"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    # Evidence passes -> EQC allows
    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250, context_hash=ctx_hash), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.ALLOW

    # But we intentionally use a mismatching authority context_hash -> TVA must fail -> executor not called
    auth = issue_wsqk_authority(
        WSQKIssueRequest(
            wallet_id=wallet_id,
            action=action,
            context_hash="x" * 64,  # wrong on purpose
            now=now,
            ttl_seconds=30,
            nonce="nonce-bad-auth",
        )
    )

    store = InMemoryNonceStore()
    executor = RecordingExecutor()

    ctx = ExecutionContext(wallet_id=wallet_id, action=action, context_hash=eqc.context_hash)
    req = ExecutionRequest(wallet_id=wallet_id, action=action, payload="payload-v0")

    with pytest.raises(TVAError) as e:
        run_with_tva(
            executor=executor,
            request=req,
            context=ctx,
            verdict=eqc.verdict,
            authority=auth,
            now=now,
            nonce_store=store,
        )

    assert str(e.value) == ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value
    assert executor.called is False
    assert executor.last_request is None
