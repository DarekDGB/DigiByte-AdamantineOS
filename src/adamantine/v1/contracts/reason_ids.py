from __future__ import annotations
from enum import Enum


class ReasonId(str, Enum):
    TVA_MISSING_CONTEXT = "TVA_MISSING_CONTEXT"
    TVA_MISSING_VERDICT = "TVA_MISSING_VERDICT"
    TVA_VERDICT_NOT_ALLOW = "TVA_VERDICT_NOT_ALLOW"
