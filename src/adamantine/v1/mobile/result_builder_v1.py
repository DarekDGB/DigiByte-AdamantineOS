from __future__ import annotations

import json
import hashlib

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.result import EQCResult
from adamantine.v1.mobile.reason_mapping_v1 import map_reason_id_to_mobile_code


def _canon_json_bytes(obj: object) -> bytes:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return s.encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_mobile_decision_result_v1(*, eqc: EQCResult, request_id: str) -> dict[str, object]:
    """
    Convert an internal EQC result into a UX-safe mobile decision result.

    Presentation-only:
      - no evidence leakage
      - no policy internals
      - deterministic output for identical inputs
    """
    rid = (request_id or "").strip()
    if not rid:
        raise ValueError("request_id must be non-empty")

    verdict = "allow" if eqc.verdict is Verdict.ALLOW else "deny"

    # For deny, choose the first reason deterministically (ReasonId ordering is stable in our results).
    if eqc.reason_ids:
        reason_id: str = eqc.reason_ids[0]
        reason_code = map_reason_id_to_mobile_code(reason_id)
        explainable = True
        confidence = "high"
    else:
        reason_code = "APPROVED"
        explainable = True
        confidence = "medium"

    out: dict[str, object] = {
        "v": "mobile_decision_result_v1",
        "request_id": rid,
        "verdict": verdict,
        "reason_code": reason_code,
        "context_hash": eqc.context_hash,
        "explainable": explainable,
        "confidence": confidence,
    }

    # Determinism helper (can be used by callers/tests if needed)
    out["_snapshot_sha256"] = _sha256_hex(_canon_json_bytes(out))
    return out
