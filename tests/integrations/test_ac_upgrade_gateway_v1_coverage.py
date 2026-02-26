from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    build_review_receipt_v1,
    compute_review_receipt_hash,
    compute_upgrade_proposal_hash,
    load_json_file,
    validate_and_canonicalize_review_receipt_v1,
    validate_and_canonicalize_upgrade_proposal_v3,
)


def _canonical_valid_proposal_base() -> Dict[str, Any]:
    # Minimal valid v3 proposal (Adamantine-side gateway contract)
    base: Dict[str, Any] = {
        "v": "upgrade_proposal_v3",
        "proposal_id": "AC-UPG-001",
        "target": {"component": "adaptive_core", "version": "v3.0.0"},
        "created_utc": "2026-02-24T00:00:00Z",
        "summary": "test",
        "domain": "SECURITY_THRESHOLDS",
        "action": "INCREASE_THRESHOLD",
        "changes": [{"change_id": "CHG-001", "type": "modify", "detail": "x"}],
        "evidence": {},
        "guardrails": [],
        "guardrails_ref": "",
    }
    return base


def _finalize_proposal_hash_like_validator(p: Dict[str, Any]) -> Dict[str, Any]:
    base = dict(p)
    base.pop("proposal_hash", None)

    # Evidence default
    if "evidence" not in base or base["evidence"] is None:
        base["evidence"] = {}

    # guardrails_ref default (validator canonicalizes missing/None to "")
    if "guardrails_ref" not in base or base["guardrails_ref"] is None:
        base["guardrails_ref"] = ""

    # Canonicalize guardrails if list
    if "guardrails" in base and isinstance(base["guardrails"], list):
        base["guardrails"] = sorted(set([str(x).strip() for x in base["guardrails"]]))

    # Canonicalize changes if list[dict]
    if "changes" in base and isinstance(base["changes"], list):
        if all(isinstance(d, dict) and "change_id" in d for d in base["changes"]):
            base["changes"] = sorted(base["changes"], key=lambda d: d["change_id"])

    h = compute_upgrade_proposal_hash(base)
    p["proposal_hash"] = h
    return p


def _valid_proposal() -> Dict[str, Any]:
    return _finalize_proposal_hash_like_validator(_canonical_valid_proposal_base())


def _valid_receipt(*, consequence_simulation: Any = None) -> Dict[str, Any]:
    # Build a valid receipt with correct receipt_hash
    base: Dict[str, Any] = {
        "v": "ac_review_receipt_v1",
        "proposal_id": "AC-UPG-001",
        "proposal_hash": "0" * 64,
        "decision": "APPROVE",
        "reviewer_id": "maintainer@local",
        "reviewed_utc": "2026-02-24T00:00:00Z",
        "notes": "ok",
    }
    if consequence_simulation is not None:
        base["consequence_simulation"] = consequence_simulation
    else:
        # Intentionally omit key to hit cs=None branch in validator
        pass

    without_hash = dict(base)
    without_hash.pop("receipt_hash", None)
    h = compute_review_receipt_hash(without_hash)
    base["receipt_hash"] = h
    return base


# -----------------------------------------------------------------------------
# Cover load_json_file success path (line 127)
# -----------------------------------------------------------------------------
def test_load_json_file_valid_object_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "ok.json"
    p.write_text(json.dumps({"x": 1}), encoding="utf-8")
    res = load_json_file(p)
    assert res == {"x": 1}


# -----------------------------------------------------------------------------
# Cover _require_str branches: missing + empty (lines 132, 135)
# -----------------------------------------------------------------------------
def test_upgrade_proposal_missing_summary_hits_missing_field_branch() -> None:
    raw = _canonical_valid_proposal_base()
    raw.pop("summary", None)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "missing 'summary'" in str(e.value)


def test_upgrade_proposal_empty_summary_hits_non_empty_str_branch() -> None:
    raw = _canonical_valid_proposal_base()
    raw["summary"] = "   "
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "'summary' must be non-empty str" in str(e.value)


