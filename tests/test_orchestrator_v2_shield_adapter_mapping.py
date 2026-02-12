from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import REQUIRED_SHIELD_LAYERS_V3, orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )


def _policy(*, min_score: int = 85) -> RiskPolicy:
    pack = PolicyPack(
        min_overall_score=min_score,
        allowed_external_reason_ids=("ok", "AC_OK", "OK", "BLOCK"),
        external_reason_map=_reason_map(),
    )
    return RiskPolicy(min_overall_score=min_score, policy_pack=pack)


def _qid_payload(*, issued_at: int, expires_at: int) -> dict[str, Any]:
    return {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "proof_hash": "proofhash123",
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    }


def _oracle_payload(*, context_hash: str, issued_at: int, expires_at: int, generated_at: int, score: int) -> dict[str, Any]:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": context_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "generated_at": generated_at,
        "overall_score": score,
        "signals": [{"source": "ac_model", "severity": 10, "reason_ids": ["AC_OK"]}],
        "oracle_version": "adaptive-core/3.0.0",
        "external_source_id": "ac-prod-1",
    }


def _shield_signal(*, layer: str, signal_id: str, context_hash: str, ext_reason: str = "OK") -> dict[str, Any]:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "signal_id": signal_id,
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "verdict": "allow",
        "reason_id": ext_reason,
        "confidence": 90,
        "facts": {"k": "v"},
        "meta": {},
    }


def _shield_bundle(*, context_hash: str, required_layers: list[str]) -> dict[str, Any]:
    # Sorted by (layer, signal_id)
    signals = [
        _shield_signal(layer="adn", signal_id="a-1", context_hash=context_hash),
        _shield_signal(layer="dqsn", signal_id="d-1", context_hash=context_hash),
        _shield_signal(layer="guardian_wallet", signal_id="g-1", context_hash=context_hash),
        _shield_signal(layer="qwg", signal_id="q-1", context_hash=context_hash),
        _shield_signal(layer="sentinel_ai", signal_id="s-1", context_hash=context_hash),
    ]
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "required_layers": required_layers,
        "signals": signals,
        "meta": {},
    }


def _envelope_v2(*, now: int, context_hash: str, shield_payload: dict[str, Any], oracle_score: int = 99) -> dict[str, Any]:
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"

    issued_at = 1706990400
    expires_at = 1706990460

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
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "proofs": {
                "wsqk": {
                    "wallet_id": "w1",
                    "action": "send",
                    "context_hash": context_hash,
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "nonce": "n1",
                }
            },
        },
        "timebox": {"issued_at": issued_iso, "expires_at": expires_iso},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": _qid_payload(issued_at=now - 10, expires_at=now + 10),
                "oracle": _oracle_payload(
                    context_hash=context_hash,
                    issued_at=now - 5,
                    expires_at=now + 5,
                    generated_at=now - 1,
                    score=oracle_score,
                ),
                "shield": shield_payload,
            },
            "body": {"ui_confirmed": True},
        },
    }


def test_orchestrator_maps_shield_adapter_invalid_to_eqc_invalid_shield_bundle() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})

    shield = _shield_bundle(context_hash=ctx_hash, required_layers=list(REQUIRED_SHIELD_LAYERS_V3))
    # Break deterministic ordering: signals must be sorted by (layer, signal_id).
    shield["signals"] = list(reversed(shield["signals"]))

    payload = _envelope_v2(now=now, context_hash=ctx_hash, shield_payload=shield, oracle_score=99)

    resp = orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(min_score=85),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert resp["artifacts"]["shield_adapter_reason"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_maps_shield_version_mismatch_to_eqc_invalid_shield_bundle() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})

    shield = _shield_bundle(context_hash=ctx_hash, required_layers=list(REQUIRED_SHIELD_LAYERS_V3))
    shield["v"] = "shield_bundle_v2"  # version mismatch

    payload = _envelope_v2(now=now, context_hash=ctx_hash, shield_payload=shield, oracle_score=99)

    resp = orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(min_score=85),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert resp["artifacts"]["shield_adapter_reason"] == ReasonId.DENY_VERSION_MISMATCH.value


def test_orchestrator_preserves_unknown_external_reason_from_shield_adapter() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})

    shield = _shield_bundle(context_hash=ctx_hash, required_layers=list(REQUIRED_SHIELD_LAYERS_V3))
    # Make one layer use a disallowed external reason id.
    for s in shield["signals"]:
        if s.get("layer") == "adn":
            s["reason_id"] = "NOT_ALLOWED"
            break

    payload = _envelope_v2(now=now, context_hash=ctx_hash, shield_payload=shield, oracle_score=99)

    resp = orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(min_score=85),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.UNKNOWN_EXTERNAL_REASON.value
    assert resp["artifacts"]["shield_adapter_reason"] == ReasonId.UNKNOWN_EXTERNAL_REASON.value
