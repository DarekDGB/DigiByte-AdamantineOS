from __future__ import annotations

import json
from pathlib import Path

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import (
    _default_policy,
    load_canonical_json,
    verify_manifest_strict,
)
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2


NOW = 1706990400
CTX_HASH = "f329ebc5291948197986496ffea7b1bc13bf0a7f35682849fab31e1f9eb4fb3b"


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "adamantine" / "v1" / "fixtures" / "v1_2_0"


def _canonical(resp: dict) -> str:
    return json.dumps(resp, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _run(name: str) -> dict:
    base = _fixture_dir()
    payload = load_canonical_json(base / name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def test_v1_2_0_manifest_is_strictly_enforced() -> None:
    verify_manifest_strict()


def test_v1_2_0_allow_fixture_shape_is_locked() -> None:
    verify_manifest_strict()
    resp = _run("allow.json")

    assert sorted(resp.keys()) == ["artifacts", "decision", "reason_id", "request_id", "status", "v"]
    assert resp["v"] == "execution_response_v1"
    assert resp["status"] == "allow"
    assert resp["reason_id"] == "OK_ALLOW"

    dec = resp["decision"]
    assert sorted(dec.keys()) == [
        "action",
        "allowed",
        "context_hash",
        "eqc",
        "intent",
        "nonce",
        "timebox",
        "tva",
        "wsqk",
    ]
    assert dec["allowed"] is True
    assert dec["context_hash"] == CTX_HASH
    assert dec["eqc"]["allowed"] is True
    assert dec["wsqk"]["allowed"] is True
    assert dec["tva"]["allowed"] is True
    assert dec["nonce"]["consumed"] is True
    assert dec["timebox"]["valid"] is True

    assert resp["artifacts"] == {"executor_result": "EXECUTED"}


def test_v1_2_0_deny_fixture_shape_is_locked() -> None:
    verify_manifest_strict()
    resp = _run("deny.json")

    assert sorted(resp.keys()) == ["artifacts", "decision", "reason_id", "request_id", "status", "v"]
    assert resp["v"] == "execution_response_v1"
    assert resp["status"] == "deny"
    assert resp["reason_id"] == "EQC_RISK_SCORE_BELOW_THRESHOLD"

    dec = resp["decision"]
    assert dec["allowed"] is False
    assert dec["context_hash"] == CTX_HASH
    assert dec["eqc"]["allowed"] is False
    assert dec["wsqk"]["allowed"] is False
    assert dec["tva"]["allowed"] is False
    assert dec["nonce"]["consumed"] is False
    assert dec["timebox"]["valid"] is True

    assert resp["artifacts"] == {"evidence": {"qid": True, "oracle": True, "shield": True}}


def test_v1_2_0_allow_is_deterministic_across_50_runs() -> None:
    verify_manifest_strict()
    first = _canonical(_run("allow.json"))
    for _ in range(50):
        assert _canonical(_run("allow.json")) == first


def test_v1_2_0_deny_is_deterministic_across_50_runs() -> None:
    verify_manifest_strict()
    first = _canonical(_run("deny.json"))
    for _ in range(50):
        assert _canonical(_run("deny.json")) == first
