from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from adamantine.v1.integrations.adaptive_core_upgrade_gateway_v1 import (
    build_review_receipt,
    evaluate_upgrade_request_v1,
)


def main() -> None:
    # Read env-provided JSON (set by workflow)
    import os

    proposal_json = os.environ.get("PROPOSAL_JSON", "").strip()
    decision = os.environ.get("RECEIPT_DECISION", "APPROVE").strip().upper()
    require_receipt = os.environ.get("REQUIRE_RECEIPT", "true").strip().lower() == "true"

    if not proposal_json:
        raise SystemExit("Missing PROPOSAL_JSON env var (paste proposal JSON into workflow input).")

    proposal = json.loads(proposal_json)

    receipt = build_review_receipt(
        proposal=proposal,
        decision=decision,
        reviewer_id="reviewer:demo",
        notes="Manual demo receipt generated via workflow_dispatch",
    )

    gw_decision = evaluate_upgrade_request_v1(
        proposal=proposal,
        review_receipt=receipt,
        require_receipt=require_receipt,
    )

    out = Path("_demo_eval")
    out.mkdir(parents=True, exist_ok=True)

    (out / "proposal.json").write_text(json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8")
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    (out / "decision.json").write_text(json.dumps(asdict(gw_decision), indent=2, sort_keys=True), encoding="utf-8")

    print("--- DECISION ---")
    print(json.dumps(asdict(gw_decision), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
