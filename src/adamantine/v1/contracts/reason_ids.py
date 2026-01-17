from __future__ import annotations

from enum import Enum


class ReasonId(str, Enum):
    # --- Presence / shape checks ---
    TVA_MISSING_CONTEXT = "TVA_MISSING_CONTEXT"
    TVA_MISSING_VERDICT = "TVA_MISSING_VERDICT"
    TVA_MISSING_AUTHORITY = "TVA_MISSING_AUTHORITY"

    # --- Verdict checks ---
    TVA_VERDICT_NOT_ALLOW = "TVA_VERDICT_NOT_ALLOW"

    # --- Binding checks (authority must match the context) ---
    TVA_AUTHORITY_WALLET_MISMATCH = "TVA_AUTHORITY_WALLET_MISMATCH"
    TVA_AUTHORITY_ACTION_MISMATCH = "TVA_AUTHORITY_ACTION_MISMATCH"
    TVA_AUTHORITY_CONTEXT_HASH_MISMATCH = "TVA_AUTHORITY_CONTEXT_HASH_MISMATCH"
