from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from adamantine.v1.contracts.combined_context_hash import EXPECTED_VALID_HASH
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations.shield_v3_live_orchestrator_harness import (
    ShieldV3LiveOrchestratorHarnessState,
    normalize_live_orchestrator_receipt,
    run_shield_v3_live_orchestrator_harness,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "shield_v3_integration" / "combined_context_hash"
CTX = EXPECTED_VALID_HASH
REQ = "req-000001"
EVID = "b" * 64
COMPONENTS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")


def _context_payload(name: str = "valid_combined_context_hash_v1.json") -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


REASON_BY_COMPONENT_DECISION = {
    "adn": {
        "ALLOW": "ADN_OK_COORDINATION_ALLOW",
        "ESCALATE": "ADN_ESCALATE_POLICY_REVIEW",
        "DENY": "ADN_DENY_DEFENSE_TRIGGERED",
        "ERROR": "ADN_ERROR_INVALID_VERDICT",
        "SKIPPED": "ADN_ERROR_INVALID_VERDICT",
    },
    "dqsn": {
        "ALLOW": "DQSN_OK_NETWORK_ALLOW",
        "ESCALATE": "DQSN_ESCALATE_QUANTUM_SIGNAL",
        "DENY": "DQSN_DENY_NETWORK_RISK",
        "ERROR": "DQSN_ERROR_INVALID_VERDICT",
        "SKIPPED": "DQSN_ERROR_INVALID_VERDICT",
    },
    "guardian_wallet": {
        "ALLOW": "GW_OK_HEALTHY_ALLOW",
        "ESCALATE": "GW_ESCALATE_QID_REQUIRED",
        "DENY": "GW_DENY_POLICY_BLOCKED",
        "ERROR": "GW_ERROR_INVALID_VERDICT",
        "SKIPPED": "GW_ERROR_INVALID_VERDICT",
    },
    "qwg": {
        "ALLOW": "QWG_OK_POSTURE_ALLOW",
        "ESCALATE": "QWG_ESCALATE_QUANTUM_POSTURE",
        "DENY": "QWG_DENY_KEY_RISK",
        "ERROR": "QWG_ERROR_INVALID_VERDICT",
        "SKIPPED": "QWG_ERROR_INVALID_VERDICT",
    },
    "sentinel_ai": {
        "ALLOW": "SNTL_OK_TELEMETRY_ALLOW",
        "ESCALATE": "SNTL_ESCALATE_THREAT_REVIEW",
        "DENY": "SNTL_DENY_THREAT_DETECTED",
        "ERROR": "SNTL_ERROR_AI_OUTPUT_UNTRUSTED",
        "SKIPPED": "SNTL_ERROR_AI_OUTPUT_UNTRUSTED",
    },
}
EVIDENCE_FAMILY_BY_COMPONENT = {
    "adn": "defense_signal",
    "dqsn": "network_observation",
    "guardian_wallet": "wallet_context",
    "qwg": "wallet_posture",
    "sentinel_ai": "telemetry",
}


def _live_component(component_id: str, decision: str = "ALLOW", *, request_id: str = REQ, context_hash: str = CTX) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "contract_version": 3,
        "schema_version": "shield.verdict.v1",
        "request_id": request_id,
        "context_hash": context_hash,
        "decision": decision,
        "reason_ids": [REASON_BY_COMPONENT_DECISION[component_id][decision]],
        "evidence_hash": EVID,
        "evidence_families": [EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
        "metadata": {},
        "fail_closed": True,
    }


def _live_components(decision: str = "ALLOW") -> list[dict[str, Any]]:
    return [_live_component(component, decision) for component in COMPONENTS]


def _classify(components: list[Mapping[str, Any]]) -> tuple[str, list[str], dict[str, Any]]:
    decisions = [str(component["decision"]) for component in components]
    if "DENY" in decisions:
        return "DENY", ["ORCH_DENY_DOMINATES"], {"handoff_allowed": False, "handoff_reason": "ORCH_DENY_DOMINATES"}
    if "ERROR" in decisions:
        return "DENY", ["ORCH_ERROR_INVALID_COMPONENT_VERDICT"], {"handoff_allowed": False, "handoff_reason": "ORCH_ERROR_INVALID_COMPONENT_VERDICT"}
    if "ESCALATE" in decisions:
        return "HUMAN_REVIEW_REQUIRED", ["ORCH_HUMAN_REVIEW_ESCALATE_PRESENT"], {"handoff_allowed": False, "handoff_reason": "ORCH_HUMAN_REVIEW_ESCALATE_PRESENT"}
    return "ALLOW", ["ORCH_OK_ALL_COMPONENTS_ALLOW"], {"handoff_allowed": True, "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW"}


def _live_build_receipt(*, request_id: str, context_hash: str, component_verdicts: list[Mapping[str, Any]]) -> dict[str, Any]:
    final_outcome, dominant_reason_ids, handoff = _classify(list(component_verdicts))
    receipt: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": request_id,
        "context_hash": context_hash,
        "component_verdicts": sorted([dict(item) for item in component_verdicts], key=lambda item: str(item["component_id"])),
        "final_outcome": final_outcome,
        "dominant_reason_ids": dominant_reason_ids,
        "receipt_hash": "",
        "adamantineos_handoff": handoff,
        "fail_closed": True,
    }
    receipt["receipt_hash"] = canonical_sha256(receipt)
    return receipt


