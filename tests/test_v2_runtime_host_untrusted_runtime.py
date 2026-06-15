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
    signals: list[dict[str, Any]] = []
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

    # CRITICAL invariant: adapter requires signals sorted by (layer, signal_id)
    signals = sorted(signals, key=lambda s: (s["layer"], s["signal_id"]))

    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": context_hash,
        "issued_at": now,
        "expires_at": now + 60,
        "required_layers": required_layers,
        "signals": signals,
        "meta": {},
        "shield_bundle_version": "1.0.0",
    }


def _envelope_v2_allow(*, now: int, context_hash: str, session_nonce: str = "n1") -> dict[str, Any]:
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"

    # include WSQK so TVA path is exercised
    proofs: dict[str, Any] = {
        "wsqk": {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": context_hash,
            "issued_at": now,
            "expires_at": now + 60,
            "nonce": session_nonce,
        }
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
        "nonce": {"value": session_nonce, "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": _qid_payload(now=now, session_nonce=session_nonce, context_hash=context_hash),
                "oracle": _oracle_payload(now=now, context_hash=context_hash, overall_score=99),
                "shield": _shield_bundle(now=now, context_hash=context_hash, required_layers=list(REQUIRED_SHIELD_LAYERS_V3)),
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
class ReplayRejectingNonceStore(NonceStore):
    """
    NonceStore that accepts a nonce ONCE, then rejects replays deterministically.
    """
    calls: int = 0
    _seen: set[tuple[str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._seen is None:
            self._seen = set()

    def check_and_mark(self, wallet_id: str, nonce: str, expires_at: int) -> bool:
        self.calls += 1
        key = (wallet_id, nonce)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


def test_untrusted_runtime_body_cannot_force_allow_or_override_fields() -> None:
    """
    Runtime may attempt to inject override fields into body.
    Those must NOT control verdict/reason/context/protection_mode.
    """
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    policy = _policy(min_score=85)
    executor = CountingExecutor()
    store = ReplayRejectingNonceStore()

    payload = _envelope_v2_allow(now=now, context_hash=ctx_hash, session_nonce="n1")

    # Hostile runtime injection into body (should be ignored or treated as inert data)
    payload["payload"]["body"]["runtime_override"] = {
        "status": "allow",
        "reason_id": "OK_ALLOW",
        "context_hash": "evil",
        "protection_mode": "off",
        "executor_called": True,
    }

    resp = run_mobile_execution_call_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "allow"
    assert executor.calls == 1
    assert store.calls == 1


def test_untrusted_runtime_replay_nonce_denies_and_never_executes() -> None:
    """
    Nonce discipline:
    - first call (allow) consumes nonce and executes once
    - second call with SAME nonce must deny and executor must NOT be called again
    """
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    policy = _policy(min_score=85)
    executor = CountingExecutor()
    store = ReplayRejectingNonceStore()

    payload = _envelope_v2_allow(now=now, context_hash=ctx_hash, session_nonce="n1")

    resp1 = run_mobile_execution_call_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    assert resp1["status"] == "allow"
    assert executor.calls == 1

    # replay exact same request/nonce
    resp2 = run_mobile_execution_call_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    assert resp2["status"] == "deny"
    assert executor.calls == 1  # unchanged (deny must not execute)


def test_untrusted_runtime_context_hash_mismatch_fail_closed() -> None:
    """
    If runtime tries to mutate evidence to mismatch the context_hash, we must deny (fail-closed).
    """
    now = 1706990400
    true_ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    policy = _policy(min_score=85)
    executor = CountingExecutor()
    store = ReplayRejectingNonceStore()

    payload = _envelope_v2_allow(now=now, context_hash=true_ctx_hash, session_nonce="n1")

    # Hostile mutation: corrupt a shield signal context_hash
    payload["payload"]["evidence"]["shield"]["signals"][0]["context_hash"] = "evil-context-hash"

    resp = run_mobile_execution_call_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert resp["status"] == "deny"
    assert executor.calls == 0
    assert store.calls == 0  # deny must not consume nonce


def test_untrusted_runtime_determinism_with_hostile_body_multi_run() -> None:
    """
    Determinism: hostile runtime injections must not create nondeterministic output.
    """
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    policy = _policy(min_score=85)

    payload = _envelope_v2_allow(now=now, context_hash=ctx_hash, session_nonce="n1")
    payload["payload"]["body"]["runtime_noise"] = {
        "fake": True,
        "attempt": {"status": "allow", "reason_id": "OK_ALLOW"},
        "array": [3, 2, 1],
    }

    out0 = run_mobile_execution_call_v2(
        payload=payload,
        now=now,
        executor=CountingExecutor(),
        nonce_store=ReplayRejectingNonceStore(),
        policy=policy,
    )

    for _ in range(50):
        outN = run_mobile_execution_call_v2(
            payload=payload,
            now=now,
            executor=CountingExecutor(),
            nonce_store=ReplayRejectingNonceStore(),
            policy=policy,
        )
        assert outN == out0
