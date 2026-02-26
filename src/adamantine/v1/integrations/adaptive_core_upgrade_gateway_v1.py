from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple, List


_ALLOWED_PROPOSAL_ROOT_KEYS = {
    "v",
    "proposal_id",
    "domain",
    "action",
    "target",
    "created_utc",
    "summary",
    "changes",
    "evidence",
    "guardrails",
    "guardrails_ref",
    "proposal_hash",
}

_ALLOWED_TARGET_KEYS = {"component", "version"}
_ALLOWED_CHANGE_KEYS = {"change_id", "type", "detail"}

_ALLOWED_DOMAINS = {"SECURITY_THRESHOLDS", "DETECTION_RULES", "ENFORCEMENT", "GUARDRAILS"}
_ALLOWED_ACTIONS = {
    "INCREASE_THRESHOLD",
    "ADD_RULE",
    "TIGHTEN_EVIDENCE",
    "STRENGTHEN_ENFORCEMENT",
    "ADD_GUARDRAIL",
}
_ALLOWED_CHANGE_TYPES = {"add", "modify", "deprecate", "remove"}

_ALLOWED_RECEIPT_KEYS = {
    "v",
    "proposal_id",
    "proposal_hash",
    "decision",
    "reviewer_id",
    "reviewed_utc",
    "consequence_simulation",
    "notes",
    "receipt_hash",
}


