from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class EvidenceWithHiddenAuthority(Evidence):
    sign: bool = False
    broadcast: bool = False
    grant_execution: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


def allow_evidence() -> Evidence:
    return Evidence()


def deny_evidence(reason: ReasonId | str) -> Evidence:
    return Evidence(
        state="DENY_EVIDENCE_REJECTED",
        outcome="DENY",
        reason_id=reason,
        accepted_as_evidence=False,
        handoff_allowed=False,
        dominant_reason_ids=(reason.value if isinstance(reason, ReasonId) else reason,),
    )


def review_evidence(reason: ReasonId | str = ReasonId.DENY_AUTHORITY_INSUFFICIENT) -> Evidence:
    return Evidence(
        state="HUMAN_REVIEW_REQUIRED",
        outcome="HUMAN_REVIEW_REQUIRED",
        reason_id=reason,
        final_outcome="HUMAN_REVIEW_REQUIRED",
        dominant_reason_ids=(reason.value if isinstance(reason, ReasonId) else reason,),
    )


def gate(name: str, passed: bool = True, reason: ReasonId | str = ReasonId.EVIDENCE_OK, review: bool = False) -> LocalPolicyGateResult:
    return LocalPolicyGateResult(name, passed, reason, requires_human_review=review)


def run_engine(**overrides):
    args = {
        "shield": allow_evidence(),
        "wsqk_v2": allow_evidence(),
        "qid": allow_evidence(),
        "adaptive_core": allow_evidence(),
        "ai_gateway": allow_evidence(),
        "replay": gate("replay"),
        "wallet_policy": gate("wallet_policy"),
        "human": gate("human"),
    }
    args.update(overrides)
    return evaluate_final_policy_engine(**args)


def assert_stopped(result, *, state, stopped_at, order):
    assert result.state == state
    assert result.outcome in {"DENY", "HUMAN_REVIEW_REQUIRED"}
    assert result.final_approval is False
    assert result.handoff_allowed is False
    assert result.stopped_at == stopped_at
    assert result.evaluation_order == order


def test_16g_all_connected_evidence_and_local_gates_still_require_final_adamantineos_decision():
    result = run_engine()

    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION
    assert result.final_approval is True
    assert result.handoff_allowed is True
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


def test_16g_missing_each_required_evidence_source_fails_closed_at_that_gate():
    expected_orders = {
        "shield": ("shield",),
        "wsqk_v2": ("shield", "wsqk_v2"),
        "qid": ("shield", "wsqk_v2", "qid"),
        "adaptive_core": ("shield", "wsqk_v2", "qid", "adaptive_core"),
        "ai_gateway": ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway"),
    }

    for source, order in expected_orders.items():
        result = run_engine(**{source: None})
        assert_stopped(
            result,
            state=FinalPolicyEngineState.DENY_MISSING_EVIDENCE,
            stopped_at=source,
            order=order,
        )
        assert result.dominant_reason_ids == (f"MISSING_EVIDENCE:{source}",)


