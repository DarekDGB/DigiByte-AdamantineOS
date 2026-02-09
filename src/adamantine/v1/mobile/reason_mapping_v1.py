from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId

# UX-safe reason codes (stable). This is the ONLY place internal ReasonId maps to UX codes.
_REASON_MAP: dict[ReasonId, str] = {
    # Allow
    ReasonId.OK_ALLOW: "APPROVED",

    # Identity / session
    ReasonId.EQC_MISSING_QID_SESSION: "IDENTITY_REQUIRED",
    ReasonId.EQC_QID_SESSION_EXPIRED: "SESSION_EXPIRED",
    ReasonId.EQC_QID_SESSION_NOT_YET_VALID: "SESSION_NOT_YET_VALID",
    ReasonId.EQC_INVALID_QID_PROOF: "IDENTITY_VERIFICATION_FAILED",

    # Evidence presence
    ReasonId.EQC_MISSING_ORACLE: "SECURITY_CHECK_INCOMPLETE",
    ReasonId.EQC_MISSING_SHIELD_BUNDLE: "SECURITY_CHECK_INCOMPLETE",

    # Risk / policy
    ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD: "SECURITY_RISK_TOO_HIGH",
    ReasonId.EQC_CONFLICTING_EVIDENCE: "SECURITY_POLICY_BLOCK",
    ReasonId.DENY_POLICY: "SECURITY_POLICY_BLOCK",

    # Generic / fail-closed
    ReasonId.DENY_ADAPTER_INVALID: "SECURITY_INPUT_INVALID",
    ReasonId.DENY_VERSION_MISMATCH: "SECURITY_VERSION_MISMATCH",
    ReasonId.ERR_INTERNAL: "SYSTEM_ERROR",
    ReasonId.ERR_UNHANDLED: "SYSTEM_ERROR",
}

_DEFAULT_CODE = "ACTION_NOT_ALLOWED"


def map_reason_id_to_mobile_code(reason_id: ReasonId) -> str:
    return _REASON_MAP.get(reason_id, _DEFAULT_CODE)
