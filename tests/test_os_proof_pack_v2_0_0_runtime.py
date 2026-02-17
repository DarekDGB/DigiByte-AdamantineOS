from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from adamantine.v1.execution.fixture_harness import (
    canonical_json_dumps,
    load_canonical_json,
    verify_manifest_strict_v2_0_0_runtime,
    _default_policy,
)
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v2.runtime_host.host import run_mobile_execution_call_v2


NOW = 1706990400


def _fixture_dir() -> Path:
    # Keep this aligned with fixture_harness location:
    # src/adamantine/v1/fixtures/v2_0_0_runtime/
    return (Path(__file__).resolve().parent.parent / "src" / "adamantine" / "v1" / "fixtures" / "v2_0_0_runtime").resolve()


def _run_request(name: str) -> Dict[str, Any]:
    payload = load_canonical_json(_fixture_dir() / name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return run_mobile_execution_call_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def _expected(name: str) -> Dict[str, Any]:
    return load_canonical_json(_fixture_dir() / name)


def _assert_locked(*, got: Dict[str, Any], expected_path: Path) -> None:
    exp = load_canonical_json(expected_path)

    if got != exp:
        suggested = canonical_json_dumps(got)
        raise AssertionError(
            "Response fixture mismatch.\n\n"
            f"EXPECTED fixture file:\n  {expected_path}\n\n"
            "SUGGESTED replacement contents (canonical JSON):\n"
            f"{suggested}\n"
        )


def test_v2_0_0_runtime_manifest_is_strictly_enforced() -> None:
    verify_manifest_strict_v2_0_0_runtime()


def test_v2_0_0_runtime_allow_response_is_locked() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    got = _run_request("request_allow.json")
    _assert_locked(got=got, expected_path=_fixture_dir() / "response_allow.json")


def test_v2_0_0_runtime_deny_response_is_locked() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    got = _run_request("request_deny.json")
    _assert_locked(got=got, expected_path=_fixture_dir() / "response_deny.json")


def test_v2_0_0_runtime_hostile_context_mismatch_denies_fail_closed() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    got = _run_request("request_hostile_context_mismatch.json")
    _assert_locked(got=got, expected_path=_fixture_dir() / "response_hostile_context_mismatch.json")


def test_v2_0_0_runtime_is_deterministic_across_50_runs_allow() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    first = canonical_json_dumps(_run_request("request_allow.json"))
    for _ in range(50):
        assert canonical_json_dumps(_run_request("request_allow.json")) == first


def test_v2_0_0_runtime_is_deterministic_across_50_runs_hostile() -> None:
    verify_manifest_strict_v2_0_0_runtime()
    first = canonical_json_dumps(_run_request("request_hostile_context_mismatch.json"))
    for _ in range(50):
        assert canonical_json_dumps(_run_request("request_hostile_context_mismatch.json")) == first
