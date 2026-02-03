# Execution Response Envelope v1

**License:** MIT License — DarekDGB

---

## 1. Purpose

This contract defines the **Execution Response Envelope v1** returned by Adamantine to mobile clients (iOS / Android) after evaluating an execution request.

Adamantine is an **execution boundary**. It produces a deterministic allow/deny outcome and supporting decision metadata.

This document is normative.

---

## 2. Non-Goals

This response envelope does **not**:
- return private keys, seeds, or mnemonics
- imply that signing or broadcasting occurred
- leak sensitive internal state
- permit ambiguous interpretation of outcomes

Adamantine returns deterministic outcomes only.

---

## 3. Envelope Overview

The response envelope is a single JSON object with a fixed schema.

- **Strict validation:** unknown fields are rejected (fail-closed)
- **Version discipline:** the response declares the contract version
- **Stable reason identifiers:** all denials and errors include a versioned reason id
- **Deterministic semantics:** the same input yields the same outcome (given identical local nonce state and timebox validity)

---

## 4. Schema (v1)

Top-level object fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `v` | string | ✅ | Contract version. Must equal `"execution_response_v1"`. |
| `request_id` | string | ✅ | Echo of the request `request_id`. |
| `status` | string | ✅ | One of: `"allow"`, `"deny"`, `"error"`. |
| `reason_id` | string | ✅ | Stable reason identifier (see Section 6). |
| `decision` | object | ✅ | Deterministic decision details. |
| `artifacts` | object | ❌ | Optional non-sensitive decision artifacts. |
| `metrics` | object | ❌ | Optional non-sensitive metrics (never authoritative). |

All fields not listed above are rejected.

---

## 5. Field Requirements

### 5.1 `v`
- Must be exactly: `"execution_response_v1"`

### 5.2 `request_id`
- Must exactly match the request `request_id`
- Non-empty ASCII string
- Must not contain secrets

### 5.3 `status`
Allowed values:
- `"allow"` — request permitted to proceed
- `"deny"` — request rejected under policy/invariants
- `"error"` — evaluation failed due to internal error or invalid conditions

Rules:
- `"deny"` is used for policy/invariant violations and validation failures.
- `"error"` is used for internal failures where a deterministic decision cannot be produced safely.

### 5.4 `reason_id`
- Required for all statuses
- Must be a stable, versioned identifier
- Must not be free-form text
- Must map to an internal enum (no magic strings)

See Section 6 for required reasons.

### 5.5 `decision`
Required object. Minimum required fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `intent` | string | ✅ | Echo of request `intent`. |
| `action` | string | ✅ | Echo of request `context.action`. |
| `allowed` | boolean | ✅ | True if status is `"allow"`. |
| `tva` | object | ✅ | TVA gate decision summary. |
| `eqc` | object | ✅ | EQC decision summary. |
| `wsqk` | object | ✅ | WSQK authority summary. |
| `nonce` | object | ✅ | Nonce consumption summary. |
| `timebox` | object | ✅ | Timebox validation summary. |
| `context_hash` | string | ✅ | Deterministic context hash (canonical form). |

Rules:
- `allowed` must be consistent with `status`:
  - status `"allow"` → `allowed == true`
  - status `"deny"` or `"error"` → `allowed == false`
- All nested objects must be strictly validated (unknown fields rejected).

### 5.6 `artifacts` (optional)
Optional object containing **non-sensitive** artifacts, such as:

| Field | Type | Description |
|---|---|---|
| `decision_token` | string | Opaque token derived from decision (non-secret). |
| `constraints` | object | Additional constraints the caller must enforce. |

Rules:
- Artifacts are never private key material
- Artifacts must not enable authority escalation
- Artifacts must be safe to store locally

### 5.7 `metrics` (optional)
Optional non-sensitive metrics for observability.

Rules:
- Metrics are never authoritative
- Metrics must not influence allow/deny decisions
- Metrics must not include secrets

---

## 6. Reason Identifiers (Required Set)

