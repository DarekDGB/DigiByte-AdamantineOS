from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import REQUIRED_SHIELD_LAYERS_V3, orchestrate_execution_v2
from adamantine.v1.integrations.qid_adapter import compute_qid_shape_a_proof_hash
from adamantine.v1.policy.risk_policy import RiskPolicy

NOW = 1706990400
ISSUED_ISO = "2024-02-03T20:00:00Z"
EXPIRES_ISO = "2024-02-03T20:01:00Z"


def _policy() -> RiskPolicy:
    reason_map = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("ok", "AC_OK", "OK", "BLOCK"),
        external_reason_map=reason_map,
    )
    return RiskPolicy(min_overall_score=85, policy_pack=pack)


def _qid_payload(*, context_hash: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": NOW - 10,
        "expires_at": NOW + 10,
        "proof_hash": "",
        "context_hash": context_hash,
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    }
    payload["proof_hash"] = compute_qid_shape_a_proof_hash(
        qid_iface_version=payload["qid_iface_version"],
        subject=payload["subject"],
        issued_at=payload["issued_at"],
        expires_at=payload["expires_at"],
        context_hash=payload["context_hash"],
        device_binding=payload["device_binding"],
        issuer_version=payload["issuer_version"],
    )
    return payload


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


def _shield_signal(*, layer: str, signal_id: str, context_hash: str) -> dict[str, Any]:
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


def _shield_bundle(*, context_hash: str) -> dict[str, Any]:
    return {
        "v": "shield_bundle_v3",
        "shield_bundle_version": "1.0.0",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": NOW,
        "expires_at": NOW + 60,
        "required_layers": list(REQUIRED_SHIELD_LAYERS_V3),
        "signals": [
            _shield_signal(layer="adn", signal_id="a-1", context_hash=context_hash),
            _shield_signal(layer="dqsn", signal_id="d-1", context_hash=context_hash),
            _shield_signal(layer="guardian_wallet", signal_id="g-1", context_hash=context_hash),
            _shield_signal(layer="qwg", signal_id="q-1", context_hash=context_hash),
            _shield_signal(layer="sentinel_ai", signal_id="s-1", context_hash=context_hash),
        ],
        "meta": {},
    }


def _envelope(*, context_fields: dict[str, str], ui_confirmed: Any) -> dict[str, Any]:
    context_hash = compute_context_hash(wallet_id="w1", action="send", fields=context_fields)
    return {
        "v": "execution_request_v2",
        "request_id": "req-step8-human-confirmation",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "app",
            "session_id": "s1",
            "action": "send",
            "fields": context_fields,
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
                "shield": _shield_bundle(context_hash=context_hash),
            },
            "body": {"ui_confirmed": ui_confirmed} if ui_confirmed is not None else {},
        },
    }


def _run(payload: dict[str, Any]) -> tuple[dict[str, Any], RecordingExecutor]:
    executor = RecordingExecutor()
    resp = orchestrate_execution_v2(
        payload=payload,
        now=NOW,
        executor=executor,
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    return resp, executor


def _assert_human_denied(resp: dict[str, Any], executor: RecordingExecutor) -> None:
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INSUFFICIENT.value
    assert resp["decision"]["allowed"] is False
    assert resp["artifacts"]["final_policy"]["stopped_at"] == "human"
    assert executor.called is False


def test_payload_only_ui_confirmation_is_denied_even_with_valid_evidence() -> None:
    payload = _envelope(context_fields={"asset": "DGB", "amount": "1"}, ui_confirmed=True)
    resp, executor = _run(payload)
    _assert_human_denied(resp, executor)


def test_bound_context_confirmation_allows_after_all_local_gates() -> None:
    payload = _envelope(
        context_fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
        ui_confirmed=True,
    )
    resp, executor = _run(payload)
    assert resp["status"] == "allow"
    assert resp["reason_id"] == ReasonId.OK_ALLOW.value
    assert resp["decision"]["allowed"] is True
    assert executor.called is True


def test_bound_context_false_with_payload_true_is_denied() -> None:
    payload = _envelope(
        context_fields={"asset": "DGB", "amount": "1", "ui_confirmed": "false"},
        ui_confirmed=True,
    )
    resp, executor = _run(payload)
    _assert_human_denied(resp, executor)


def test_bound_context_true_with_payload_false_is_denied() -> None:
    payload = _envelope(
        context_fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
        ui_confirmed=False,
    )
    resp, executor = _run(payload)
    _assert_human_denied(resp, executor)


def test_bound_context_true_with_missing_payload_confirmation_is_denied() -> None:
    payload = _envelope(
        context_fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
        ui_confirmed=None,
    )
    resp, executor = _run(payload)
    _assert_human_denied(resp, executor)
