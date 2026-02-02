# Adamantine Wallet OS — External Interfaces

**License:** MIT License — DarekDGB

---

## 1. Purpose

This document defines the **external interface rules** for Adamantine Wallet OS.

External interfaces describe how untrusted callers interact with Adamantine.
They are treated as **security-critical contracts** and are enforced strictly.

Any deviation from this document is considered a breaking change.

---

## 2. Interface Philosophy

All external interfaces follow these principles:

- Explicit over implicit
- Deterministic over permissive
- Fail-closed over best-effort
- Versioned over inferred
- Deny-by-default over allow-by-assumption

Adamantine never infers intent or authority from context alone.

---

## 3. Execution Boundary

Adamantine exposes a **single execution boundary** to external callers.

- All interactions occur via versioned execution envelopes
- No internal functions are callable directly
- No partial execution is permitted

If an execution request cannot be fully validated, it is rejected.

---

## 4. Input Validation Rules

### 4.1 Strict Decoding

- All inputs MUST conform exactly to the declared schema
- Unknown or unexpected fields are **rejected**
- Type coercion is not permitted
- Missing required fields result in rejection

This rule applies recursively to all nested structures.

---

### 4.2 Canonicalization

Before evaluation, all requests are:

- Canonicalized into a deterministic representation
- Normalized for ordering and encoding
- Hashed only after canonicalization

Canonicalization rules are part of the contract and versioned.

---

### 4.3 Versioning

- Every request MUST declare a version
- Version mismatches result in rejection
- Backward compatibility is explicit, never assumed

Forward compatibility is achieved through **new versions**, not permissive parsing.

---

## 5. Authority Declaration

- Authority MUST be explicitly declared per request
- Authority cannot be inferred or escalated
- Absence of authority is treated as denial

Authority evaluation is enforced by the TVA gate.

---

## 6. Time and Nonce Requirements

### 6.1 Timeboxes

- Requests MUST include issued-at and expiry timestamps
- Execution outside the declared timebox is rejected
- No implicit grace periods exist

### 6.2 Nonces

- Every execution request MUST include a nonce
- Nonces are single-use
- Replay attempts are deterministically rejected

---

## 7. Key Custody Neutrality

Adamantine treats key custody as **external and opaque**.

Rules:
- Adamantine never receives private key material
- Key distribution (single-device or multi-device) is not a deny condition
- Execution decisions depend only on declared context, authority, timebox, nonce, and explicit policy

Key custody choice is the user's responsibility.

---

## 8. Adapters

Adapters connect Adamantine to external systems.

Adapter rules:
- Adapters are non-authoritative
- Adapter outputs are validated
- Adapter failure results in deterministic rejection
- Adapters may not bypass execution rules

---

## 9. Observability

- Interfaces may emit non-sensitive metrics
- Reason identifiers are stable and versioned
- No secrets or private material are logged

Observability must never influence execution decisions.

---

## 10. Breaking Changes

Any of the following constitute a breaking change:

- Schema modification
- Validation rule changes
- Canonicalization changes
- Authority semantics changes
- Timebox or nonce rule changes

Breaking changes require:
- New contract version
- Updated tests
- Explicit documentation

---

## 11. Summary

External interfaces are treated as **attack surfaces**, not conveniences.

Anything not explicitly allowed is rejected.