Reason identifiers are stable and versioned.
They must be implemented as a single internal enum.

Minimum required reason ids for v1:

### Success
- `OK_ALLOW` — request allowed

### Validation / Interface
- `DENY_SCHEMA_INVALID` — schema/typing violation
- `DENY_UNKNOWN_FIELD` — unknown field detected
- `DENY_VERSION_MISMATCH` — unsupported envelope version
- `DENY_INTENT_UNSUPPORTED` — intent not supported
- `DENY_PAYLOAD_INVALID` — payload does not match intent schema

### Timebox
- `DENY_TIMEBOX_INVALID` — timebox fields invalid
- `DENY_TIMEBOX_EXPIRED` — request expired
- `DENY_TIMEBOX_NOT_YET_VALID` — request issued in the future
- `DENY_TIMEBOX_SKEW_EXCEEDED` — clock skew beyond allowed maximum

### Nonce / Replay
- `DENY_NONCE_INVALID` — nonce fields invalid
- `DENY_NONCE_REPLAY` — nonce already used
- `DENY_NONCE_STORE_ERROR` — nonce store failure (fail-closed)

### Authority / Policy / Gates
- `DENY_AUTHORITY_INVALID` — authority object invalid
- `DENY_AUTHORITY_INSUFFICIENT` — insufficient authority for action
- `DENY_POLICY` — policy pack denied
- `DENY_EQC` — EQC denied
- `DENY_WSQK` — WSQK denied
- `DENY_TVA` — TVA denied

### Adapter / External Inputs
- `DENY_ADAPTER_INVALID` — adapter input/output invalid
- `DENY_ADAPTER_UNAVAILABLE` — adapter unavailable (fail-closed)

### Internal Errors
- `ERR_INTERNAL` — internal error (fail-safe denial)
- `ERR_UNHANDLED` — unexpected exception (fail-safe denial)

Notes:
- Implementations may add additional reason ids without breaking v1 only if:
  - they are part of the same enum set
  - they are documented in a versioned reason map
  - they are test-locked
- Reason ids must remain stable over time.

---

## 7. Canonicalization and Determinism

`context_hash` MUST be computed from the canonicalized request context.

The response MUST remain deterministic given:
- identical canonical request
- identical nonce store state
- identical timebox validity outcome

No non-deterministic fields (timestamps, random ids, varying ordering) may appear.

---

## 8. Key Custody Neutrality (Normative)

The response must never deny solely due to multi-device key presence.

If key custody metadata is present in the request payload, it may be echoed only as non-authoritative observability, but must not drive denial by itself.

---

## 9. Minimal Examples

### 9.1 Allow

```json
{
  "v": "execution_response_v1",
  "request_id": "req_2026_02_03_0001",
  "status": "allow",
  "reason_id": "OK_ALLOW",
  "decision": {
    "intent": "authorize",
    "action": "send",
    "allowed": true,
    "tva": { "allowed": true },
    "eqc": { "allowed": true },
    "wsqk": { "allowed": true },
    "nonce": { "consumed": true },
    "timebox": { "valid": true },
    "context_hash": "hash_redacted"
  }
}
```

### 9.2 Deny (Replay)

```json
{
  "v": "execution_response_v1",
  "request_id": "req_2026_02_03_0001",
  "status": "deny",
  "reason_id": "DENY_NONCE_REPLAY",
  "decision": {
    "intent": "authorize",
    "action": "send",
    "allowed": false,
    "tva": { "allowed": false },
    "eqc": { "allowed": true },
    "wsqk": { "allowed": true },
    "nonce": { "consumed": false },
    "timebox": { "valid": true },
    "context_hash": "hash_redacted"
  }
}
```

---

## 10. Compatibility

- This contract is valid only when `v == "execution_response_v1"`.
- Any changes to schema, validation, reason ids, or determinism rules require a new version.

---

## 11. Summary

Execution Response Envelope v1 provides a strict, deterministic, fail-closed response format with stable reason identifiers.

Anything not explicitly allowed by this contract is rejected.
