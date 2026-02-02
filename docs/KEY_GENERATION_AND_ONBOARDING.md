# Adamantine Wallet OS — Key Generation & Onboarding

MIT License  
Author attribution: **DarekDGB**

---

## Purpose

This document defines **where, when, and how cryptographic keys are generated**
for wallets that use Adamantine Wallet OS.

Adamantine itself **never generates, imports, stores, exports, or backs up keys**.
This is intentional and non-negotiable.

---

## Key Generation Authority

**Keys are generated exclusively by the platform-native Key Custody Module.**

Adamantine Wallet OS is **not involved** in key generation.

This occurs during **wallet onboarding**, before Adamantine is ever invoked.

---

## iOS Key Generation

On iOS, keys are generated using:

- Secure Enclave (when available)
- iOS Keychain services

Properties:
- Private keys are **non-exportable**
- Keys are **device-bound**
- Signing requires **Face ID / Touch ID / device passcode**
- No cloud sync
- No seed phrase exposure by Adamantine

Adamantine only receives a **reference/handle** to request signing later.

---

## Android Key Generation

On Android, keys are generated using:

- Android Keystore System
- Hardware-backed TEE / StrongBox when available

Properties:
- Private keys are **non-exportable**
- Keys are **hardware-backed when supported**
- User authentication required for signing
- No cloud sync
- No raw key access by Adamantine

---

## Onboarding Timeline

1. Wallet application initializes custody module
2. Custody module generates keypair
3. Custody module stores key securely
4. Wallet registers a logical wallet_id
5. Adamantine Wallet OS becomes active **after onboarding completes**

Adamantine does **not** participate in steps 1–3.

---

## Explicit Non-Goals

Adamantine Wallet OS will never:
- Generate keys
- Import seed phrases
- Export private keys
- Back up secrets
- Sync keys across devices
- Perform signing internally

---

## Security Rationale

This separation enforces:

- Minimal Trusted Computing Base
- Hardware-enforced isolation
- Clear responsibility boundaries
- Reduced attack surface
- Deterministic execution control

---

## Invariant Alignment

This document enforces the core invariant:

> **Decision, authority, and execution are never combined.**

Key generation and custody are execution capability.  
Adamantine only decides **if** execution may proceed.

---

© 2025 DarekDGB — MIT Licensed
