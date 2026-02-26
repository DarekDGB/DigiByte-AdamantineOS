from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    ReceiptDecision,
    build_review_receipt_v1,
    compute_review_receipt_hash,
    compute_upgrade_proposal_hash,
    validate_and_canonicalize_review_receipt_v1,
    validate_and_canonicalize_upgrade_proposal_v3,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_template() -> dict[str, Any]:
    p = _repo_root() / "proposals" / "template" / "upgrade_proposal_v3.template.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _finalize_proposal_hash_like_validator(proposal: dict[str, Any]) -> dict[str, Any]:
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

    h = compute_upgrade_proposal_hash(base)
    proposal["proposal_hash"] = h
    return proposal


def _valid_proposal() -> dict[str, Any]:
    return _finalize_proposal_hash_like_validator(_load_template())


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
    assert "unknown keys" in str(e.value)


def test_upgrade_proposal_v3_rejects_hash_mismatch() -> None:
    raw = _valid_proposal()
    raw["proposal_hash"] = "0" * 64

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_upgrade_proposal_v3(raw)
    assert "proposal_hash mismatch" in str(e.value)


def test_build_and_validate_review_receipt_roundtrip() -> None:
    proposal = _valid_proposal()
    v = validate_and_canonicalize_upgrade_proposal_v3(proposal)

    receipt = build_review_receipt_v1(
        proposal_id=v.canonical["proposal_id"],
        proposal_hash=v.canonical["proposal_hash"],
        decision=ReceiptDecision.APPROVE,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        notes="Reviewed manually; OK to proceed.",
        consequence_simulation={
            "transactions_analyzed": 10,
            "newly_denied": 1,
            "newly_allowed": 0,
            "false_positive_increase": 0,
            "false_negative_decrease": 1,
            "safe_to_deploy": True,
        },
    )

    out = validate_and_canonicalize_review_receipt_v1(receipt)
    assert out.canonical["receipt_hash"] == out.computed_hash
    assert out.canonical["decision"] == "APPROVE"


def test_review_receipt_rejects_bad_receipt_hash() -> None:
    proposal = _valid_proposal()
    v = validate_and_canonicalize_upgrade_proposal_v3(proposal)

    receipt = build_review_receipt_v1(
        proposal_id=v.canonical["proposal_id"],
        proposal_hash=v.canonical["proposal_hash"],
        decision=ReceiptDecision.DENY,
        reviewer_id="DarekDGB",
        reviewed_utc="2026-02-26T00:00:00Z",
        notes=None,
        consequence_simulation=None,
    )
    receipt["receipt_hash"] = "0" * 64

    with pytest.raises(ValueError) as e:
        validate_and_canonicalize_review_receipt_v1(receipt)
    assert "receipt_hash mismatch" in str(e.value)


def test_receipt_hash_helper_is_deterministic() -> None:
    base = {
        "v": "proposal_review_receipt_v1",
        "proposal_id": "AC-TEST-001",
        "proposal_hash": "1" * 64,
        "decision": "APPROVE",
        "reviewer_id": "DarekDGB",
        "reviewed_utc": "2026-02-26T00:00:00Z",
        "consequence_simulation": None,
        "notes": None,
    }
    h1 = compute_review_receipt_hash(base)
    h2 = compute_review_receipt_hash(dict(base))
    assert h1 == h2