def test_level_3_live_harness_accepts_real_orchestrator_allow_as_evidence_only() -> None:
    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=_live_build_receipt,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.LIVE_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.context_hash == CTX
    assert result.request_id == REQ
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.handoff_allowed is True
    assert result.source_receipt_hash is not None
    assert result.normalized_receipt_hash is not None
    assert result.source_receipt_hash == result.normalized_receipt_hash
    assert result.adapter_harness is not None
    assert result.adapter_harness.final_approval is False


def test_level_3_live_harness_maps_orchestrator_deny_to_deny_dominates_block() -> None:
    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=_live_build_receipt,
        component_verdicts=_live_components("DENY"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.LIVE_DENY_DOMINATES_BLOCK
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.final_approval is False
    assert result.final_outcome == "DENY"
    assert result.handoff_allowed is False
    assert result.dominant_reason_ids == ("ORCH_DENY_DOMINATES",)


def test_level_3_live_harness_maps_orchestrator_error_to_deny_block() -> None:
    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=_live_build_receipt,
        component_verdicts=_live_components("ERROR"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.LIVE_DENY_DOMINATES_BLOCK
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.final_outcome == "DENY"
    assert result.final_approval is False


def test_level_3_live_harness_maps_orchestrator_escalate_to_human_review() -> None:
    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=_live_build_receipt,
        component_verdicts=_live_components("ESCALATE"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.LIVE_HUMAN_REVIEW_REQUIRED
    assert result.reason_id == ReasonId.DENY_AUTHORITY_INSUFFICIENT
    assert result.final_outcome == "HUMAN_REVIEW_REQUIRED"
    assert result.handoff_allowed is False
    assert result.final_approval is False


def test_level_3_live_harness_rejects_invalid_combined_context_before_live_call() -> None:
    called = False

    def builder(**kwargs: object) -> dict[str, Any]:
        nonlocal called
        called = True
        return _live_build_receipt(**kwargs)  # type: ignore[arg-type]

    invalid_context = _context_payload()
    invalid_context["timestamp"] = "2026-06-08T00:00:00Z"

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=invalid_context,
        live_receipt_builder=builder,
        component_verdicts=_live_components("ALLOW"),
    )

    assert called is False
    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_CONTEXT_CONTRACT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False
    assert result.adapter_harness is None


def test_level_3_live_harness_rejects_missing_live_builder() -> None:
    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=None,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_ORCHESTRATOR_UNAVAILABLE
    assert result.reason_id == ReasonId.DENY_ADAPTER_UNAVAILABLE
    assert result.final_approval is False
    assert result.dominant_reason_ids == ("LIVE_ORCHESTRATOR_BUILDER_REQUIRED",)


def test_level_3_live_harness_rejects_live_builder_exception_fail_closed() -> None:
    def builder(**kwargs: object) -> dict[str, Any]:
        raise RuntimeError("boom")

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=builder,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_ORCHESTRATOR_EXCEPTION
    assert result.reason_id == ReasonId.DENY_ADAPTER_UNAVAILABLE
    assert result.dominant_reason_ids == ("LIVE_ORCHESTRATOR_EXCEPTION:RuntimeError",)
    assert result.final_approval is False


def test_level_3_live_harness_rejects_tampered_live_receipt_hash() -> None:
    def builder(**kwargs: object) -> dict[str, Any]:
        receipt = _live_build_receipt(**kwargs)  # type: ignore[arg-type]
        receipt["receipt_hash"] = "c" * 64
        return receipt

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=builder,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_LIVE_RECEIPT_TAMPERED
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False
    assert result.adapter_harness is None


def test_level_3_live_harness_rejects_unknown_live_receipt_field() -> None:
    def builder(**kwargs: object) -> dict[str, Any]:
        receipt = _live_build_receipt(**kwargs)  # type: ignore[arg-type]
        receipt["extra"] = True
        receipt["receipt_hash"] = canonical_sha256({**receipt, "receipt_hash": ""})
        return receipt

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=builder,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_LIVE_RECEIPT_SHAPE
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_level_3_live_harness_rejects_source_authority_bypass_before_normalization() -> None:
    components = _live_components("ALLOW")
    components[0]["metadata"] = {"final_approval": True}

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=_live_build_receipt,
        component_verdicts=components,
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_AUTHORITY_BYPASS
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.final_approval is False


def test_level_3_live_harness_rejects_request_mismatch_from_live_receipt() -> None:
    def builder(**kwargs: object) -> dict[str, Any]:
        receipt = _live_build_receipt(**kwargs)  # type: ignore[arg-type]
        receipt["request_id"] = "other-request"
        receipt["receipt_hash"] = canonical_sha256({**receipt, "receipt_hash": ""})
        return receipt

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=builder,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_LIVE_RECEIPT_SHAPE
    assert "request mismatch" in result.dominant_reason_ids[0]
    assert result.final_approval is False


def test_level_3_live_harness_rejects_skipped_component_as_unsafe_for_handoff() -> None:
    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=_live_build_receipt,
        component_verdicts=_live_components("SKIPPED"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_LIVE_RECEIPT_SHAPE
    assert "unsupported live component decision" in result.dominant_reason_ids[0]
    assert result.final_approval is False


def test_level_3_live_harness_rejects_hidden_component_deny_under_live_final_allow() -> None:
    def builder(**kwargs: object) -> dict[str, Any]:
        receipt = _live_build_receipt(**kwargs)  # type: ignore[arg-type]
        receipt["component_verdicts"][0]["decision"] = "DENY"
        component_id = str(receipt["component_verdicts"][0]["component_id"])
        receipt["component_verdicts"][0]["reason_ids"] = [REASON_BY_COMPONENT_DECISION[component_id]["DENY"]]
        receipt["receipt_hash"] = canonical_sha256({**receipt, "receipt_hash": ""})
        return receipt

    result = run_shield_v3_live_orchestrator_harness(
        combined_context_payload=_context_payload(),
        live_receipt_builder=builder,
        component_verdicts=_live_components("ALLOW"),
    )

    assert result.state == ShieldV3LiveOrchestratorHarnessState.REJECTED_ADAPTER_HARNESS
    assert result.reason_id == ReasonId.EQC_CONFLICTING_EVIDENCE
    assert result.dominant_reason_ids == ("REJECTED_RECEIPT_VERIFICATION",)
    assert result.final_approval is False
    assert result.adapter_harness is not None
    assert result.adapter_harness.final_approval is False


def test_normalizer_rejects_non_mapping_live_receipt() -> None:
    try:
        normalize_live_orchestrator_receipt(["bad"], expected_context_hash=CTX, expected_request_id=REQ)
    except ValueError as exc:
        assert "must be object" in str(exc)
    else:
        raise AssertionError("normalizer must reject non-mapping live receipt")


def _valid_live_receipt() -> dict[str, Any]:
    return _live_build_receipt(request_id=REQ, context_hash=CTX, component_verdicts=_live_components("ALLOW"))


def _assert_normalizer_rejects(receipt: Any, text: str, *, context_hash: str = CTX, request_id: str = REQ) -> None:
    try:
        normalize_live_orchestrator_receipt(receipt, expected_context_hash=context_hash, expected_request_id=request_id)
    except ValueError as exc:
        assert text in str(exc)
    else:
        raise AssertionError("normalizer must reject invalid live receipt")


def test_level_3_private_request_id_helper_returns_none_for_non_mapping() -> None:
    from adamantine.v1.integrations.shield_v3_live_orchestrator_harness import _request_id_from_context

    assert _request_id_from_context(["not", "context"]) is None


def test_normalizer_rejects_invalid_source_hash_type_and_non_hex() -> None:
    bad_type = _valid_live_receipt()
    bad_type["receipt_hash"] = 123
    _assert_normalizer_rejects(bad_type, "receipt_hash must be 64-character")

    bad_hex = _valid_live_receipt()
    bad_hex["receipt_hash"] = "g" * 64
    _assert_normalizer_rejects(bad_hex, "receipt_hash must be sha256 hex")


def test_normalizer_rejects_bad_top_level_schema_contract_fail_closed_context_and_outcome() -> None:
    bad_schema = _valid_live_receipt()
    bad_schema["schema_version"] = "bad"
    bad_schema["receipt_hash"] = canonical_sha256({**bad_schema, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_schema, "schema mismatch")

    bad_contract = _valid_live_receipt()
    bad_contract["contract_version"] = 4
    bad_contract["receipt_hash"] = canonical_sha256({**bad_contract, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_contract, "contract mismatch")

    bad_fail_closed = _valid_live_receipt()
    bad_fail_closed["fail_closed"] = False
    bad_fail_closed["receipt_hash"] = canonical_sha256({**bad_fail_closed, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_fail_closed, "must be fail_closed")

    bad_context_hash = _valid_live_receipt()
    bad_context_hash["context_hash"] = "bad"
    bad_context_hash["receipt_hash"] = canonical_sha256({**bad_context_hash, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_context_hash, "context_hash must be 64-character")

    bad_expected_context = _valid_live_receipt()
    _assert_normalizer_rejects(bad_expected_context, "expected_context_hash must be sha256 hex", context_hash="g" * 64)

    bad_outcome = _valid_live_receipt()
    bad_outcome["final_outcome"] = "MAYBE"
    bad_outcome["receipt_hash"] = canonical_sha256({**bad_outcome, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_outcome, "final outcome unsupported")


def test_normalizer_rejects_bad_component_and_handoff_containers() -> None:
    bad_components = _valid_live_receipt()
    bad_components["component_verdicts"] = []
    bad_components["receipt_hash"] = canonical_sha256({**bad_components, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_components, "component verdicts invalid")

    bad_reasons = _valid_live_receipt()
    bad_reasons["dominant_reason_ids"] = []
    bad_reasons["receipt_hash"] = canonical_sha256({**bad_reasons, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_reasons, "dominant reason ids invalid")

    bad_handoff = _valid_live_receipt()
    bad_handoff["adamantineos_handoff"] = []
    bad_handoff["receipt_hash"] = canonical_sha256({**bad_handoff, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_handoff, "handoff invalid")

    bad_handoff_values = _valid_live_receipt()
    bad_handoff_values["adamantineos_handoff"] = {"handoff_allowed": "yes", "handoff_reason": " "}
    bad_handoff_values["receipt_hash"] = canonical_sha256({**bad_handoff_values, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_handoff_values, "handoff values invalid")


def test_normalizer_rejects_bad_live_component_schema_variants() -> None:
    bad_component_object = _valid_live_receipt()
    bad_component_object["component_verdicts"] = ["bad"]
    bad_component_object["receipt_hash"] = canonical_sha256({**bad_component_object, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_object, "component verdict must be object")

    bad_component_fields = _valid_live_receipt()
    bad_component_fields["component_verdicts"][0]["extra"] = True
    bad_component_fields["receipt_hash"] = canonical_sha256({**bad_component_fields, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_fields, "component verdict fields must match")

    bad_component_schema = _valid_live_receipt()
    bad_component_schema["component_verdicts"][0]["schema_version"] = "bad"
    bad_component_schema["receipt_hash"] = canonical_sha256({**bad_component_schema, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_schema, "component schema mismatch")

    bad_component_contract = _valid_live_receipt()
    bad_component_contract["component_verdicts"][0]["contract_version"] = 4
    bad_component_contract["receipt_hash"] = canonical_sha256({**bad_component_contract, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_contract, "component contract mismatch")

    bad_component_fail_closed = _valid_live_receipt()
    bad_component_fail_closed["component_verdicts"][0]["fail_closed"] = False
    bad_component_fail_closed["receipt_hash"] = canonical_sha256({**bad_component_fail_closed, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_fail_closed, "component must be fail_closed")


def test_normalizer_rejects_bad_live_component_binding_and_values() -> None:
    bad_component_request = _valid_live_receipt()
    bad_component_request["component_verdicts"][0]["request_id"] = "other"
    bad_component_request["receipt_hash"] = canonical_sha256({**bad_component_request, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_request, "component request mismatch")

    bad_component_context = _valid_live_receipt()
    bad_component_context["component_verdicts"][0]["context_hash"] = "c" * 64
    bad_component_context["receipt_hash"] = canonical_sha256({**bad_component_context, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_context, "component context mismatch")

    bad_component_id = _valid_live_receipt()
    bad_component_id["component_verdicts"][0]["component_id"] = " "
    bad_component_id["receipt_hash"] = canonical_sha256({**bad_component_id, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_component_id, "component_id invalid")

    bad_decision = _valid_live_receipt()
    bad_decision["component_verdicts"][0]["decision"] = "MAYBE"
    bad_decision["receipt_hash"] = canonical_sha256({**bad_decision, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_decision, "component decision unsupported")

    bad_reason_ids = _valid_live_receipt()
    bad_reason_ids["component_verdicts"][0]["reason_ids"] = []
    bad_reason_ids["receipt_hash"] = canonical_sha256({**bad_reason_ids, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_reason_ids, "reason_ids invalid")

    bad_reason_id = _valid_live_receipt()
    bad_reason_id["component_verdicts"][0]["reason_ids"] = [""]
    bad_reason_id["receipt_hash"] = canonical_sha256({**bad_reason_id, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_reason_id, "reason_id invalid")


def test_normalizer_rejects_bad_live_component_evidence_and_metadata() -> None:
    bad_evidence_hash = _valid_live_receipt()
    bad_evidence_hash["component_verdicts"][0]["evidence_hash"] = "bad"
    bad_evidence_hash["receipt_hash"] = canonical_sha256({**bad_evidence_hash, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_evidence_hash, "component.evidence_hash must be 64-character")

    bad_evidence_families = _valid_live_receipt()
    bad_evidence_families["component_verdicts"][0]["evidence_families"] = []
    bad_evidence_families["receipt_hash"] = canonical_sha256({**bad_evidence_families, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_evidence_families, "evidence_families invalid")

    bad_metadata = _valid_live_receipt()
    bad_metadata["component_verdicts"][0]["metadata"] = []
    bad_metadata["receipt_hash"] = canonical_sha256({**bad_metadata, "receipt_hash": ""})
    _assert_normalizer_rejects(bad_metadata, "metadata invalid")


def test_normalizer_rejects_live_receipt_context_mismatch_against_expected_hash() -> None:
    receipt = _valid_live_receipt()
    _assert_normalizer_rejects(receipt, "receipt context mismatch", context_hash="c" * 64)
