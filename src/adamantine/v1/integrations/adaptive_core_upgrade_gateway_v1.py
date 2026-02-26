from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, List


class ReceiptDecision(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"


_ALLOWED_ROOT_KEYS = {
    "v",
    "proposal_id",
    "target",
    "created_utc",
    "summary",
    "domain",
    "action",
    "changes",
    "evidence",
    "guardrails",
    "guardrails_ref",
    "proposal_hash",
}

_ALLOWED_TARGET_KEYS = {"component", "version"}
_ALLOWED_CHANGE_KEYS = {"change_id", "type", "detail"}
_ALLOWED_CHANGE_TYPES = {"add", "modify", "deprecate", "remove"}

_ALLOWED_DOMAINS = {"SECURITY_THRESHOLDS", "BEHAVIOR_FLAGS", "POLICY_LIMITS", "RISK_RULES"}
_ALLOWED_ACTIONS = {"INCREASE_THRESHOLD", "DECREASE_THRESHOLD", "ADD_RULE", "REMOVE_RULE", "MODIFY_RULE"}


@dataclass(frozen=True, slots=True)
class UpgradeProposalValidationResult:
    canonical: Dict[str, Any]
    computed_hash: str


@dataclass(frozen=True, slots=True)
class ReviewReceiptValidationResult:
    canonical: Dict[str, Any]
    computed_hash: str


@dataclass(frozen=True, slots=True)
class UpgradeGatewayDecision:
    """Fail-closed decision output for the v1 upgrade gateway.

    This stays intentionally tiny: the caller can log/audit `reason_id`,
    and pin the decision to deterministic hashes.
    """

    allow: bool
    reason_id: str
    proposal_hash: str
    receipt_hash: str


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_json_bytes(obj: Any) -> bytes:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")


def compute_upgrade_proposal_hash(canonical_without_hash: Mapping[str, Any]) -> str:
    return _sha256_hex(_canonical_json_bytes(canonical_without_hash))


def compute_review_receipt_hash(canonical_without_hash: Mapping[str, Any]) -> str:
    return _sha256_hex(_canonical_json_bytes(canonical_without_hash))


# -----------------------------------------------------------------------------
# Compatibility helpers
# -----------------------------------------------------------------------------


def compute_proposal_hash(canonical_without_hash: Mapping[str, Any]) -> str:
    """Alias for the Adaptive Core v3 proposal hash function."""
    return compute_upgrade_proposal_hash(canonical_without_hash)


def validate_and_canonicalize_upgrade_proposal(raw: Mapping[str, Any]) -> UpgradeProposalValidationResult:
    """Alias for v3 upgrade proposal validator."""
    return validate_and_canonicalize_upgrade_proposal_v3(raw)


def validate_and_canonicalize_review_receipt(raw: Mapping[str, Any]) -> ReviewReceiptValidationResult:
    """Alias for v1 review receipt validator."""
    return validate_and_canonicalize_review_receipt_v1(raw)


def build_review_receipt(
    proposal: Mapping[str, Any],
    decision: str,
    reviewer_id: str,
    notes: str,
    *,
    consequence_simulation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a v1 review receipt from a (possibly non-canonical) proposal."""
    pv = validate_and_canonicalize_upgrade_proposal_v3(proposal)
    canonical = pv.canonical
    reviewed_utc = str(canonical["created_utc"])
    dec = ReceiptDecision(decision)
    return build_review_receipt_v1(
        proposal_id=str(canonical["proposal_id"]),
        proposal_hash=str(pv.computed_hash),
        decision=dec,
        reviewer_id=reviewer_id,
        reviewed_utc=reviewed_utc,
        notes=notes,
        consequence_simulation=dict(consequence_simulation) if consequence_simulation is not None else None,
    )


def load_json_file(path: Path) -> Dict[str, Any]:
    """Load JSON from disk and require an object root."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"invalid json: {path}") from e
    if not isinstance(data, dict):
        raise ValueError(f"json root must be object: {path}")
    return data


def _require_str(m: Mapping[str, Any], key: str) -> str:
    if key not in m:
        raise ValueError(f"missing {key!r}")
    v = m[key]
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{key!r} must be non-empty str")
    return v.strip()


def _require_exact_keys(obj: Mapping[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj.keys()) - set(allowed))
    if extra:
        raise ValueError(f"unknown keys in {ctx}: {extra}")


def _require_timestamp_z(value: str, key: str) -> str:
    if not value.endswith("Z"):
        raise ValueError(f"{key} must end with 'Z'")
    try:
        datetime.fromisoformat(value[:-1])
    except ValueError as e:
        raise ValueError(f"{key} invalid ISO8601 timestamp") from e
    return value


def _canon_guardrails(guardrails: Any, guardrails_ref: Any) -> Tuple[List[str], str]:
    if guardrails is None:
        gids: List[str] = []
    else:
        if not isinstance(guardrails, list):
            raise ValueError("'guardrails' must be list[str]")
        gids = []
        for g in guardrails:
            if not isinstance(g, str) or not g.strip():
                raise ValueError("guardrail ids must be non-empty str")
            gids.append(g.strip())

    # IMPORTANT: empty-string is allowed (canonical default)
    if guardrails_ref is None:
        ref = ""
    else:
        if not isinstance(guardrails_ref, str):
            raise ValueError("'guardrails_ref' must be str if present")
        ref = guardrails_ref.strip()

    gids = sorted(set(gids))
    return gids, ref


def validate_and_canonicalize_upgrade_proposal_v3(raw: Mapping[str, Any]) -> UpgradeProposalValidationResult:
    if not isinstance(raw, Mapping):
        raise ValueError("proposal must be an object")

    _require_exact_keys(raw, _ALLOWED_ROOT_KEYS, ctx="proposal")

    v = _require_str(raw, "v")
    if v != "upgrade_proposal_v3":
        raise ValueError("bad 'v'")

    proposal_id = _require_str(raw, "proposal_id")
    if " " in proposal_id:
        raise ValueError("proposal_id must not contain spaces")

    created_utc = _require_timestamp_z(_require_str(raw, "created_utc"), key="created_utc")
    summary = _require_str(raw, "summary")

    domain = _require_str(raw, "domain")
    if domain not in _ALLOWED_DOMAINS:
        raise ValueError(f"bad domain {domain!r}")

    action = _require_str(raw, "action")
    if action not in _ALLOWED_ACTIONS:
        raise ValueError(f"bad action {action!r}")

    target_any = raw.get("target")
    if not isinstance(target_any, Mapping):
        raise ValueError("'target' must be object")
    _require_exact_keys(target_any, _ALLOWED_TARGET_KEYS, ctx="target")
    component = _require_str(target_any, "component")
    version = _require_str(target_any, "version")

    changes_any = raw.get("changes")
    if not isinstance(changes_any, list) or not changes_any:
        raise ValueError("'changes' must be non-empty list")

    changes: List[Dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in changes_any:
        if not isinstance(item, Mapping):
            raise ValueError("change entry must be object")
        _require_exact_keys(item, _ALLOWED_CHANGE_KEYS, ctx="change")
        cid = _require_str(item, "change_id")
        ctype = _require_str(item, "type")
        detail = _require_str(item, "detail")
        if ctype not in _ALLOWED_CHANGE_TYPES:
            raise ValueError(f"bad change.type {ctype!r}")
        if cid in seen_ids:
            raise ValueError(f"duplicate change_id {cid!r}")
        seen_ids.add(cid)
        changes.append({"change_id": cid, "type": ctype, "detail": detail})

    changes.sort(key=lambda d: d["change_id"])

    evidence = raw.get("evidence")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("'evidence' must be object")

    gids, gref = _canon_guardrails(raw.get("guardrails"), raw.get("guardrails_ref"))

    proposal_hash = _require_str(raw, "proposal_hash")
    if len(proposal_hash) != 64 or any(c not in "0123456789abcdef" for c in proposal_hash):
        raise ValueError("proposal_hash must be 64 lowercase hex chars")

    canonical: Dict[str, Any] = {
        "v": v,
        "proposal_id": proposal_id,
        "target": {"component": component, "version": version},
        "created_utc": created_utc,
        "summary": summary,
        "domain": domain,
        "action": action,
        "changes": changes,
        "evidence": dict(evidence) if isinstance(evidence, dict) else {},
        "guardrails": gids,
        "guardrails_ref": gref,
        "proposal_hash": proposal_hash,
    }

    without_hash = dict(canonical)
    without_hash.pop("proposal_hash", None)
    computed = compute_upgrade_proposal_hash(without_hash)

    if proposal_hash != computed:
        raise ValueError(f"proposal_hash mismatch: expected {computed} got {proposal_hash}")

    return UpgradeProposalValidationResult(canonical=canonical, computed_hash=computed)


def build_review_receipt_v1(
    *,
    proposal_id: str,
    proposal_hash: str,
    decision: ReceiptDecision,
    reviewer_id: str,
    reviewed_utc: str,
    notes: str,
    consequence_simulation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(consequence_simulation, (dict, type(None))):
        raise ValueError("consequence_simulation must be object if present")

    base: Dict[str, Any] = {
        "v": "ac_review_receipt_v1",
        "proposal_id": proposal_id,
        "proposal_hash": proposal_hash,
        "decision": decision.value,
        "reviewer_id": reviewer_id,
        "reviewed_utc": reviewed_utc,
        "notes": notes,
        "consequence_simulation": dict(consequence_simulation) if consequence_simulation else {},
        "receipt_hash": "",
    }

    without_hash = dict(base)
    without_hash.pop("receipt_hash", None)
    h = compute_review_receipt_hash(without_hash)
    base["receipt_hash"] = h
    return base


def validate_and_canonicalize_review_receipt_v1(raw: Mapping[str, Any]) -> ReviewReceiptValidationResult:
    if not isinstance(raw, Mapping):
        raise ValueError("receipt must be object")

    allowed = {
        "v",
        "proposal_id",
        "proposal_hash",
        "decision",
        "reviewer_id",
        "reviewed_utc",
        "notes",
        "consequence_simulation",
        "receipt_hash",
    }
    _require_exact_keys(raw, allowed, ctx="receipt")

    v = _require_str(raw, "v")
    if v != "ac_review_receipt_v1":
        raise ValueError("bad receipt v")

    proposal_id = _require_str(raw, "proposal_id")
    proposal_hash = _require_str(raw, "proposal_hash")
    if len(proposal_hash) != 64 or any(c not in "0123456789abcdef" for c in proposal_hash):
        raise ValueError("bad proposal_hash")

    decision_s = _require_str(raw, "decision")
    try:
        decision = ReceiptDecision(decision_s)
    except ValueError as e:
        raise ValueError("bad decision") from e

    reviewer_id = _require_str(raw, "reviewer_id")
    reviewed_utc = _require_timestamp_z(_require_str(raw, "reviewed_utc"), key="reviewed_utc")
    notes = _require_str(raw, "notes")

    cs = raw.get("consequence_simulation")
    if cs is None:
        cs_obj: Dict[str, Any] = {}
    else:
        if not isinstance(cs, dict):
            raise ValueError("consequence_simulation must be object")
        cs_obj = dict(cs)

    receipt_hash = _require_str(raw, "receipt_hash")
    if len(receipt_hash) != 64 or any(c not in "0123456789abcdef" for c in receipt_hash):
        raise ValueError("bad receipt_hash format")

    canonical: Dict[str, Any] = {
        "v": v,
        "proposal_id": proposal_id,
        "proposal_hash": proposal_hash,
        "decision": decision.value,
        "reviewer_id": reviewer_id,
        "reviewed_utc": reviewed_utc,
        "notes": notes,
        "consequence_simulation": cs_obj,
        "receipt_hash": receipt_hash,
    }

    without_hash = dict(canonical)
    without_hash.pop("receipt_hash", None)
    computed = compute_review_receipt_hash(without_hash)

    if receipt_hash != computed:
        raise ValueError(f"receipt_hash mismatch: expected {computed} got {receipt_hash}")

    return ReviewReceiptValidationResult(canonical=canonical, computed_hash=computed)


# -----------------------------------------------------------------------------
# Policy gate (wiring completion point)
# -----------------------------------------------------------------------------


def evaluate_upgrade_request_v1(
    *,
    proposal: Mapping[str, Any],
    review_receipt: Optional[Mapping[str, Any]] = None,
    require_receipt: bool = True,
) -> UpgradeGatewayDecision:
    """Evaluate an Adaptive Core v3 upgrade request through the gateway.

    Invariants:
    - Fail-closed by default (receipt required).
    - Deterministic: no wall-clock reads.
    - Binding: receipt must match proposal_id and proposal_hash.
    """
    try:
        pv = validate_and_canonicalize_upgrade_proposal_v3(proposal)
    except ValueError:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="UPGRADE_PROPOSAL_INVALID",
            proposal_hash="",
            receipt_hash="",
        )

    proposal_id = str(pv.canonical["proposal_id"])
    proposal_hash = str(pv.computed_hash)

    if require_receipt and review_receipt is None:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="REVIEW_RECEIPT_MISSING",
            proposal_hash=proposal_hash,
            receipt_hash="",
        )

    if review_receipt is None:
        return UpgradeGatewayDecision(
            allow=True,
            reason_id="UPGRADE_APPROVED_NO_RECEIPT",
            proposal_hash=proposal_hash,
            receipt_hash="",
        )

    try:
        rv = validate_and_canonicalize_review_receipt_v1(review_receipt)
    except ValueError:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="REVIEW_RECEIPT_INVALID",
            proposal_hash=proposal_hash,
            receipt_hash="",
        )

    receipt = rv.canonical
    receipt_hash = str(rv.computed_hash)

    if str(receipt.get("proposal_id", "")) != proposal_id:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="REVIEW_RECEIPT_MISMATCH",
            proposal_hash=proposal_hash,
            receipt_hash=receipt_hash,
        )

    if str(receipt.get("proposal_hash", "")) != proposal_hash:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="REVIEW_RECEIPT_MISMATCH",
            proposal_hash=proposal_hash,
            receipt_hash=receipt_hash,
        )

    decision = str(receipt.get("decision", ""))
    if decision == ReceiptDecision.DENY.value:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="REVIEW_DENIED",
            proposal_hash=proposal_hash,
            receipt_hash=receipt_hash,
        )

    if decision != ReceiptDecision.APPROVE.value:
        return UpgradeGatewayDecision(
            allow=False,
            reason_id="REVIEW_DECISION_INVALID",
            proposal_hash=proposal_hash,
            receipt_hash=receipt_hash,
        )

    return UpgradeGatewayDecision(
        allow=True,
        reason_id="UPGRADE_APPROVED",
        proposal_hash=proposal_hash,
        receipt_hash=receipt_hash,
    )
