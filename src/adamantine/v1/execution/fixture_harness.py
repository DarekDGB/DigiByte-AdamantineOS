"""
Utility functions to load and execute deterministic end-to-end fixtures for
Adamantine Wallet OS v1.3.0 OS Proof Pack.

Manifest enforcement is semantic and deterministic:
- We reject duplicate keys when parsing JSON (deny-by-default)
- We hash canonicalized JSON (sort_keys + stable separators)
  so whitespace/formatting changes do NOT break the manifest,
  but any semantic change DOES.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

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


_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "v1_3_0"
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
    # Deterministic representation
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex_of_canonical_json_file(path: Path) -> str:
    """
    Semantic hash:
    - parse with duplicate-key rejection
    - hash canonical dumps
    """
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


def verify_manifest_strict() -> None:
    """
    Strict CI contract (semantic):
    - manifest must list exactly all fixture .json files (excluding itself)
    - SHA256 is over canonical JSON (whitespace doesn't matter)
    - mismatch error prints the correct hash for iPhone copy/paste updates
    """
    base = _FIXTURE_DIR.resolve()
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


def verify_manifest() -> bool:
    try:
        verify_manifest_strict()
        return True
    except Exception:
        return False


def run_fixture(fixture_name: str, *, now: int) -> Dict[str, Any]:
    verify_manifest_strict()

    payload = load_canonical_json((_FIXTURE_DIR / fixture_name).resolve())
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)


def run_all(*, now: int) -> Dict[str, Dict[str, Any]]:
    verify_manifest_strict()
    results: Dict[str, Dict[str, Any]] = {}
    for p in _FIXTURE_DIR.iterdir():
        if p.suffix != ".json":
            continue
        if p.name == _MANIFEST:
            continue
        results[p.name] = run_fixture(p.name, now=now)
    return results
