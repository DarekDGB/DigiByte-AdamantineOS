# Foundation Frozen — v0.1.0 Baseline

Author attribution: **DarekDGB**

This document defines the frozen foundation baseline of **AdamantineOS**.

The foundation baseline consists of the minimal, deterministic, fail-closed execution pipeline:

**EQC → WSQK → TVA → Execution**

---

## Purpose of the foundation freeze

The foundation freeze establishes a fixed, known-good reference point prior to any
identity, risk, or adaptive integrations.

This baseline exists to:
- provide a stable rollback anchor
- enable precise audit and regression comparison
- separate foundational correctness from integration complexity

---

## Baseline scope

At the v0.1.0 foundation baseline, the repository guarantees:

- Contracts-first architecture
- Deterministic context hashing
- Fail-closed authority issuance (WSQK)
- Final enforcement gate via TVA
- Replay protection using injected nonce storage
- High-coverage, deterministic test suite

EQC behavior at this baseline is intentionally minimal and enforces
**presence-based validation only**.

---

## Explicit non-scope

The following are **not** part of the foundation baseline:

- Q-ID session or identity integration
- Shield or Adaptive Core risk integration
- Mobile (iOS / Android) runtime implementation
- Durable, crash-safe nonce storage
- External dependencies beyond the foundation contracts

---

## Integration constraint

All work performed after the foundation baseline MUST adhere to the following constraints:

- Deny-by-default semantics
- Negative-first validation
- Deterministic behavior only
- No silent fallback paths
- No external dependency coupling inside core contracts
