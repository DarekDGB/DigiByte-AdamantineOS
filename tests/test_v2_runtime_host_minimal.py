from __future__ import annotations

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash
from dataclasses import dataclass
from typing import Any

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.orchestrator_v2 import REQUIRED_SHIELD_LAYERS_V3
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v2.runtime_host.host import run_mobile_execution_call_v2


def _reason_map() -> ExternalReasonMap:
    # Mirror the repo’s own example ids ("OK", "AC_OK")
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )


def _policy(*, min_score: int = 85) -> RiskPolicy:
    pack = PolicyPack(
        min_overall_score=min_score,
        allowed_external_reason_ids=("OK", "AC_OK", "BLOCK"),
        external_reason_map=_reason_map(),
    )
    return RiskPolicy(min_overall_score=min_score, policy_pack=pack)


def _qid_payload(*, now: int, session_nonce: str, context_hash: str | None = None) -> dict[str, Any]:
    # Valid Q-ID session + replay proof (safe to always include)
    return bind_shape_a_proof_hash({
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": now - 10,
        "expires_at": now + 10,
        "proof_hash": "proofhash123",
        "context_hash": context_hash,
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
        "replay_proof": {
            "proof_version": "qid-replay-v1",
            "wallet_id": "w1",
            "subject": "did:example:123",
            "proof_hash": "proofhash123",
            "device_binding": "device-1",
            "session_nonce": session_nonce,
            "fresh": True,
            "registry_commitment": "reg-commit-1",
        },
    })


def _oracle_payload(*, now: int, context_hash: str, overall_score: int) -> dict[str, Any]:
    # Must match adaptive_core_oracle_v3_adapter expectations
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": context_hash,
        "issued_at": now - 5,
        "expires_at": now + 5,
        "generated_at": now - 1,
        "external_source_id": "ac-prod-1",
        "oracle_version": "adaptive-core/3.0.0",
        "overall_score": overall_score,
        "signals": [
            {
                "source": "ac_model",
                "severity": 10,
                "reason_ids": ["AC_OK"],
            }
        ],
    }


def _shield_bundle(*, now: int, context_hash: str, required_layers: list[str]) -> dict[str, Any]:
    # Must match shield_v3_adapter expectations (require_versions=True in orchestrator_v2)
    signals: list[dict[str, Any]] = []
    # create deterministic IDs for each layer
    for i, layer in enumerate(required_layers, start=1):
        signals.append(
            {
                "v": "shield_signal_v3",
                "signal_id": f"{layer}-{i}",
                "layer": layer,
                "layer_version": "1.0.0",
                "context_hash": context_hash,
                "issued_at": now,
                "expires_at": now + 60,
                "verdict": "allow",
                "reason_id": "OK",
                "confidence": 90,
                "facts": {"k": "v"},
                "meta": {},
            }
        )

    # CRITICAL: shield_v3_adapter requires signals sorted by (layer, signal_id)
    signals = sorted(signals, key=lambda s: (s["layer"], s["signal_id"]))

    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": now,
        "expires_at": now + 60,
        "required_layers": required_layers,  # keep canonical required_layers order
        "signals": signals,
        "meta": {},
        "shield_bundle_version": "1.0.0",
    }


def _envelope_v2(
    *,
    now: int,
    context_hash: str,
    shield_required_layers: list[str],
    oracle_score: int,
    with_wsqk: bool,
) -> dict[str, Any]:
    # Envelope v2 strict top-level contract
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"

    proofs: dict[str, Any] = {}
    if with_wsqk:
        proofs["wsqk"] = {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": context_hash,
            "issued_at": now,
            "expires_at": now + 60,
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
                "qid": _qid_payload(now=now, session_nonce="n1", context_hash=context_hash),
                "oracle": _oracle_payload(now=now, context_hash=context_hash, overall_score=oracle_score),
                "shield": _shield_bundle(now=now, context_hash=context_hash, required_layers=shield_required_layers),
            },
            "body": {"ui_confirmed": True},
        },
    }


@dataclass(slots=True)
class CountingExecutor(Executor):
    calls: int = 0

    def execute(self, req: Any) -> str:
        self.calls += 1
        return "EXECUTED"


@dataclass(slots=True)
class CountingNonceStore(NonceStore):
    calls: int = 0
    accept: bool = True

    def check_and_mark(self, wallet_id: str, nonce: str, expires_at: int) -> bool:
        self.calls += 1
        return self.accept


def test_runtime_host_deny_never_calls_executor() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    executor = CountingExecutor()
    store = CountingNonceStore()
    policy = _policy(min_score=85)

    # DENY by making oracle score too low
    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=1,
        with_wsqk=True,
    )

    resp = run_mobile_execution_call_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    assert executor.calls == 0
    assert store.calls == 0  # nonce must not be consumed on deny


def test_runtime_host_allow_calls_executor_exactly_once() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    executor = CountingExecutor()
    store = CountingNonceStore()
    policy = _policy(min_score=85)

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=99,
        with_wsqk=True,
    )

    resp = run_mobile_execution_call_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "allow"
    assert executor.calls == 1
    assert store.calls == 1  # nonce consumed exactly once on allow


def test_runtime_host_determinism_multi_run() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    policy = _policy(min_score=85)

    payload = _envelope_v2(
        now=now,
        context_hash=ctx_hash,
        shield_required_layers=list(REQUIRED_SHIELD_LAYERS_V3),
        oracle_score=99,
        with_wsqk=True,
    )

    out0 = run_mobile_execution_call_v2(
        payload=payload, now=now, executor=CountingExecutor(), nonce_store=CountingNonceStore(), policy=policy
    )

    for _ in range(50):
        outN = run_mobile_execution_call_v2(
            payload=payload, now=now, executor=CountingExecutor(), nonce_store=CountingNonceStore(), policy=policy
        )
        assert outN == out0
