from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    ReceiptDecision,
    compute_review_receipt_hash,
    evaluate_upgrade_request_v1,
    validate_and_canonicalize_upgrade_proposal_v3,
)


@dataclass(frozen=True, slots=True)
class _Decision:
    allow: bool
    reason_id: str


def _valid_proposal() -> Dict[str, Any]:
    raw: Dict[str, Any] = {
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
        "proposal_hash": "",
    }

    # Canonicalize + compute correct proposal_hash using the validator’s rules.
    # We let the real validator compute what it expects by:
    # - computing hash over canonical_without_hash (same as gateway)
    from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import compute_upgrade_proposal_hash

    canonical_without_hash = dict(raw)
    canonical_without_hash.pop("proposal_hash", None)
    raw["proposal_hash"] = compute_upgrade_proposal_hash(canonical_without_hash)
    return raw


def _valid_receipt_for(p: Dict[str, Any], decision: ReceiptDecision) -> Dict[str, Any]:
    pv = validate_and_canonicalize_upgrade_proposal_v3(p)
    proposal_id = str(pv.canonical["proposal_id"])
    proposal_hash = str(pv.computed_hash)

    r: Dict[str, Any] = {
        "v": "ac_review_receipt_v1",
        "proposal_id": proposal_id,
        "proposal_hash": proposal_hash,
        "decision": decision.value,
        "reviewer_id": "maintainer@local",
        "reviewed_utc": "2026-02-24T00:00:00Z",
        "notes": "ok",
        "consequence_simulation": {},
        "receipt_hash": "",
    }

    without_hash = dict(r)
    without_hash.pop("receipt_hash", None)
    r["receipt_hash"] = compute_review_receipt_hash(without_hash)
    return r


def test_evaluate_upgrade_denies_invalid_receipt() -> None:
    p = _valid_proposal()
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt={"v": "ac_review_receipt_v1"})
    assert d.allow is False
    assert d.reason_id == "REVIEW_RECEIPT_INVALID"


def test_evaluate_upgrade_denies_receipt_mismatch() -> None:
    p = _valid_proposal()
    r = _valid_receipt_for(p, decision=ReceiptDecision.APPROVE)

    # Tamper proposal_hash BUT keep receipt internally valid by recomputing receipt_hash.
    r["proposal_hash"] = "0" * 64
    without_hash = dict(r)
    without_hash.pop("receipt_hash", None)
    r["receipt_hash"] = compute_review_receipt_hash(without_hash)

    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=r)
    assert d.allow is False
    assert d.reason_id == "REVIEW_RECEIPT_MISMATCH"


def test_evaluate_upgrade_denies_when_reviewer_denies() -> None:
    p = _valid_proposal()
    r = _valid_receipt_for(p, decision=ReceiptDecision.DENY)
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=r)
    assert d.allow is False
    assert d.reason_id == "REVIEW_RECEIPT_DENY"


def test_evaluate_upgrade_allows_when_reviewer_approves_and_hashes_match() -> None:
    p = _valid_proposal()
    r = _valid_receipt_for(p, decision=ReceiptDecision.APPROVE)
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=r)
    assert d.allow is True
    assert d.reason_id == "REVIEW_RECEIPT_APPROVE"
