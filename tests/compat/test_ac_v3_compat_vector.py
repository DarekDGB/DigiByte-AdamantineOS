from __future__ import annotations

import json
from pathlib import Path

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    build_review_receipt,
    compute_proposal_hash,
    evaluate_upgrade_request_v1,
    validate_and_canonicalize_upgrade_proposal_v3,
)


def _load_json(rel: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    p = root / "compat_vectors" / rel
    return json.loads(p.read_text(encoding="utf-8"))


def test_compat_vector_ac_v3_upgrade_proposal_approve() -> None:
    proposal = _load_json("ac_v3_upgrade_proposal.json")
    expected = _load_json("expected_decision_approve.json")

    # Seal hash deterministically (canonical-without-hash)
    without_hash = dict(proposal)
    without_hash.pop("proposal_hash", None)
    proposal["proposal_hash"] = compute_proposal_hash(without_hash)

    pv = validate_and_canonicalize_upgrade_proposal_v3(proposal)

    receipt = build_review_receipt(
        proposal=pv.canonical,
        decision="APPROVE",
        reviewer_id="reviewer:compat",
        notes="Compat vector lock",
    )

    decision = evaluate_upgrade_request_v1(
        proposal=pv.canonical,
        review_receipt=receipt,
        require_receipt=True,
    )

    assert decision.allow is expected["allow"]
    assert decision.reason_id == expected["reason_id"]

    # Also lock these invariants:
    assert decision.proposal_hash == pv.computed_hash
    assert decision.receipt_hash
