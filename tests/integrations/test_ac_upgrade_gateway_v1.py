from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    ReceiptDecision,
    build_review_receipt,
    compute_upgrade_proposal_hash,
    validate_and_canonicalize_review_receipt,
    validate_and_canonicalize_upgrade_proposal,
)


def _repo_root() -> Path:
    # This file lives in tests/integrations/, so:
    # parents[0] = integrations
    # parents[1] = tests
    # parents[2] = repo root
    return Path(__file__).resolve().parents[2]


def _load_template() -> Dict[str, Any]:
    p = _repo_root() / "proposals" / "template" / "upgrade_proposal_v3.template.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _finalize_proposal_hash_like_validator(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute proposal_hash over the canonical form the gateway validator expects:
    - evidence defaults to {}
    - guardrails_ref defaults to ""
    - guardrails sorted/deduped (if list)
    - changes sorted by change_id (if list of dicts containing change_id)
    """
    base = dict(proposal)
    base.pop("proposal_hash", None)

    if "evidence" not in base or base["evidence"] is None:
        base["evidence"] = {}

    if "guardrails_ref" not in base or base["guardrails_ref"] is None:
        base["guardrails_ref"] = ""

    if "guardrails" in base and isinstance(base["guardrails"], list):
        base["guardrails"] = sorted(set([str(x).strip() for x in base["guardrails"]]))

    if "changes" in base and isinstance(base["changes"], list):
        if all(isinstance(d, dict) and "change_id" in d for d in base["changes"]):
            base["changes"] = sorted(base["changes"], key=lambda d: d["change_id"])

    proposal["proposal_hash"] = compute_upgrade_proposal_hash(base)
    return proposal


def _valid_proposal() -> Dict[str, Any]:
    return _finalize_proposal_hash_like_validator(_load_template())


def _expect_value_error(fn, contains: str) -> None:
    with pytest.raises(ValueError) as e:
        fn()
    assert contains in str(e.value)


# -----------------------------------------------------------------------------
# Proposal validation (happy path + fail-closed branches)
# -----------------------------------------------------------------------------


def test_upgrade_proposal_v3_validates_and_hash_matches() -> None:
    raw = _valid_proposal()
    res = validate_and_canonicalize_upgrade_proposal(raw)
    assert res.canonical["v"] == "upgrade_proposal_v3"
    assert res.canonical["proposal_hash"] == res.computed_hash


def test_upgrade_proposal_v3_rejects_unknown_root_keys() -> None:
    raw = _valid_proposal()
    raw["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "unknown keys in proposal")


def test_upgrade_proposal_v3_rejects_missing_required_field() -> None:
    raw = _valid_proposal()
    raw.pop("summary", None)
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "missing 'summary'")


def test_upgrade_proposal_v3_rejects_blank_required_str() -> None:
    raw = _valid_proposal()
    raw["summary"] = "   "
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "must be non-empty str")


def test_upgrade_proposal_v3_rejects_bad_v() -> None:
    raw = _valid_proposal()
    raw["v"] = "wrong"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "bad 'v'")


def test_upgrade_proposal_v3_rejects_spaces_in_proposal_id() -> None:
    raw = _valid_proposal()
    raw["proposal_id"] = "AC BAD"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "must not contain spaces")


def test_upgrade_proposal_v3_rejects_domain_outside_allowlist() -> None:
    raw = _valid_proposal()
    raw["domain"] = "UI_LOGIC"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "bad 'domain'")


def test_upgrade_proposal_v3_rejects_action_outside_allowlist() -> None:
    raw = _valid_proposal()
    raw["action"] = "LOWER_THRESHOLD"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "bad 'action'")


def test_upgrade_proposal_v3_rejects_target_not_object() -> None:
    raw = _valid_proposal()
    raw["target"] = []  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "'target' must be object")


def test_upgrade_proposal_v3_rejects_target_unknown_key() -> None:
    raw = _valid_proposal()
    raw["target"]["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "unknown keys in target")


def test_upgrade_proposal_v3_rejects_timestamp_missing_z() -> None:
    raw = _valid_proposal()
    raw["created_utc"] = "2026-02-24T00:00:00"  # missing Z
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "created_utc must end with 'Z'")


def test_upgrade_proposal_v3_rejects_timestamp_invalid_isoformat() -> None:
    raw = _valid_proposal()
    raw["created_utc"] = "2026-99-99T00:00:00Z"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "invalid ISO8601 timestamp")


def test_upgrade_proposal_v3_rejects_changes_empty() -> None:
    raw = _valid_proposal()
    raw["changes"] = []
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "'changes' must be non-empty list")


def test_upgrade_proposal_v3_rejects_change_entry_not_object() -> None:
    raw = _valid_proposal()
    raw["changes"] = [123]  # type: ignore[list-item]

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "change entry must be object")


def test_upgrade_proposal_v3_rejects_change_unknown_key() -> None:
    raw = _valid_proposal()
    raw["changes"][0]["extra"] = "x"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "unknown keys in change")


def test_upgrade_proposal_v3_rejects_change_bad_type() -> None:
    raw = _valid_proposal()
    raw["changes"][0]["type"] = "hack"
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "bad change.type")


def test_upgrade_proposal_v3_rejects_duplicate_change_id() -> None:
    raw = _valid_proposal()
    raw["changes"].append(dict(raw["changes"][0]))
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "duplicate change_id")


def test_upgrade_proposal_v3_rejects_evidence_wrong_type() -> None:
    raw = _valid_proposal()
    raw["evidence"] = []  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "'evidence' must be object")


def test_upgrade_proposal_v3_accepts_guardrails_none_canonicalizes_to_empty() -> None:
    raw = _load_template()
    raw["guardrails"] = None  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)

    res = validate_and_canonicalize_upgrade_proposal(raw)
    assert res.canonical["guardrails"] == []


def test_upgrade_proposal_v3_rejects_guardrails_not_list() -> None:
    raw = _valid_proposal()
    raw["guardrails"] = "AMG-001"  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "'guardrails' must be list[str]")


def test_upgrade_proposal_v3_rejects_guardrails_element_not_str() -> None:
    raw = _valid_proposal()
    raw["guardrails"] = ["AMG-001", 123]  # type: ignore[list-item]
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "guardrail ids must be non-empty str")


def test_upgrade_proposal_v3_rejects_guardrails_ref_invalid_type() -> None:
    raw = _valid_proposal()
    raw["guardrails_ref"] = 123  # type: ignore[assignment]
    raw = _finalize_proposal_hash_like_validator(raw)

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "'guardrails_ref' must be non-empty str")


def test_upgrade_proposal_v3_rejects_hash_invalid_format() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "A" * 64  # uppercase invalid

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "proposal_hash must be 64 lowercase hex chars")


def test_upgrade_proposal_v3_rejects_hash_mismatch() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "0" * 64  # wrong

    _expect_value_error(lambda: validate_and_canonicalize_upgrade_proposal(raw), "expected")


def test_upgrade_proposal_v3_canonicalization_sorts_and_dedupes() -> None:
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


# -----------------------------------------------------------------------------
# Review receipt validation (happy path + fail-closed branches)
# -----------------------------------------------------------------------------


def test_build_and_validate_review_receipt_roundtrip() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.APPROVE,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={"transactions_analyzed": 10, "false_positive_increase": 0, "safe_to_deploy": True},
        notes="Reviewed.",
    )

    res = validate_and_canonicalize_review_receipt(receipt)
    assert res.canonical["decision"] == "APPROVE"
    assert res.canonical["receipt_hash"] == res.computed_hash


def test_review_receipt_rejects_unknown_keys() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.DENY,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="No.",
    )
    receipt["extra"] = "x"

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "unknown keys in receipt")


def test_review_receipt_rejects_bad_v() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.DENY,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="No.",
    )
    receipt["v"] = "wrong"

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "bad 'v'")


def test_review_receipt_rejects_bad_reviewed_utc() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.DENY,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="No.",
    )
    receipt["reviewed_utc"] = "2026-02-26T00:00:00"  # missing Z

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "must end with 'Z'")


def test_review_receipt_rejects_consequence_simulation_wrong_type() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.DENY,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="No.",
    )
    receipt["consequence_simulation"] = []  # type: ignore[assignment]

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "'consequence_simulation' must be object")


def test_review_receipt_rejects_notes_wrong_type() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.DENY,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="No.",
    )
    receipt["notes"] = 123  # type: ignore[assignment]

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "'notes' must be non-empty str")


def test_review_receipt_rejects_bad_receipt_hash_format() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.APPROVE,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="Ok.",
    )
    receipt["receipt_hash"] = "A" * 64

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "receipt_hash must be 64 lowercase hex chars")


def test_review_receipt_rejects_bad_receipt_hash_mismatch() -> None:
    proposal = validate_and_canonicalize_upgrade_proposal(_valid_proposal()).canonical

    receipt = build_review_receipt(
        proposal=proposal,
        decision=ReceiptDecision.APPROVE,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        consequence_simulation={},
        notes="Ok.",
    )
    receipt["receipt_hash"] = "0" * 64

    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(receipt), "expected")


def test_review_receipt_rejects_non_mapping_root() -> None:
    _expect_value_error(lambda: validate_and_canonicalize_review_receipt(["nope"]), "receipt must be an object")  # type: ignore[arg-type]
