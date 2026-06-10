from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.adaptive_core_policy_evidence import (
    AdaptiveCorePolicyEvidenceState,
    normalize_adaptive_core_policy_evidence,
)

FIXTURE = Path(
    "tests/fixtures/adaptive_core_external_baseline/adaptive_core_adamantine_advisory_evidence_v1.json"
)
CTX = "a" * 64
NOW = 1_760_000_200


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _run(value: object):
    return normalize_adaptive_core_policy_evidence(
        value,
        now=NOW,
        expected_context_hash=CTX,
        reason_map=PolicyPack().external_reason_map,
    )


def test_milestone_16e_external_adaptive_core_export_shape_is_evidence_only() -> None:
    result = _run(_fixture())

    assert result.state is AdaptiveCorePolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id is ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.handoff_allowed is True
    assert result.final_approval is False
    assert result.source == "adaptive_core"
    assert result.context_hash == CTX
    assert result.overall_score == 91
    assert result.issued_at == 1_760_000_000
    assert result.expires_at == 1_760_003_600
    assert result.oracle_version == "adaptive-core/3.0.0"
    assert result.external_source_id == "adaptive-core-v3-adamantine-export"
    assert result.report is not None
    assert result.oracle is not None


def test_milestone_16e_external_adaptive_core_evidence_alone_is_not_final_approval() -> None:
    result = _run(_fixture())

    assert result.accepted_as_evidence is True
    assert result.handoff_allowed is True
    assert result.final_approval is False
    assert result.outcome == "ALLOW_EVIDENCE"


def test_milestone_16e_external_adaptive_core_hidden_authority_field_denies() -> None:
    payload = _fixture()
    payload["final_approval"] = True

    result = _run(payload)

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.handoff_allowed is False


def test_milestone_16e_external_adaptive_core_context_mismatch_denies() -> None:
    payload = _fixture()
    payload["context_hash"] = "b" * 64

    result = _run(payload)

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16e_external_adaptive_core_low_score_denies() -> None:
    payload = _fixture()
    payload["overall_score"] = 84

    result = _run(payload)

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_SCORE_BELOW_THRESHOLD
    assert result.reason_id is ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


@dataclass(frozen=True)
class _PriorResult:
    outcome: str
    reason_id: ReasonId


def test_milestone_16e_prior_gate_deny_dominates_adaptive_core_success() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _fixture(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=PolicyPack().external_reason_map,
        prior_gate_results=[_PriorResult(outcome="DENY", reason_id=ReasonId.DENY_WSQK)],
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_EARLIER_GATE_DENIED
    assert result.reason_id == ReasonId.DENY_WSQK.value
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.report is None
    assert result.oracle is None


def test_milestone_16e_external_import_failure_shape_is_not_allow() -> None:
    result = _run(
        {
            "source": "DigiByte-Adaptive-Core",
            "error": "ImportError",
            "message": "external Adaptive Core package unavailable",
        }
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16e_missing_or_unknown_external_fields_fail_closed() -> None:
    missing = _fixture()
    missing.pop("signals")
    unknown = _fixture()
    unknown["unexpected"] = "value"

    missing_result = _run(missing)
    unknown_result = _run(unknown)

    assert missing_result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert missing_result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT
    assert unknown_result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert unknown_result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT
