from __future__ import annotations

from typing import Any, Mapping

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import REQUIRED_SHIELD_LAYERS_V3, orchestrate_execution_v2
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy, ShieldRuntimeBoundary


NOW = 1706990400
REQUEST_ID = "req-1"
COMPONENT_IDS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")
EVIDENCE_FAMILY_BY_COMPONENT = {
    "adn": "defense_signal",
    "dqsn": "network_observation",
    "guardian_wallet": "wallet_context",
    "qwg": "wallet_posture",
    "sentinel_ai": "telemetry",
}
REASON_BY_COMPONENT = {
    "adn": "ADN_OK_COORDINATION_ALLOW",
    "dqsn": "DQSN_OK_NETWORK_ALLOW",
    "guardian_wallet": "GW_OK_HEALTHY_ALLOW",
    "qwg": "QWG_OK_POSTURE_ALLOW",
    "sentinel_ai": "SNTL_OK_TELEMETRY_ALLOW",
}


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )


def _policy() -> RiskPolicy:
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("ok", "AC_OK", "OK", "BLOCK"),
        external_reason_map=_reason_map(),
    )
    return RiskPolicy(
        min_overall_score=85,
        policy_pack=pack,
        shield_runtime_boundary=ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2,
        require_authenticated_external_evidence=True,
    )


def _ctx_hash() -> str:
    return compute_context_hash(
        wallet_id="w1",
        action="send",
        fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
    )


def _qid_payload(*, context_hash: str) -> dict[str, Any]:
    return bind_shape_a_proof_hash(
        {
            "qid_iface_version": "qid-session-v0",
            "subject": "did:example:123",
            "issued_at": NOW - 10,
            "expires_at": NOW + 10,
            "proof_hash": "proofhash123",
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


def _component_verdicts(*, context_hash: str) -> list[dict[str, Any]]:
    return [
        {
            "component_id": component_id,
            "contract_version": 3,
            "schema_version": "shield.verdict.v1",
            "request_id": REQUEST_ID,
            "context_hash": context_hash,
            "decision": "ALLOW",
            "reason_ids": [REASON_BY_COMPONENT[component_id]],
            "evidence_hash": "b" * 64,
            "evidence_families": [EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
            "metadata": {},
            "fail_closed": True,
        }
        for component_id in COMPONENT_IDS
    ]


def _shield_receipt(*, context_hash: str) -> dict[str, Any]:
    reason = "ORCH_OK_ALL_COMPONENTS_ALLOW"
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": REQUEST_ID,
        "context_hash": context_hash,
        "component_verdicts": _component_verdicts(context_hash=context_hash),
        "final_outcome": "ALLOW",
        "dominant_reason_ids": [reason],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": True,
            "handoff_reason": reason,
        },
        "fail_closed": True,
    }
    base["receipt_hash"] = canonical_sha256(base)
    return base


def _request(*, context_hash: str) -> dict[str, Any]:
    return {
        "v": "execution_request_v2",
        "request_id": REQUEST_ID,
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "app",
            "session_id": "s1",
            "action": "send",
            "fields": {"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
        },
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "proofs": {
                "wsqk": {
                    "wallet_id": "w1",
                    "action": "send",
                    "context_hash": context_hash,
                    "issued_at": NOW,
                    "expires_at": NOW + 60,
                    "nonce": "n1",
                }
            },
        },
        "timebox": {"issued_at": "2024-02-03T20:00:00Z", "expires_at": "2024-02-03T20:01:00Z"},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": _qid_payload(context_hash=context_hash),
                "oracle": _oracle_payload(context_hash=context_hash),
                "shield": _shield_receipt(context_hash=context_hash),
            },
            "body": {"ui_confirmed": True},
        },
    }


def _oracle_verifier(payload: Mapping[str, Any], expected_context_hash: str) -> None:
    if payload.get("context_hash") != expected_context_hash:
        raise ValueError("oracle context mismatch")
    if payload.get("external_source_id") != "ac-prod-1":
        raise ValueError("untrusted oracle signer")


def _shield_receipt_verifier(payload: Mapping[str, Any], expected_context_hash: str) -> None:
    if payload.get("context_hash") != expected_context_hash:
        raise ValueError("shield receipt context mismatch")
    if payload.get("schema_version") != "shield.receipt.v1":
        raise ValueError("untrusted shield receipt")


