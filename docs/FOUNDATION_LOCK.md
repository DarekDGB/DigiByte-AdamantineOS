# Foundation Lock

**License:** MIT License — DarekDGB

---

## 1. Purpose

This document defines what it means for the Adamantine Wallet OS **foundation** to be **locked**.

A locked foundation is a security and stability checkpoint:
- Interfaces are stable
- Behavior is deterministic
- Invariants are enforced
- Tests are green and meaningful
- Coverage is consistently high
- Future work builds *on top* of this boundary without weakening it

---

## 2. What “Locked” Means

When the foundation is locked:

- **Core invariants are non-negotiable** (deny-by-default, fail-closed, determinism, no hidden authority).
- **The execution boundary is preserved** (Adamantine is not a wallet runtime).
- **Key custody remains external** (Adamantine never handles private keys).
- **No cloud syncing** is introduced.
- **Only iOS + Android** are supported (no web).
- All changes after lock must be **additive**, **versioned**, and **test-locked**.

---

## 3. Locked Foundation Components (Implemented)

The following components are part of the locked foundation and are implemented and test-covered:

- **TVA Gate** — Trust/authority gate for execution decisions.
- **EQC v1** — Deterministic equilibrium confirmation logic.
- **WSQK v1** — Wallet-scoped enforcement primitives (no key custody).
- **Nonce Store** — Replay protection via single-use nonce enforcement.
- **Metrics / Audit Signals** — Non-sensitive decision telemetry and reason identifiers.
- **Adapters** — Integration boundaries for external systems (e.g., Q-ID, Adaptive Core).

Adamantine remains strictly an **execution boundary**: it decides *allow/deny* under declared conditions.

---

## 4. Explicit Non-Goals (Remain Out of Scope)

The foundation lock explicitly excludes:

- Private key generation, storage, derivation, or export
- Transaction signing or broadcasting
- Wallet runtime / UI concerns
- Cloud-based recovery or syncing
- Any assumption that keys are single-device

Key custody and signing remain external responsibilities.

---

## 5. Quality Gate (Lock Criteria)

A foundation lock requires:

- **All tests green** on CI
- **High, stable coverage** (target ~97% in this repo)
- **Negative-first security tests** for boundary enforcement
- **Deterministic behavior** (no time/random/order dependence beyond explicit timebox rules)
- **Fail-closed semantics** for all validation and gating paths

If a change reduces determinism, weakens invariants, or introduces silent fallback,
the foundation is no longer considered locked.

---

## 6. Change Control After Lock

After foundation lock:

- No breaking changes without **versioning**
- No relaxation of validation rules
- No expansion of scope into wallet runtime or key custody
- No hidden authority, no bypasses, no “temporary” exceptions

Any change must include:
- Updated tests
- Updated docs (if behavior or contracts change)
- Clear reason identifiers for new rejection paths

---

## 7. Roadmap Position

The foundation lock enables the next phase:

- **Execution wiring via versioned execution envelopes**
- Strict mobile integration boundaries
- Deterministic request/response contracts

The next step is to freeze the **Execution Envelope v1** contracts
so iOS and Android can integrate against a stable, enforceable boundary.

---

## 8. Summary

Foundation lock is a commitment:

- The core is stable
- The boundary is respected
- The security posture is preserved
- Everything that follows is additive,

versioned, and test-locked
