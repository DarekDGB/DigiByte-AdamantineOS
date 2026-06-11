# AdamantineOS — Device Loss & Recovery Model

MIT License  
Author attribution: **DarekDGB**

---

## Purpose

This document defines the **device loss and recovery model** for wallets that use AdamantineOS.

AdamantineOS enforces execution safety. It does **not** provide recovery services, backups, or key exports.

---

## Non-Negotiable Recovery Statement

**Device-only keys mean device loss can mean permanent loss of funds.**

This is an intentional security posture, not an accident.

AdamantineOS will not introduce recovery shortcuts that weaken custody invariants.

---

## What Happens If the Device Is Lost

If the phone is lost, stolen, wiped, or permanently damaged:

- the private key remains **non-exportable**
- the private key is **not recoverable** via cloud
- the private key is **not recoverable** via Adamantine
- any funds controlled by that key are effectively inaccessible

---

## What Recovery Is NOT

AdamantineOS will never provide:

- iCloud / Google Drive key backups
- seed phrase export from Adamantine
- automatic cross-device migration
- recovery via maintainer or support channels
- hidden “restore” mechanisms

---

## Allowed User Strategy (Explicit Responsibility)

Users may choose external, manual strategies outside Adamantine, such as:

- keeping funds split across multiple wallets/keys
- maintaining independent cold storage elsewhere (separate product)
- using multiple devices with different keys (distinct wallet_ids)

These strategies are outside Adamantine’s scope and do not change its invariants.

---

## Why This Model Exists

This model eliminates entire classes of real-world wallet failures:

- cloud account takeover
- SIM swap + iCloud/Google compromise
- malicious “support” recovery scams
- developer mistakes in backup encryption
- silent sync metadata leakage
- “restore path” becoming a backdoor

The safest recovery is **no recovery path inside the security boundary**.

---

## Operational Guidance (Wallet App UX)

Wallet runtimes integrating Adamantine should:

- warn users clearly that device loss can mean permanent loss
- require explicit user acknowledgement during onboarding
- avoid language suggesting “account-style recovery”

This is a security product, not a convenience product.

---

## Invariant Alignment

Key custody is external, device-only, non-exportable.

Adamantine:
- gates execution
- fails closed
- remains deterministic and auditable

Nothing about device loss changes the execution boundary rules.

---

© 2025 DarekDGB — MIT Licensed
