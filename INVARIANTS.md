# Adamantine Wallet OS — Invariants

This repository is rebuilt from first principles.

---

## Foundation Freeze

- A known-good baseline **must be tagged** before any integration or expansion work.
- The current locked baseline is **v0.1.1-foundation-locked**.
- At the frozen foundation baseline:
  - EQC may enforce **minimal presence checks** only.
  - No external intelligence is required.
- Integration evidence (**Q-ID session + RiskReport**) becomes **mandatory only after**
  the integration gate is explicitly wired and versioned.

No code may silently transition from “foundation” to “integration” behavior.

---

## Post-Foundation Lock Invariants (v0.1.1+)

Once the foundation is locked, the following invariants are **non-negotiable**:

- Execution **must always** follow:
  ```
  EQC → WSQK → TVA → Execution
  ```
- Decision, authority, and execution **must never be combined**.
- All enforcement gates are **deny-by-default**.
- Missing, malformed, or unverifiable evidence **always results in DENY**.
- No fallback to weaker modes is permitted.
- No environment-dependent behavior is permitted.
- No maintainer, developer, or system override paths exist.

Any change violating these requires a **major version bump**.

---

## Core Laws

- No hidden authority
- No privileged maintainer paths
- No silent fallback
- Fail-closed always
- Deterministic behavior only
- Read-only observation before action
- Human-in-the-loop where consequence exists

These laws apply to **all future code**, regardless of platform or language.

---

## Truth Primitives

Adamantine operates on three immutable truth primitives:

- **EQC** — truth extraction (decision without authority)
- **WSQK** — sovereign, scoped authority (no execution)
- **TVA** — final enforcement gate (no decision logic)

Only what is aligned across all three may execute.

---

## Scope Discipline

- Architecture before implementation
- Contracts before features
- Tests before trust
- Ports before platforms
- Documentation before optimization

---

## Explicit Non-Goals

Adamantine Wallet OS will **never**:
- Manage private keys directly
- Perform signing internally
- Perform network broadcasting
- Act as an intelligence or learning engine
- Make autonomous decisions on behalf of the user

---

## Final Statement

These invariants are enforced by:
- contracts
- tests
- documentation
- versioning discipline

They exist to ensure that **unsafe execution is impossible by design**, not by policy.
