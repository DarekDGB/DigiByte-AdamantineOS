"""
Utility functions to load and execute deterministic end-to-end fixtures for
Adamantine Wallet OS v1.2.0.

This harness is the OS Proof Pack:
- frozen fixture pack
- manifest-enforced drift prevention (SHA256)
- canonical JSON loader (reject dup keys, deterministic ordering)
- orchestrator_v2 full-path execution

It is intentionally opinionated and fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "v1_2_0"
_MANIFEST_NAME = "manifest.json"


class FixtureError(RuntimeError):
    pass


def _fixture_path(name: str) -> Path:
    if not isinstance(name, str) or not name.endswith(".json") or "/" in name or "\\" in name:
        raise FixtureError("invalid fixture name")
    p = (_FIXTURE_DIR / name).resolve()
    if _FIXTURE_DIR not in p.parents:
        raise FixtureError("fixture path escape detected")
    return p


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _load_manifest() -> Dict[str, str]:
    mp = (_FIXTURE_DIR / _MANIFEST_NAME).resolve()
    if not mp.exists():
        raise FixtureError("fixture manifest missing")
    raw = mp.read_bytes()
    obj = _canonical_json_loads(raw)
    if not isinstance(obj, dict):
        raise FixtureError("fixture manifest invalid")
    out: Dict[str, str] = {}
    for k, v in obj.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
        else:
            raise FixtureError("fixture manifest invalid")
    return out


def _canonical_object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # Reject duplicate keys (deny-by-default).
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise FixtureError(f"duplicate json key: {k}")
        out[k] = v
    return out


def _canonical_json_loads(raw: bytes) -> Any:
    # Strict JSON, duplicate-key rejection.
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_canonical_object_pairs_hook,
    )


def canonicalize_json(obj: Any) -> str:
    # Deterministic ordering for stable hashing / snapshots.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_fixture(name: str) -> Dict[str, Any]:
    p = _fixture_path(name)
    if not p.exists():
        raise FixtureError("fixture missing")
    raw = p.read_bytes()
    obj = _canonical_json_loads(raw)
    if not isinstance(obj, dict):
        raise FixtureError("fixture must be a JSON object")
    return obj


def verify_manifest() -> bool:
    manifest = _load_manifest()
    # Enforce that every listed fixture exists and matches hash.
    for fname, expected in manifest.items():
        fp = _fixture_path(fname)
        if not fp.exists():
            raise FixtureError("fixture listed in manifest missing")
        raw = fp.read_bytes()
        got = _sha256_bytes(raw)
        if got != expected:
            raise FixtureError(f"fixture hash mismatch: {fname}")
    return True


def _default_policy(*, min_score: int = 85) -> RiskPolicy:
    # Mirror the policy style used in orchestrator_v2 matrix tests:
    # explicit allowed_external_reason_ids + explicit reason map.
    reason_map = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )
    pack = PolicyPack(
        min_overall_score=min_score,
        allowed_external_reason_ids=("ok", "AC_OK", "OK", "BLOCK"),
        external_reason_map=reason_map,
    )
    return RiskPolicy(min_overall_score=min_score, policy_pack=pack)


def run_fixture(name: str, *, now: int) -> Dict[str, Any]:
    # Hard-lock drift prevention first.
    verify_manifest()

    payload = load_fixture(name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy(min_score=85)

    resp = orchestrate_execution_v2(
        payload=payload,
        now=now,
        executor=executor,
        nonce_store=store,
        policy=policy,
    )

    # Minimal structural invariants (fixture harness level).
    if not isinstance(resp, dict):
        raise FixtureError("orchestrator response must be dict")
    if "status" not in resp or "reason_id" not in resp:
        raise FixtureError("orchestrator response missing required fields")
    return resp


def run_all(*, now: int) -> Dict[str, Dict[str, Any]]:
    verify_manifest()
    base = _FIXTURE_DIR.resolve()
    results: Dict[str, Dict[str, Any]] = {}
    for p in base.iterdir():
        if p.suffix != ".json":
            continue
        if p.name == _MANIFEST_NAME:
            continue
        results[p.name] = run_fixture(p.name, now=now)
    return results
