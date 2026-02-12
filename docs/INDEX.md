# Adamantine Wallet OS --- Documentation Index

**License:** MIT License\
**Author:** DarekDGB\
**Repository:** DigiByte Adamantine Wallet OS\
**Scope:** Foundation Documentation Index

------------------------------------------------------------------------

## 1. Purpose

This document is the **authoritative index** of all documentation that
defines the Adamantine Wallet OS foundation.

The foundation is **contract-first**, **invariant-driven**, and
**deterministic**.\
Runtime wallet execution, UI, clients, and integrations are
intentionally excluded from this repository.

If a document is not listed here, it is **not part of the foundation
contract**.

------------------------------------------------------------------------

## 2. Foundation Status

**Current status:** v1.2.0 Integration Harness Sealed

Foundation includes: - Contracts - Deterministic reasoning - Fail-closed
gates - Authority model - Execution boundaries - Canonical fixture proof
pack (v1.2.0)

Explicitly not included: - Wallet runtime - Transaction construction -
Signing or broadcasting - Client SDKs - Shield or Adaptive Core
implementations (evidence only)

------------------------------------------------------------------------

## 3. Normative Sources (Highest Authority)

The following documents define **non-negotiable truth**.\
If code or documentation conflicts with these, **these documents win**.

-   `INVARIANTS.md`\
-   `FOUNDATIONS.md`

------------------------------------------------------------------------

## 4. Architectural Definition

-   `ARCHITECTURE.md`\
-   `DECISION_AUTHORITY_EXECUTION.md`\
-   `TRUST_BOUNDARIES.md`\
-   `THREAT_MODEL.md`

------------------------------------------------------------------------

## 5. Interface & Boundary Contracts

-   `INTERFACES.md`\
-   `EXTERNAL_INTERFACES.md`\
-   `KEY_EXECUTION_BOUNDARY.md`

------------------------------------------------------------------------

## 6. Contract Specifications

### Execution & Mobile

-   `docs/CONTRACTS/mobile_execution_call_v1.md`
-   `docs/CONTRACTS/mobile_decision_result_v1.md`
-   `docs/execution_request_v1.md`
-   `docs/execution_response_v1.md`

### Shield v3

-   `docs/CONTRACTS/shield_signal_v3.md`
-   `docs/CONTRACTS/shield_bundle_v3.md`

### Runtime Boundary

-   `docs/CONTRACTS/wallet_runtime_boundary_v1.md`

### Context

-   `docs/CONTEXT_HASH_SPEC.md`

------------------------------------------------------------------------

## 7. Deterministic Proof Packs

-   `docs/OS_PROOF_PACK_v1_2_0.md`\
    Canonical JSON fixture system, manifest enforcement, and
    reproducible execution validation.

------------------------------------------------------------------------

## 8. Authority & Key Custody

-   `KEY_CUSTODY.md`
-   `KEY_CUSTODY_OPTIONS.md`
-   `DEVICE_LOSS_AND_RECOVERY_MODEL.md`

------------------------------------------------------------------------

## 9. Observability & Operations

-   `OBSERVABILITY.md`
-   `SECURITY.md`

------------------------------------------------------------------------

## 10. Change Control

-   `CHANGELOG.md`

Breaking changes: - require new versions - require updated contracts -
require explicit documentation

------------------------------------------------------------------------

## 11. Reading Order (Recommended)

1.  `INVARIANTS.md`
2.  `FOUNDATIONS.md`
3.  `ARCHITECTURE.md`
4.  `DECISION_AUTHORITY_EXECUTION.md`
5.  `INTERFACES.md`
6.  `EXTERNAL_INTERFACES.md`
7.  Contract specifications
8.  Proof pack documentation

------------------------------------------------------------------------

## 12. Final Rule

If something is unclear, **assume denial** until proven otherwise by a
contract.

This index reflects the foundation state as of **v1.2.0**.
