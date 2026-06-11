from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import adamantine.v1.execution.orchestrator_v2 as orch
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineResult,
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )


def _policy(*, min_score: int = 85) -> orch.RiskPolicy:
    pack = PolicyPack(
        min_overall_score=min_score,
        allowed_external_reason_ids=("ok", "AC_OK", "OK", "BLOCK"),
        external_reason_map=_reason_map(),
    )
    return orch.RiskPolicy(min_overall_score=min_score, policy_pack=pack)


def _qid_payload(*, issued_at: int, expires_at: int) -> dict[str, Any]:
    return {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "proof_hash": "proofhash123",
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    }


def _oracle_payload(*, context_hash: str, issued_at: int, expires_at: int, generated_at: int, score: int) -> dict[str, Any]:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": context_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "generated_at": generated_at,
        "overall_score": score,
        "signals": [{"source": "ac_model", "severity": 10, "reason_ids": ["AC_OK"]}],
        "oracle_version": "adaptive-core/3.0.0",
        "external_source_id": "ac-prod-1",
    }


def _shield_signal(*, layer: str, signal_id: str, context_hash: str, ext_reason: str = "OK") -> dict[str, Any]:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "layer_version": "1.0.0",
        "signal_id": signal_id,
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "verdict": "allow",
        "reason_id": ext_reason,
        "confidence": 90,
        "facts": {"k": "v"},
        "meta": {},
    }


def _shield_bundle(*, context_hash: str, required_layers: list[str]) -> dict[str, Any]:
    signals = [
        _shield_signal(layer="adn", signal_id="a-1", context_hash=context_hash),
        _shield_signal(layer="dqsn", signal_id="d-1", context_hash=context_hash),
        _shield_signal(layer="guardian_wallet", signal_id="g-1", context_hash=context_hash),
        _shield_signal(layer="qwg", signal_id="q-1", context_hash=context_hash),
        _shield_signal(layer="sentinel_ai", signal_id="s-1", context_hash=context_hash),
    ]
    return {
        "v": "shield_bundle_v3",
        "shield_bundle_version": "1.0.0",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "required_layers": required_layers,
        "signals": signals,
        "meta": {},
    }


def _envelope_v2(
    *,
    now: int,
    context_hash: str,
    shield_context_hash: str | None = None,
    shield_required_layers: list[str],
    oracle_score: int,
    with_wsqk: bool,
) -> dict[str, Any]:
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"
    issued_at = 1706990400
    expires_at = 1706990460

    proofs: dict[str, Any] = {}
    if with_wsqk:
        proofs["wsqk"] = {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": context_hash,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": "n1",
        }

    return {
        "v": "execution_request_v2",
        "request_id": "req-1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "app",
            "session_id": "s1",
            "action": "send",
            "fields": {"asset": "DGB", "amount": "1"},
        },
        "authority": {"class": "user", "scope": {"policy_pack": "default"}, "proofs": proofs},
        "timebox": {"issued_at": issued_iso, "expires_at": expires_iso},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": _qid_payload(issued_at=now - 10, expires_at=now + 10),
                "oracle": _oracle_payload(
                    context_hash=context_hash,
                    issued_at=now - 5,
                    expires_at=now + 5,
                    generated_at=now - 1,
                    score=oracle_score,
                ),
                "shield": _shield_bundle(
                    context_hash=(shield_context_hash if shield_context_hash is not None else context_hash),
                    required_layers=shield_required_layers,
                ),
            },
            "body": {"ui_confirmed": True},
        },
    }


@dataclass(frozen=True)
class Evidence:
    state: str = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    outcome: str = "ALLOW_EVIDENCE"
    reason_id: ReasonId | str = ReasonId.EVIDENCE_OK
    accepted_as_evidence: bool = True
    final_approval: object = False
    handoff_allowed: bool = True
    context_hash: str = "a" * 64
    dominant_reason_ids: tuple[str, ...] = (ReasonId.EVIDENCE_OK.value,)
    final_outcome: str | None = None
    metadata: object = field(default_factory=dict)


class SlottedFinalApprovalEvidence:
    __slots__ = "final_approval"

    def __init__(self, value: object) -> None:
        self.final_approval = value


class SlottedHiddenAuthorityEvidence:
    __slots__ = ("accepted_as_evidence", "handoff_allowed", "context_hash", "metadata", "final_approval")

    def __init__(self) -> None:
        self.accepted_as_evidence = True
        self.handoff_allowed = True
        self.context_hash = "a" * 64
        self.metadata = {"nested": {"broadcast": True}}
        self.final_approval = False


class StringSlotsHiddenAuthorityEvidence:
    __slots__ = "metadata"

    def __init__(self) -> None:
        self.metadata = {"override": True}


def gates() -> dict[str, LocalPolicyGateResult]:
    return {
        "replay": LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
        "wallet_policy": LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
        "human": LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
    }


