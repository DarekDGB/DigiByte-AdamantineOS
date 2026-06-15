from __future__ import annotations

from typing import Any

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import REQUIRED_SHIELD_LAYERS_V3, orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy, ShieldRuntimeBoundary

NOW = 1706990400
ISSUED_ISO = "2024-02-03T20:00:00Z"
EXPIRES_ISO = "2024-02-03T20:01:00Z"

_COMPONENT_IDS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")
_REASON_BY_COMPONENT = {
    "adn": "ADN_OK_COORDINATION_ALLOW",
    "dqsn": "DQSN_OK_NETWORK_ALLOW",
    "guardian_wallet": "GW_OK_HEALTHY_ALLOW",
    "qwg": "QWG_OK_POSTURE_ALLOW",
    "sentinel_ai": "SNTL_OK_TELEMETRY_ALLOW",
}
_EVIDENCE_FAMILY_BY_COMPONENT = {
    "adn": "defense_signal",
    "dqsn": "network_observation",
    "guardian_wallet": "wallet_context",
    "qwg": "wallet_posture",
    "sentinel_ai": "telemetry",
}


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )


def _policy(*, boundary: ShieldRuntimeBoundary) -> RiskPolicy:
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("ok", "AC_OK", "OK"),
        external_reason_map=_reason_map(),
    )
    return RiskPolicy(min_overall_score=85, policy_pack=pack, shield_runtime_boundary=boundary)


def _qid_payload(*, context_hash: str) -> dict[str, Any]:
    return bind_shape_a_proof_hash(
        {
            "qid_iface_version": "qid-session-v0",
            "subject": "did:example:step4",
            "issued_at": NOW - 10,
            "expires_at": NOW + 10,
            "proof_hash": "placeholder",
            "context_hash": context_hash,
            "device_binding": "device-1",
            "issuer_version": "qid-v0",
        }
    )


def _oracle_payload(*, context_hash: str) -> dict[str, Any]:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": context_hash,
        "issued_at": NOW - 5,
        "expires_at": NOW + 5,
        "generated_at": NOW - 1,
        "overall_score": 99,
        "signals": [{"source": "ac_model", "severity": 10, "reason_ids": ["AC_OK"]}],
        "oracle_version": "adaptive-core/3.0.0",
        "external_source_id": "ac-prod-1",
    }


def _legacy_shield_signal(*, layer: str, signal_id: str, context_hash: str) -> dict[str, Any]:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "layer_version": "1.0.0",
        "signal_id": signal_id,
        "context_hash": context_hash,
        "issued_at": NOW,
        "expires_at": NOW + 60,
        "verdict": "allow",
        "reason_id": "OK",
        "confidence": 90,
        "facts": {"k": "v"},
        "meta": {},
    }


def _legacy_shield_bundle(*, context_hash: str) -> dict[str, Any]:
    return {
        "v": "shield_bundle_v3",
        "shield_bundle_version": "1.0.0",
        "bundle_id": "legacy-bundle-step4",
        "context_hash": context_hash,
        "issued_at": NOW,
        "expires_at": NOW + 60,
        "required_layers": list(REQUIRED_SHIELD_LAYERS_V3),
        "signals": [
            _legacy_shield_signal(layer="adn", signal_id="a-1", context_hash=context_hash),
            _legacy_shield_signal(layer="dqsn", signal_id="d-1", context_hash=context_hash),
            _legacy_shield_signal(layer="guardian_wallet", signal_id="g-1", context_hash=context_hash),
            _legacy_shield_signal(layer="qwg", signal_id="q-1", context_hash=context_hash),
            _legacy_shield_signal(layer="sentinel_ai", signal_id="s-1", context_hash=context_hash),
        ],
        "meta": {},
    }


def _receipt_component(*, component_id: str, request_id: str, context_hash: str) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "contract_version": 3,
        "schema_version": "shield.verdict.v1",
        "request_id": request_id,
        "context_hash": context_hash,
        "decision": "ALLOW",
        "reason_ids": [_REASON_BY_COMPONENT[component_id]],
        "evidence_hash": "b" * 64,
        "evidence_families": [_EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
        "metadata": {},
        "fail_closed": True,
    }


