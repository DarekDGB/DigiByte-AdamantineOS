from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from adamantine.v1.contracts.policy_pack import PolicyPack


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
    The PolicyPack is the contract-driven source for thresholds/allowlists.

    IMPORTANT:
    - If policy_pack is provided, it defines min_overall_score and allowlisted external reason IDs.
    - If policy_pack is None, defaults remain deterministic and safe.
    """

    min_overall_score: int = 85
    unknown_reason_mode: UnknownReasonMode = UnknownReasonMode.DENY_EXPLICIT
    resilience_mode: ResilienceMode = ResilienceMode.STRICT_FAIL_CLOSED
    policy_pack: PolicyPack | None = None

    def validate(self) -> None:
        if self.policy_pack is not None:
            if not isinstance(self.policy_pack, PolicyPack):
                raise ValueError("policy_pack must be PolicyPack or None")
            self.policy_pack.validate()

        # If a pack exists, min_overall_score must match it (avoid split-brain).
        if self.policy_pack is not None:
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

    def effective_allowed_external_reason_ids(self) -> tuple[str, ...]:
        """
        Returns the allowlist used by adapters.

        If a PolicyPack is present, it is the source of truth.
        Otherwise, return a deterministic safe default.
        """
        if self.policy_pack is not None:
            return self.policy_pack.allowed_external_reason_ids
        return ("ok",)
