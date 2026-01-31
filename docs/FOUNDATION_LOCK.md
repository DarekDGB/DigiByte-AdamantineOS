# FOUNDATION LOCK — Adamantine Wallet OS

**Status:** Foundation Locked  
**Tag:** v0.1.1-foundation-locked  
**Author:** DarekDGB  
**Date:** 2026-01-28

---

## Purpose

This document defines the **irreversible foundation lock** of Adamantine Wallet OS.

From this point forward, the execution model, contracts, and invariants defined here
**must not change without an explicit major-version break**.

This file exists to prevent:
- silent authority creep
- accidental weakening of security properties
- undocumented behavior changes
- retroactive reinterpretation of intent

---

## Locked Execution Pipeline

The following execution pipeline is **final and mandatory**:

```
EQC → WSQK → TVA → Execution
```

No stage may be skipped.  
No stage may merge responsibilities with another.

---

## Locked Responsibilities

### EQC (Execution Qualification Check)
- Deterministic context hashing
- Evidence-based decisioning
- Fail-closed behavior on missing or invalid evidence
- No execution authority

### WSQK (Scoped Wallet Quantum Key / Authority)
- Time-bound authority
- Context-bound authority
- Nonce-scoped authority
- No execution logic

### TVA (Terminal Verification Authority)
- Final enforcement gate
- Replay protection
- Binding verification
- No decision logic

### Execution Boundary
- Executes **only** after TVA approval
- No side-channel execution paths
- No implicit retries or fallbacks

---

## Invariants (Non-Negotiable)

The following invariants are **permanently enforced**:

- Fail-closed by default
- No hidden authority
- No global mutable state
- Deterministic behavior only
- Explicit user intent where consequence exists
- Test-enforced contracts and invariants

---

## What Requires a Major Version Bump

Any change to the following **requires a major version increment**:

- Contract field meanings
- Execution order
- Authority semantics
- Default failure behavior
- Security invariants
- Evidence requirements

---

## Explicitly Forbidden

The following are **not allowed**:

- Bypass paths around EQC, WSQK, or TVA
- Silent fallback to weaker security modes
- Implicit trust in external systems
- Environment-dependent behavior
- Hidden maintainer overrides

---

## Scope Clarification

This lock applies to:
- Core contracts
- Enforcement logic
- Adapter boundaries
- Policy semantics

It does **not** define:
- UI behavior
- Mobile UX
- Key storage implementations
- Network transport logic

---

## Final Statement

Adamantine Wallet OS is designed so that **unsafe execution is impossible by design**.

This foundation lock ensures that future growth does not compromise that goal.
