from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    ReceiptDecision,
    build_review_receipt,
    compute_proposal_hash,
    load_json_file,
    validate_and_canonicalize_review_receipt,
    validate_and_canonicalize_upgrade_proposal,
)


def _repo_root() -> Path:
    # tests/integrations/<file>.py -> parents[2] is repo root
    return Path(__file__).resolve().parents[2]


def _load_template() -> Dict[str, Any]:
    p = _repo_root() / "proposals" / "template" / "upgrade_proposal_v3.template.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _finalize_proposal_hash_like_validator(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Compute proposal_hash over the canonical form that validator expects."""
    base = dict(proposal)
    base.pop("proposal_hash", None)

    if "evidence" not in base or base["evidence"] is None:
        base["evidence"] = {}

    if "guardrails_ref" not in base or base["guardrails_ref"] is None:
        base["guardrails_ref"] = ""

    if "guardrails" in base:
        # validator maps None -> []
        if base["guardrails"] is None:
            base["guardrails"] = []
        elif isinstance(base["guardrails"], list):
            base["guardrails"] = sorted(set([str(x).strip() for x in base["guardrails"]]))

    if "changes" in base and isinstance(base["changes"], list):
        if all(isinstance(d, dict) and "change_id" in d for d in base["changes"]):
            base["changes"] = sorted(base["changes"], key=lambda d: d["change_id"])

    proposal["proposal_hash"] = compute_proposal_hash(base)
    return proposal


def _valid_proposal() -> Dict[str, Any]:
    return _finalize_proposal_hash_like_validator(_load_template())


def test_upgrade_proposal_v3_validates_and_hash_matches() -> None:
    raw = _valid_proposal()
    res = validate_and_canonicalize_upgrade_proposal(raw)
    assert res.computed_hash == res.canonical["proposal_hash"]


def test_upgrade_proposal_v3_rejects_unknown_root_keys() -> None:
    raw = _valid_proposal()
    raw["extra"] = 1
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)

    assert "unknown keys" in str(e.value)


def test_upgrade_proposal_v3_rejects_hash_mismatch() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "0" * 64

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)

    assert "proposal_hash" in str(e.value)


def test_upgrade_proposal_v3_rejects_bad_timestamp_format() -> None:
    raw = _valid_proposal()
    raw["created_utc"] = "2026-02-24T00:00:00"  # missing Z
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)

    assert "created_utc" in str(e.value)


def test_upgrade_proposal_v3_rejects_invalid_iso_date_even_with_z() -> None:
    raw = _valid_proposal()
    raw["created_utc"] = "2026-99-99T00:00:00Z"
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError):
        validate_and_canonicalize_upgrade_proposal(raw)


def test_upgrade_proposal_v3_rejects_target_not_object() -> None:
    raw = _valid_proposal()
    raw["target"] = []  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)
    assert "target" in str(e.value)


def test_upgrade_proposal_v3_rejects_target_unknown_key() -> None:
    raw = _valid_proposal()
    assert isinstance(raw["target"], dict)
    raw["target"]["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)
    assert "unknown keys" in str(e.value)


def test_upgrade_proposal_v3_changes_validation_branches() -> None:
    # empty
    raw = _valid_proposal()
    raw["changes"] = []
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError):
        validate_and_canonicalize_upgrade_proposal(raw)

    # entry not object
    raw = _valid_proposal()
    raw["changes"] = [123]  # type: ignore[list-item]
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)
    assert "change" in str(e.value)

    # unknown key
    raw = _valid_proposal()
    assert isinstance(raw["changes"], list)
    assert isinstance(raw["changes"][0], dict)
    raw["changes"][0]["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError):
        validate_and_canonicalize_upgrade_proposal(raw)

    # bad type
    raw = _valid_proposal()
    raw["changes"][0]["type"] = "hack"
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)
    assert "bad change.type" in str(e.value)

    # duplicate id
    raw = _valid_proposal()
    raw["changes"].append(dict(raw["changes"][0]))
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)
    assert "duplicate change_id" in str(e.value)