def test_claude_f1_live_runtime_invokes_final_policy_before_executor(monkeypatch) -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(orch.REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=99,
        with_wsqk=True,
    )
    executor = RecordingExecutor()

    def deny_final_policy(**kwargs):
        assert kwargs["expected_context_hash"] == ctx_hash
        return FinalPolicyEngineResult(
            state=FinalPolicyEngineState.DENY_HUMAN_GATE,
            outcome="DENY",
            reason_id="NOT_A_VALID_REASON",
            final_approval=False,
            handoff_allowed=False,
            stopped_at="human",
            evaluation_order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay", "wallet_policy", "human"),
            dominant_reason_ids=("NOT_A_VALID_REASON",),
        )

    monkeypatch.setattr(orch, "evaluate_final_policy_engine", deny_final_policy)
    resp = orch.orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(min_score=85),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.UNKNOWN_EXTERNAL_REASON.value
    assert resp["artifacts"]["final_policy"]["state"] == FinalPolicyEngineState.DENY_HUMAN_GATE.value
    assert executor.called is False


def test_runtime_final_policy_reason_accepts_real_reason_id() -> None:
    result = FinalPolicyEngineResult(
        state=FinalPolicyEngineState.DENY_HUMAN_GATE,
        outcome="DENY",
        reason_id=ReasonId.DENY_POLICY,
        final_approval=False,
        handoff_allowed=False,
        stopped_at="human",
        evaluation_order=("human",),
        dominant_reason_ids=(),
    )
    assert orch._runtime_final_policy_reason(result) is ReasonId.DENY_POLICY


def test_runtime_final_policy_reason_handles_non_string_reason() -> None:
    result = FinalPolicyEngineResult(
        state=FinalPolicyEngineState.DENY_HUMAN_GATE,
        outcome="DENY",
        reason_id=object(),  # type: ignore[arg-type]
        final_approval=False,
        handoff_allowed=False,
        stopped_at="human",
        evaluation_order=("human",),
        dominant_reason_ids=(),
    )
    assert orch._runtime_final_policy_reason(result) is ReasonId.UNKNOWN_EXTERNAL_REASON