# -----------------------------------------------------------------------------
# Cover _canon_guardrails guardrails_ref None default (line 170)
# -----------------------------------------------------------------------------
def test_upgrade_proposal_guardrails_ref_missing_defaults_to_empty_string() -> None:
    raw = _canonical_valid_proposal_base()
    raw.pop("guardrails_ref", None)  # raw.get -> None -> ref=""
    raw = _finalize_proposal_hash_like_validator(raw)

    res = validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert res.canonical["guardrails_ref"] == ""


# -----------------------------------------------------------------------------
# Cover proposal validator early rejects (lines 184, 190, 194, 202, 206, 245)
# -----------------------------------------------------------------------------
def test_upgrade_proposal_rejects_non_mapping_root() -> None:
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(["nope"])  # type: ignore[arg-type]
    assert "proposal must be an object" in str(e.value)


def test_upgrade_proposal_rejects_bad_v() -> None:
    raw = _valid_proposal()
    raw["v"] = "wrong"
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "bad 'v'" in str(e.value)


def test_upgrade_proposal_rejects_spaces_in_proposal_id() -> None:
    raw = _valid_proposal()
    raw["proposal_id"] = "BAD ID"
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "proposal_id must not contain spaces" in str(e.value)


def test_upgrade_proposal_rejects_bad_domain() -> None:
    raw = _valid_proposal()
    raw["domain"] = "NOT_A_DOMAIN"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "bad domain" in str(e.value)


def test_upgrade_proposal_rejects_bad_action() -> None:
    raw = _valid_proposal()
    raw["action"] = "NOT_AN_ACTION"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "bad action" in str(e.value)


def test_upgrade_proposal_rejects_bad_proposal_hash_format() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "A" * 64  # uppercase invalid
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "proposal_hash must be 64 lowercase hex chars" in str(e.value)


# -----------------------------------------------------------------------------
# Cover receipt builder branch: consequence_simulation wrong type (line 283)
# -----------------------------------------------------------------------------
def test_build_review_receipt_v1_rejects_bad_consequence_simulation_type() -> None:
    with pytest.raises(ValueError) as e:
        build_review_receipt_v1(
            proposal_id="AC-UPG-001",
            proposal_hash="0" * 64,
            decision="APPROVE",  # type: ignore[arg-type]
            reviewer_id="maintainer@local",
            reviewed_utc="2026-02-24T00:00:00Z",
            notes="ok",
            consequence_simulation=["nope"],  # type: ignore[arg-type]
        )
    assert "consequence_simulation must be object if present" in str(e.value)


# -----------------------------------------------------------------------------
# Cover receipt validator branches (lines 306, 323, 328, 342, 345, 350)
# -----------------------------------------------------------------------------
def test_review_receipt_rejects_non_mapping_root() -> None:
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_review_receipt_v1(["nope"])  # type: ignore[arg-type]
    assert "receipt must be object" in str(e.value)


def test_review_receipt_rejects_bad_v() -> None:
    r = _valid_receipt()
    r["v"] = "wrong"
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_review_receipt_v1(r)
    assert "bad receipt v" in str(e.value)


def test_review_receipt_rejects_bad_proposal_hash_format() -> None:
    r = _valid_receipt()
    r["proposal_hash"] = "A" * 64
    # receipt_hash now wrong, but validator fails earlier at proposal_hash format
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_review_receipt_v1(r)
    assert "bad proposal_hash" in str(e.value)


def test_review_receipt_consequence_simulation_none_branch_defaults_to_empty() -> None:
    r = _valid_receipt(consequence_simulation=None)  # omit key -> cs is None -> {}
    res = validate_and_canonicalize_review_receipt_v1(r)
    assert res.canonical["consequence_simulation"] == {}


def test_review_receipt_rejects_consequence_simulation_not_object() -> None:
    r = _valid_receipt(consequence_simulation=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_review_receipt_v1(r)
    assert "consequence_simulation must be object" in str(e.value)


def test_review_receipt_rejects_bad_receipt_hash_format() -> None:
    r = _valid_receipt()
    r["receipt_hash"] = "A" * 64
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_review_receipt_v1(r)
    assert "bad receipt_hash format" in str(e.value)
