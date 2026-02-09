# Adamantine Wallet OS — Interfaces

**License:** MIT License  
**Author:** DarekDGB  
**Repository:** DigiByte Adamantine Wallet OS  
**Scope:** Foundation Interfaces (Contracts, No Runtime)

---

## 1. Purpose

This document defines the **interface contracts** that form the explicit boundaries between components in the Adamantine Wallet OS foundation.

An interface in Adamantine is:
- a **contract**, not an integration
- **deterministic**, versioned, and test-enforced
- independent of runtime, UI, or storage

Interfaces define **what may be exchanged**, not **how it is used**.

---

## 2. Interface Philosophy

All interfaces in this system obey the following rules:

- **Fail-closed**: invalid or missing data results in rejection
- **Explicit inputs only**: no hidden state, no globals
- **Deterministic semantics**: same input → same result
- **No authority leakage**: interfaces never grant permission implicitly
- **Single source of truth**: all semantics map to `ReasonId`

If a behavior is not defined by an interface contract, it does not exist.

---

## 3. Core v1 Contracts

### 3.1 Execution Context

The execution context defines *what is being requested*.

**Fields**
- `wallet_id: str`
- `action: str`
- `context_hash: str` (64-char hex)

**Notes**
- `context_hash` uniquely binds all downstream decisions
- Any mismatch results in **DENY**

---

### 3.2 Verdict

Verdict is a **decision outcome**, not authority.

**Allowed Values**
- `ALLOW`
- `DENY`
- `STEP_UP` *(reserved for future additive extensions)*

**Rules**
- Only `ALLOW` may proceed to authority enforcement
- All other values halt execution

---

### 3.3 EQC Result (Decision Output)

The EQC result represents the **deterministic reasoning outcome**.

**Fields**
- `verdict: Verdict`
- `reason_ids: tuple[str, ...]`
- `context_hash: str`

**Rules**
- `reason_ids` MUST be stable and ordered
- `context_hash` MUST match the execution context
- EQC does not grant authority

---

### 3.4 WSQK Authority Token

WSQK is the **only authority token** in the foundation.

**Fields**
- `wallet_id: str`
- `action: str`
- `context_hash: str`
- `issued_at: int` *(unix seconds)*
- `expires_at: int` *(unix seconds)*
- `nonce: str` *(single-use)*

**Properties**
- context-bound
- time-bound
- single-use
- unforgeable by construction

Authority is invalid outside its exact scope.

---

## 4. Gates and Makers (v1)

### 4.1 TVA Gate (Final Enforcement)

**Function Signature**
```
enforce_tva(
    context,
    verdict,
    authority,
    *,
    now: int | None = None,
    nonce_store: NonceStore | None = None
) -> None
```

**Enforcement Rules**
- Fail-closed on missing inputs
- Fail-closed unless `verdict == ALLOW`
- Fail-closed unless authority binds exactly:
  - `wallet_id`
  - `action`
  - `context_hash`
- Fail-closed unless time window holds:
  - `issued_at ≤ now ≤ expires_at`
- Fail-closed unless nonce is accepted as single-use

**Determinism Requirements**
- `now` MUST be injected
- `nonce_store` MUST be injected
- No global state permitted

TVA is the **last gate** before execution.

---

### 4.2 WSQK Issuer (Authority Maker)

**Function**
```
issue_wsqk_authority(WSQKIssueRequest) -> WSQKAuthority
```

**Issuer Guarantees**
- Does not execute
- Does not evaluate policy
- Does not infer intent
- Produces authority only when explicitly requested

**Inputs**
- explicit context
- injected `now`
- injected TTL
- injected nonce

---

## 5. Evidence Interfaces (Non-Authoritative)

The following interfaces provide **signals only**:

- Q-ID session evidence
- Shield v3 signals and bundles
- Adaptive Core v3 oracle reports

Rules:
- Evidence can strengthen **DENY**
- Evidence can never force **ALLOW**
- Evidence must pass adapter validation before use

---

## 6. Reason IDs

`ReasonId` is the **single source of truth** for all outcomes.

Rules:
- No magic strings
- No dynamic reason creation
- External reasons MUST be mapped via adapters
- Reason ordering is deterministic

Any unmapped or unknown reason results in **DENY**.

---

## 7. Versioning and Freeze

All interfaces in this document are **frozen at the foundation tag**.

Future changes must:
- be additive
- preserve backward compatibility
- never weaken enforcement semantics

Breaking changes require a new major version.