def _orchestrator_receipt(*, request_id: str, context_hash: str) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": request_id,
        "context_hash": context_hash,
        "component_verdicts": [
            _receipt_component(component_id=component_id, request_id=request_id, context_hash=context_hash)
            for component_id in _COMPONENT_IDS
        ],
        "final_outcome": "ALLOW",
        "dominant_reason_ids": ["ORCH_OK_ALL_COMPONENTS_ALLOW"],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": True,
            "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW",
        },
        "fail_closed": True,
    }
    receipt["receipt_hash"] = canonical_sha256(receipt)
    return receipt


def _envelope(*, context_hash: str, shield: dict[str, Any]) -> dict[str, Any]:
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
        "authority": {"class": "user", "scope": {"policy_pack": "default"}, "proofs": {}},
        "timebox": {"issued_at": ISSUED_ISO, "expires_at": EXPIRES_ISO},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": _qid_payload(context_hash=context_hash),
                "oracle": _oracle_payload(context_hash=context_hash),
                "shield": shield,
            },
            "body": {"ui_confirmed": True},
        },
    }


def test_orchestrator_only_mode_rejects_legacy_bundle_shape() -> None:
    context_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    resp = orchestrate_execution_v2(
        payload=_envelope(context_hash=context_hash, shield=_legacy_shield_bundle(context_hash=context_hash)),
        now=NOW,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(boundary=ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    artifact = resp["artifacts"]["shield_runtime_boundary"]
    assert artifact["mode"] == ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2.value
    assert artifact["verified"] is False
    assert artifact["accepted_as_evidence"] is False
    assert artifact["final_approval"] is False
    assert artifact["route_status"] == "receipt_rejected_at_orchestrator_only_boundary"


def test_orchestrator_only_mode_accepts_receipt_as_evidence_only_and_fails_closed_until_step5() -> None:
    context_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    executor = RecordingExecutor()
    resp = orchestrate_execution_v2(
        payload=_envelope(
            context_hash=context_hash,
            shield=_orchestrator_receipt(request_id="req-1", context_hash=context_hash),
        ),
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(boundary=ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_POLICY.value
    assert resp["decision"]["evidence"]["shield"]["valid"] is True
    assert resp["decision"]["allowed"] is False
    assert executor.called is False

    artifact = resp["artifacts"]["shield_runtime_boundary"]
    assert artifact["mode"] == ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2.value
    assert artifact["receipt_state"] == "VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS"
    assert artifact["verified"] is True
    assert artifact["accepted_as_evidence"] is True
    assert artifact["final_approval"] is False
    assert artifact["handoff_allowed"] is True
    assert artifact["route_status"] == "receipt_verified_evidence_only_waiting_for_aos_m_002b_runtime_route"
    assert resp["artifacts"]["final_policy"]["final_approval"] is False
    assert resp["artifacts"]["final_policy"]["stopped_at"] == "wallet_policy"


def test_legacy_bundle_boundary_is_explicitly_named_test_only() -> None:
    policy = _policy(boundary=ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY)
    policy.validate()
    assert policy.shield_runtime_boundary is ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY


def test_policy_rejects_non_enum_shield_runtime_boundary() -> None:
    policy = RiskPolicy(shield_runtime_boundary="ORCHESTRATOR_RECEIPT_V3_2")  # type: ignore[arg-type]
    try:
        policy.validate()
    except ValueError as exc:
        assert str(exc) == "shield_runtime_boundary must be ShieldRuntimeBoundary"
    else:  # pragma: no cover - defensive assertion path
        raise AssertionError("policy accepted non-enum Shield runtime boundary")


def test_shield_runtime_boundary_lock_document_is_indexed() -> None:
    doc = __import__("pathlib").Path("docs/ADAMANTINEOS_SHIELD_RUNTIME_BOUNDARY_LOCK.md").read_text()
    index = __import__("pathlib").Path("docs/INDEX.md").read_text()
    assert "ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2" in doc
    assert "ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY" in doc
    assert "ADAMANTINEOS_SHIELD_RUNTIME_BOUNDARY_LOCK.md" in index
