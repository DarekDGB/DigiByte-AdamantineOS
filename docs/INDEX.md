# AdamantineOS Documentation Index

## Current Version

**v3.0.0 --- Connected Evidence Architecture Release**

------------------------------------------------------------------------


## Connected Evidence Architecture

The `v3.0.0` release connects Shield components, Shield Orchestrator v3.2 receipts, WSQK v2, Q-ID, Adaptive Core, AI Gateway evidence-only input, replay / nonce enforcement, wallet policy evidence, and human review into the final AdamantineOS fail-closed decision engine.

- Shield components: Guardian Wallet, ADN, Sentinel AI, DQSN, QWG
- Shield Orchestrator v3.2 receipt boundary
- Shield runtime boundary lock: production uses Orchestrator receipt-only; legacy bundle mode is test-only until the Step 5 runtime route is wired
- WSQK v2 posture / policy evidence
- Q-ID identity / session evidence
- Adaptive Core advisory policy evidence
- AI Gateway evidence only, never final authority
- Replay / nonce freshness gate
- Human review exact-context gate
- Final allow / deny / review decision

------------------------------------------------------------------------

# Core Documentation

Architecture and system design documents.

-   Adaptive Core Governance Flow
-   Contracts and artifact definitions
-   Invariant definitions

------------------------------------------------------------------------

# Governance

Documents describing governance interactions.

-   Adaptive Core ÃÂ¢ÃÂÃÂ Adamantine Governance Flow
-   Governance Review Contract

------------------------------------------------------------------------

# Contracts

Artifact schemas and interface definitions.

-   upgrade_proposal_v3
-   proposal_review_receipt_v1
-   wsqk_authority_v2
-   WSQK v2 reason IDs
-   WSQK v2 Q-ID posture binding

------------------------------------------------------------------------

# Security Principles

AdamantineOS follows strict architectural guardrails:

-   deterministic behavior
-   failÃÂ¢ÃÂÃÂclosed validation
-   canonical serialization
-   explicit invariants
-   no silent fallback

------------------------------------------------------------------------

# Proof Packs

Audit maps connecting contracts, invariants, implementation, tests, and CI proof.

-   [WSQK v2 Quantum-Aware Proof Pack](PROOF_PACKS/wsqk_v2_quantum_aware_proof_pack.md)

------------------------------------------------------------------------

# Proof Philosophy

Every major feature is supported by:

-   deterministic tests
-   contract schemas
-   documentation alignment


------------------------------------------------------------------------

## Release Gate

Final release-gate and proof documents for the AdamantineOS v3.0.0 tag boundary.

-   [Milestone 19 Final Release Gate](ADAMANTINEOS_MILESTONE_19_FINAL_RELEASE_GATE.md)
-   [Milestone 19 Tag Decision](ADAMANTINEOS_MILESTONE_19_TAG_DECISION.md)
-   [Shield Runtime Boundary Lock](ADAMANTINEOS_SHIELD_RUNTIME_BOUNDARY_LOCK.md)
-   [Reproducible Audit Guide](ADAMANTINEOS_REPRODUCIBLE_AUDIT_GUIDE.md)
-   [Final Proof Pack Index](ADAMANTINEOS_FINAL_PROOF_PACK_INDEX.md)
-   [v3.0.0 Release Notes](ADAMANTINEOS_V3_0_0_RELEASE_NOTES.md)

Milestone 19 records the final release-gate proof set and release-stamped state for the approved `v3.0.0` tag. AdamantineOS must only be tagged after this release-stamp update is copied back, CI remains green, and the final copied-repo ZIP is inspected.
