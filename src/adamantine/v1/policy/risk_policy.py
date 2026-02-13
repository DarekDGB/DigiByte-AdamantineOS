from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.shield import ExternalReasonMap


class UnknownReasonMode(str, Enum):
    """
    How to handle external reason codes that have no explicit mapping.

    Fail-closed default: deny explicitly.
    """

    DENY_EXPLICIT = "DENY_EXPLICIT"


class ResilienceMode(str, Enum):
    """
    How strict the system is when evidence is missing/malformed.

    Fail-closed default: strict deny.
    """

    STRICT_FAIL_CLOSED = "STRICT_FAIL_CLOSED"


@dataclass(frozen=True)
class RiskPolicy:
    """
    Deterministic risk policy config.

    This remains a small immutable config object, but can optionally carry a PolicyPack.
    The PolicyPack is the contract-driven source for thresholds/allowlists/mapping.

    IMPORTANT:
    - If policy_pack is provided, it defines min_overall_score + allowlisted external reason IDs + mapping table.
    - If policy_pack is None, defaults remain deterministic and safe.
    """

    min_overall_score: int = 85
    unknown_reason_mode: UnknownReasonMode = UnknownReasonMode.DENY_EXPLICIT
    resilience_mode: ResilienceMode = ResilienceMode.STRICT_FAIL_CLOSED
    policy_pack: PolicyPack | None = None

    # Step 4 (v1.3.x): posture requirements (no silent downgrade)
    # If True, caller must request a protected call (wsqk present) or we fail closed.
    require_protected_call: bool = False
    # If True, orchestrator must not proceed unless protection_mode would be "full".
    # (This is a policy-level posture latch; defaults to False to preserve proof packs.)
    require_full_mode: bool = False

    def validate(self) -> None:
        if self.policy_pack is not None:
            if not isinstance(self.policy_pack, PolicyPack):
                raise ValueError("policy_pack must be PolicyPack or None")
            # PolicyPack is the single source of truth and must validate first.
            self.policy_pack.validate()

            # Avoid split-brain: min_overall_score must match pack.
            if self.min_overall_score != self.policy_pack.min_overall_score:
                raise ValueError("min_overall_score must match policy_pack.min_overall_score")

        if not isinstance(self.min_overall_score, int):
            raise ValueError("min_overall_score must be int")
        if not (0 <= self.min_overall_score <= 100):
            raise ValueError("min_overall_score must be in range 0..100")

        if not isinstance(self.unknown_reason_mode, UnknownReasonMode):
            raise ValueError("unknown_reason_mode must be UnknownReasonMode")

        if not isinstance(self.resilience_mode, ResilienceMode):
            raise ValueError("resilience_mode must be ResilienceMode")

        if not isinstance(self.require_protected_call, bool):
            raise ValueError("require_protected_call must be bool")

        if not isinstance(self.require_full_mode, bool):
            raise ValueError("require_full_mode must be bool")

    def effective_allowed_external_reason_ids(self) -> tuple[str, ...]:
        """
        Returns the allowlist used by adapters.

        If a PolicyPack is present, it is the source of truth.
        Otherwise, return a deterministic safe default.
        """
        if self.policy_pack is not None:
            return self.policy_pack.allowed_external_reason_ids
        return ("ok",)

    def effective_external_reason_map(self) -> ExternalReasonMap | None:
        """
        Returns the ExternalReasonMap used by adapters.

        If a PolicyPack is present, it is the source of truth.
        If not present, return None so callers can fail-closed or inject explicitly.
        """
        if self.policy_pack is not None:
            return self.policy_pack.external_reason_map
        return None
