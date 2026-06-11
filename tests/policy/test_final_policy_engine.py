from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)


@dataclass(frozen=True)
class Evidence:
    state: str = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    outcome: str = "ALLOW_EVIDENCE"
    reason_id: ReasonId | str = ReasonId.EVIDENCE_OK
    accepted_as_evidence: bool = True
    final_approval: bool = False
    handoff_allowed: bool = True
    dominant_reason_ids: tuple[str, ...] = (ReasonId.EVIDENCE_OK.value,)
    final_outcome: str | None = None


def allow_evidence() -> Evidence:
    return Evidence()


def allow_gates() -> dict[str, LocalPolicyGateResult]:
    return {
        "replay": LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
        "wallet_policy": LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
        "human": LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
    }


def run_engine(**overrides):
    gates = allow_gates()
    args = {
        "shield": allow_evidence(),
        "wsqk_v2": allow_evidence(),
        "qid": allow_evidence(),
        "adaptive_core": allow_evidence(),
        "ai_gateway": allow_evidence(),
        **gates,
    }
    args.update(overrides)
    return evaluate_final_policy_engine(**args)


def test_all_evidence_and_local_gates_pass_before_final_adamantineos_approval():
    result = run_engine()

    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION
    assert result.outcome == "ALLOW"
    assert result.reason_id == ReasonId.OK_ALLOW
    assert result.final_approval is True
    assert result.handoff_allowed is True
    assert result.stopped_at == "final_adamantineos_decision"
    assert result.evaluation_order == (
        "shield",
        "wsqk_v2",
        "qid",
        "adaptive_core",
        "ai_gateway",
        "replay",
        "wallet_policy",
        "human",
        "final_adamantineos_decision",
    )
    assert result.dominant_reason_ids == (ReasonId.OK_ALLOW.value,)


def test_missing_shield_evidence_fails_closed_before_wsqk():
    result = run_engine(shield=None)

    assert result.state == FinalPolicyEngineState.DENY_MISSING_EVIDENCE
    assert result.outcome == "DENY"
    assert result.stopped_at == "shield"
    assert result.evaluation_order == ("shield",)
    assert result.dominant_reason_ids == ("MISSING_EVIDENCE:shield",)
    assert result.final_approval is False


def test_shield_deny_stops_before_wsqk():
    result = run_engine(
        shield=Evidence(
            state="LIVE_DENY_DOMINATES_BLOCK",
            outcome="DENY",
            reason_id=ReasonId.DENY_POLICY,
            accepted_as_evidence=False,
            handoff_allowed=False,
            dominant_reason_ids=("SHIELD_DENY",),
        )
    )

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON
    assert result.stopped_at == "shield"
    assert result.evaluation_order == ("shield",)


def test_wsqk_deny_stops_before_qid():
    result = run_engine(
        wsqk_v2=Evidence(
            state="DENY_WSQK_REJECTED",
            outcome="DENY",
            reason_id=ReasonId.DENY_WSQK,
            accepted_as_evidence=False,
            handoff_allowed=False,
            dominant_reason_ids=(ReasonId.DENY_WSQK.value,),
        )
    )

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.reason_id == ReasonId.DENY_WSQK.value
    assert result.stopped_at == "wsqk_v2"
    assert result.evaluation_order == ("shield", "wsqk_v2")


def test_qid_deny_stops_before_adaptive_core():
    result = run_engine(
        qid=Evidence(
            state="DENY_QID_REJECTED",
            outcome="DENY",
            reason_id=ReasonId.EQC_INVALID_QID_PROOF,
            accepted_as_evidence=False,
            handoff_allowed=False,
            dominant_reason_ids=(ReasonId.EQC_INVALID_QID_PROOF.value,),
        )
    )

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.stopped_at == "qid"
    assert result.evaluation_order == ("shield", "wsqk_v2", "qid")


def test_adaptive_core_deny_stops_before_ai_gateway():
    result = run_engine(
        adaptive_core=Evidence(
            state="DENY_SCORE_BELOW_THRESHOLD",
            outcome="DENY",
            reason_id=ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD,
            accepted_as_evidence=False,
            handoff_allowed=False,
            dominant_reason_ids=(ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value,),
        )
    )

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.stopped_at == "adaptive_core"
    assert result.evaluation_order == ("shield", "wsqk_v2", "qid", "adaptive_core")


def test_ai_gateway_deny_stops_before_replay_gate():
    result = run_engine(
        ai_gateway=Evidence(
            state="DENY_AI_GATEWAY_REJECTED",
            outcome="DENY",
            reason_id="AI_GATEWAY_POLICY_REJECTED",
            accepted_as_evidence=False,
            handoff_allowed=False,
            dominant_reason_ids=("AI_GATEWAY_POLICY_REJECTED",),
        )
    )

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON
    assert result.stopped_at == "ai_gateway"
    assert result.evaluation_order == ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway")