def test_16g_deny_dominates_in_locked_evidence_order():
    cases = (
        ("shield", ReasonId.EQC_INVALID_SHIELD_BUNDLE, ("shield",)),
        ("wsqk_v2", ReasonId.DENY_WSQK, ("shield", "wsqk_v2")),
        ("qid", ReasonId.EQC_INVALID_QID_PROOF, ("shield", "wsqk_v2", "qid")),
        ("adaptive_core", ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD, ("shield", "wsqk_v2", "qid", "adaptive_core")),
        ("ai_gateway", ReasonId.DENY_ADAPTER_INVALID, ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway")),
    )

    for source, reason, order in cases:
        result = run_engine(**{source: deny_evidence(reason)})
        assert_stopped(
            result,
            state=FinalPolicyEngineState.DENY_EVIDENCE_REJECTED,
            stopped_at=source,
            order=order,
        )
        assert result.dominant_reason_ids == (reason.value,)


def test_16g_human_review_from_any_evidence_source_never_becomes_autonomous_allow():
    cases = (
        ("shield", ("shield",)),
        ("wsqk_v2", ("shield", "wsqk_v2")),
        ("qid", ("shield", "wsqk_v2", "qid")),
        ("adaptive_core", ("shield", "wsqk_v2", "qid", "adaptive_core")),
        ("ai_gateway", ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway")),
    )

    for source, order in cases:
        result = run_engine(**{source: review_evidence()})
        assert_stopped(
            result,
            state=FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED,
            stopped_at=source,
            order=order,
        )


def test_16g_local_gates_cannot_be_skipped_after_all_external_evidence_allows():
    replay = run_engine(replay=gate("replay", False, ReasonId.DENY_NONCE_REPLAY))
    assert_stopped(
        replay,
        state=FinalPolicyEngineState.DENY_REPLAY_GATE,
        stopped_at="replay",
        order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay"),
    )

    wallet = run_engine(wallet_policy=gate("wallet_policy", False, ReasonId.DENY_POLICY))
    assert_stopped(
        wallet,
        state=FinalPolicyEngineState.DENY_WALLET_POLICY_GATE,
        stopped_at="wallet_policy",
        order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay", "wallet_policy"),
    )

    human = run_engine(human=gate("human", False, ReasonId.DENY_AUTHORITY_INSUFFICIENT))
    assert_stopped(
        human,
        state=FinalPolicyEngineState.DENY_HUMAN_GATE,
        stopped_at="human",
        order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay", "wallet_policy", "human"),
    )


def test_16g_human_review_local_gate_blocks_autonomous_approval():
    result = run_engine(human=gate("human", True, "HUMAN_REVIEW_REQUIRED_EXACT_CONTEXT", review=True))

    assert_stopped(
        result,
        state=FinalPolicyEngineState.HUMAN_REVIEW_REQUIRED,
        stopped_at="human",
        order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay", "wallet_policy", "human"),
    )
    assert result.reason_id == "HUMAN_REVIEW_REQUIRED_EXACT_CONTEXT"


def test_16g_upstream_final_approval_attempt_from_each_evidence_source_fails_closed():
    for source in ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway"):
        result = run_engine(**{source: Evidence(final_approval=True)})
        assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS
        assert result.reason_id == ReasonId.DENY_AUTHORITY_INVALID
        assert result.stopped_at == source
        assert result.dominant_reason_ids == (f"UPSTREAM_FINAL_APPROVAL_BYPASS:{source}",)
        assert result.final_approval is False


def test_16g_hidden_signing_and_execution_authority_fields_fail_closed():
    cases = (
        ("shield", EvidenceWithHiddenAuthority(sign=True)),
        ("wsqk_v2", EvidenceWithHiddenAuthority(broadcast=True)),
        ("qid", EvidenceWithHiddenAuthority(grant_execution=True)),
        ("adaptive_core", EvidenceWithHiddenAuthority(metadata={"override": True})),
        ("ai_gateway", EvidenceWithHiddenAuthority(metadata={"nested": {"trusted": True}})),
    )

    for source, evidence in cases:
        result = run_engine(**{source: evidence})
        assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS
        assert result.reason_id == ReasonId.DENY_AUTHORITY_INVALID
        assert result.stopped_at == source
        assert result.dominant_reason_ids == (f"HIDDEN_AUTHORITY_BYPASS:{source}",)
        assert result.final_approval is False


def test_16g_handoff_blocked_from_any_evidence_source_fails_before_local_gates():
    for source in ("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway"):
        result = run_engine(**{source: Evidence(handoff_allowed=False)})
        assert result.state == FinalPolicyEngineState.DENY_HANDOFF_BLOCKED
        assert result.stopped_at == source
        assert result.final_approval is False


def test_16g_invalid_local_gate_shape_cannot_be_reused_as_human_approval():
    result = run_engine(human={"gate": "human", "passed": True, "context_hash": "different-context"})

    assert_stopped(
        result,
        state=FinalPolicyEngineState.DENY_GATE_SHAPE_INVALID,
        stopped_at="human",
        order=("shield", "wsqk_v2", "qid", "adaptive_core", "ai_gateway", "replay", "wallet_policy", "human"),
    )
    assert result.dominant_reason_ids == ("INVALID_LOCAL_GATE:human",)


def test_16g_external_dependency_failure_shape_never_becomes_allow():
    unavailable = Evidence(
        state="DENY_EXTERNAL_DEPENDENCY_UNAVAILABLE",
        outcome="DENY",
        reason_id=ReasonId.DENY_ADAPTER_UNAVAILABLE,
        accepted_as_evidence=False,
        handoff_allowed=False,
        dominant_reason_ids=(ReasonId.DENY_ADAPTER_UNAVAILABLE.value,),
    )

    result = run_engine(ai_gateway=unavailable)

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.reason_id == ReasonId.DENY_ADAPTER_UNAVAILABLE.value
    assert result.stopped_at == "ai_gateway"
    assert result.final_approval is False


def test_16g_mapping_evidence_with_authority_key_fails_closed_before_shape_fallback():
    result = run_engine(qid={"accepted_as_evidence": True, "handoff_allowed": True, "override": True})

    assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS
    assert result.stopped_at == "qid"
    assert result.dominant_reason_ids == ("HIDDEN_AUTHORITY_BYPASS:qid",)


def test_16g_mapping_evidence_with_nested_authority_list_fails_closed():
    result = run_engine(adaptive_core={"metadata": [{"trusted": True}]})

    assert result.state == FinalPolicyEngineState.DENY_AUTHORITY_BYPASS
    assert result.stopped_at == "adaptive_core"


def test_16g_plain_object_without_evidence_shape_fails_closed_as_rejected_evidence():
    class PlainObject:
        pass

    result = run_engine(ai_gateway=PlainObject())

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.stopped_at == "ai_gateway"


def test_16g_non_string_object_attributes_are_ignored_but_shape_still_checked():
    class OddEvidence:
        accepted_as_evidence = True
        handoff_allowed = True
        final_approval = False

        def __init__(self):
            self.__dict__[1] = "non-string-key"

    result = run_engine(shield=OddEvidence())

    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION
    assert result.final_approval is True


def test_16g_slot_only_object_without_mapping_state_fails_closed():
    class SlotOnlyEvidence:
        __slots__ = ()

    result = run_engine(wsqk_v2=SlotOnlyEvidence())

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.stopped_at == "wsqk_v2"
