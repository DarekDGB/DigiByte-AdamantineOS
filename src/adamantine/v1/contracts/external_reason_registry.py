from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True, slots=True)
class ExternalReasonLayerAllowlist:
    """Allowlist of external reason IDs for one Shield layer."""

    layer: str
    allowed_external_reason_ids: Tuple[str, ...]

    def validate(self) -> None:
        if not isinstance(self.layer, str) or not self.layer.strip():
            raise ValueError("layer must be non-empty str")

        if not isinstance(self.allowed_external_reason_ids, tuple) or len(self.allowed_external_reason_ids) == 0:
            raise ValueError("allowed_external_reason_ids must be a non-empty tuple")

        seen: set[str] = set()
        for rid in self.allowed_external_reason_ids:
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError("allowed_external_reason_ids entries must be non-empty str")
            if rid in seen:
                raise ValueError("allowed_external_reason_ids entries must be unique")
            seen.add(rid)


@dataclass(frozen=True, slots=True)
class ExternalReasonRegistryV1:
    """Deny-by-default registry for external reason IDs.

    Purpose
    - Prevent free-form external reason strings from Shield / Oracle sources.
    - Provide contract-level governance: new external reason IDs require registry updates + tests.

    Deny-by-default semantics
    - If a source/layer is not present in the registry, all external reason IDs for it are rejected.
    - If an external reason ID is not allowlisted for that source/layer, it is rejected.
    """

    # Adaptive Core Oracle v3 reason IDs (external) allowlist.
    oracle_allowed_external_reason_ids: Tuple[str, ...] = ()

    # Shield v3 per-layer allowlists.
    shield_layer_allowlists: Tuple[ExternalReasonLayerAllowlist, ...] = ()

    # Canonical Shield v3 layers (contract-level).
    ALLOWED_SHIELD_LAYERS: Tuple[str, ...] = (
        "sentinel_ai",
        "adn",
        "dqsn",
        "qwg",
        "guardian_wallet",
    )

    def validate(self) -> None:
        if not isinstance(self.oracle_allowed_external_reason_ids, tuple):
            raise ValueError("oracle_allowed_external_reason_ids must be tuple")

        seen_oracle: set[str] = set()
        for rid in self.oracle_allowed_external_reason_ids:
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError("oracle_allowed_external_reason_ids entries must be non-empty str")
            if rid in seen_oracle:
                raise ValueError("oracle_allowed_external_reason_ids must be unique")
            seen_oracle.add(rid)

        if not isinstance(self.shield_layer_allowlists, tuple):
            raise ValueError("shield_layer_allowlists must be tuple")

        seen_layers: set[str] = set()
        for entry in self.shield_layer_allowlists:
            if not isinstance(entry, ExternalReasonLayerAllowlist):
                raise ValueError("shield_layer_allowlists entries must be ExternalReasonLayerAllowlist")
            entry.validate()
            if entry.layer not in self.ALLOWED_SHIELD_LAYERS:
                raise ValueError(f"unknown shield layer in registry: {entry.layer}")
            if entry.layer in seen_layers:
                raise ValueError("shield_layer_allowlists must not contain duplicate layers")
            seen_layers.add(entry.layer)

    def is_oracle_reason_allowed(self, external_reason_id: str) -> bool:
        rid = str(external_reason_id or "").strip()
        if not rid:
            return False
        # Deny-by-default if oracle list empty.
        return rid in set(self.oracle_allowed_external_reason_ids)

    def is_shield_reason_allowed(self, *, layer: str, external_reason_id: str) -> bool:
        lyr = str(layer or "").strip()
        rid = str(external_reason_id or "").strip()
        if not lyr or not rid:
            return False
        # Deny-by-default: missing layer entry => reject.
        for entry in self.shield_layer_allowlists:
            if entry.layer == lyr:
                return rid in set(entry.allowed_external_reason_ids)
        return False
