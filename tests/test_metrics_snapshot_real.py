from __future__ import annotations

from adamantine.v1.obs.metrics import Metrics


class RecordingMetrics(Metrics):
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, reason_id: str) -> None:
        if not isinstance(reason_id, str) or not reason_id:
            return
        self.counts[reason_id] = self.counts.get(reason_id, 0) + 1


def test_metrics_snapshot_returns_dict() -> None:
    m = RecordingMetrics()
    m.inc("X")
    snap = m.snapshot()
    assert snap == {"X": 1}
