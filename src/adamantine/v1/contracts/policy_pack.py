from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry


_DEFAULT_REASON_MAP = ExternalReasonMap(
    entries=(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
)


@dataclass(frozen=True, slots=True)
class PolicyPack:
    """
    Deterministic policy pack for evidence evaluation.

    SECURITY INVARIANTS:
    - Pure data: no environment reads, no time access, no IO.
    - Used to tune gates WITHOUT changing code (future mobile can ship packs).
    - Validation must be strict and fail-closed.

    v1 fields:
    - min_overall_score: minimum risk report score required to allow
    - allowed_external_reason_ids: allowlist for external reason IDs from oracles/adapters
    - external_reason_map: explicit mapping table for external reason codes -> internal ReasonId strings

    Critical invariant:
    - allowed_external_reason_ids MUST be a subset of external_reason_map entries.
      (No allow-without-map drift.)
    """
    min_overall_score: int = 85
    allowed_external_reason_ids: Tuple[str, ...] = ("ok",)
    external_reason_map: ExternalReasonMap = _DEFAULT_REASON_MAP

    def validate(self) -> None:
        if not isinstance(self.min_overall_score, int):
            raise ValueError("min_overall_score must be int")
        if not (0 <= self.min_overall_score <= 100):
            raise ValueError("min_overall_score must be in range 0..100")

        if not isinstance(self.allowed_external_reason_ids, tuple):
            raise ValueError("allowed_external_reason_ids must be tuple")
        if len(self.allowed_external_reason_ids) == 0:
            raise ValueError("allowed_external_reason_ids must not be empty")

        # Strict: entries must be non-empty str, unique
        seen: set[str] = set()
        for rid in self.allowed_external_reason_ids:
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError("allowed_external_reason_ids entries must be non-empty str")
            if rid in seen:
                raise ValueError("allowed_external_reason_ids must be unique")
            seen.add(rid)

        # Mapping table: must exist and validate
        if not isinstance(self.external_reason_map, ExternalReasonMap):
            raise ValueError("external_reason_map must be ExternalReasonMap")
        if not isinstance(self.external_reason_map.entries, tuple) or len(self.external_reason_map.entries) == 0:
            raise ValueError("external_reason_map must be non-empty")
        self.external_reason_map.validate()

        # Subset invariant: allowlist must be fully mappable
        for rid in self.allowed_external_reason_ids:
            if self.external_reason_map.lookup(rid) is None:
                raise ValueError("allowed_external_reason_ids must be subset of external_reason_map")
