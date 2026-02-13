from __future__ import annotations

"""Regression lock: Shield evidence can only strengthen deny.

Invariant (v1.3.0):
- If a request is denied due to *conflicting shield evidence*, then:
  * adding more (benign) shield evidence details must not flip the outcome to allow
  * reordering signals (even if all other content is identical) must not flip to allow

This is a forever-test: any future change that accidentally weakens the shield gate
should fail CI.
"""

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
    # Shared map for both Oracle v3 and Shield v3 adapters.
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            # Non-OK internal reason triggers EQC_CONFLICTING_EVIDENCE.
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


def _shield_signal(
    *,
    layer: str,
    signal_id: str,
    context_hash: str,
    ext_reason: str,
    facts: dict[str, Any] | None = None,
    meta: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        # v1.3 strict
        "layer_version": "1.0.0",
        "signal_id": signal_id,
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "verdict": "allow",  # verdict does not matter; reason_id drives conflict detection
        "reason_id": ext_reason,
        "confidence": 90,
        "facts": facts if facts is not None else {"k": "v"},
        "meta": meta if meta is not None else {},
    }


def _shield_bundle(*, context_hash: str, ext_reason_for_layer: dict[str, str], reorder: bool = False) -> dict[str, Any]:
    # Signals MUST be sorted by (layer, signal_id) to pass the shield adapter.
    # This helper can optionally break ordering to assert that it still cannot allow.
    signals = [
        _shield_signal(layer="adn", signal_id="a-1", context_hash=context_hash, ext_reason=ext_reason_for_layer["adn"]),
        _shield_signal(layer="dqsn", signal_id="d-1", context_hash=context_hash, ext_reason=ext_reason_for_layer["dqsn"]),
        _shield_signal(
            layer="guardian_wallet",
            signal_id="g-1",
            context_hash=context_hash,
            ext_reason=ext_reason_for_layer["guardian_wallet"],
        ),
        _shield_signal(layer="qwg", signal_id="q-1", context_hash=context_hash, ext_reason=ext_reason_for_layer["qwg"]),
        _shield_signal(
            layer="sentinel_ai",
            signal_id="s-1",
            context_hash=context_hash,
            ext_reason=ext_reason_for_layer["sentinel_ai"],
        ),
    ]

    if reorder:
        signals = list(reversed(signals))

    return {
        "v": "shield_bundle_v3",
        "shield_bundle_version": "1.0.0",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "required_layers": list(REQUIRED_SHIELD_LAYERS_V3),
        "signals": signals,
        "meta": {},
    }


def _envelope_v2(
    *,
    now: int,
    context_hash: str,
    shield_bundle: dict[str, Any],
    oracle_score: int,
    with_wsqk: bool,
) -> dict[str, Any]:
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"

    issued_at = 1706990400
    expires_at = 1706990460

    proofs: dict[str, Any] = {}
    if with_wsqk:
        proofs["wsqk"] = {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": context_hash,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": "n1",
        }

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
        "authority": {"class": "user", "scope": {"policy_pack": "default"}, "proofs": proofs},
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
                "shield": shield_bundle,
            },
            "body": {"ui_confirmed": True},
        },
    }


def test_regression_shield_conflict_can_never_flip_to_allow() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    # Base: one layer reports BLOCK (maps to non-OK internal reason) => EQC must deny.
    ext_reason_for_layer = {
        "sentinel_ai": "OK",
        "adn": "OK",
        "dqsn": "OK",
        "qwg": "OK",
        "guardian_wallet": "BLOCK",  # conflict trigger
    }

    base_shield = _shield_bundle(context_hash=ctx_hash, ext_reason_for_layer=ext_reason_for_layer)
    base_req = _envelope_v2(now=now, context_hash=ctx_hash, shield_bundle=base_shield, oracle_score=99, with_wsqk=True)
    base_resp = orchestrate_execution_v2(payload=base_req, now=now, executor=executor, nonce_store=store, policy=policy)

    assert base_resp["status"] == "deny"
    assert base_resp["reason_id"] == ReasonId.EQC_CONFLICTING_EVIDENCE.value

    # Variant A: add more benign shield evidence *details* (facts/meta) but keep the conflict.
    # Must still deny.
    ext_reason_for_layer_a = dict(ext_reason_for_layer)
    shield_a = _shield_bundle(context_hash=ctx_hash, ext_reason_for_layer=ext_reason_for_layer_a)
    # inflate benign details within caps
    shield_a["signals"] = list(shield_a["signals"])
    for s in shield_a["signals"]:
        if s["layer"] == "guardian_wallet":
            s["facts"] = {"k": "v", "more": "x" * 10, "risk": 1, "arr": ["a", "b"]}
            s["meta"] = {"src": "gw", "note": "extra"}

    req_a = _envelope_v2(now=now, context_hash=ctx_hash, shield_bundle=shield_a, oracle_score=99, with_wsqk=True)
    resp_a = orchestrate_execution_v2(payload=req_a, now=now, executor=RecordingExecutor(), nonce_store=InMemoryNonceStore(), policy=policy)

    assert resp_a["status"] == "deny"
    assert resp_a["reason_id"] == ReasonId.EQC_CONFLICTING_EVIDENCE.value

    # Variant B: reorder signals (break adapter ordering). Must still deny (cannot become allow).
    shield_b = _shield_bundle(context_hash=ctx_hash, ext_reason_for_layer=ext_reason_for_layer, reorder=True)
    req_b = _envelope_v2(now=now, context_hash=ctx_hash, shield_bundle=shield_b, oracle_score=99, with_wsqk=True)
    resp_b = orchestrate_execution_v2(payload=req_b, now=now, executor=RecordingExecutor(), nonce_store=InMemoryNonceStore(), policy=policy)

    assert resp_b["status"] == "deny"
    assert resp_b["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
