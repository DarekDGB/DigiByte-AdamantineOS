from __future__ import annotations

from adamantine.v1.obs.metrics import InMemoryMetrics, NullMetrics


def test_metrics_objects_have_no_payload_storage_fields() -> None:
    for m in (InMemoryMetrics(), NullMetrics()):
        # deny-by-default leakage surface: metrics must never keep request/payload/context
        assert not hasattr(m, "payload")
        assert not hasattr(m, "request")
        assert not hasattr(m, "context")
        assert not hasattr(m, "raw")
        assert not hasattr(m, "evidence")
        assert not hasattr(m, "session")
        assert not hasattr(m, "risk")
