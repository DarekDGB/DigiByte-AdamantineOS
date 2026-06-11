from __future__ import annotations

from dataclasses import dataclass, field

import adamantine.v1.execution.orchestrator_v2 as orch
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineResult,
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)
from tests.test_execution_orchestrator_v2_matrix import _envelope_v2, _policy


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
