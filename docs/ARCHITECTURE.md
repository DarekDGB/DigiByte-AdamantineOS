# Adamantine Wallet OS — Architecture

**License:** MIT License  
**Author:** DarekDGB  
**Repository:** DigiByte Adamantine Wallet OS  
**Status:** Foundation Architecture (Frozen)

---

## 1. Purpose and Scope

This document defines the **architectural design** of the Adamantine Wallet OS as implemented in this repository.

Adamantine is a **deterministic security decision engine** designed to sit at the *final execution boundary* of DigiByte wallets and related systems.

It is intentionally **not**:
- a wallet runtime
- a key management system
- a signer
- a transaction builder
- a user interface
- a network node

Its sole responsibility is to answer one question:

> **Is this execution allowed, under these exact conditions, at this exact time?**

This architecture is **sealed** at the foundation milestone and may only evolve through **additive, contract-compatible changes**.

---

## 2. Architectural Principles

Adamantine is built around a small set of non-negotiable principles:

- **Deny-by-default** — anything ambiguous is denied
- **Fail-closed** — malformed or partial input halts execution
- **Determinism** — identical inputs always produce identical outputs
- **Separation of concerns** — evidence, decision, authority, and execution are isolated
- **No hidden authority** — all power is explicit and inspectable
- **Explainability** — every decision maps to a stable `ReasonId`

These principles are enforced through contracts, adapters, and tests.

---

## 3. High-Level Layer Model

The system is structured into five strictly ordered layers:

| Layer | Role | Can Allow? |
|-----|-----|-----------|
| Evidence Providers | Observation & analysis | ❌ |
| Adapters | Validation & normalization | ❌ |
| Decision Core (EQC) | Deterministic reasoning | ❌ |
| Authority & Enforcement | Time-bound permission | ✅ |
| Execution | Performed externally | ❌ |

No layer may skip or subsume another.

---

## 4. Evidence Providers (No Authority)

Evidence providers emit **signals only**.  
They do not grant permission and cannot override decisions.

### 4.1 Q-ID
Provides:
- identity assertions
- session validity
- temporal bounds

Q-ID evidence answers *who* and *when*, never *whether*.

---

### 4.2 Shield v3

Shield v3 is a **multi-layer defensive evidence system** composed of:

- Sentinel AI
- ADN (Autonomous Defense Network)
- DQSN (Distributed Quantum Shield Network)
- QWG (Quantum Wallet Guard)
- Guardian Wallet signals

Shield signals:
- describe observed risk or anomalies
- may strengthen a denial
- can never force an allow

---

### 4.3 Adaptive Core v3 Oracle

The Adaptive Core Oracle provides:
- deterministic risk scoring
- context-hash–bound assessments
- time-window–bound evaluations

Despite its name, the oracle has **no authority**.
It is an evidence source, not a decision-maker.

---

## 5. Adapter Layer (Fail-Closed)

Adapters form the **trust boundary** between external systems and Adamantine.

Their responsibilities include:
- strict schema validation
- version pinning
- context hash enforcement
- rejection of unknown fields
- rejection of unknown external reason identifiers
- deterministic normalization

Adapters **never**:
- infer intent
- apply policy
- allow execution

Any adapter failure results in **DENY**.

---

## 6. Decision Core — EQC v2

EQC (Equilibrium Confirmation) v2 is the deterministic reasoning engine.

### 6.1 Inputs
EQC v2 consumes:
- validated Q-ID session evidence
- Shield v3 evidence bundle
- Adaptive Core v3 oracle report
- explicit PolicyPack thresholds

### 6.2 Reasoning Rules

EQC v2 enforces strict rules:
- missing required evidence → **DENY**
- conflicting evidence → **DENY**
- evidence may strengthen **DENY**
- evidence may **never** force **ALLOW**

EQC produces a **decision outcome**, not authority.

---

## 7. Authority and Enforcement

Authority is strictly internal and time-bound.

### 7.1 WSQK (Wallet-Scoped Quantum Key)
- defines *who* may act
- scoped to wallet, action, and context
- limited in duration

### 7.2 TVA Gate
- binds authority to context hash
- enforces validity windows
- validates nonce consumption

### 7.3 Nonce Store
- injected dependency
- enforces single-use execution
- prevents replay attacks

Only this layer may emit **ALLOW**.

---

## 8. Execution Boundary

Adamantine outputs a **decision object**, not executable behavior.

It does not:
- build transactions
- sign data
- broadcast to networks

Execution is performed by external runtimes that consume Adamantine’s decision.

---

## 9. Architectural Invariants

The following invariants are enforced across all layers:

- evidence ≠ authority ≠ execution
- deny-by-default
- deterministic evaluation
- explicit contracts only
- no implicit trust
- no hidden control paths

Violating an invariant is considered a security failure.

---

## 10. Freeze Status

This architecture is **frozen** at the foundation tag.

Future development must:
- respect existing contracts
- preserve invariants
- remain backward compatible
- be strictly additive

Any deviation requires a new major version.
