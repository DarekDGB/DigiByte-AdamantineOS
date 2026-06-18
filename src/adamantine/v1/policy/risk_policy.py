from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

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


class ShieldRuntimeBoundary(str, Enum):
    """
    Explicit Shield evidence boundary selected for orchestrator_v2.

    LEGACY_BUNDLE_V3_TEST_ONLY preserves the pre-hardening local bundle path
    for old fixtures and compatibility tests only. Production hardening selects
    ORCHESTRATOR_RECEIPT_V3_2 so Shield reaches AdamantineOS through the single
    external Orchestrator receipt boundary.
    """

    LEGACY_BUNDLE_V3_TEST_ONLY = "LEGACY_BUNDLE_V3_TEST_ONLY"
    ORCHESTRATOR_RECEIPT_V3_2 = "ORCHESTRATOR_RECEIPT_V3_2"


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

    # v1.3.0 Step 4 posture latches
    # These are explicit policy-level requirements that the orchestrator must enforce.
    # They prevent silent security downgrades in production configurations.
    require_protected_call: bool = False
    require_full_mode: bool = False

    # v1.4.0 Q-ID linkage latch
    # If enabled, protected executions MUST supply a valid Q-ID replay proof.
    require_qid_replay_proof: bool = False

    # Post-v3.0.0 AOS-RT-002 production Shield runtime boundary lock.
    # The production-safe default is the Orchestrator v3.2 receipt boundary.
    # LEGACY_BUNDLE_V3_TEST_ONLY remains available only when explicitly selected
    # by old fixture harnesses or compatibility tests; plain RiskPolicy() must not
    # silently select the TEST-ONLY path.
    shield_runtime_boundary: ShieldRuntimeBoundary = ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2

    # Post-v3.0.0 AOS-RT-008 trusted Shield receipt denylist.
    # This is injected only from trusted integrator policy/config, never from the
    # untrusted execution request payload. It allows an integrator to fail-close
    # specific receipt hashes that have been revoked, replay-risked, or otherwise
    # rejected outside the deterministic verifier.
    rejected_shield_receipt_hashes: tuple[str, ...] = ()

    # Step 11.1 Shield-live authenticity latch.
    # When enabled, v2 runtime cannot accept Shield receipt or Adaptive Core
    # oracle evidence unless the integrator injects trusted external
    # authenticity verifiers. This is the hard gate for any active Shield/live
    # protection claim; without it, those objects remain integrity-checked
    # evidence only.
    require_authenticated_external_evidence: bool = False

    def validate(self) -> None:
        if self.policy_pack is not None:
            if not isinstance(self.policy_pack, PolicyPack):
                raise ValueError("policy_pack must be PolicyPack or None")
            # PolicyPack is the single source of truth and must validate first.
            self.policy_pack.validate()

            # Avoid split-brain: min_overall_score must match pack.
            if self.min_overall_score != self.policy_pack.min_overall_score:
                raise ValueError("min_overall_score must match policy_pack.min_overall_score")

        if type(self.min_overall_score) is not int:
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

        if not isinstance(self.require_qid_replay_proof, bool):
            raise ValueError("require_qid_replay_proof must be bool")

        if not isinstance(self.shield_runtime_boundary, ShieldRuntimeBoundary):
            raise ValueError("shield_runtime_boundary must be ShieldRuntimeBoundary")

        if not isinstance(self.require_authenticated_external_evidence, bool):
            raise ValueError("require_authenticated_external_evidence must be bool")

        if not isinstance(self.rejected_shield_receipt_hashes, tuple):
            raise ValueError("rejected_shield_receipt_hashes must be tuple[str, ...]")

        seen_receipt_hashes: set[str] = set()
        for receipt_hash in self.rejected_shield_receipt_hashes:
            if not isinstance(receipt_hash, str):
                raise ValueError("rejected_shield_receipt_hashes entries must be str")
            if re.fullmatch(r"[0-9a-f]{64}", receipt_hash) is None:
                raise ValueError("rejected_shield_receipt_hashes entries must be lowercase sha256 hex")
            if receipt_hash in seen_receipt_hashes:
                raise ValueError("rejected_shield_receipt_hashes must not contain duplicates")
            seen_receipt_hashes.add(receipt_hash)

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
