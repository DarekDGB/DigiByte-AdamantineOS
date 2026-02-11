"""
Utility functions to load and execute deterministic end-to-end fixtures for
Adamantine Wallet OS v1.2.0.  These helpers are part of the OS proof pack and
provide an opinionated integration harness around ``orchestrate_execution_v2``.

The harness performs the following steps:

* Loads frozen JSON fixtures from ``adamantine/v1/fixtures/v1_2_0`` using a
  canonical JSON loader that rejects duplicate keys. This prevents ambiguous
  parsing and hidden state.
* Builds a minimal but complete ``RiskPolicy`` and ``PolicyPack`` to drive
  the orchestrator.  External reason mappings and allowlists are derived
  from the official test matrix used by ``orchestrator_v2``.
* Executes the orchestrator with an in‑memory nonce store and recording
  executor.  The resulting response dict is returned directly.
* Provides helpers to run all fixtures in one call and to verify the SHA256
  manifest of the fixtures.  The manifest is stored alongside the fixtures
  and is used by CI to detect accidental changes.

These utilities are not part of the core deterministic engine; they live
in ``execution`` because they orchestrate the full execution path.  They
are intended for integration tests and reproducibility checking.
"""

from __future__ import annotations

import json
import hashlib
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
    """Raised when canonical JSON loading fails."""


class DuplicateKeyError(CanonicalJSONError):
    """Raised when a duplicate key is encountered in a JSON object."""


def _no_duplicate_object_pairs_hook(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    """
    ``object_pairs_hook`` callback for ``json.loads`` that constructs a dict
    while rejecting duplicate keys.  JSON allows duplicate object keys, but
    Adamantine treats this as a schema error to prevent hidden state.
    """
    obj: Dict[str, Any] = {}
    for k, v in pairs:
        if k in obj:
            raise DuplicateKeyError(f"duplicate key: {k}")
        obj[k] = v
    return obj


def load_canonical_json(path: Path) -> Any:
    """
    Load a JSON file using a strict parser that rejects duplicate object keys.

    Raises CanonicalJSONError on failure.
    """
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


def sha256_hex_of_file_bytes(path: Path) -> str:
    """SHA256 of the exact on-disk bytes (no canonicalization)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_policy() -> RiskPolicy:
    """
    Mirror orchestrator_v2 test matrix policy:
    - min score 85
    - allowlisted external reason IDs
    - explicit external->internal reason mapping
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
    return RiskPolicy(min_overall_score=85, policy_pack=pack)


def run_fixture(fixture_name: str, *, now: int) -> Dict[str, Any]:
    """
    Execute a single fixture using orchestrator_v2 and return the response.
    """
    # Hard-lock fixture drift before executing anything.
    verify_manifest_strict()

    base = Path(__file__).parent.parent / "fixtures" / "v1_2_0"
    file_path = base / fixture_name
    data = load_canonical_json(file_path)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=data, now=now, executor=executor, nonce_store=store, policy=policy)


def run_all(*, now: int) -> Dict[str, Dict[str, Any]]:
    """
    Execute all fixtures in v1_2_0 and return fixture_name -> response.
    """
    verify_manifest_strict()
    results: Dict[str, Dict[str, Any]] = {}
    base = Path(__file__).parent.parent / "fixtures" / "v1_2_0"
    for p in base.iterdir():
        if p.suffix != ".json":
            continue
        if p.name == "manifest.json":
            continue
        results[p.name] = run_fixture(p.name, now=now)
    return results


def verify_manifest() -> bool:
    """
    Best-effort check: returns True if all listed hashes match.
    """
    base = Path(__file__).parent.parent / "fixtures" / "v1_2_0"
    manifest_path = base / "manifest.json"
    manifest = load_canonical_json(manifest_path)
    for filename, expected in manifest.items():
        fixture_path = base / filename
        actual = sha256_hex_of_file_bytes(fixture_path)
        if actual != expected:
            return False
    return True


def verify_manifest_strict() -> None:
    """
    Strict CI contract:
    - manifest must list exactly all fixture json files (excluding itself)
    - no extras, no missing
    - SHA256 is of exact bytes (format drift counts)
    """
    base = Path(__file__).parent.parent / "fixtures" / "v1_2_0"
    manifest_path = base / "manifest.json"

    obj = load_canonical_json(manifest_path)
    if not isinstance(obj, dict):
        raise CanonicalJSONError("manifest must be a JSON object")

    manifest: Dict[str, str] = {}
    for k, v in obj.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise CanonicalJSONError("manifest must map string->string")
        manifest[k] = v

    fixture_files = sorted(
        p.name for p in base.iterdir() if p.suffix == ".json" and p.name != "manifest.json"
    )
    manifest_files = sorted(manifest.keys())

    if fixture_files != manifest_files:
        raise CanonicalJSONError(
            f"manifest fixture set mismatch: fixtures={fixture_files} manifest={manifest_files}"
        )

    for filename in fixture_files:
        fixture_path = base / filename
        expected = manifest[filename]
        actual = sha256_hex_of_file_bytes(fixture_path)
        if actual != expected:
            raise CanonicalJSONError(f"fixture hash mismatch: {filename}")
