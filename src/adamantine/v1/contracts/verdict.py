from __future__ import annotations
from enum import Enum


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    STEP_UP = "STEP_UP"
