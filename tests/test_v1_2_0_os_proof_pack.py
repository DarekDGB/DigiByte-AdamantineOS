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
    return Path(__file__).resolve().parent.parent / "src" / "adamantine" / "v1" / "fixtures" / "v1_3_0"


def _canonical(resp: dict) -> str:
    return json.dumps(resp, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _run(name: str) -> dict:
    base = _fixture_dir()
    payload = load_canonical_json(base / name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def test_v1_3_0_manifest_is_strictly_enforced() -> None:
    verify_manifest_strict()


def test_v1_3_0_full_allow_fixture_shape_is_locked() -> None:
    verify_manifest_strict()
    resp = _run("full_allow.json")

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
        "protection_mode",
        "timebox",
        "tva",
        "wsqk",
    ]
    assert dec["allowed"] is True
    assert dec["protection_mode"] == "full"
    assert dec["context_hash"] == CTX_HASH
    assert dec["eqc"]["allowed"] is True
    assert dec["wsqk"]["allowed"] is True
    assert dec["tva"]["allowed"] is True
    assert dec["nonce"]["consumed"] is True
    assert dec["timebox"]["valid"] is True

    assert resp["artifacts"] == {"executor_result": "EXECUTED"}


def test_v1_3_0_minimal_deny_fixture_shape_is_locked() -> None:
    verify_manifest_strict()
    resp = _run("minimal_deny.json")

    assert sorted(resp.keys()) == ["artifacts", "decision", "reason_id", "request_id", "status", "v"]
    assert resp["v"] == "execution_response_v1"
    assert resp["status"] == "deny"
    assert resp["reason_id"] == "EQC_INVALID_SHIELD_BUNDLE"

    dec = resp["decision"]
    assert dec["allowed"] is False
    assert dec["protection_mode"] == "minimal"
    assert dec["context_hash"] == CTX_HASH
    assert dec["eqc"]["allowed"] is False
    assert dec["wsqk"]["allowed"] is False
    assert dec["tva"]["allowed"] is False
    assert dec["nonce"]["consumed"] is False
    assert dec["timebox"]["valid"] is True

    # Governance: mapped reason visible + original adapter reason preserved in artifacts
    assert "shield_adapter_reason" in resp["artifacts"]
    assert "shield_adapter_message" in resp["artifacts"]


def test_v1_3_0_legacy_deny_fixture_shape_is_locked() -> None:
    verify_manifest_strict()
    resp = _run("legacy_deny.json")

    assert sorted(resp.keys()) == ["artifacts", "decision", "reason_id", "request_id", "status", "v"]
    assert resp["v"] == "execution_response_v1"
    assert resp["status"] == "deny"
    assert resp["reason_id"] == "EQC_INVALID_QID_PROOF"

    dec = resp["decision"]
    assert dec["allowed"] is False
    assert dec["protection_mode"] == "legacy"
    assert dec["context_hash"] == CTX_HASH
    assert dec["eqc"]["allowed"] is False
    assert dec["wsqk"]["allowed"] is False
    assert dec["tva"]["allowed"] is False
    assert dec["nonce"]["consumed"] is False
    assert dec["timebox"]["valid"] is True

    assert resp["artifacts"] == {"error": "proof_hash must be non-empty str"}


def test_v1_3_0_full_allow_is_deterministic_across_50_runs() -> None:
    verify_manifest_strict()
    first = _canonical(_run("full_allow.json"))
    for _ in range(50):
        assert _canonical(_run("full_allow.json")) == first


def test_v1_3_0_minimal_deny_is_deterministic_across_50_runs() -> None:
    verify_manifest_strict()
    first = _canonical(_run("minimal_deny.json"))
    for _ in range(50):
        assert _canonical(_run("minimal_deny.json")) == first


def test_v1_3_0_legacy_deny_is_deterministic_across_50_runs() -> None:
    verify_manifest_strict()
    first = _canonical(_run("legacy_deny.json"))
    for _ in range(50):
        assert _canonical(_run("legacy_deny.json")) == first