def test_upstream_final_approval_attempt_is_authority_bypass():
    result = run_engine(wsqk_v2=Evidence(final_approval=True))

    assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS
    assert result.reason_id == ReasonId.DENY_AUTHORITY_INVALID
    assert result.stopped_at == "wsqk_v2"
    assert result.dominant_reason_ids == ("UPSTREAM_FINAL_APPROVAL_BYPASS:wsqk_v2",)


def test_evidence_handoff_false_blocks_even_when_accepted():
    result = run_engine(ai_gateway=Evidence(handoff_allowed=False))

    assert result.state == FinalPolicyEngineState.DENY_HANDOFF_BLOCKED
    assert result.stopped_at == "ai_gateway"
    assert result.final_approval is False


def test_human_review_from_evidence_stops_without_autonomous_allow():
    result = run_engine(
        shield=Evidence(
            state="LIVE_HUMAN_REVIEW_REQUIRED",
            outcome="ALLOW_EVIDENCE",
            final_outcome="HUMAN_REVIEW_REQUIRED",
            reason_id=ReasonId.DENY_AUTHORITY_INSUFFICIENT,
            dominant_reason_ids=(ReasonId.DENY_AUTHORITY_INSUFFICIENT.value,),
        )
    )

    assert result.state == FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED
    assert result.outcome == "HUMAN_REVIEW_REQUIRED"
    assert result.stopped_at == "shield"
    assert result.final_approval is False
    assert result.handoff_allowed is False


def test_replay_gate_deny_after_all_evidence_passes():
    result = run_engine(replay=LocalPolicyGateResult("replay", False, ReasonId.DENY_NONCE_REPLAY))

    assert result.state == FinalPolicyEngineState.DENY_REPLAY_GATE
    assert result.reason_id == ReasonId.DENY_NONCE_REPLAY
    assert result.stopped_at == "replay"
    assert result.evaluation_order == ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay")


def test_wallet_policy_gate_deny_after_replay_passes():
    result = run_engine(wallet_policy=LocalPolicyGateResult("wallet_policy", False, ReasonId.DENY_POLICY))

    assert result.state == FinalPolicyEngineState.DENY_WALLET_POLICY_GATE
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.stopped_at == "wallet_policy"


def test_human_gate_deny_blocks_final_approval():
    result = run_engine(human=LocalPolicyGateResult("human", False, ReasonId.DENY_AUTHORITY_INSUFFICIENT))

    assert result.state == FinalPolicyEngineState.DENY_HUMAN_GATE
    assert result.reason_id == ReasonId.DENY_AUTHORITY_INSUFFICIENT
    assert result.stopped_at == "human"
    assert result.final_approval is False


def test_local_gate_can_require_human_review_without_allowing():
    result = run_engine(wallet_policy=LocalPolicyGateResult("wallet_policy", True, "WALLET_POLICY_REQUIRES_HUMAN", requires_human_review=True))

    assert result.state == FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED
    assert result.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON
    assert result.stopped_at == "wallet_policy"
    assert result.final_approval is False


def test_invalid_local_gate_shape_fails_closed():
    result = run_engine(replay=LocalPolicyGateResult("wrong_gate", True, ReasonId.EVIDENCE_OK))

    assert result.state == FinalPolicyEngineState.DENY_GATE_SHAPE_INVALID
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.stopped_at == "replay"
    assert result.dominant_reason_ids == ("INVALID_LOCAL_GATE:replay",)


def test_invalid_local_gate_object_fails_closed():
    result = run_engine(human={"gate": "human", "passed": True})

    assert result.state == FinalPolicyEngineState.DENY_GATE_SHAPE_INVALID
    assert result.stopped_at == "human"


def test_reason_fallback_uses_reason_id_when_dominant_reasons_empty():
    result = run_engine(
        qid=Evidence(
            state="DENY_QID_REJECTED",
            accepted_as_evidence=False,
            handoff_allowed=False,
            reason_id=ReasonId.QID_REPLAY_NONCE_MISMATCH,
            dominant_reason_ids=(),
        )
    )

    assert result.reason_id == ReasonId.QID_REPLAY_NONCE_MISMATCH
    assert result.dominant_reason_ids == (ReasonId.QID_REPLAY_NONCE_MISMATCH.value,)


def test_reason_fallback_uses_policy_when_reason_id_missing():
    class BrokenEvidence:
        accepted_as_evidence = False
        final_approval = False
        handoff_allowed = False
        dominant_reason_ids = ()

    result = run_engine(adaptive_core=BrokenEvidence())

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.dominant_reason_ids == (ReasonId.DENY_POLICY.value,)


def test_non_string_dominant_reasons_are_ignored():
    result = run_engine(
        ai_gateway=Evidence(
            accepted_as_evidence=False,
            handoff_allowed=False,
            reason_id="AI_REASON",
            dominant_reason_ids=("", 123, "AI_REASON"),
        )
    )

    assert result.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON
    assert result.dominant_reason_ids == (ReasonId.UNKNOWN_EXTERNAL_REASON.value,)
