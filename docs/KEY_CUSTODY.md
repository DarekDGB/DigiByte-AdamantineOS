# Adamantine Wallet OS — Key Custody Model (Step 18A)

Author attribution: **DarekDGB**

This document freezes the **Key Custody Model** for Adamantine Wallet OS.

Adamantine is an **execution boundary**. It enforces deterministic, fail‑closed rules that decide whether an action is allowed to proceed. Adamantine is **not** a wallet runtime and **never** becomes a key manager.

---

## Non‑negotiable statement

**Adamantine Wallet OS will never manage private keys directly.**

Meaning:
- Adamantine does **not** generate seed phrases.
- Adamantine does **not** store seed phrases.
- Adamantine does **not** export seed phrases.
- Adamantine does **not** sign transactions.
- Adamantine does **not** broadcast transactions.

Adamantine only controls **whether** an external request may execute.

---

## Where keys live

Keys belong to a **separate key custody module** (platform-native, minimal TCB) that is outside Adamantine’s core.

### iOS key custody (expected model)

On iOS, keys should be stored in the **Keychain**, and when possible protected by the **Secure Enclave**.

Practical posture:
- **Device-only keys by default**: the private key material should remain on the device.
- **Biometric / passcode gating**: require Face ID / Touch ID / device passcode for signing operations.
- **Non‑exportable keys where possible**: prefer keys that cannot be exported as raw material (Secure Enclave-backed).

**Cloud syncing is optional and must be explicit.**

Important distinction (this explains your “password leak” messages):
- iOS can warn you about leaked passwords because those credentials were **seen in external breaches** (websites/app databases), not because iOS “leaked them.”
- If you enable iCloud Keychain, some secrets can sync across devices, but Apple states iCloud Keychain is end‑to‑end encrypted. Still, for a high-security crypto wallet posture, Adamantine should default to **device-only custody**, and treat any syncing as a **conscious opt‑in** feature with clear warnings.

### Android key custody (expected model)

On Android, keys should be stored via the **Android Keystore System**, ideally backed by hardware security (StrongBox / TEE where available).

Practical posture:
- **Hardware-backed keys where possible**.
- **User authentication required** (biometric / device credential) to authorize signing.
- **Non-exportable keys** when supported.

---

## What Adamantine receives

Adamantine should never receive raw private keys. It should only receive:
- **A signing request intent** (what must be signed),
- **Context** (wallet_id, action, context_hash, fields),
- **Authority** (WSQK) and the gate decision (EQC verdict),
- **A handle/reference** to the platform custody module (not the key itself).

In other words, Adamantine can decide:
> “Allowed to sign this exact thing under this exact context, right now.”

But the signing is performed by the custody module.

---

## Why this separation exists

This is a deliberate **Minimal TCB** move:
- Key custody is the highest-risk component.
- Adamantine must stay small, deterministic, and auditable.
- Splitting custody from enforcement prevents “feature creep” from turning Adamantine into a monolithic wallet.

This also enforces the core law:
> **Decision, authority, and execution are never combined.**

Key custody is execution-capability; Adamantine decides if that capability may be used.

---

## Failure rules

If key custody cannot comply (device locked, biometrics fail, keystore unavailable, user cancels):
- The operation **fails closed**.
- Adamantine records only **reason IDs** (no sensitive payloads).
- No partial signing, no fallback signing.

---

## Threat model notes

This custody model is designed to reduce damage from:
- malware trying to trigger unauthorized signing
- UI deception / social engineering
- compromised app state
- repeated/replayed requests
- “silent” background signing

Adamantine blocks execution before custody is invoked unless all required proofs and gates are satisfied.

---

## Explicit non-goals

Adamantine Wallet OS will never:
- manage private keys directly
- perform signing internally
- perform network broadcasting
- act as an intelligence or learning engine
- make autonomous decisions on behalf of the user

---

## Compatibility with future Shield layers

Shield layers (Sentinel / DQSN / ADN / Adaptive Core / QWG / Guardian Wallet) can produce evidence and risk signals.
Adamantine consumes that evidence via strict adapters and still enforces:
- deterministic context hashing
- deny-by-default execution
- time-bound authority (WSQK)
- replay protection (nonce store)

Key custody remains separate even as the evidence stack grows.
