from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from adamantine.v1.contracts.shield import ShieldSignal


@dataclass(frozen=True, slots=True)
class ShieldBundleV3:
    """
    Internalized Shield v3 evidence bundle (post-parse, post-mapping).

    - signals are internal ShieldSignal objects (ReasonIds already mapped)
    - still evidence-only (never grants allow by itself)
    """
    bundle_id: str
    context_hash: str
    issued_at: int
    expires_at: int
    required_layers: Tuple[str, ...]
    signals: Tuple[ShieldSignal, ...]

    def validate(self) -> None:
        if not isinstance(self.bundle_id, str) or not self.bundle_id.strip():
            raise ValueError("bundle_id must be non-empty str")

        if not isinstance(self.context_hash, str) or len(self.context_hash) != 64:
            raise ValueError("context_hash must be 64-char hex str")

        if not isinstance(self.issued_at, int) or not isinstance(self.expires_at, int):
            raise ValueError("issued_at/expires_at must be int")

        if self.expires_at < self.issued_at:
            raise ValueError("expires_at must be >= issued_at")

        if not isinstance(self.required_layers, tuple) or len(self.required_layers) == 0:
            raise ValueError("required_layers must be a non-empty tuple")

        for layer in self.required_layers:
            if not isinstance(layer, str) or not layer.strip():
                raise ValueError("required_layers entries must be non-empty str")

        if not isinstance(self.signals, tuple) or len(self.signals) == 0:
            raise ValueError("signals must be a non-empty tuple")

        for s in self.signals:
            if not isinstance(s, ShieldSignal):
                raise ValueError("signals must contain ShieldSignal")
            s.validate()
