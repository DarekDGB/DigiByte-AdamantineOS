# Adamantine Wallet OS — Architecture

**License:** MIT License — DarekDGB

---
This document describes the **sealed architecture** of the Adamantine Wallet OS foundation.

Adamantine is a **deterministic security decision engine**, not a wallet runtime.

---

## Architectural Layers

### 1. Evidence Providers (No Authority)

These systems observe, analyse, or assess risk.  
They **never** grant permission.

- **Q-ID** — identity/session evidence
- **Shield v3**
  - Sentinel AI
  - ADN
  - DQSN
  - QWG
  - Guardian Wallet
- **Adaptive Core v3 Oracle**
  - deterministic risk scoring
  - context-bound
  - time-bound

Evidence is **informational only**.

---

### 2. Fail-Closed Adapters

Adapters translate external evidence into **validated internal representations**.

Responsibilities:
- schema validation
- version pinning
- context-hash enforcement
- deny unknown fields
- deny unknown reason IDs

Adapters **do not decide**.

---

### 3. Decision Core (EQC v2)

**EQC v2** performs deterministic multi-evidence reasoning.

Inputs:
- Q-ID session
- Shield v3 bundle
- Adaptive Core oracle report

Rules:
- missing evidence → DENY
- conflicting evidence → DENY
- external systems can strengthen DENY
- external systems can never force ALLOW

---

### 4. Authority & Enforcement

- **WSQK** — scoped authority
- **TVA Gate** — authority binding, time, nonce
- **Nonce Store** — replay protection

Only this layer can produce **ALLOW**.

---

### 5. Execution Boundary

Adamantine outputs a **decision**, not an action.

Execution happens outside this system.

---

## Invariants

- deny-by-default
- evidence ≠ authority ≠ execution
- deterministic behaviour only
- no hidden power
- explicit contracts

This architecture is **frozen** at foundation tag.
