from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from adamantine.v1.contracts.reason_ids import ReasonId


class ShieldSource(str, Enum):
    """
    Canonical sources of security signals (typed, deterministic).
    """
    SENTINEL = "sentinel"
    DQSN = "dqsn"
    ADN = "adn"
    QWG = "qwg"
    GUARDIAN = "guardian"
    ADAPTIVE_CORE = "adaptive-core"


@dataclass(frozen=True, slots=True)
class ShieldSignal:
    """
    Internalized (post-mapping) security signal.

    Contract rule:
    - reason_ids must be internal ReasonId strings (no raw external codes here).
    """
    source: ShieldSource
    severity: int  # 0..100
    reason_ids: Tuple[str, ...]  # internal ReasonId values

    def validate(self) -> None:
        if not isinstance(self.source, ShieldSource):
            raise ValueError("source must be ShieldSource")

        if type(self.severity) is not int or not (0 <= self.severity <= 100):
            raise ValueError("severity must be int in range 0..100")

        if not isinstance(self.reason_ids, tuple) or len(self.reason_ids) == 0:
            raise ValueError("reason_ids must be a non-empty tuple")

        seen: set[str] = set()
        for rid in self.reason_ids:
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError("reason_ids entries must be non-empty str")
            # Must be a valid internal ReasonId value
            try:
                ReasonId(rid)
            except Exception as e:
                raise ValueError(f"reason_ids entry is not a valid internal ReasonId: {rid}") from e
            if rid in seen:
                raise ValueError("reason_ids must be unique")
            seen.add(rid)


@dataclass(frozen=True, slots=True)
class ExternalReasonMapEntry:
    """
    One explicit mapping from an external reason code -> internal ReasonId value.
    """
    external_id: str
    internal_reason_id: str  # must be ReasonId value

    def validate(self) -> None:
        if not isinstance(self.external_id, str) or not self.external_id.strip():
            raise ValueError("external_id must be non-empty str")

        if not isinstance(self.internal_reason_id, str) or not self.internal_reason_id.strip():
            raise ValueError("internal_reason_id must be non-empty str")

        try:
            ReasonId(self.internal_reason_id)
        except Exception as e:
            raise ValueError(f"internal_reason_id is not a valid ReasonId: {self.internal_reason_id}") from e


@dataclass(frozen=True, slots=True)
class ExternalReasonMap:
    """
    Deterministic mapping table for external reason codes.

    Invariant:
    - external ids must be unique
    - internal ids must be valid ReasonId values
    """
    entries: Tuple[ExternalReasonMapEntry, ...]

    def validate(self) -> None:
        if not isinstance(self.entries, tuple) or len(self.entries) == 0:
            raise ValueError("entries must be a non-empty tuple")

        seen_ext: set[str] = set()
        for e in self.entries:
            if not isinstance(e, ExternalReasonMapEntry):
                raise ValueError("entries must contain ExternalReasonMapEntry")
            e.validate()
            if e.external_id in seen_ext:
                raise ValueError("external_id must be unique in mapping table")
            seen_ext.add(e.external_id)

    def lookup(self, external_id: str) -> str | None:
        """
        Deterministic lookup; returns internal ReasonId string or None.
        """
        ext = str(external_id or "").strip()
        if not ext:
            return None
        for e in self.entries:
            if e.external_id == ext:
                return e.internal_reason_id
        return None
