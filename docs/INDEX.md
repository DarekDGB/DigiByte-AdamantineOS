# Adamantine Wallet OS — Documentation Index

**License:** MIT License  
**Author:** DarekDGB  
**Repository:** DigiByte Adamantine Wallet OS  
**Scope:** Foundation Documentation Index

---

## 1. Purpose

This document is the **authoritative index** of all documentation that defines the Adamantine Wallet OS foundation.

The foundation is **contract-first**, **invariant-driven**, and **deterministic**.  
Runtime wallet execution, UI, clients, and integrations are intentionally excluded from this repository.

If a document is not listed here, it is **not part of the foundation contract**.

---

## 2. Foundation Status

**Current status:** Foundation sealed (pre-v1.0)

Included:
- Contracts
- Deterministic reasoning
- Fail-closed gates
- Authority model
- Execution boundaries

Explicitly not included:
- Wallet runtime
- Transaction construction
- Signing or broadcasting
- Client SDKs
- Shield or Adaptive Core implementations (evidence only)

---

## 3. Normative Sources (Highest Authority)

The following documents define **non-negotiable truth**.  
If code or documentation conflicts with these, **these documents win**.

- **`INVARIANTS.md`**  
  Core security and architectural invariants.

- **`FOUNDATIONS.md`**  
  Definitions and sequencing of EQC, WSQK, TVA, and execution flow.

---

## 4. Architectural Definition

These documents describe **how the system is structured** and **why boundaries exist**.

- **`ARCHITECTURE.md`**  
  Formal architecture of the sealed foundation.

- **`DECISION_AUTHORITY_EXECUTION.md`**  
  The core law: decision ≠ authority ≠ execution.

- **`TRUST_BOUNDARIES.md`**  
  Explicit trust termination points and validation requirements.

- **`THREAT_MODEL.md`**  
  Foundation-level threat assumptions and defenses.

---

## 5. Interface & Boundary Contracts

These documents define **contract surfaces** and **external interaction rules**.

- **`INTERFACES.md`**  
  Internal contract interfaces and enforcement semantics.

- **`EXTERNAL_INTERFACES.md`**  
  Rules for untrusted external callers and systems.

- **`KEY_EXECUTION_BOUNDARY.md`**  
  Key usage and execution boundary constraints.

---

## 6. Contract Specifications

Versioned, test-enforced contracts that define data shapes and semantics.

### Execution & Mobile
- `docs/CONTRACTS/mobile_execution_call_v1.md`
- `docs/CONTRACTS/mobile_decision_result_v1.md`
- `docs/execution_request_v1.md`
- `docs/execution_response_v1.md`

### Shield v3
- `docs/CONTRACTS/shield_signal_v3.md`
- `docs/CONTRACTS/shield_bundle_v3.md`

### Runtime Boundary
- `docs/CONTRACTS/wallet_runtime_boundary_v1.md`

### Context
- `docs/CONTEXT_HASH_SPEC.md`

---

## 7. Authority & Key Custody

Documents defining authority, keys, and recovery boundaries.

- `KEY_CUSTODY.md`
- `KEY_CUSTODY_OPTIONS.md`
- `DEVICE_LOSS_AND_RECOVERY_MODEL.md`

---

## 8. Observability & Operations

- `OBSERVABILITY.md`  
  Metrics, logging, and non-influential observability rules.

- `SECURITY.md`  
  Security posture and disclosure guidelines.

---

## 9. Change Control

- **`CHANGELOG.md`**  
  Records foundation milestones and contract changes.

Breaking changes:
- require new versions
- require updated contracts
- require explicit documentation

---

## 10. Reading Order (Recommended)

For new contributors or reviewers:

1. `INVARIANTS.md`
2. `FOUNDATIONS.md`
3. `ARCHITECTURE.md`
4. `DECISION_AUTHORITY_EXECUTION.md`
5. `INTERFACES.md`
6. `EXTERNAL_INTERFACES.md`
7. Contract specifications

---

## 11. Final Rule

If something is unclear, **assume denial** until proven otherwise by a contract.

This index is frozen at the foundation tag.