def test_upgrade_proposal_v3_evidence_wrong_type_rejected() -> None:
    raw = _valid_proposal()
    raw["evidence"] = []  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal(raw)
    assert "evidence" in str(e.value)


def test_upgrade_proposal_v3_guardrails_branches() -> None:
    # guardrails missing -> treated as [] (canonical)
    raw = _load_template()
    raw.pop("guardrails", None)
    raw["guardrails"] = []
    raw = _finalize_proposal_hash_like_validator(raw)
    res = validate_and_canonicalize_upgrade_proposal(raw)
    assert res.canonical["guardrails"] == []

    # explicit None branch
    raw = _load_template()
    raw["guardrails"] = None
    raw = _finalize_proposal_hash_like_validator(raw)
    res = validate_and_canonicalize_upgrade_proposal(raw)
    assert res.canonical["guardrails"] == []

    # not list
    raw = _valid_proposal()
    raw["guardrails"] = "AMG-001"  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError):
        validate_and_canonicalize_upgrade_proposal(raw)

    # element not str
    raw = _valid_proposal()
    raw["guardrails"] = ["AMG-001", 123]  # type: ignore[list-item]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError):
        validate_and_canonicalize_upgrade_proposal(raw)

    # guardrails_ref invalid
    raw = _valid_proposal()
    raw["guardrails_ref"] = 123  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)
    with pytest.raises(ValueError):
        validate_and_canonicalize_upgrade_proposal(raw)


def test_canonicalization_sorts_changes_and_guardrails() -> None:
    raw = _load_template()
    raw["guardrails"] = ["AMG-011", "AMG-001", "AMG-001"]
    raw["changes"] = [
        {"change_id": "CHG-002", "type": "modify", "detail": "b"},
        {"change_id": "CHG-001", "type": "modify", "detail": "a"},
    ]
    raw = _finalize_proposal_hash_like_validator(raw)
    res = validate_and_canonicalize_upgrade_proposal(raw)
    assert res.canonical["guardrails"] == ["AMG-001", "AMG-011"]
    assert [c["change_id"] for c in res.canonical["changes"]] == ["CHG-001", "CHG-002"]


def test_build_and_validate_review_receipt_roundtrip() -> None:
    proposal = _valid_proposal()
    receipt = build_review_receipt(
        proposal,
        decision=ReceiptDecision.APPROVE.value,
        reviewer_id="maintainer@local",
        notes="ok",
        consequence_simulation={"impact": "low"},
    )
    rr = validate_and_canonicalize_review_receipt(receipt)
    assert rr.canonical["receipt_hash"] == rr.computed_hash


def test_review_receipt_rejects_bad_receipt_hash_and_bad_decision() -> None:
    proposal = _valid_proposal()
    receipt = build_review_receipt(
        proposal,
        decision=ReceiptDecision.DENY.value,
        reviewer_id="maintainer@local",
        notes="no",
    )

    # bad hash
    receipt["receipt_hash"] = "0" * 64
    with pytest.raises(ValueError):
        validate_and_canonicalize_review_receipt(receipt)

    # bad decision
    receipt = build_review_receipt(
        proposal,
        decision=ReceiptDecision.APPROVE.value,
        reviewer_id="maintainer@local",
        notes="ok",
    )
    receipt["decision"] = "maybe"
    with pytest.raises(ValueError):
        validate_and_canonicalize_review_receipt(receipt)


def test_load_json_file_invalid_json_and_non_object() -> None:
    tmp = Path(__file__).parent
    bad = tmp / "_tmp_bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    try:
        with pytest.raises(ValueError):
            load_json_file(bad)
    finally:
        bad.unlink(missing_ok=True)

    arr = tmp / "_tmp_arr.json"
    arr.write_text("[]", encoding="utf-8")
    try:
        with pytest.raises(ValueError):
            load_json_file(arr)
    finally:
        arr.unlink(missing_ok=True)
