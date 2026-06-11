# AdamantineOS Documentation Index

## Current Version

**v2.2.0 --- WSQK v2 Quantum-Aware Upgrade**

------------------------------------------------------------------------

# Core Documentation

Architecture and system design documents.

-   Adaptive Core Governance Flow
-   Contracts and artifact definitions
-   Invariant definitions

------------------------------------------------------------------------

# Governance

Documents describing governance interactions.

-   Adaptive Core → Adamantine Governance Flow
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
-   fail‑closed validation
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

Final gate documents before any AdamantineOS version bump or tag decision.

-   [Milestone 19 Final Release Gate](ADAMANTINEOS_MILESTONE_19_FINAL_RELEASE_GATE.md)
-   [Milestone 19 Tag Decision](ADAMANTINEOS_MILESTONE_19_TAG_DECISION.md)
-   [Final Proof Pack Index](ADAMANTINEOS_FINAL_PROOF_PACK_INDEX.md)

Milestone 19 does not approve a tag by itself. AdamantineOS remains `v2.2.0` and untagged until the final gate passes after fresh ZIP inspection, repeated tests, 100.00% coverage, and explicit maintainer approval.
