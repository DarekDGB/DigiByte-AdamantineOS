# Foundation Lock

**License:** MIT License — DarekDGB

---

## 1. Purpose

This document defines what it means for the Adamantine Wallet OS **execution foundation** to be **locked**.

A locked foundation is a security and stability checkpoint:
- Interfaces are stable
- Behavior is deterministic
- Invariants are enforced
- Tests are green and meaningful
- Coverage is consistently high
- End-to-end execution guarantees are proven
- Future work builds *on top* of this boundary without weakening it

---

## 2. What “Locked” Means

When the foundation is locked:

- **Core invariants are non-negotiable** (deny-by-default, fail-closed, determinism, no hidden authority).
- **The execution boundary is sealed** (Adamantine is not a wallet runtime).
- **Key custody remains external** (Adamantine never handles private keys).
- **No cloud syncing** is introduced.
- **Only iOS + Android** are supported (no web).
- **Execution requires explicit authority and TVA enforcement**.
- All changes after lock must be **additive**, **versioned**, and **test-locked**.

---

## 3. Locked Foundation Components (Implemented)

The following components are part of the locked execution foundation and are implemented and test-covered:

- **EQC v1** — Deterministic execution evaluation and context hashing.
- **WSQK v1** — Wallet-scoped, time-bound authority primitives (no key custody).
- **TVA Gate** — Mandatory authority, expiry, and replay enforcement.
- **Nonce Store** — Single-use nonce enforcement for replay protection.
- **Execution Boundary** — The only allowed path to execution.
- **Execution Envelopes v1** — Versioned, fail-closed request/response contracts.
- **Adapters** — Strict integration boundaries for external systems (Q-ID, Adaptive Core).
- **ExternalReasonMap / PolicyPack** — Explicit, versioned governance for external signals.
- **Metrics / Audit Signals** — Non-sensitive observability via reason identifiers.

Adamantine remains strictly an **execution boundary**: it decides *allow / deny* under explicit, verifiable conditions.

---

## 4. Explicit Non-Goals (Remain Out of Scope)

The foundation lock explicitly excludes:

- Private key generation, storage, derivation, or export
- Transaction signing or broadcasting
- Wallet runtime or UI concerns
- Cloud-based recovery or syncing
- Any assumption that keys are single-device
- Any implicit trust in upstream intelligence

Key custody, signing, and UI remain external responsibilities.

---

## 5. Quality Gate (Lock Criteria)

An execution foundation lock requires:

- **All tests green** on CI
- **High, stable coverage** (≈97% in this repository)
- **Negative-first security tests** for all boundary conditions
- **End-to-end execution proofs** (EQC → WSQK → TVA)
- **Deterministic behavior** (no hidden time, randomness, or ordering effects)
- **Fail-closed semantics** for all validation, adapters, and gates

If a change reduces determinism, weakens invariants, or introduces silent fallback,
the foundation is no longer considered locked.

---

## 6. Change Control After Lock

After foundation lock:

- No breaking changes without **explicit versioning**
- No relaxation of validation or gating rules
- No expansion into wallet runtime or key custody
- No hidden authority, bypass paths, or undocumented behavior

Any change must include:
- Updated or additional tests
- Updated documentation if contracts or behavior change
- Explicit reason identifiers for new rejection paths

---

## 7. Roadmap Position

The execution foundation lock enables subsequent work:

- Controlled orchestration around the execution boundary
- Strict mobile integration boundaries (iOS / Android)
- Additional execution wiring built **on top of** sealed contracts

The execution boundary itself remains immutable.

---

## 8. Summary

Foundation lock is a commitment:

- The execution boundary is sealed
- Determinism is enforced
- Authority is explicit and time-bound
- Execution is impossible without TVA
- Everything that follows is additive, versioned, and test-locked