def test_authenticated_external_evidence_requires_oracle_verifier_before_accepting_self_hashed_oracle() -> None:
    context_hash = _ctx_hash()
    executor = RecordingExecutor()

    response = orchestrate_execution_v2(
        payload=_request(context_hash=context_hash),
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
        shield_receipt_verifier=_shield_receipt_verifier,
        oracle_verifier=None,
    )

    assert response["status"] == "deny"
    assert response["reason_id"] == ReasonId.ORACLE_AUTHENTICITY_VERIFIER_MISSING.value
    assert executor.called is False


def test_authenticated_external_evidence_requires_shield_receipt_verifier_before_accepting_self_hashed_receipt() -> None:
    context_hash = _ctx_hash()
    executor = RecordingExecutor()

    response = orchestrate_execution_v2(
        payload=_request(context_hash=context_hash),
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
        shield_receipt_verifier=None,
        oracle_verifier=_oracle_verifier,
    )

    assert response["status"] == "deny"
    assert response["reason_id"] == ReasonId.SHIELD_AUTHENTICITY_VERIFIER_MISSING.value
    assert executor.called is False


def test_authenticated_external_evidence_rejects_failing_shield_receipt_verifier() -> None:
    context_hash = _ctx_hash()
    executor = RecordingExecutor()

    def _reject_shield(payload: Mapping[str, Any], expected_context_hash: str) -> None:
        raise ValueError("bad shield signature")

    response = orchestrate_execution_v2(
        payload=_request(context_hash=context_hash),
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
        shield_receipt_verifier=_reject_shield,
        oracle_verifier=_oracle_verifier,
    )

    assert response["status"] == "deny"
    assert response["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert executor.called is False


def test_authenticated_external_evidence_verifiers_allow_receipt_to_continue_without_final_shield_authority() -> None:
    context_hash = _ctx_hash()
    executor = RecordingExecutor()

    response = orchestrate_execution_v2(
        payload=_request(context_hash=context_hash),
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
        shield_receipt_verifier=_shield_receipt_verifier,
        oracle_verifier=_oracle_verifier,
    )

    assert response["status"] == "allow"
    assert response["reason_id"] == ReasonId.OK_ALLOW.value
    assert response["artifacts"]["shield_runtime_boundary"]["accepted_as_evidence"] is True
    assert response["artifacts"]["shield_runtime_boundary"]["final_approval"] is False
    assert executor.called is True


def test_authenticated_external_evidence_preserves_verifier_adapter_error_reason() -> None:
    context_hash = _ctx_hash()
    executor = RecordingExecutor()

    def _adapter_error_shield(payload: Mapping[str, Any], expected_context_hash: str) -> None:
        raise AdapterError(ReasonId.EQC_CONFLICTING_EVIDENCE, "trusted shield signer rejected receipt")

    response = orchestrate_execution_v2(
        payload=_request(context_hash=context_hash),
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
        shield_receipt_verifier=_adapter_error_shield,
        oracle_verifier=_oracle_verifier,
    )

    assert response["status"] == "deny"
    assert response["reason_id"] == ReasonId.EQC_CONFLICTING_EVIDENCE.value
    assert executor.called is False


def test_risk_policy_rejects_non_bool_authenticated_external_evidence_latch() -> None:
    policy = RiskPolicy(require_authenticated_external_evidence="yes")  # type: ignore[arg-type]

    try:
        policy.validate()
    except ValueError as exc:
        assert "require_authenticated_external_evidence must be bool" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("policy.validate() should fail closed on non-bool latch")


def test_authenticated_external_evidence_latch_is_documented_in_source_and_docs() -> None:
    files = [
        "src/adamantine/v1/policy/risk_policy.py",
        "src/adamantine/v1/execution/orchestrator_v2.py",
        "src/adamantine/v2/runtime_host/host.py",
        "docs/EXTERNAL_INTERFACES.md",
        "docs/ADAMANTINEOS_SHIELD_RUNTIME_BOUNDARY_LOCK.md",
        "INVARIANTS.md",
    ]
    joined = "\n".join(__import__("pathlib").Path(path).read_text(encoding="utf-8") for path in files)

    assert "require_authenticated_external_evidence" in joined
    assert "shield_receipt_verifier(payload, expected_context_hash)" in joined
    assert "oracle_verifier(payload, expected_context_hash)" in joined
    assert "SHIELD_AUTHENTICITY_VERIFIER_MISSING" in joined
    assert "ORACLE_AUTHENTICITY_VERIFIER_MISSING" in joined
    assert 'not a public "Shield live" protection claim' in joined
