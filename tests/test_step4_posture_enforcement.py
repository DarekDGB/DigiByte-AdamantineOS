from __future__ import annotations

from pathlib import Path

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import load_canonical_json
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


NOW = 1706990400


def _fixture_dir() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "src"
        / "adamantine"
        / "v1"
        / "fixtures"
        / "v1_3_0"
    )


def _policy(*, require_protected_call: bool = False, require_full_mode: bool = False) -> RiskPolicy:
    # Deterministic policy pack to satisfy registry + mapping requirements.
    allowed = ("ok", "OK", "AC_OK", "BLOCK")
    reason_map = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )
    pack = PolicyPack(min_overall_score=85, allowed_external_reason_ids=allowed, external_reason_map=reason_map)
    return RiskPolicy(
        min_overall_score=85,
        policy_pack=pack,
        require_protected_call=require_protected_call,
        require_full_mode=require_full_mode,
    )


def _run(payload: dict, *, policy: RiskPolicy) -> dict:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    return orchestrate_execution_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def test_step4_policy_can_require_protected_call() -> None:
    payload = load_canonical_json(_fixture_dir() / "full_allow.json")
    # Remove WSQK proof request signal -> protected_requested=False.
    payload["authority"]["proofs"] = {}

    resp = _run(payload, policy=_policy(require_protected_call=True))
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_POLICY.value
    assert resp["decision"]["protection_mode"] == "legacy"
    assert resp["artifacts"] == {"error": "policy requires protected execution"}


def test_step4_policy_can_latch_full_mode() -> None:
    payload = load_canonical_json(_fixture_dir() / "full_allow.json")
    # Remove WSQK proof request signal -> protection_mode cannot become full.
    payload["authority"]["proofs"] = {}

    resp = _run(payload, policy=_policy(require_full_mode=True))
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_POLICY.value
    assert resp["decision"]["protection_mode"] == "legacy"
    assert resp["artifacts"] == {"error": "policy requires full protection mode"}
