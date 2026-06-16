from __future__ import annotations

import json
from pathlib import Path

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import (
    _default_policy,
    load_canonical_json,
    verify_manifest_strict_v1_4_0,
)
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2


NOW = 1706990400
CTX_HASH = "3d92615f920ff2b0529e0967ce92a957e8616c785969961c5c21746e0488cce5"


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "adamantine" / "v1" / "fixtures" / "v1_4_0"


def _canonical(resp: dict) -> str:
    return json.dumps(resp, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _run(name: str) -> dict:
    base = _fixture_dir()
    payload = load_canonical_json(base / name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    policy = policy.__class__(
        min_overall_score=policy.min_overall_score,
        unknown_reason_mode=policy.unknown_reason_mode,
        resilience_mode=policy.resilience_mode,
        policy_pack=policy.policy_pack,
        require_protected_call=policy.require_protected_call,
        require_full_mode=policy.require_full_mode,
        require_qid_replay_proof=True,
        shield_runtime_boundary=policy.shield_runtime_boundary,
    )
    return orchestrate_execution_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def test_v1_4_0_manifest_is_strictly_enforced() -> None:
    verify_manifest_strict_v1_4_0()


def test_v1_4_0_full_allow_fixture_shape_is_locked() -> None:
    verify_manifest_strict_v1_4_0()
    resp = _run("full_allow.json")

    assert resp["v"] == "execution_response_v2"
    assert resp["status"] == "allow"
    assert resp["reason_id"] == "OK_ALLOW"
    assert resp["context_hash"] == CTX_HASH

    dec = resp["decision"]
    assert dec["allowed"] is True
    assert dec["protection_mode"] == "full"
    assert dec["gates"]["eqc"]["allowed"] is True
    assert dec["gates"]["wsqk"]["allowed"] is True
    assert dec["gates"]["tva"]["allowed"] is True
    assert dec["nonce"]["consumed"] is True
    assert dec["timebox"]["valid"] is True


def test_v1_4_0_missing_replay_proof_denies_fail_closed() -> None:
    verify_manifest_strict_v1_4_0()
    resp = _run("replay_missing_deny.json")

    assert resp["status"] == "deny"
    assert resp["reason_id"] == "QID_REPLAY_PROOF_MISSING"
    assert resp["decision"]["protection_mode"] == "legacy"
    assert resp["decision"]["nonce"]["consumed"] is False


def test_v1_4_0_wallet_mismatch_denies_with_distinct_reason() -> None:
    verify_manifest_strict_v1_4_0()
    resp = _run("replay_wallet_mismatch_deny.json")

    assert resp["status"] == "deny"
    assert resp["reason_id"] == "QID_REPLAY_WALLET_MISMATCH"
    assert resp["decision"]["protection_mode"] == "legacy"


def test_v1_4_0_nonce_replay_denies_with_distinct_reason() -> None:
    verify_manifest_strict_v1_4_0()
    resp = _run("replay_nonce_replay_deny.json")

    assert resp["status"] == "deny"
    assert resp["reason_id"] == "QID_NONCE_REPLAY"
    assert resp["decision"]["protection_mode"] == "legacy"


def test_v1_4_0_is_deterministic_across_50_runs() -> None:
    verify_manifest_strict_v1_4_0()
    first = _canonical(_run("replay_nonce_replay_deny.json"))
    for _ in range(50):
        assert _canonical(_run("replay_nonce_replay_deny.json")) == first
