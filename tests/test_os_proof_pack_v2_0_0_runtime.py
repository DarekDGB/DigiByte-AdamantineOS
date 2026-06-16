from __future__ import annotations

from pathlib import Path
from typing import Any

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import (
    canonical_json_dumps,
    load_canonical_json,
    verify_manifest_strict_v2_0_0_runtime,
)
from adamantine.v1.policy.risk_policy import RiskPolicy, ShieldRuntimeBoundary
from adamantine.v2.runtime_host.host import run_mobile_execution_call_v2

NOW = 1706990400


def _fixture_dir() -> Path:
    # src/adamantine/v1/fixtures/v2_0_0_runtime/
    return (
        Path(__file__).resolve().parent.parent / "src" / "adamantine" / "v1" / "fixtures" / "v2_0_0_runtime"
    ).resolve()


def _default_policy() -> RiskPolicy:
    """
    Local policy builder to avoid importing a private helper from fixture_harness.
    Must remain semantically aligned with the fixture harness policy.
    """
    allowed = ("ok", "AC_OK", "OK", "BLOCK")
    reason_map = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=allowed,
        external_reason_map=reason_map,
    )
    return RiskPolicy(
        min_overall_score=85,
        policy_pack=pack,
        shield_runtime_boundary=ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY,
    )


def _run_request(name: str) -> dict[str, Any]:
    payload = load_canonical_json(_fixture_dir() / name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return run_mobile_execution_call_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


def _assert_locked(*, got: dict[str, Any], expected_path: Path) -> None:
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
