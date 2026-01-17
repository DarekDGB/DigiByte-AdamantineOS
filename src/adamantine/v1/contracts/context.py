from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    wallet_id: str
    action: str
    context_hash: str
