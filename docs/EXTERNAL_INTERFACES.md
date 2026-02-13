# Adamantine Wallet OS — External Interfaces

**License:** MIT License  
**Author:** DarekDGB  
**Repository:** DigiByte Adamantine Wallet OS  
**Scope:** External Interface Contracts (Foundation)

---

## 1. Purpose and Scope

This document defines the **external interface contracts** for the Adamantine Wallet OS.

External interfaces describe how **untrusted callers and systems** interact with Adamantine at its boundaries.  
They are treated as **security-critical attack surfaces** and are enforced strictly.

Adamantine exposes **no internal APIs**.  
All interaction occurs through explicit, versioned, contract-defined interfaces.

Any deviation from this document is considered a **breaking change**.

---

## 2. External Interface Philosophy

All external interfaces in Adamantine adhere to the following principles:

- **Explicit over implicit** — nothing is inferred
- **Deterministic over permissive** — same input, same outcome
- **Fail-closed over best-effort** — invalid input halts execution
- **Versioned over inferred** — compatibility is explicit
- **Deny-by-default** — absence of proof is denial

Adamantine never infers intent, authority, or legitimacy from context alone.

---

## 3. Execution Boundary Model

Adamantine exposes a **single execution boundary**.

### Boundary Characteristics
- Interaction occurs via **versioned execution envelopes**
- No partial execution paths exist
- No internal functions are callable externally
- All validation occurs **before** any reasoning

If a request cannot be fully validated, it is **rejected deterministically**.

---

## 4. Input Validation Rules

### 4.1 Strict Decoding

All external inputs MUST satisfy:

- Exact schema conformance
- No unknown or extra fields
- No type coercion
- No implicit defaults
- No missing required fields

Validation rules apply **recursively** to all nested structures.

Any violation results in **DENY**.

---

### 4.2 Canonicalization

Before evaluation, all requests are:

- Canonicalized into a deterministic form
- Normalized for field ordering and encoding
- Hashed only **after** canonicalization

Canonicalization rules are:
- part of the contract
- versioned
- test-enforced

No non-canonical data is evaluated.

---

### 4.3 Version Declaration

- Every external request MUST declare a contract version
- Version mismatches result in rejection
- Backward compatibility is explicit and opt-in
- Forward compatibility requires new versions

Adamantine never guesses intent across versions.

---

## 5. Authority Declaration Rules

Authority is **never inferred**.

Rules:
- Authority MUST be explicitly declared
- Authority MUST be scoped to context
- Authority MUST be time-bound
- Authority MUST be single-use

Absence or invalidity of authority results in **DENY**.

Authority enforcement is performed exclusively by the **TVA gate**.

---

## 6. Time and Nonce Requirements

### 6.1 Timeboxes

All external execution requests MUST include:

- `issued_at`
- `expires_at`

Rules:
- Execution outside the declared time window is rejected
- No implicit grace periods exist
- Clock input (`now`) is injected, never global

---

### 6.2 Nonce Enforcement

- Every execution request MUST include a nonce
- Nonces are single-use
- Replay attempts are deterministically rejected
- Nonce storage is injected and explicit

Nonce enforcement is mandatory for **ALLOW**.

---

## 7. Key Custody Neutrality

Adamantine is **key-custody agnostic**.

Rules:
- Adamantine never receives private key material
- Adamantine does not track key distribution
- Multi-device key usage is not a deny condition
- Decisions depend only on:
  - declared context
  - explicit authority
  - timebox
  - nonce
  - policy

Key custody decisions remain the responsibility of the user or wallet runtime.

---

## 8. External System Adapters

Adapters connect Adamantine to external systems (e.g. Q-ID, Shield, Adaptive Core).

Adapter guarantees:
- non-authoritative
- fail-closed
- schema-validated
- version-pinned
- deterministic

Adapter failure always results in **DENY**.

Adapters cannot bypass execution rules or grant authority.

---

## 9. Observability Constraints

External interfaces may emit **non-sensitive observability data**.

Rules:
- Metrics are informational only
- `ReasonId` values are stable and versioned
- No secrets, keys, or private data are logged
- Observability never influences decisions

---

## 10. Breaking Change Definition

Any of the following constitute a breaking change:

- schema modification
- validation rule changes
- canonicalization changes
- authority semantics changes
- timebox or nonce semantics changes

Breaking changes require:
- new contract version
- updated tests
- explicit documentation

---

## 11. Security Summary

External interfaces are treated as **hostile entry points**, not conveniences.

Anything not explicitly allowed is rejected.

This model ensures that Adamantine remains deterministic, auditable, and resistant to ambiguity-based attacks.

## Protection Mode (v1.3.0)

Execution responses include `decision.protection_mode` to make the security posture auditable and deterministic:
- `legacy` / `minimal` / `full` (see `docs/CONTRACTS/mobile_decision_result_v1.md`).
