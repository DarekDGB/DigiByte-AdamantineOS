# Adamantine Wallet OS — Key Custody Model

Author attribution: **DarekDGB**

MIT License © 2025 DarekDGB

---

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

Keys belong to a **separate key custody module** (platform‑native, minimal TCB) that is outside Adamantine’s core.

### iOS key custody (strict device‑only model)

On iOS, keys must be stored in the **Keychain**, and when available protected by the **Secure Enclave**.

Security posture:
- **Device‑only keys**: private key material remains on the device.
- **Biometric / passcode gating**: Face ID, Touch ID, or device passcode required for signing.
- **Non‑exportable keys**: Secure Enclave‑backed keys where possible.
- **No cloud synchronization**: keys are never synced, backed up, or mirrored externally.

Adamantine assumes **local‑only custody**. Any form of key replication or syncing is explicitly out of scope.

### Android key custody (strict device‑only model)

On Android, keys must be stored using the **Android Keystore System**, backed by hardware security (TEE / StrongBox) where available.

Security posture:
- **Hardware‑backed keys only when possible**.
- **User authentication required** for signing.
- **Non‑exportable keys** enforced.
- **No cloud or cross‑device replication**.

---

## What Adamantine receives

Adamantine never receives raw private keys.

It receives only:
- A **signing request intent** (what must be signed),
- **Context** (wallet_id, action, context_hash, fields),
- **Authority** (WSQK) and decision (EQC verdict),
- A **reference/handle** to the platform custody module (never the key).

Adamantine can decide:
> “This exact operation may execute right now.”

The custody module performs signing independently.

---

## Why this separation exists

This separation enforces **Minimal Trusted Computing Base (TCB)**:

- Key custody is the highest‑risk component.
- Adamantine must remain small, deterministic, and auditable.
- Enforcement and execution must never collapse into one unit.

Core law enforced:
> **Decision, authority, and execution are never combined.**

---

## Failure rules

If key custody cannot comply (device locked, biometric failure, keystore unavailable, user cancellation):
- Execution **fails closed**.
- Only **Reason IDs** are recorded.
- No retries, no fallbacks, no partial signing.

---

## Threat model notes

This custody model mitigates:
- malware‑triggered signing attempts
- UI deception and social engineering
- compromised application state
- replay and timing attacks
- background or silent execution

Adamantine blocks execution **before** custody is invoked unless all proofs and gates pass.

---

## Explicit non‑goals

Adamantine Wallet OS will never:
- manage private keys directly
- perform signing internally
- broadcast transactions
- act as an intelligence engine
- make autonomous decisions

---

## Compatibility with Shield layers

Shield layers (Sentinel, DQSN, ADN, Adaptive Core, QWG, Guardian Wallet) may generate evidence.

Adamantine consumes evidence via strict adapters and enforces:
- deterministic context hashing
- deny‑by‑default execution
- time‑bound authority (WSQK)
- replay protection

Key custody remains isolated regardless of future integrations.
