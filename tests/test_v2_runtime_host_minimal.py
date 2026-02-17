from __future__ import annotations

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
        "ac_iface_version": "ac-oracle-v3",
        "context_hash": context_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "generated_at": generated_at,
        "score": score,
        "reason_id": "AC_OK",
        "version": "adaptive-core-v3",
        "meta": {"engine": "test"},
    }


def _shield_bundle(*, context_hash: str, required_layers: list[str]) -> dict[str, Any]:
    layers = []
    for name in required_layers:
        layers.append(
            {
                "layer": name,
                "layer_version": "v3",
                "verdict": "allow",
                "reason_id": "ok",
                "score": 100,
                "meta": {"m": "t"},
            }
        )
    return {
        "shield_bundle_version": "shield-bundle-v3",
        "context_hash": context_hash,
        "layers": layers,
    }


def _envelope_v2(
    *,
    now: int,
    context_hash: str,
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
                "shield": _shield_bundle(context_hash=context_hash, required_layers=shield_required_layers),
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
    assert store.calls == 0  # nonce should not be consumed on deny


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
    assert resp["reason_id"] == ReasonId.OK_ALLOW.value
    assert executor.calls == 1
    assert store.calls == 1  # nonce consumed exactly once on allow


def test_runtime_host_determinism_multi_run() -> None:
    now = 1706990400
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    policy = _policy(min_score=85)

    # Fresh executor/store each run to avoid shared state affecting output.
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
