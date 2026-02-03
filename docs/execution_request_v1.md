# Execution Request Envelope v1

**License:** MIT License — DarekDGB

---

## 1. Purpose

This contract defines the **Execution Request Envelope v1** used by mobile clients (iOS / Android) to request an execution decision from Adamantine.

Adamantine is an **execution boundary**. This envelope is the only supported external entry format for execution decisions.

This document is normative.

---

## 2. Non-Goals

This envelope does **not**:
- carry private keys, seeds, or mnemonics
- instruct Adamantine to sign or broadcast
- imply single-device key custody
- enable cloud sync

Key custody is external to Adamantine.

---

## 3. Envelope Overview

The request envelope is a single JSON object with a fixed schema.

- **Strict validation:** unknown fields are rejected (fail-closed)
- **Deterministic canonicalization:** all hashing operates on canonical form
- **Version discipline:** the request must declare the contract version

---

## 4. Schema (v1)

Top-level object fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `v` | string | ✅ | Contract version. Must equal `"execution_request_v1"`. |
| `request_id` | string | ✅ | Caller-generated unique identifier (non-secret). |
| `intent` | string | ✅ | Declared intent (e.g. `"authorize"`, `"sign_request"`, `"eqc_check"`). |
| `context` | object | ✅ | Context used for TVA/EQC decisions. |
| `authority` | object | ✅ | Declared authority scope (no key material). |
| `timebox` | object | ✅ | Issued-at and expiry timestamps. |
| `nonce` | object | ✅ | Single-use nonce for replay protection. |
| `payload` | object | ✅ | Intent-specific body. |
| `audit` | object | ❌ | Optional non-sensitive observability fields. |

All fields not listed above are rejected.

---

## 5. Field Requirements

### 5.1 `v`
- Must be exactly: `"execution_request_v1"`

### 5.2 `request_id`
- Required
- Non-empty ASCII string
- Must be unique per request from the caller perspective
- Must not contain secrets

### 5.3 `intent`
- Required
- Non-empty string
- Must match a supported intent name in the implementation
- Must bind the payload schema (no intent ambiguity)

### 5.4 `context`
Required object. Minimum required fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `wallet_id` | string | ✅ | Logical wallet identifier (non-secret). |
| `device_id` | string | ✅ | Logical device identifier (non-secret). |
| `app_id` | string | ✅ | App bundle/package identifier. |
| `session_id` | string | ✅ | Current session identifier (non-secret). |
| `action` | string | ✅ | High-level action name (e.g. `"send"`, `"export"`, `"link_device"`). |
| `fields` | object | ✅ | Action fields used for deterministic context hashing. |

Rules:
- `fields` must be a JSON object
- `fields` must be fully canonicalized before hashing
- `fields` must not contain private keys or seeds

### 5.5 `authority`
Required object. Minimum required fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `class` | string | ✅ | Authority class label (e.g. `"user"`, `"device"`, `"session"`, `"policy"`). |
| `scope` | object | ✅ | Declared scope constraints (typed object). |
| `proofs` | object | ❌ | Optional external proofs (e.g. Q-ID proof blob reference). |

Rules:
- Authority is explicit; it is never inferred.
- Authority may not be escalated by adapters.
- Authority objects must be strictly validated (unknown fields rejected).

### 5.6 `timebox`
Required object:

| Field | Type | Required | Description |
|---|---|---:|---|
| `issued_at` | string | ✅ | ISO-8601 timestamp (UTC recommended). |
| `expires_at` | string | ✅ | ISO-8601 timestamp. Must be > `issued_at`. |
| `max_skew_seconds` | integer | ❌ | Optional allowed clock skew. If absent, skew is 0. |

Rules:
- Requests outside the timebox are rejected.
- No implicit grace period exists.
- If `max_skew_seconds` is used, it must be bounded by policy (implementation-defined).

### 5.7 `nonce`
Required object:

| Field | Type | Required | Description |
|---|---|---:|---|
| `value` | string | ✅ | Nonce value (opaque to caller, treated as string). |
| `store` | string | ✅ | Nonce store namespace (e.g. `"tva"`). |
| `mode` | string | ✅ | Must equal `"single_use"`. |

Rules:
- Nonces are single-use.
- Replays must be rejected deterministically.
- Nonce state is local; no cloud dependency is assumed.

### 5.8 `payload`
Required object. Shape is **intent-specific**.

Rules:
- Must be strictly validated against the schema for `intent`
- Must not include private key material
- Must not be interpreted under any intent other than declared `intent`

### 5.9 `audit` (optional)
Optional object for non-sensitive traceability.

Recommended fields:

| Field | Type | Description |
|---|---|---|
| `client_version` | string | App version string. |
| `platform` | string | `"ios"` or `"android"`. |
| `locale` | string | Locale identifier. |
| `notes` | string | Non-sensitive, non-secret notes. |

Rules:
- `audit` is never authoritative
- `audit` fields must not influence allow/deny decisions

---

## 6. Canonicalization Rules (Normative)

Canonicalization is required for deterministic hashing and evaluation.

The canonical form MUST:
- sort object keys lexicographically (byte-wise)
- preserve exact types (no coercion)
- encode strings exactly as provided (no trimming)
- represent numbers in a deterministic form (implementation-defined; recommend avoiding floats)
- remove no fields (unless explicitly defined by the contract)

Hashing (e.g. deterministic context hash) MUST use canonical form only.

---

## 7. Validation Rules (Fail-Closed)

A request MUST be rejected if any of the following occur:
- unknown field exists at any level
- required field is missing
- type mismatch occurs
- timestamps are invalid or outside declared timebox
- nonce mode is not `"single_use"`
- payload does not match the schema for the declared intent

---

## 8. Key Custody Neutrality (Normative)

Adamantine must not deny execution solely because keys may exist on multiple devices.

This envelope may optionally include key-custody *metadata* inside `payload` (intent-specific),
but Adamantine must treat custody presence as **non-authoritative** and **non-denying by itself**.

Only explicit policy, context, authority, timebox, and nonce may deny.

---

## 9. Minimal Example

```json
{
  "v": "execution_request_v1",
  "request_id": "req_2026_02_03_0001",
  "intent": "authorize",
  "context": {
    "wallet_id": "wlt_abc123",
    "device_id": "dev_xyz789",
    "app_id": "com.example.wallet",
    "session_id": "sess_001",
    "action": "send",
    "fields": {
      "asset": "DGB",
      "to": "DGB_ADDRESS_REDACTED",
      "amount": "12.34"
    }
  },
  "authority": {
    "class": "user",
    "scope": {
      "policy_pack": "default"
    }
  },
  "timebox": {
    "issued_at": "2026-02-03T20:00:00Z",
    "expires_at": "2026-02-03T20:01:00Z"
  },
  "nonce": {
    "value": "nonce_8c6f1a2b",
    "store": "tva",
    "mode": "single_use"
  },
  "payload": {
    "ui_confirmed": true
  },
  "audit": {
    "platform": "ios",
    "client_version": "0.1.0"
  }
}
```

---

## 10. Compatibility

- This contract is valid only when `v == "execution_request_v1"`.
- Any changes to schema, validation, or canonicalization require a new version.

---

## 11. Summary

Execution Request Envelope v1 provides a strict, deterministic, fail-closed interface for mobile callers to request execution decisions from Adamantine.

Anything not explicitly allowed by this contract is rejected.
