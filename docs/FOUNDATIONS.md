# 📘 FOUNDATIONS — EQC, WSQK, TVA

## Purpose of this document
This document defines the **three foundational primitives** of Adamantine Wallet OS.

It explains **what they are**, **what they are not**, and **how they relate**.

This document is **normative**.  
If future code contradicts this document, **this document wins**.

---

## 1️⃣ EQC — Equilibrium Confirmation

### What EQC is
**EQC (Equilibrium Confirmation)** is the **decision layer**.

It answers one question only:

> **“Should this action be allowed, denied, or require step-up?”**

EQC evaluates an **execution context** and returns a **deterministic verdict**.

### What EQC does
- Consumes an immutable execution context
- Applies explicit rules and classifiers
- Produces:
  - a verdict (`ALLOW`, `DENY`, `STEP_UP`)
  - a context hash
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
- Grants **scoped authority** after EQC approval
- Binds authority to:
  - a specific wallet
  - a specific action
  - a specific context hash
- Enforces:
  - time limits (TTL)
  - single-use (nonce)
  - non-reusability across contexts

WSQK is:
- narrow
- time-bound
- single-purpose
- non-transferable

### What WSQK does NOT do
WSQK does **not**:
- decide whether something is safe
- execute anything
- evaluate risk
- persist long-term secrets
- override EQC

WSQK can authorize — **but it cannot execute**.

---

## 3️⃣ TVA — Truth Vector Authority

### What TVA is
**TVA (Truth Vector Authority)** is the **enforcement law**.

It answers one question only:

> **“Is execution allowed to continue at all?”**

TVA is not a decision engine and not an authority generator.  
TVA is the **gate**.

### What TVA does
TVA enforces that **all required truths align** before execution:

- a valid execution context exists
- EQC verdict is `ALLOW`
- WSQK authority exists
- authority matches the context
- authority is unused and unexpired

If **any condition fails**, execution **does not continue**.

TVA is:
- fail-closed
- non-negotiable
- final

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

These three primitives form a **strict sequence**:

```
EQC  →  WSQK  →  TVA  →  Execution
```

- **EQC** decides *if* something should happen
- **WSQK** authorizes *that exact execution*
- **TVA** enforces that nothing proceeds unless everything aligns

No component can bypass another.

---

## 5️⃣ Non-Negotiable Invariants

- Decision ≠ Authority ≠ Execution
- No implicit trust
- No fallback paths
- No hidden power
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
No implementation is implied by this text.

---

© 2025 DarekDGB — MIT License
