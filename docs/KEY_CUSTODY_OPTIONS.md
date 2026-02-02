# Adamantine Wallet OS — Key Custody Options

MIT License  
© 2026 DarekDGB

---

## Purpose

This document explains **key custody choices available to users** of systems built with
Adamantine Wallet OS, including the **risks, benefits, and guarantees** associated with each.

Adamantine **does not enforce how keys are stored**.  
Adamantine enforces **how and when actions are allowed to execute**.

Key custody is a **user decision**. Execution safety is **Adamantine’s responsibility**.

---

## Core Principle

> **Adamantine enforces execution safety, not custody purity.**

This means:
- Users are free to choose how they manage keys.
- Adamantine does not block execution based on key origin.
- Security guarantees vary depending on the custody model chosen.

---

## Option A — Device‑Only Keys (Highest Assurance)

### Description
Keys are generated and stored on a single device using platform‑native secure storage
(e.g. iOS Secure Enclave, Android Keystore).

Keys are:
- non‑exportable
- never written down
- never copied to another device

### Benefits
- Maximum resistance to theft and malware
- Minimal trusted computing base (TCB)
- No key duplication
- Strong protection against social engineering

### Risks / Trade‑offs
- Loss of device = loss of funds
- No recovery without on‑chain transfer beforehand
- Single‑device usability

### Adamantine Guarantee Level
**Maximum**  
Adamantine can offer its strongest execution guarantees under this model.

---

## Option B — Paper Backup / Reusable Keys

### Description
Keys are generated once and written down or otherwise recorded by the user.
The same keys may be imported into multiple devices.

### Benefits
- Recovery possible after device loss
- Multi‑device access
- Familiar model for many crypto users

### Risks / Trade‑offs
- Keys exist outside secure hardware
- Increased exposure to theft, copying, or coercion
- Impossible to prove keys were not duplicated

### Adamantine Guarantee Level
**Reduced (Execution‑only)**  
Adamantine still enforces execution safety, but **cannot guarantee key secrecy**.

---

## Option C — Shared / Family Wallets (Same Keys on Multiple Devices)

### Description
Multiple trusted parties (e.g. spouses) intentionally share the same keys
across multiple devices.

### Benefits
- Shared control and convenience
- Redundancy across devices

### Risks / Trade‑offs
- Larger attack surface
- Trust assumptions between parties
- Compromise of one device affects all

### Adamantine Guarantee Level
**Execution‑safe per device**  
Each device must still pass EQC, WSQK, and TVA checks independently.

---

## Option D — External Custody / Hardware Wallets

### Description
Keys are stored in an external device or system (hardware wallet, multisig, external signer).
Adamantine only gates execution requests.

### Benefits
- Strong physical separation
- Flexible custody strategies
- Advanced setups (multisig, air‑gapped)

### Risks / Trade‑offs
- Additional complexity
- External device trust assumptions
- UX friction

### Adamantine Guarantee Level
**Boundary‑enforced**  
Adamantine ensures only approved execution requests reach the signer.

---

## Important Clarifications

- Adamantine **never blocks execution** because keys exist elsewhere.
- Adamantine **never imports, exports, or validates private keys**.
- Adamantine **never automates recovery or migration**.
- Users may step outside Adamantine’s guarantee envelope by choice.

---

## Summary Table

| Custody Model | Recovery | Key Duplication | Security Level | Adamantine Role |
|--------------|---------|-----------------|----------------|-----------------|
| Device‑only | ❌ | ❌ | Highest | Full execution guarantee |
| Paper backup | ✅ | ⚠️ | Medium | Execution‑only |
| Shared keys | ✅ | ⚠️ | Medium | Per‑device enforcement |
| External custody | Depends | Depends | High | Boundary enforcement |

---

## Final Note

Adamantine Wallet OS is designed to be **honest about guarantees**.

> **Inside the envelope, guarantees are strong.  
> Outside the envelope, users retain freedom — and responsibility.**

This is intentional.
