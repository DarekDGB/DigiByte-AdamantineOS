## Adamantine Wallet OS — Execution Boundary

**License:** MIT  
**© 2025 DarekDGB**

---

## Purpose

This document defines the **execution boundary** between:

- private key custody (platform secure hardware)
- transaction execution (Adamantine Wallet OS)

Adamantine **never touches private keys**.

It only decides *whether execution is permitted*.

---

## Separation of Responsibilities

### What Adamantine Does
- validates execution context (EQC)
- enforces authority (WSQK)
- blocks replay, expiry, mismatch (TVA)
- allows or denies execution

### What Adamantine Never Does
- generate keys
- store keys
- sign transactions
- broadcast transactions

---

## Execution Flow (iOS / Android)

1. Wallet UI constructs intent (SEND, SIGN, etc.)
2. EQC evaluates context + evidence
3. WSQK authority is issued (time + nonce bound)
4. TVA validates execution request
5. **ONLY THEN** platform keystore is asked to sign

If TVA denies → signing is never reached.

---

## iOS Example Boundary

- Keys live in **Secure Enclave**
- Accessed via Keychain + Secure Enclave APIs
- Signing requires:
  - device unlock
  - biometric / passcode
  - non-exportable key reference

Adamantine only sees:
- hash
- verdict
- authority
- nonce

Never the key.

---

## Android Example Boundary

- Keys live in **Android Keystore**
- Backed by TEE / StrongBox when available
- Non-exportable keys
- Biometric-gated signing

Same invariant:  
**No authority → no signing call**

---

## Security Invariants

- Execution boundary is one-way
- No backdoor path to signing
- No silent fallback
- User presence required where impact exists
- Deterministic failure on violation

---

## Why This Matters

Even if:
- UI is compromised
- app logic is modified
- malware is present

Keys remain safe  
and execution is denied.

---

## Status

Design locked. 
