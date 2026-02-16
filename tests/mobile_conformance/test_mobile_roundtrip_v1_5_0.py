from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import (
    _default_policy,
    load_canonical_json,
    verify_manifest_strict_for,
)
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2


NOW = 1706990400


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_dir() -> Path:
    return _repo_root() / "src" / "adamantine" / "v1" / "fixtures" / "v1_5_0_mobile"


def _load_schema(name: str) -> dict:
    p = _repo_root() / "contracts" / name
    return json.loads(p.read_text(encoding="utf-8"))


def _validate(schema: dict, instance: dict) -> None:
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        raise AssertionError(errors[0].message)


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _run_request(request_fixture_name: str) -> dict:
    base = _fixture_dir()
    payload = load_canonical_json(base / request_fixture_name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


@pytest.mark.parametrize(
    "request_name,response_name",
    [
        ("request_legacy.json", "response_legacy.json"),
        ("request_minimal.json", "response_minimal.json"),
        ("request_full_allow.json", "response_full_allow.json"),
        ("request_full_deny.json", "response_full_deny.json"),
    ],
)
def test_mobile_v1_5_0_roundtrip_is_schema_valid_and_exact(request_name: str, response_name: str) -> None:
    # Fixture integrity lock
    verify_manifest_strict_for("v1_5_0_mobile")

    req_schema = _load_schema("mobile_request_v2.schema.json")
    resp_schema = _load_schema("mobile_response_v2.schema.json")

    base = _fixture_dir()
    req = load_canonical_json(base / request_name)
    expected = load_canonical_json(base / response_name)

    # Contract validity (schemas)
    _validate(req_schema, req)
    _validate(resp_schema, expected)

    # Runtime roundtrip must match fixture exactly
    got = _run_request(request_name)
    _validate(resp_schema, got)

    assert _canonical(got) == _canonical(expected)


def test_mobile_v1_5_0_is_deterministic_across_100_runs() -> None:
    verify_manifest_strict_for("v1_5_0_mobile")
    first = _canonical(_run_request("request_full_deny.json"))
    for _ in range(100):
        assert _canonical(_run_request("request_full_deny.json")) == first
