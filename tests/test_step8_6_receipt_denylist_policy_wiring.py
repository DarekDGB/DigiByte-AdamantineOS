from __future__ import annotations

from typing import Any

import pytest

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy, ShieldRuntimeBoundary

NOW = 1706990400
ISSUED_ISO = "2024-02-03T20:00:00Z"
EXPIRES_ISO = "2024-02-03T20:01:00Z"
REQ = "req-1"

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


def _policy(*, rejected_hashes: tuple[str, ...] = ()) -> RiskPolicy:
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("ok", "AC_OK", "OK"),
        external_reason_map=_reason_map(),
    )
    return RiskPolicy(
        min_overall_score=85,
        policy_pack=pack,
        shield_runtime_boundary=ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2,
        rejected_shield_receipt_hashes=rejected_hashes,
    )


def _qid_payload(*, context_hash: str) -> dict[str, Any]:
    return bind_shape_a_proof_hash(
        {
            "qid_iface_version": "qid-session-v0",
            "subject": "did:example:step8-6",
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


def _receipt_component(*, component_id: str, context_hash: str) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "contract_version": 3,
        "schema_version": "shield.verdict.v1",
        "request_id": REQ,
        "context_hash": context_hash,
        "decision": "ALLOW",
        "reason_ids": [_REASON_BY_COMPONENT[component_id]],
        "evidence_hash": "b" * 64,
        "evidence_families": [_EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
        "metadata": {},
        "fail_closed": True,
    }


def _orchestrator_receipt(*, context_hash: str) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": REQ,
        "context_hash": context_hash,
        "component_verdicts": [
            _receipt_component(component_id=component_id, context_hash=context_hash)
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
        "request_id": REQ,
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


def _run(*, receipt: dict[str, Any], policy: RiskPolicy) -> dict[str, Any]:
    ctx_hash = str(receipt["context_hash"])
    return orchestrate_execution_v2(
        payload=_envelope(context_hash=ctx_hash, shield=receipt),
        now=NOW,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=policy,
    )


def test_receipt_denylist_default_empty_keeps_verified_receipt_path_active() -> None:
    ctx_hash = compute_context_hash(
        wallet_id="w1",
        action="send",
        fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
    )
    receipt = _orchestrator_receipt(context_hash=ctx_hash)

    resp = _run(receipt=receipt, policy=_policy())

    assert resp["decision"]["evidence"]["shield"]["valid"] is True
    artifact = resp["artifacts"]["shield_runtime_boundary"]
    assert artifact["receipt_state"] == "VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS"
    assert artifact["receipt_hash"] == receipt["receipt_hash"]


def test_receipt_denylist_from_policy_fails_closed_before_eqc_continuation() -> None:
    ctx_hash = compute_context_hash(
        wallet_id="w1",
        action="send",
        fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
    )
    receipt = _orchestrator_receipt(context_hash=ctx_hash)

    resp = _run(receipt=receipt, policy=_policy(rejected_hashes=(receipt["receipt_hash"],)))

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_SHIELD_STALE.value
    assert resp["decision"]["evidence"]["shield"]["valid"] is False
    artifact = resp["artifacts"]["shield_runtime_boundary"]
    assert artifact["receipt_state"] == "REJECTED_REPLAY_RISK"
    assert artifact["verified"] is False
    assert artifact["accepted_as_evidence"] is False
    assert artifact["route_status"] == "receipt_rejected_at_orchestrator_only_boundary"
    assert artifact["receipt_hash"] == receipt["receipt_hash"]


@pytest.mark.parametrize(
    "bad_hashes, message",
    [
        (["a" * 64], "must be tuple"),
        ((123,), "entries must be str"),
        (("A" * 64,), "lowercase sha256 hex"),
        (("z" * 64,), "lowercase sha256 hex"),
        (("a" * 63,), "lowercase sha256 hex"),
        (("a" * 64, "a" * 64), "must not contain duplicates"),
    ],
)
def test_receipt_denylist_policy_validation_fails_closed(bad_hashes: object, message: str) -> None:
    policy = RiskPolicy(rejected_shield_receipt_hashes=bad_hashes)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=message):
        policy.validate()