def test_claude_f2_cross_context_splice_denies_at_engine() -> None:
    bad = Evidence(context_hash="b" * 64)
    result = evaluate_final_policy_engine(
        shield=bad,
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        expected_context_hash="a" * 64,
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.DENY_CONTEXT_MISMATCH
    assert result.reason_id is ReasonId.EQC_CONFLICTING_EVIDENCE


def test_claude_f3_truthy_final_approval_and_slots_are_authority_bypass() -> None:
    result = evaluate_final_policy_engine(
        shield=SlottedFinalApprovalEvidence("yes"),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS


def test_claude_f4_deny_dominates_over_human_review_signal() -> None:
    result = evaluate_final_policy_engine(
        shield=Evidence(
            state=FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED.value,
            outcome=FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED.value,
            accepted_as_evidence=False,
            handoff_allowed=False,
            reason_id=ReasonId.DENY_POLICY,
            dominant_reason_ids=(ReasonId.DENY_POLICY.value,),
        ),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.outcome == "DENY"


def test_claude_f5_slots_and_nested_containers_are_scanned() -> None:
    result = evaluate_final_policy_engine(
        shield=SlottedHiddenAuthorityEvidence(),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        expected_context_hash="a" * 64,
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS


def test_claude_f5_set_container_scan_branch_is_locked() -> None:
    result = evaluate_final_policy_engine(
        shield=Evidence(metadata={"safe_set": {"safe"}}),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION


def test_claude_f6_human_review_requires_exact_status_not_substring() -> None:
    result = evaluate_final_policy_engine(
        shield=Evidence(state="NOT_HUMAN_REVIEW_REQUIRED_BUT_CONTAINS_TOKEN"),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION


def test_claude_f7_unknown_reason_ids_are_sanitized_at_engine_layer() -> None:
    result = evaluate_final_policy_engine(
        shield=Evidence(accepted_as_evidence=False, handoff_allowed=False, reason_id="FAKE_REASON", dominant_reason_ids=("FAKE_REASON",)),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        **gates(),
    )
    assert result.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON
    assert result.dominant_reason_ids == (ReasonId.UNKNOWN_EXTERNAL_REASON.value,)


def test_engine_sanitizes_non_string_local_gate_reason() -> None:
    result = evaluate_final_policy_engine(
        shield=Evidence(),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        replay=LocalPolicyGateResult("replay", False, object()),  # type: ignore[arg-type]
        wallet_policy=LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
        human=LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
    )
    assert result.reason_id is not ReasonId.OK_ALLOW
    assert result.dominant_reason_ids == (ReasonId.UNKNOWN_EXTERNAL_REASON.value,)


def test_string_slots_hidden_authority_branch_is_locked() -> None:
    result = evaluate_final_policy_engine(
        shield=StringSlotsHiddenAuthorityEvidence(),
        wsqk_v2=Evidence(),
        qid=Evidence(),
        adaptive_core=Evidence(),
        ai_gateway=Evidence(),
        **gates(),
    )
    assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS


def _v1_envelope(now: int, context_hash: str) -> dict[str, Any]:
    issued_at = 1706990400
    expires_at = 1706990460
    return {
        "v": "execution_request_v1",
        "request_id": "req-v1-m18",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "app",
            "session_id": "s1",
            "action": "SEND",
            "fields": {"amount": "10", "to": "DGB1"},
        },
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "proofs": {
                "wsqk": {
                    "wallet_id": "w1",
                    "action": "SEND",
                    "context_hash": context_hash,
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "nonce": "nonce-1",
                }
            },
        },
        "timebox": {"issued_at": "2024-02-03T20:00:00Z", "expires_at": "2024-02-03T20:01:00Z"},
        "nonce": {"value": "nonce-1", "store": "tva", "mode": "single_use"},
        "payload": {
            "ui_confirmed": True,
            "evidence": {
                "qid": {
                    "qid_iface_version": "qid-session-v0",
                    "subject": "did:example:123",
                    "issued_at": now - 50,
                    "expires_at": now + 50,
                    "proof_hash": "proofhash123",
                    "device_binding": "device-1",
                    "issuer_version": "qid-v0",
                },
                "risk": {
                    "ac_iface_version": "adaptive-core-risk-v0",
                    "context_hash": context_hash,
                    "generated_at": now - 10,
                    "overall_score": 95,
                    "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"]}],
                    "oracle_version": "ac-v0",
                    "external_source_id": "rpt-1",
                },
            },
        },
        "audit": {"platform": "ios", "client_version": "0.1.0"},
    }


def test_claude_n2_legacy_v1_executes_only_after_final_policy(monkeypatch) -> None:
    import adamantine.v1.execution.orchestrator_v1 as legacy

    now = 1706990400
    fields = {"amount": "10", "to": "DGB1"}
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=fields)
    payload = _v1_envelope(now, ctx_hash)
    executor = RecordingExecutor()

    def deny_final_policy(**kwargs):
        assert kwargs["expected_context_hash"] == ctx_hash
        return FinalPolicyEngineResult(
            state=FinalPolicyEngineState.DENY_HUMAN_GATE,
            outcome="DENY",
            reason_id="NOT_A_VALID_REASON",
            final_approval=False,
            handoff_allowed=False,
            stopped_at="human",
            evaluation_order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay", "wallet_policy", "human"),
            dominant_reason_ids=("NOT_A_VALID_REASON",),
        )

    monkeypatch.setattr(legacy, "evaluate_final_policy_engine", deny_final_policy)
    resp = legacy.orchestrate_execution_v1(
        payload=payload,
        now=now,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(min_score=85),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.UNKNOWN_EXTERNAL_REASON.value
    assert resp["artifacts"]["final_policy"]["state"] == FinalPolicyEngineState.DENY_HUMAN_GATE.value
    assert executor.called is False


def test_claude_n1_eqc_deny_reaches_final_policy_engine(monkeypatch) -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(orch.REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=50,
        with_wsqk=True,
    )
    observed: dict[str, Any] = {}
    real_engine = orch.evaluate_final_policy_engine

    def observe_engine(**kwargs):
        result = real_engine(**kwargs)
        observed["stopped_at"] = result.stopped_at
        observed["state"] = result.state.value
        observed["shield_source"] = kwargs["shield"].source
        observed["adaptive_core_source"] = kwargs["adaptive_core"].source
        return result

    monkeypatch.setattr(orch, "evaluate_final_policy_engine", observe_engine)
    executor = RecordingExecutor()
    resp = orch.orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(min_score=85),
    )

    assert resp["status"] == "deny"
    assert observed["stopped_at"] == "wallet_policy"
    assert observed["state"] == FinalPolicyEngineState.DENY_WALLET_POLICY_GATE.value
    assert observed["shield_source"].startswith("shield:")
    assert observed["adaptive_core_source"] == "adaptive_core:oracle_v3"
    assert executor.called is False


def test_claude_n2_v1_final_policy_reason_sanitizes_bad_values() -> None:
    import adamantine.v1.execution.orchestrator_v1 as legacy

    class StringReason:
        reason_id = "NOT_A_VALID_REASON"

    class ObjectReason:
        reason_id = object()

    class EnumReason:
        reason_id = ReasonId.DENY_POLICY

    assert legacy._v1_final_policy_reason(StringReason()) is ReasonId.UNKNOWN_EXTERNAL_REASON
    assert legacy._v1_final_policy_reason(ObjectReason()) is ReasonId.UNKNOWN_EXTERNAL_REASON
    assert legacy._v1_final_policy_reason(EnumReason()) is ReasonId.DENY_POLICY
