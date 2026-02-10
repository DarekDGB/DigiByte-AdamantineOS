# Execution Request Envelope v2 (Evidence Wiring)

**License:** MIT License — DarekDGB

---

## 1. Purpose

This contract defines **Execution Request Envelope v2**, an additive evolution of v1 that
adds **required evidence wiring** for:

- **Q-ID session** (identity / session proof)
- **Adaptive Core Oracle v3** (oracle verdict)
- **Shield bundle v3** (5-layer Shield signals)

**Important:** v2 requests still return **Execution Response v1** (`docs/execution_response_v1.md`).
The response contract remains frozen and mobile-compatible.

This document is normative.

---

## 2. Non-Goals

This envelope does **not**:
- carry private keys, seeds, or mnemonics
- instruct Adamantine to sign or broadcast
- change key-custody policy
- change response schema (response remains v1)

---

## 3. Envelope Overview

The v2 request envelope is a single JSON object with a fixed schema.

- **Strict validation:** unknown fields are rejected (fail-closed)
- **Version discipline:** the request must declare the contract version
- **Evidence required:** Q-ID + Oracle + Shield bundle are mandatory

---

## 4. Schema (v2)

Top-level object fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `v` | string | ✅ | Contract version. Must equal `"execution_request_v2"`. |
| `request_id` | string | ✅ | Caller-generated unique identifier (non-secret). |
| `intent` | string | ✅ | Declared intent (e.g. `"authorize"`, `"sign_request"`, `"eqc_check"`). |
| `context` | object | ✅ | Context used for TVA/EQC decisions. |
| `authority` | object | ✅ | Declared authority scope (no key material). |
| `timebox` | object | ✅ | Issued-at and expiry timestamps. |
| `nonce` | object | ✅ | Single-use nonce for replay protection. |
| `payload` | object | ✅ | v2 payload (includes required evidence + intent body). |
| `audit` | object | ❌ | Optional non-sensitive observability fields. |

All fields not listed above are rejected.

---

## 5. Field Requirements

### 5.1 `v`
- Must be exactly: `"execution_request_v2"`

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
Same shape as v1 (`docs/execution_request_v1.md`), including:
- `wallet_id`, `device_id`, `app_id`, `session_id`, `action`, `fields`

Rules:
- `fields` must be a JSON object
- `fields` must not contain private keys or seeds

### 5.5 `authority`
Same shape as v1, including:
- `class` (string)
- `scope` (object)
- optional `proofs` (object)

### 5.6 `timebox`
Same shape as v1, including:
- `issued_at` (ISO-8601 with timezone)
- `expires_at` (ISO-8601 with timezone, must be > issued_at)
- optional `max_skew_seconds` (non-negative int)

### 5.7 `nonce`
Same shape as v1, including:
- `value` (string)
- `store` (string)
- `mode` must equal `"single_use"`

---

## 6. `payload` (v2)

The v2 `payload` is a strict object with exactly:

| Field | Type | Required | Description |
|---|---|---:|---|
| `evidence` | object | ✅ | Required evidence bundle (Q-ID + Oracle + Shield). |
| `body` | object | ✅ | Intent-specific payload body. |

Unknown fields inside `payload` are rejected.

### 6.1 `payload.evidence`

`evidence` is a strict object with exactly:

| Field | Type | Required | Description |
|---|---|---:|---|
| `qid` | object | ✅ | Q-ID session payload (see `src/adamantine/v1/contracts/qid.py`). |
| `oracle` | object | ✅ | Adaptive Core Oracle v3 payload (see `src/adamantine/v1/contracts/adaptive_core_oracle_v3.py`). |
| `shield` | object | ✅ | Shield bundle v3 payload (see `docs/CONTRACTS/shield_bundle_v3.md`). |

Rules:
- All three evidence fields are required.
- Evidence objects must be non-empty JSON objects.
- Evidence is evaluated under **EQC v2** in orchestrator v2 (additive path), not in the envelope parser.

### 6.2 `payload.body`

`body` is a strict JSON object whose schema is **intent-specific**.

Rules:
- `body` must be strictly validated against the schema for the declared `intent`
- `body` must not include private key material
- `body` must not be interpreted under any intent other than declared `intent`

---

## 7. Validation Rules (Fail-Closed)

A request MUST be rejected if any of the following occur:
- unknown field exists at any level
- required field is missing
- type mismatch occurs
- timestamps are invalid or outside declared timebox
- nonce mode is not `"single_use"`
- `payload` is missing `evidence` or `body`
- `evidence` is missing `qid` or `oracle` or `shield`

---

## 8. Minimal Example

```json
{
  "v": "execution_request_v2",
  "request_id": "req_2026_02_10_0001",
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
    "issued_at": "2026-02-10T19:00:00Z",
    "expires_at": "2026-02-10T19:01:00Z"
  },
  "nonce": {
    "value": "n1",
    "store": "tva",
    "mode": "single_use"
  },
  "payload": {
    "evidence": {
      "qid": { "v": "qid_session_v1", "session": { "redacted": true } },
      "oracle": { "v": "adaptive_core_oracle_v3", "oracle": { "redacted": true } },
      "shield": { "v": "shield_bundle_v3", "bundle": { "redacted": true } }
    },
    "body": {
      "ui_confirmed": true
    }
  },
  "audit": {
    "platform": "ios",
    "client_version": "1.0.0"
  }
}
```

