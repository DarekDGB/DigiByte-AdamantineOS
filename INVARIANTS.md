# AdamantineOS — Invariants

**License:** MIT License — DarekDGB

---

## 1. Purpose

This document defines the **non-negotiable invariants** of AdamantineOS.

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

### 7.1 Adapters Are Non-Authoritative

Adapters do not grant authority.

Adapters cannot approve execution by themselves.

### 7.2 Adapters Cannot Bypass Enforcement

Adapters cannot bypass Adamantine enforcement rules.

Adapter output must pass the same deterministic validation path as all other inputs.

### 7.3 Adapter Failure Is Deterministic

Adapter validation failure causes deterministic rejection.

Adapter ambiguity, malformed output, or unsupported output causes deterministic rejection.

---

## 8. Observability Invariants

### 8.1 No Sensitive Logging

Private keys, secrets, seeds, mnemonics, signatures, sensitive payloads, and private user material MUST NOT be logged.

### 8.2 Non-Sensitive Metrics Only

Metrics must not expose sensitive user material.

### 8.3 Observability Has No Authority

Observability must not affect execution decisions.

Logging, tracing, or metrics must never change allow/deny outcomes.

---

## 9. Evolution Invariants

### 9.1 Invariants May Not Be Weakened

Existing invariants may not be weakened by refactors, optimizations, integrations, or version upgrades.

### 9.2 New Invariants Must Strengthen the System

New invariants may be added only if they:

- Do not conflict with existing invariants
- Strengthen security, determinism, or contract discipline
- Are documented
- Are test-locked where applicable

---

## 10. v1.3.0 Protection Mode Invariants

### 10.1 Protection Mode Semantics Are Fixed

`protection_mode` is an auditable output field with deterministic semantics:

- `legacy`: protected call not requested OR Q-ID invalid/missing
- `minimal`: Q-ID valid, but Oracle and/or Shield invalid/missing
- `full`: Q-ID valid + Oracle valid + Shield valid, as configured

These semantics are regression-locked by a truth-table test.

### 10.2 No Silent Downgrade Under Policy

If policy requires a stricter posture, orchestrator must fail-closed:

- `require_protected_call=True` and protected request missing → DENY with `ReasonId.DENY_POLICY`
- `require_full_mode=True` and full mode impossible → DENY with `ReasonId.DENY_POLICY`

### 10.3 Shield Can Only Strengthen Deny

If Shield evidence results in DENY, then:

- Adding more `OK` or allow-looking evidence must never flip the decision to ALLOW
- Reordering signals must never flip the decision to ALLOW

This is regression-locked permanently.

---

## 11. Cross-Repo Compatibility Invariants

### 11.1 Compatibility Vectors Are Frozen Truth

Compatibility vectors under `tests/compat_vectors/` are frozen truth for external governance artifacts.

### 11.2 Compatibility Tests Must Enforce Contract Behavior

Tests under `tests/compat/` MUST enforce:

- Canonicalization rules
- `proposal_hash` invariants
- Receipt reason IDs
- Decision reason IDs

### 11.3 Vector Breakage Is Contract Breakage

If any refactor changes behavior such that compatibility vectors no longer pass, that is a breaking change.

The change MUST be treated as a contract violation unless it is handled through an explicit major version bump.

---

## 12. WSQK v2 Quantum-Aware Authority Invariants

### 12.1 Required Evidence Families Are a Sorted Canonical Set

`required_evidence_families` MUST be stored and compared as a sorted canonical set.

Order of input is normalized on issuance.

Two authorities requiring the same families MUST produce identical `proof_bindings_hash` values regardless of input order.

### 12.2 No Implicit Quantum Posture

WSQK v2 MUST NOT infer, assume, or silently downgrade quantum or security posture.

Missing, ambiguous, unknown, unsupported, revoked, or insufficient posture MUST deny deterministically.

### 12.3 Valid Signature Is Not Valid Authority

A cryptographically valid signature is insufficient by itself.

WSQK v2 authority remains valid only when all of the following satisfy explicit policy:

- Wallet
- Action
- Context
- Timebox
- Nonce
- Required evidence families
- Declared quantum posture

### 12.4 WSQK v2 Reason IDs Are Stable Contract Values

WSQK v2 deny semantics MUST use stable `ReasonId` enum values instead of freeform strings.

Evidence-family shape failures, unknown evidence families, and invalid quantum posture MUST map to dedicated WSQK-v2-specific reason IDs.

These values are regression-locked and become inputs for Phase 4 TVA enforcement.

### 12.5 TVA Enforces WSQK v2 Quantum Requirements Explicitly

When TVA receives explicit WSQK v2 requirements, it MUST deny WSQK v1 authority instead of silently treating it as quantum-aware.

TVA MUST compare required evidence families using the sorted canonical set rule.

TVA MUST compare declared quantum posture exactly.

TVA MUST recompute `proof_bindings_hash` from canonical WSQK v2 fields and deny any mismatch before nonce acceptance.

---

## 13. Summary

Invariants define the identity of AdamantineOS.

They are not guidelines.

They are laws.
