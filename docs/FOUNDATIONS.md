# 📘 FOUNDATIONS — EQC, WSQK, TVA

## Purpose of this document
This document defines the **three foundational primitives** of Adamantine Wallet OS.

It explains **what they are**, **what they are not**, and **how they relate**.

This document is **normative**.  
If future code, documentation, or behavior contradicts this document, **this document wins**.

---

## 1️⃣ EQC — Equilibrium Confirmation

### What EQC is
**EQC (Equilibrium Confirmation)** is the **decision layer**.

It answers one question only:

> **“Should this action be allowed, denied, or require step-up?”**

EQC evaluates an **execution context** and returns a **deterministic verdict**.

### What EQC does
- Consumes an immutable execution context
- Applies explicit, deterministic rules
- Produces:
  - a verdict (`ALLOW`, `DENY`, `STEP_UP`)
  - a deterministic context hash
  - reason identifiers (explainability)

EQC is:
- deterministic
- side-effect free
- replayable
- auditable

### What EQC does NOT do
EQC does **not**:
- execute actions
- generate keys
- grant authority
- access the network
- mutate state
- retry, learn, or adapt
- bypass user intent

EQC can decide — **but it cannot act**.

---

## 2️⃣ WSQK — Wallet-Scoped Quantum Key

### What WSQK is
**WSQK (Wallet-Scoped Quantum Key)** is the **authority layer**.

It answers one question only:

> **“Is this specific execution permitted right now, in this exact context?”**

WSQK represents **permission**, not decision.

### What WSQK does
- Grants **scoped authority** only after EQC approval
- Binds authority to:
  - a specific wallet
  - a specific action
  - a specific context hash
- Enforces:
  - explicit issuance time (`issued_at`)
  - explicit expiry (`expires_at`)
  - single-use via nonce (replay protection)

WSQK is:
- narrow
- time-bound
- single-use
- non-transferable
- context-bound

### What WSQK does NOT do
WSQK does **not**:
- decide whether something is safe
- execute anything
- evaluate risk
- persist long-term secrets
- override EQC
- self-extend or renew

WSQK can authorize — **but it cannot execute**.

---

## 3️⃣ TVA — Truth Vector Authority

### What TVA is
**TVA (Truth Vector Authority)** is the **enforcement law**.

It answers one question only:

> **“Is execution allowed to continue at all?”**

TVA is not a decision engine and not an authority generator.  
TVA is the **final gate**.

### What TVA does
TVA enforces that **all required truths align** before execution:

- a valid execution context exists
- an EQC verdict exists and is `ALLOW`
- a WSQK authority exists
- authority binds exactly to the context
- authority time window is valid (`issued_at ≤ now ≤ expires_at`)
- authority nonce is unused (single-use)

If **any condition fails**, execution **does not continue**.

TVA is:
- fail-closed
- deterministic
- non-negotiable
- final

### Determinism rule
TVA **does not read global time or global state**.

All external truths must be **explicitly injected**, including:
- `now` (unix seconds)
- `nonce_store` (replay protection)

### What TVA does NOT do
TVA does **not**:
- decide policy
- generate authority
- recover from failure
- retry or fallback
- explain user intent

TVA does not argue.  
It only permits or refuses continuation.

---

## 4️⃣ Relationship Between EQC, WSQK, and TVA

These three primitives form a **strict, non-bypassable sequence**:

```
EQC  →  WSQK  →  TVA  →  Execution
```

- **EQC** decides *if* something should happen
- **WSQK** authorizes *that exact execution*
- **TVA** enforces that nothing proceeds unless everything aligns

No component can bypass another.  
No component can impersonate another.

---

## 5️⃣ Non-Negotiable Invariants

- Decision ≠ Authority ≠ Execution
- No implicit trust
- No fallback paths
- No hidden power
- No global time or state
- No single component can act alone

Execution is only possible when:

> **Decision, authority, and context are all aligned.**

---

## 6️⃣ Why This Exists

Traditional wallets fail because:
- decisions and execution are intertwined
- authority is long-lived and reusable
- enforcement is implicit or optional

Adamantine separates these concerns so that:
- mistakes are caught before execution
- malware cannot escalate privilege
- replay attacks are blocked
- user intent cannot be silently overridden

---

## 7️⃣ One-Sentence Summary

- **EQC decides**
- **WSQK authorizes**
- **TVA enforces**

> **Only what is aligned is permitted to continue.**

---

## Status

This document defines **v1 foundations**.

It reflects:
- EQC v1 (deterministic decision + context hash)
- WSQK v1 Phase 2 (time-bound + nonce)
- TVA v1 (binding + expiry + replay enforcement)

No runtime wallet execution is implied by this text.

---

© 2025 DarekDGB — MIT License
