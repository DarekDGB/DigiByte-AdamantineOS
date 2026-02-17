"""Deterministic OS Proof Pack fixture harness.

This module enforces semantic fixture locking via a manifest:
- Reject duplicate JSON keys
- Canonicalize JSON (sort_keys + stable separators)
- Hash canonical JSON with SHA-256

Supports multiple proof packs (v1_2_0, v1_3_0) without mixing them.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


class CanonicalJSONError(Exception):
    """Raised when canonical JSON loading or enforcement fails."""


class DuplicateKeyError(CanonicalJSONError):
    """Raised when a duplicate key is encountered in a JSON object."""


_FIXTURES_BASE = Path(__file__).parent.parent / "fixtures"
_MANIFEST = "manifest.json"


def _no_duplicate_object_pairs_hook(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate key: {k}")
        out[k] = v
    return out


def load_canonical_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        raise CanonicalJSONError(f"failed to read {path}: {e}") from e

    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_object_pairs_hook)
    except DuplicateKeyError:
        raise
    except Exception as e:
        raise CanonicalJSONError(f"invalid JSON in {path}: {e}") from e


def canonical_json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex_of_canonical_json_file(path: Path) -> str:
    obj = load_canonical_json(path)
    s = canonical_json_dumps(obj)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _default_policy() -> RiskPolicy:
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
    return RiskPolicy(min_overall_score=85, policy_pack=pack)


def _fixture_dir(pack_dirname: str) -> Path:
    base = (_FIXTURES_BASE / pack_dirname).resolve()
    if not base.exists() or not base.is_dir():
        raise CanonicalJSONError(f"fixture pack directory missing: {base}")
    return base


def verify_manifest_strict_for(pack_dirname: str) -> None:
    """Verify a proof pack manifest strictly (semantic)."""
    base = _fixture_dir(pack_dirname)
    manifest_path = base / _MANIFEST

    obj = load_canonical_json(manifest_path)
    if not isinstance(obj, dict):
        raise CanonicalJSONError("manifest must be a JSON object")

    manifest: Dict[str, str] = {}
    for k, v in obj.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise CanonicalJSONError("manifest must map string->string")
        manifest[k] = v

    fixture_files = sorted(p.name for p in base.iterdir() if p.suffix == ".json" and p.name != _MANIFEST)
    manifest_files = sorted(manifest.keys())

    if fixture_files != manifest_files:
        raise CanonicalJSONError(
            f"manifest fixture set mismatch: fixtures={fixture_files} manifest={manifest_files}"
        )

    for filename in fixture_files:
        fixture_path = base / filename
        expected = manifest[filename]
        actual = sha256_hex_of_canonical_json_file(fixture_path)
        if actual != expected:
            raise CanonicalJSONError(
                f"fixture canonical hash mismatch: {filename} expected={expected} actual={actual}"
            )


def verify_manifest_strict() -> None:
    """Default: v1_3_0 OS Proof Pack."""
    verify_manifest_strict_for("v1_3_0")


def verify_manifest_strict_v1_2_0() -> None:
    verify_manifest_strict_for("v1_2_0")


def verify_manifest_strict_v1_3_0() -> None:
    verify_manifest_strict_for("v1_3_0")


def verify_manifest_strict_v1_4_0() -> None:
    verify_manifest_strict_for("v1_4_0")


def verify_manifest_strict_v2_0_0_runtime() -> None:
    verify_manifest_strict_for("v2_0_0_runtime")


def run_fixture(pack_dirname: str, fixture_name: str, *, now: int) -> Dict[str, Any]:
    verify_manifest_strict_for(pack_dirname)

    payload = load_canonical_json((_fixture_dir(pack_dirname) / fixture_name).resolve())
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)


def run_all(pack_dirname: str, *, now: int) -> Dict[str, Dict[str, Any]]:
    verify_manifest_strict_for(pack_dirname)
    results: Dict[str, Dict[str, Any]] = {}
    base = _fixture_dir(pack_dirname)
    for p in base.iterdir():
        if p.suffix != ".json":
            continue
        if p.name == _MANIFEST:
            continue
        results[p.name] = run_fixture(pack_dirname, p.name, now=now)
    return results
