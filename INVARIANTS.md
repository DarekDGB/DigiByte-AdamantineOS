# Adamantine Wallet OS — Invariants

**License:** MIT License — DarekDGB

---

## 1. Purpose

This document defines the **non-negotiable invariants** of Adamantine Wallet OS.

Invariants are permanent rules that must remain true across all versions,
refactors, optimizations, and integrations.

Any violation of an invariant is a **security defect**.

---

## 2. Foundational Invariants

These invariants apply to all components without exception.

### 2.1 Deny-by-Default
If an action is not explicitly permitted, it is denied.

### 2.2 Fail-Closed
Ambiguity, partial data, or unexpected input results in rejection.

### 2.3 Determinism
Given the same valid input, Adamantine must always produce the same output.

### 2.4 No Hidden Authority
All authority must be declared explicitly.
No authority may be inferred, escalated, or assumed.

### 2.5 No Silent Fallback
Failures must surface as explicit, deterministic rejections.

---

## 3. Execution Boundary Invariants

### 3.1 Execution Boundary Only
Adamantine is an execution boundary, not a wallet runtime.

It evaluates *whether* execution is allowed.
It never performs execution itself.

### 3.2 Explicit Execution Envelopes
All interactions occur via versioned execution envelopes.
Internal functions are never exposed externally.

### 3.3 Single Evaluation
Each execution request is evaluated exactly once.

Replays are rejected deterministically.

---

## 4. Key Custody Invariants

### 4.1 External Key Custody
Adamantine never:
- Holds private keys
- Generates private keys
- Derives seeds or mnemonics

All key custody is external.

### 4.2 Key Distribution Neutrality
The presence of keys on multiple devices MUST NOT, by itself, cause denial.

Execution decisions depend only on:
- Declared context
- Declared authority
- Timebox validity
- Nonce validity
- Explicit policy

Single-device and multi-device custody are treated neutrally.

---

## 5. Time and Replay Invariants

### 5.1 Timebox Enforcement
Execution is valid only within the declared time window.

Expired or future-dated requests are rejected.

### 5.2 Nonce Enforcement
Each execution request must include a nonce.

Nonces are single-use.
Replay attempts are rejected deterministically.

---

## 6. Interface and Contract Invariants

### 6.1 Strict Validation
Unknown or unexpected fields are rejected.

### 6.2 Version Discipline
All interfaces are versioned.
Compatibility is explicit, never implicit.

### 6.3 Canonicalization
Canonical representations are used for hashing and evaluation.

---

## 7. Adapter Invariants

Adapters:
- Are non-authoritative
- Cannot bypass enforcement rules
- Are validated before use
- Cause deterministic rejection on failure

---

## 8. Observability Invariants

- No private or sensitive material is logged
- Metrics are non-sensitive
- Observability does not affect execution decisions

---

## 9. Evolution Rules

Invariants may not be weakened.

New invariants may be added only if:
- They do not conflict with existing ones
- They strengthen security or determinism
- They are documented and test-locked

---

## 10. Summary

Invariants define the identity of Adamantine Wallet OS.

They are not guidelines.
They are laws.

## 3. v1.3.0 Invariants

### 3.1 Protection Mode Semantics Are Fixed
`protection_mode` is an auditable output field with deterministic semantics:

- `legacy`: protected call not requested OR Q-ID invalid/missing
- `minimal`: Q-ID valid, but Oracle and/or Shield invalid/missing
- `full`: Q-ID valid + Oracle valid + Shield valid (as configured)

These semantics are regression-locked by a truth-table test.

### 3.2 No Silent Downgrade Under Policy
If policy requires a stricter posture, orchestrator must fail-closed:

- `require_protected_call=True` and protected request missing → DENY (ReasonId.DENY_POLICY)
- `require_full_mode=True` and full mode impossible → DENY (ReasonId.DENY_POLICY)

### 3.3 Shield Can Only Strengthen Deny
If Shield evidence results in DENY, then:
- adding more “OK/allow-looking” evidence must never flip to ALLOW
- reordering signals must never flip to ALLOW

This is regression-locked permanently.
