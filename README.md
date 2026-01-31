# 🔷 DigiByte Adamantine Wallet OS

<!--
BADGES: Replace <ORG> and <REPO> with your GitHub org/user + repository name.
Example: https://github.com/DarekDGB/DigiByte-Adamantine-Wallet-OS
-->

![CI](https://github.com/<ORG>/<REPO>/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-foundation--locked-important)
![Platform](https://img.shields.io/badge/platform-iOS%20%2B%20Android-only)

## Status: Foundation Locked (Not a wallet runtime yet)

This repository is a **clean, locked foundation** focused on **contracts, invariants, and deterministic fail-closed execution**.

Implemented:
- EQC v1 (decision foundation + deterministic context hashing)
- WSQK Authority v1 (time-bound authority + nonce)
- TVA Gate (binding, expiry, replay protection via injected nonce store)
- PolicyPack-driven risk thresholds & allowlists
- ExternalReasonMap-enforced adapters
- High-coverage CI with invariant-locked tests

Not implemented (by design):
- Wallet execution environment (keys, signing, broadcasting)
- Mobile runtime (iOS / Android)
- Shield v3 / Adaptive Core v3 live integration
- Durable nonce storage

**Quantum-Secure Execution Layer for DigiByte Wallets**  
*Architecture by DarekDGB — MIT Licensed*

---

## Purpose

**Adamantine Wallet OS** is not a traditional cryptocurrency wallet.

It is a **Wallet Operating System** whose sole responsibility is to ensure that  
**only context-approved, deterministic, and user-authorised actions are allowed  
to execute**, even under hostile conditions such as malware, compromised devices,
network anomalies, or social engineering.

Adamantine exists to make *unsafe wallet behaviour impossible by design*.

---

## What Adamantine IS

Adamantine Wallet OS is:

- a **secure execution layer** for DigiByte wallets
- a **consumer of shield intelligence**, not a generator of it
- a **runtime enforcement environment**, not a decision engine
- **mobile-first** (iOS and Android only)
- **consensus-neutral** (does not alter DigiByte protocol rules)
- **open-source and auditable** (MIT licensed)

It is the place where **decisions become irreversible actions — safely**.

---

## What Adamantine is NOT

Adamantine is **not**:

- a replacement for DigiByte Core
- a consensus or mining component
- a web wallet or browser runtime
- an AI or learning system
- a node authority
- a monolithic “do-everything” wallet

All intelligence, learning, and risk assessment happens *outside* Adamantine.

Adamantine only executes what is already approved.

---

## Architectural Position

Adamantine sits at the **final execution boundary** of the DigiByte security stack.

Execution pipeline:

```
EQC → WSQK → TVA → Execution
```

Upstream systems may:
- observe
- analyse
- classify
- recommend
- warn

But **only Adamantine executes**.

This separation is intentional and enforced.

---

## Architecture Diagram

```mermaid
flowchart TD
  %% External evidence (NOT executed here)
  subgraph Upstream["Upstream Intelligence (outside Adamantine)"]
    QID["Q-ID Session Proof (external)"]
    AC["Adaptive Core Risk Report (external)"]
  end

  %% Adapter boundary (strict validation, fail-closed)
  subgraph Adapters["Adapter Boundary (fail-closed)"]
    QIDA["qid_adapter: parse_qid_session()"]
    ACA["adaptive_core_adapter: parse_risk_report()"]
    MAP["ExternalReasonMap (explicit mapping)"]
    PACK["PolicyPack (thresholds + allowlists)"]
  end

  %% Core execution boundary
  subgraph Core["Adamantine Execution Boundary (locked)"]
    CTX["Execution Context\n(wallet_id + action + fields)"]
    HASH["Deterministic Context Hash"]
    EQC["EQC\nDecision Gate"]
    WSQK["WSQK Authority\n(time-bound + nonce)"]
    TVA["TVA Gate\n(binding + expiry + replay protection)"]
    EXEC["Execution Boundary\n(run_with_tva)"]
  end

  QID --> QIDA
  AC --> ACA
  PACK --> EQC
  PACK --> ACA
  MAP --> ACA

  CTX --> HASH --> EQC
  QIDA --> EQC
  ACA --> EQC

  EQC -->|ALLOW only| WSQK --> TVA --> EXEC
  EQC -->|DENY| TVA
```

---

## Core Principle

> **Decision, authority, and execution are never combined.**

Adamantine enforces execution **only after**:
- a valid decision exists
- authority is scoped and time-bound
- context integrity is verified

If any condition fails, execution does not occur.

There are no bypass paths.

---

## Security Philosophy

Adamantine is built on strict invariants:

- fail-closed by default
- no hidden authority
- no privileged maintainer paths
- deterministic behaviour only
- explicit user involvement where consequence exists
- explainability over automation

These rules are defined in `INVARIANTS.md` and apply to all future code.

---

## Project Status

This repository represents a **foundation-locked baseline**.

There is currently:
- no mobile runtime
- no signing or broadcasting logic
- no client UI

This is intentional.

Architecture, contracts, and invariants are defined **before** runtime integration begins.

---

## License

MIT License  
© 2025 **DarekDGB**

Use is permitted with attribution.
