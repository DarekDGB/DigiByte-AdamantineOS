from __future__ import annotations

from dataclasses import dataclass, field


class Metrics:
    """
    Minimal metrics sink.

    SECURITY INVARIANT:
    - Must not store payloads, secrets, context fields, or request objects.
    - Only aggregated counters keyed by ReasonId strings.
    """

    def inc(self, reason_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def snapshot(self) -> dict[str, int]:  # pragma: no cover
        raise NotImplementedError


@dataclass(slots=True)
class NullMetrics(Metrics):
    """
    No-op metrics sink (default).
    """

    def inc(self, reason_id: str) -> None:
        return

    def snapshot(self) -> dict[str, int]:
        return {}


@dataclass(slots=True)
class InMemoryMetrics(Metrics):
    """
    In-memory counter store for tests/dev.

    Stores:
    - {reason_id: count}

    Does NOT store payloads or objects.
    """
    _counters: dict[str, int] = field(default_factory=dict)

    def inc(self, reason_id: str) -> None:
        rid = str(reason_id or "").strip()
        if not rid:
            return
        self._counters[rid] = self._counters.get(rid, 0) + 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counters)
