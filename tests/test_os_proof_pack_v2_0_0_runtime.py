from __future__ import annotations

import json
from pathlib import Path

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import (
    _default_policy,
    load_canonical_json,
    verify_manifest_strict_v2_0_0_runtime,
)
from adamantine.v2.runtime_host.host import run_mobile_execution_call_v2


NOW = 1706990400


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "adamantine" / "v1" / "fixtures" / "v2_0_0_runtime"


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _run_request(name: str) -> dict:
    base = _fixture_dir()
    payload = load_canonical_json(base / name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return run_mobile_execution_call_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def _expected(name: str) -> dict:
    return load_canonical_json(_fixture_dir() / name)


def test_v2_0_0_runtime_manifest_is_strictly_enforced() -> None:
    verify_manifest_strict_v2_0_0_runtime()


def test_v2_0_0_runtime_allow_response_is_locked() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    got = _run_request("request_allow.json")
    exp = _expected("response_allow.json")
    assert got == exp


def test_v2_0_0_runtime_deny_response_is_locked() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    got = _run_request("request_deny.json")
    exp = _expected("response_deny.json")
    assert got == exp


def test_v2_0_0_runtime_hostile_context_mismatch_denies_fail_closed() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    got = _run_request("request_hostile_context_mismatch.json")
    exp = _expected("response_hostile_context_mismatch.json")
    assert got == exp


def test_v2_0_0_runtime_is_deterministic_across_50_runs_allow() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    first = _canonical(_run_request("request_allow.json"))
    for _ in range(50):
        assert _canonical(_run_request("request_allow.json")) == first


def test_v2_0_0_runtime_is_deterministic_across_50_runs_hostile() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    first = _canonical(_run_request("request_hostile_context_mismatch.json"))
    for _ in range(50):
        assert _canonical(_run_request("request_hostile_context_mismatch.json")) == first
