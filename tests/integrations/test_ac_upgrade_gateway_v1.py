from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    build_review_receipt_v1,
    compute_proposal_hash,
    compute_receipt_hash,
    load_json_file,
    validate_and_canonicalize_upgrade_proposal_v3,
    validate_review_receipt_v1,
)


def _repo_root() -> Path:
    # tests/integrations/<file>.py -> parents[2] is repo root
    return Path(__file__).resolve().parents[2]


def _load_template() -> Dict[str, Any]:
    p = _repo_root() / "proposals" / "template" / "upgrade_proposal_v3.template.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _finalize_proposal_hash_like_validator(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute proposal_hash over the canonical form that the validator expects:
    - changes sorted by change_id
    - guardrails sorted/deduped; missing/None => []
    - evidence defaults to {}
    - guardrails_ref defaults to ""
    """
    base = dict(proposal)
    base.pop("proposal_hash", None)

    # evidence default
    if "evidence" not in base or base["evidence"] is None:
        base["evidence"] = {}

    # guardrails_ref default
    if "guardrails_ref" not in base or base["guardrails_ref"] is None:
        base["guardrails_ref"] = ""

    # guardrails canonical outcome for missing/None is []
    if "guardrails" not in base or base["guardrails"] is None:
        base["guardrails"] = []
    elif isinstance(base["guardrails"], list):
        base["guardrails"] = sorted(set([str(x).strip() for x in base["guardrails"]]))

    # canonicalize changes (only if entries look like dicts with change_id)
    if "changes" in base and isinstance(base["changes"], list):
        if all(isinstance(d, dict) and "change_id" in d for d in base["changes"]):
            base["changes"] = sorted(base["changes"], key=lambda d: d["change_id"])

    proposal["proposal_hash"] = compute_proposal_hash(base)
    return proposal


def _valid_proposal() -> Dict[str, Any]:
    return _finalize_proposal_hash_like_validator(_load_template())


def _finalize_receipt_hash_like_validator(receipt: Dict[str, Any]) -> Dict[str, Any]:
    base = dict(receipt)
    base.pop("receipt_hash", None)
    receipt["receipt_hash"] = compute_receipt_hash(base)
    return receipt


def test_upgrade_proposal_v3_validates_and_hash_matches() -> None:
    raw = _valid_proposal()
    res = validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert res.canonical["proposal_hash"] == res.computed_hash


def test_upgrade_proposal_v3_rejects_unknown_root_keys() -> None:
    raw = _valid_proposal()
    raw["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)

    assert "unknown keys in proposal" in str(e.value)


def test_upgrade_proposal_v3_rejects_bad_domain_and_action() -> None:
    raw = _valid_proposal()
    raw["domain"] = "UI_LOGIC"
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "bad domain" in str(e.value)

    raw = _valid_proposal()
    raw["action"] = "LOWER_THRESHOLD"
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "bad action" in str(e.value)


def test_upgrade_proposal_v3_rejects_hash_mismatch() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "0" * 64

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)

    assert "AC_UPG_V3_HASH_INVALID" in str(e.value)


def test_upgrade_proposal_v3_rejects_hash_invalid_format() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "A" * 64  # uppercase not allowed

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)

    assert "AC_UPG_V3_HASH_INVALID" in str(e.value)


def test_upgrade_proposal_v3_guardrails_none_and_missing_are_canonicalized() -> None:
    raw = _load_template()
    raw.pop("guardrails", None)  # missing -> treated as None -> []
    raw = _finalize_proposal_hash_like_validator(raw)

    res = validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert res.canonical["guardrails"] == []

    raw = _load_template()
    raw["guardrails"] = None
    raw = _finalize_proposal_hash_like_validator(raw)

    res = validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert res.canonical["guardrails"] == []


def test_upgrade_proposal_v3_canonicalization_sorts_changes_and_guardrails() -> None:
    raw = _load_template()
    raw["guardrails"] = ["AMG-011", "AMG-001", "AMG-001"]
    raw["changes"] = [
        {"change_id": "CHG-002", "type": "modify", "detail": "b"},
        {"change_id": "CHG-001", "type": "modify", "detail": "a"},
    ]
    raw = _finalize_proposal_hash_like_validator(raw)

    res = validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert res.canonical["guardrails"] == ["AMG-001", "AMG-011"]
    assert [c["change_id"] for c in res.canonical["changes"]] == ["CHG-001", "CHG-002"]


def test_upgrade_proposal_v3_rejects_bad_timestamp_and_blank_summary() -> None:
    raw = _valid_proposal()
    raw["created_utc"] = "2026-02-24T00:00:00"  # missing Z
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "created_utc must end with 'Z'" in str(e.value)

    raw = _valid_proposal()
    raw["created_utc"] = "2026-99-99T00:00:00Z"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "invalid ISO8601 timestamp" in str(e.value)

    raw = _valid_proposal()
    raw["summary"] = "   "
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "must be non-empty str" in str(e.value)


def test_upgrade_proposal_v3_rejects_target_shape_and_unknown_key() -> None:
    raw = _valid_proposal()
    raw["target"] = []  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "'target' must be object" in str(e.value)

    raw = _valid_proposal()
    raw["target"]["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "unknown keys in target" in str(e.value)


def test_upgrade_proposal_v3_rejects_changes_shape_and_duplicates() -> None:
    raw = _valid_proposal()
    raw["changes"] = []
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "'changes' must be non-empty list" in str(e.value)

    raw = _valid_proposal()
    raw["changes"] = [123]  # type: ignore[list-item]
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "change entry must be object" in str(e.value)

    raw = _valid_proposal()
    raw["changes"][0]["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "unknown keys in change" in str(e.value)

    raw = _valid_proposal()
    raw["changes"][0]["type"] = "hack"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "bad change.type" in str(e.value)

    raw = _valid_proposal()
    raw["changes"].append(dict(raw["changes"][0]))
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "duplicate change_id" in str(e.value)


def test_upgrade_proposal_v3_rejects_evidence_and_guardrails_types() -> None:
    raw = _valid_proposal()
    raw["evidence"] = []  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "'evidence' must be object" in str(e.value)

    raw = _valid_proposal()
    raw["guardrails"] = "AMG-001"  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "'guardrails' must be list[str]" in str(e.value)

    raw = _valid_proposal()
    raw["guardrails"] = ["AMG-001", 123]  # type: ignore[list-item]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "guardrail ids must be non-empty str" in str(e.value)

    raw = _valid_proposal()
    raw["guardrails_ref"] = 123  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "'guardrails_ref' must be non-empty str" in str(e.value)


def test_load_json_file_invalid_and_non_object_fail_closed(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        load_json_file(p)
    assert "DENY_SCHEMA_INVALID" in str(e.value)

    q = tmp_path / "arr.json"
    q.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        load_json_file(q)
    assert "DENY_SCHEMA_INVALID" in str(e.value)


def test_build_and_validate_review_receipt_roundtrip() -> None:
    proposal = _valid_proposal()

    receipt = build_review_receipt_v1(
        proposal_hash=proposal["proposal_hash"],
        decision="APPROVE",
        reviewer="DarekDGB",
        reviewer_notes="OK",
    )
    validate_review_receipt_v1(receipt, expected_proposal_hash=proposal["proposal_hash"])


def test_review_receipt_rejects_bad_fields_and_hash_mismatch() -> None:
    proposal = _valid_proposal()

    receipt = build_review_receipt_v1(
        proposal_hash=proposal["proposal_hash"],
        decision="APPROVE",
        reviewer="DarekDGB",
        reviewer_notes="OK",
    )

    # tamper receipt_hash
    bad = dict(receipt)
    bad["receipt_hash"] = "0" * 64
    with pytest.raises(ValueError) as e:
        validate_review_receipt_v1(bad, expected_proposal_hash=proposal["proposal_hash"])
    assert "AC_UPG_RECEIPT_HASH_INVALID" in str(e.value)

    # bad decision
    bad2 = dict(receipt)
    bad2["decision"] = "MAYBE"
    bad2 = _finalize_receipt_hash_like_validator(bad2)
    with pytest.raises(ValueError) as e:
        validate_review_receipt_v1(bad2, expected_proposal_hash=proposal["proposal_hash"])
    assert "bad decision" in str(e.value)

    # expected proposal hash mismatch
    with pytest.raises(ValueError) as e:
        validate_review_receipt_v1(receipt, expected_proposal_hash="1" * 64)
    assert "proposal_hash mismatch" in str(e.value)

    # invalid receipt_hash format
    bad3 = dict(receipt)
    bad3["receipt_hash"] = "A" * 64
    with pytest.raises(ValueError) as e:
        validate_review_receipt_v1(bad3, expected_proposal_hash=proposal["proposal_hash"])
    assert "receipt_hash must be 64 lowercase hex chars" in str(e.value)
