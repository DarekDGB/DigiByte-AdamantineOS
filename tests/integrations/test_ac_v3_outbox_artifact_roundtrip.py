from __future__ import annotations

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    build_review_receipt,
    compute_proposal_hash,
    evaluate_upgrade_request_v1,
    validate_and_canonicalize_upgrade_proposal_v3,
)


def _ac_v3_outbox_like_proposal() -> dict:
    # Mirrors Adaptive Core template shape (upgrade_proposal_v3)
    # Domain/action chosen to be compatible with both systems.
    return {
        "v": "upgrade_proposal_v3",
        "proposal_id": "AC-20260226-001",
        "domain": "SECURITY_THRESHOLDS",
        "action": "INCREASE_THRESHOLD",
        "target": {"component": "eqc_engine", "version": "3.0.0"},
        "created_utc": "2026-02-26T00:00:00Z",
        "summary": "Increase EQC threshold due to rising conflicting evidence pattern.",
        "changes": [
            {
                "change_id": "CHG-001",
                "type": "modify",
                "detail": "Increase EQC threshold from 0.70 to 0.80 to reduce false negatives.",
            }
        ],
        "evidence": {},
        "guardrails": ["AMG-001"],
        "guardrails_ref": "docs/ADAPTIVE_CORE_GUARDRAILS.md",
        "proposal_hash": "",
    }


def test_ac_v3_outbox_artifact_roundtrip_through_gateway() -> None:
    proposal = _ac_v3_outbox_like_proposal()

    # Seal proposal_hash exactly like Adaptive Core: sha256(canonical_without_hash)
    without_hash = dict(proposal)
    without_hash.pop("proposal_hash", None)
    proposal["proposal_hash"] = compute_proposal_hash(without_hash)

    pv = validate_and_canonicalize_upgrade_proposal_v3(proposal)
    assert pv.computed_hash == proposal["proposal_hash"]

    receipt = build_review_receipt(
        proposal=pv.canonical,
        decision="APPROVE",
        reviewer_id="reviewer:test",
        notes="E2E proof: AC v3 proposal accepted by Adamantine upgrade gateway.",
    )

    decision = evaluate_upgrade_request_v1(
        proposal=pv.canonical,
        review_receipt=receipt,
        require_receipt=True,
    )

    assert decision.allow is True
    assert decision.reason_id == "REVIEW_RECEIPT_APPROVE"
    assert decision.proposal_hash == pv.computed_hash
    assert decision.receipt_hash


def test_ac_v3_outbox_artifact_denies_when_receipt_missing() -> None:
    proposal = _ac_v3_outbox_like_proposal()

    without_hash = dict(proposal)
    without_hash.pop("proposal_hash", None)
    proposal["proposal_hash"] = compute_proposal_hash(without_hash)

    pv = validate_and_canonicalize_upgrade_proposal_v3(proposal)

    decision = evaluate_upgrade_request_v1(
        proposal=pv.canonical,
        review_receipt=None,
        require_receipt=True,
    )

    assert decision.allow is False
    assert decision.reason_id == "REVIEW_RECEIPT_MISSING"
    assert decision.proposal_hash == pv.computed_hash