class ReceiptDecision(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class UpgradeProposalValidationResult:
    canonical: Dict[str, Any]
    computed_hash: str


@dataclass(frozen=True, slots=True)
class ReviewReceiptValidationResult:
    canonical: Dict[str, Any]
    computed_hash: str


def _canonical_json_bytes(obj: Any) -> bytes:
    # Must match Adaptive Core proposal hashing: UTF-8, sorted keys, no whitespace, ensure_ascii=False.
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _require_exact_keys(obj: Mapping[str, Any], allowed: set[str], ctx: str) -> None:
    extra = sorted(set(obj.keys()) - allowed)
    if extra:
        raise ValueError(f"unknown keys in {ctx}: {extra}")


def _require_str(m: Mapping[str, Any], key: str) -> str:
    if key not in m:
        raise ValueError(f"missing field: {key}")
    v = m[key]
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{key!r} must be non-empty str")
    return v.strip()


def _require_timestamp_z(value: str, *, field: str) -> str:
    if not value.endswith("Z"):
        raise ValueError(f"{field} must end with 'Z'")
    try:
        # Validate ISO8601 without 'Z' (datetime.fromisoformat can't parse Z directly)
        datetime.fromisoformat(value[:-1])
    except ValueError as e:
        raise ValueError(f"invalid ISO8601 timestamp in {field}") from e
    return value


def compute_upgrade_proposal_hash(canonical_without_hash: Mapping[str, Any]) -> str:
    return _sha256_hex(_canonical_json_bytes(canonical_without_hash))


def compute_review_receipt_hash(canonical_without_hash: Mapping[str, Any]) -> str:
    return _sha256_hex(_canonical_json_bytes(canonical_without_hash))


def _canon_guardrails(guardrails: Any, guardrails_ref: Any) -> Tuple[List[str], str]:
    # guardrails: None -> [], list[str] -> sorted+deduped
    if guardrails is None:
        gids: List[str] = []
    else:
        if not isinstance(guardrails, list):
            raise ValueError("'guardrails' must be list[str] or null")
        gids = []
        for g in guardrails:
            if not isinstance(g, str) or not g.strip():
                raise ValueError("guardrail ids must be non-empty str")
            gids.append(g.strip())
        gids = sorted(set(gids))

    ref = ""
    if guardrails_ref is not None:
        if not isinstance(guardrails_ref, str) or not guardrails_ref.strip():
            raise ValueError("'guardrails_ref' must be non-empty str if present")
        ref = guardrails_ref.strip()
    return gids, ref


def validate_and_canonicalize_upgrade_proposal_v3(raw: Mapping[str, Any]) -> UpgradeProposalValidationResult:
    if not isinstance(raw, Mapping):
        raise ValueError("proposal must be an object")

    _require_exact_keys(raw, _ALLOWED_PROPOSAL_ROOT_KEYS, ctx="proposal")

    v = _require_str(raw, "v")
    if v != "upgrade_proposal_v3":
        raise ValueError("bad 'v'")

    proposal_id = _require_str(raw, "proposal_id")
    if " " in proposal_id:
        raise ValueError("proposal_id must not contain spaces")

    domain = _require_str(raw, "domain")
    if domain not in _ALLOWED_DOMAINS:
        raise ValueError(f"domain not allowed: {domain}")

    action = _require_str(raw, "action")
    if action not in _ALLOWED_ACTIONS:
        raise ValueError(f"action not allowed: {action}")

    target = raw.get("target")
    if not isinstance(target, Mapping):
        raise ValueError("'target' must be object")
    _require_exact_keys(target, _ALLOWED_TARGET_KEYS, ctx="target")
    component = _require_str(target, "component")
    version = _require_str(target, "version")

    created_utc = _require_timestamp_z(_require_str(raw, "created_utc"), field="created_utc")
    summary = _require_str(raw, "summary")

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
        raise ValueError("'evidence' must be object if present")

    gids, gref = _canon_guardrails(raw.get("guardrails"), raw.get("guardrails_ref"))

    proposal_hash = _require_str(raw, "proposal_hash")
    if len(proposal_hash) != 64 or any(c not in "0123456789abcdef" for c in proposal_hash):
        raise ValueError("proposal_hash must be 64 lowercase hex chars")

    canonical: Dict[str, Any] = {
        "v": v,
        "proposal_id": proposal_id,
        "domain": domain,
        "action": action,
        "target": {"component": component, "version": version},
        "created_utc": created_utc,
        "summary": summary,
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
    notes: Optional[str] = None,
    consequence_simulation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(proposal_hash, str) or len(proposal_hash) != 64 or any(c not in "0123456789abcdef" for c in proposal_hash):
        raise ValueError("proposal_hash must be 64 lowercase hex chars")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("reviewer_id must be non-empty str")

    reviewed_utc = _require_timestamp_z(reviewed_utc, field="reviewed_utc")

    receipt: Dict[str, Any] = {
        "v": "proposal_review_receipt_v1",
        "proposal_id": proposal_id,
        "proposal_hash": proposal_hash,
        "decision": decision.value,
        "reviewer_id": reviewer_id.strip(),
        "reviewed_utc": reviewed_utc,
        "consequence_simulation": consequence_simulation if consequence_simulation is not None else None,
        "notes": notes if (notes is None or (isinstance(notes, str) and notes.strip())) else notes,
        "receipt_hash": "",
    }

    # Hash over canonical WITHOUT receipt_hash
    without = dict(receipt)
    without.pop("receipt_hash", None)
    receipt_hash = compute_review_receipt_hash(without)
    receipt["receipt_hash"] = receipt_hash
    return receipt


def validate_and_canonicalize_review_receipt_v1(raw: Mapping[str, Any]) -> ReviewReceiptValidationResult:
    if not isinstance(raw, Mapping):
        raise ValueError("receipt must be an object")

    _require_exact_keys(raw, _ALLOWED_RECEIPT_KEYS, ctx="receipt")

    v = _require_str(raw, "v")
    if v != "proposal_review_receipt_v1":
        raise ValueError("bad 'v'")

    proposal_id = _require_str(raw, "proposal_id")
    proposal_hash = _require_str(raw, "proposal_hash")
    if len(proposal_hash) != 64 or any(c not in "0123456789abcdef" for c in proposal_hash):
        raise ValueError("proposal_hash must be 64 lowercase hex chars")

    decision = _require_str(raw, "decision")
    if decision not in (ReceiptDecision.APPROVE.value, ReceiptDecision.DENY.value):
        raise ValueError("decision must be APPROVE or DENY")

    reviewer_id = _require_str(raw, "reviewer_id")
    reviewed_utc = _require_timestamp_z(_require_str(raw, "reviewed_utc"), field="reviewed_utc")

    cs = raw.get("consequence_simulation")
    if cs is not None and not isinstance(cs, dict):
        raise ValueError("consequence_simulation must be object or null")

    notes = raw.get("notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        raise ValueError("notes must be non-empty str if present")

    receipt_hash = _require_str(raw, "receipt_hash")
    if len(receipt_hash) != 64 or any(c not in "0123456789abcdef" for c in receipt_hash):
        raise ValueError("receipt_hash must be 64 lowercase hex chars")

    canonical: Dict[str, Any] = {
        "v": v,
        "proposal_id": proposal_id,
        "proposal_hash": proposal_hash,
        "decision": decision,
        "reviewer_id": reviewer_id,
        "reviewed_utc": reviewed_utc,
        "consequence_simulation": cs,
        "notes": notes,
        "receipt_hash": receipt_hash,
    }

    without = dict(canonical)
    without.pop("receipt_hash", None)
    computed = compute_review_receipt_hash(without)

    if receipt_hash != computed:
        raise ValueError(f"receipt_hash mismatch: expected {computed} got {receipt_hash}")

    return ReviewReceiptValidationResult(canonical=canonical, computed_hash=computed)
