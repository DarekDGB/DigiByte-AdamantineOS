from __future__ import annotations

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash
from typing import Any

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import REQUIRED_SHIELD_LAYERS_V3, orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy, ShieldRuntimeBoundary


def _reason_map() -> ExternalReasonMap:
    # Shared map for both Oracle v3 and Shield v3 adapters.
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
    return RiskPolicy(
        min_overall_score=min_score,
        policy_pack=pack,
        shield_runtime_boundary=ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY,
    )


def _qid_payload(*, issued_at: int, expires_at: int, context_hash: str | None = None) -> dict[str, Any]:
    return bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "proof_hash": "proofhash123",
        "context_hash": context_hash,
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    })


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
        # v1.3 strict
        "layer_version": "1.0.0",
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
    # Signals MUST be sorted by (layer, signal_id) for adapter determinism.
    signals = [
        _shield_signal(layer="adn", signal_id="a-1", context_hash=context_hash),
        _shield_signal(layer="dqsn", signal_id="d-1", context_hash=context_hash),
        _shield_signal(layer="guardian_wallet", signal_id="g-1", context_hash=context_hash),
        _shield_signal(layer="qwg", signal_id="q-1", context_hash=context_hash),
        _shield_signal(layer="sentinel_ai", signal_id="s-1", context_hash=context_hash),
    ]
    return {
        "v": "shield_bundle_v3",
        # v1.3 strict
        "shield_bundle_version": "1.0.0",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "required_layers": required_layers,
        "signals": signals,
        "meta": {},
    }


def _envelope_v2(
    *,
    now: int,
    context_hash: str,
    shield_context_hash: str | None = None,
    shield_required_layers: list[str],
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
            "fields": {"asset": "DGB", "amount": "1", "ui_confirmed": "true"},
        },
        "authority": {"class": "user", "scope": {"policy_pack": "default"}, "proofs": proofs},
        "timebox": {"issued_at": issued_iso, "expires_at": expires_iso},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": _qid_payload(issued_at=now - 10, expires_at=now + 10, context_hash=context_hash),
                "oracle": _oracle_payload(
                    context_hash=context_hash,
                    issued_at=now - 5,
                    expires_at=now + 5,
                    generated_at=now - 1,
                    score=oracle_score,
                ),
                "shield": _shield_bundle(
                    context_hash=(shield_context_hash if shield_context_hash is not None else context_hash),
                    required_layers=shield_required_layers,
                ),
            },
            "body": {"ui_confirmed": True},
        },
    }


def _d(resp: dict[str, Any], *path: str) -> Any:
    cur: Any = resp
    for p in path:
        cur = cur[p]
    return cur


def test_allow_path_multi_evidence() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=99,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "allow"
    assert resp["reason_id"] == ReasonId.OK_ALLOW.value
    assert _d(resp, "decision", "allowed") is True
    assert _d(resp, "decision", "gates", "eqc", "allowed") is True
    assert _d(resp, "decision", "gates", "wsqk", "allowed") is True
    assert _d(resp, "decision", "gates", "tva", "allowed") is True
    assert _d(resp, "decision", "nonce", "consumed") is True
    assert executor.called is True


def test_deny_if_missing_any_required_shield_layer() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    bad_layers = [x for x in REQUIRED_SHIELD_LAYERS_V3 if x != "dqsn"]

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=bad_layers,
        oracle_score=99,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert _d(resp, "decision", "allowed") is False
    assert _d(resp, "decision", "gates", "eqc", "allowed") is False
    assert executor.called is False


def test_deny_if_unknown_required_layer_present() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    bad = list(REQUIRED_SHIELD_LAYERS_V3)
    bad[2] = "unknown_layer"

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=bad,
        oracle_score=99,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    # Governance (v1.3): structural shield invalid -> EQC_INVALID_SHIELD_BUNDLE (stable, wallet-facing)
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert executor.called is False


def test_deny_if_duplicate_required_layer_present() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    bad = list(REQUIRED_SHIELD_LAYERS_V3) + ["dqsn"]

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=bad,
        oracle_score=99,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert executor.called is False


def test_deny_if_required_layers_wrong_order() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    bad = list(REQUIRED_SHIELD_LAYERS_V3)
    bad[0], bad[1] = bad[1], bad[0]

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=bad,
        oracle_score=99,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert executor.called is False


def test_deny_if_oracle_score_below_threshold() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=10,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value
    assert _d(resp, "decision", "allowed") is False
    assert executor.called is False


def test_deny_if_shield_context_hash_mismatch() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_context_hash="0" * 64,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=99,
        with_wsqk=True,
    )

    resp = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    # Governance (v1.3): structural shield invalid -> EQC_INVALID_SHIELD_BUNDLE (stable, wallet-facing)
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    assert executor.called is False


def test_determinism_same_input_same_output() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1", "ui_confirmed": "true"})
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _policy(min_score=85)

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=10,
        with_wsqk=False,
    )

    r1 = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    r2 = orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert r1 == r2
