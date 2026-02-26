from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    ReceiptDecision,
    build_review_receipt_v1,
    compute_upgrade_proposal_hash,
    evaluate_upgrade_request_v1,
)


def _canonical_valid_proposal_base() -> Dict[str, Any]:
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

    if "evidence" not in base or base["evidence"] is None:
        base["evidence"] = {}

    if "guardrails_ref" not in base or base["guardrails_ref"] is None:
        base["guardrails_ref"] = ""

    if "guardrails" in base and isinstance(base["guardrails"], list):
        base["guardrails"] = sorted(set([str(x).strip() for x in base["guardrails"]]))

    if "changes" in base and isinstance(base["changes"], list):
        if all(isinstance(d, dict) and "change_id" in d for d in base["changes"]):
            base["changes"] = sorted(base["changes"], key=lambda d: d["change_id"])

    p["proposal_hash"] = compute_upgrade_proposal_hash(base)
    return p


def _valid_proposal() -> Dict[str, Any]:
    return _finalize_proposal_hash_like_validator(_canonical_valid_proposal_base())


def _valid_receipt_for(
    proposal: Mapping[str, Any],
    *,
    decision: ReceiptDecision,
    consequence_simulation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    proposal_id = str(proposal["proposal_id"])
    proposal_hash = str(proposal["proposal_hash"])
    reviewed_utc = str(proposal["created_utc"])
    return build_review_receipt_v1(
        proposal_id=proposal_id,
        proposal_hash=proposal_hash,
        decision=decision,
        reviewer_id="maintainer@local",
        reviewed_utc=reviewed_utc,
        notes="ok",
        consequence_simulation=dict(consequence_simulation) if consequence_simulation is not None else None,
    )


def test_evaluate_upgrade_denies_invalid_proposal_fail_closed() -> None:
    d = evaluate_upgrade_request_v1(proposal={})
    assert d.allow is False
    assert d.reason_id == "UPGRADE_PROPOSAL_INVALID"


def test_evaluate_upgrade_denies_missing_receipt_by_default() -> None:
    p = _valid_proposal()
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=None)
    assert d.allow is False
    assert d.reason_id == "REVIEW_RECEIPT_MISSING"
    assert d.proposal_hash == p["proposal_hash"]


def test_evaluate_upgrade_allows_when_receipt_not_required() -> None:
    p = _valid_proposal()
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=None, require_receipt=False)
    assert d.allow is True
    assert d.reason_id == "UPGRADE_APPROVED_NO_RECEIPT"


def test_evaluate_upgrade_denies_invalid_receipt() -> None:
    p = _valid_proposal()
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt={"v": "ac_review_receipt_v1"})
    assert d.allow is False
    assert d.reason_id == "REVIEW_RECEIPT_INVALID"


def test_evaluate_upgrade_denies_receipt_mismatch() -> None:
    p = _valid_proposal()
    r = _valid_receipt_for(p, decision=ReceiptDecision.APPROVE)
    r["proposal_hash"] = "0" * 64
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=r)
    assert d.allow is False
    assert d.reason_id == "REVIEW_RECEIPT_MISMATCH"


def test_evaluate_upgrade_denies_when_reviewer_denies() -> None:
    p = _valid_proposal()
    r = _valid_receipt_for(p, decision=ReceiptDecision.DENY)
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=r)
    assert d.allow is False
    assert d.reason_id == "REVIEW_DENIED"


def test_evaluate_upgrade_allows_when_receipt_approves() -> None:
    p = _valid_proposal()
    r = _valid_receipt_for(p, decision=ReceiptDecision.APPROVE, consequence_simulation={"impact": "low"})
    d = evaluate_upgrade_request_v1(proposal=p, review_receipt=r)
    assert d.allow is True
    assert d.reason_id == "UPGRADE_APPROVED"
    assert d.proposal_hash == p["proposal_hash"]
    assert d.receipt_hash == r["receipt_hash"]
