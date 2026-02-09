# Shield Bundle v3 (Contract Freeze)

**License:** MIT — **DarekDGB**

This document freezes the **Shield v3 evidence bundle** format.

A bundle is a deterministic container of **multiple shield_signal_v3** records.
It is **evidence only**.

- **No authority**
- **No execution**
- **No trust by default**
- **Fail-closed adapters**

---

## 1. Version

- **Interface name:** `shield_bundle_v3`
- **Signal contract:** `shield_signal_v3`
- **Stability level:** **FROZEN**
- **Breaking change rule:** any semantic change requires `shield_bundle_v4`

---

## 2. Purpose

`shield_bundle_v3` allows Adamantine/EQC to reason over multiple Shield layers in one deterministic input, while keeping each layer’s signal isolated and auditable.

Bundles are validated and normalized at the adapter boundary before any policy reasoning.

---

## 3. Data model

Field | Type | Required | Notes
---|---|---:|---
`v` | `str` | ✅ | Must equal `"shield_bundle_v3"`
`bundle_id` | `str` | ✅ | Caller-generated unique id for this bundle
`context_hash` | `str` | ✅ | 64-char hex. Must match all contained signals
`issued_at` | `int` | ✅ | Unix seconds
`expires_at` | `int` | ✅ | Unix seconds, must be `>= issued_at`
`signals` | `array` | ✅ | Non-empty array of `shield_signal_v3`
`required_layers` | `array` | ✅ | Array of layer strings. Must be a subset of allowed layers.
`meta` | `object` | ❌ | Deterministic metadata (no PII). Optional.

---

## 4. Bundle invariants (hard)

### 4.1 Version pinning
- `v` must equal `"shield_bundle_v3"`
- each signal must have `v == "shield_signal_v3"`

### 4.2 Context binding
- bundle `context_hash` must equal each signal `context_hash`

### 4.3 Time window
- `expires_at >= issued_at`
- Each signal must satisfy `signal.expires_at >= signal.issued_at`
- Signals may have narrower windows than the bundle, but must not extend beyond bundle window:
  - `signal.issued_at >= bundle.issued_at`
  - `signal.expires_at <= bundle.expires_at`

### 4.4 Required layers completeness
- `required_layers` must be non-empty
- `signals` must include **at least one** signal for each layer in `required_layers`
- Unknown layers are rejected (fail-closed)

### 4.5 Layer uniqueness rule (v3)
To ensure determinism and prevent ambiguity:

- at most **one** signal per layer in a bundle

If a producer needs to include multiple observations for the same layer, it must aggregate deterministically into a single signal’s `facts`.

### 4.6 Unknown fields
- Bundles and signals are deny-by-default.
- Unknown top-level fields cause rejection.

---

## 5. Deterministic ordering (hard)

The `signals` array MUST be sorted deterministically by:

1. `layer` (ascending)
2. `signal_id` (ascending)

Adapters must reject bundles that are not sorted (to prevent hidden ordering attacks).

---

## 6. Reason mapping discipline

Adapters MUST:

- reject unknown `signal.reason_id` unless explicitly mapped
- map external shield reasons into Adamantine internal `ReasonId` deterministically
- never allow shield evidence to force `allow`

Shield can only:
- strengthen deny
- increase confidence in deny
- provide additional evidence for policy evaluation

---

## 7. Example (non-normative)

```json
{
  "v": "shield_bundle_v3",
  "bundle_id": "shield-000042",
  "context_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "issued_at": 1760000000,
  "expires_at": 1760000300,
  "required_layers": ["qwg", "guardian_wallet"],
  "signals": [
    {
      "v": "shield_signal_v3",
      "layer": "guardian_wallet",
      "signal_id": "gw-000001",
      "context_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "issued_at": 1760000000,
      "expires_at": 1760000300,
      "verdict": "deny",
      "reason_id": "GW_POLICY_BLOCK",
      "confidence": 88,
      "facts": {
        "policy": "no-large-send",
        "limit": 1000,
        "asset": "DGB"
      }
    },
    {
      "v": "shield_signal_v3",
      "layer": "qwg",
      "signal_id": "qwg-000001",
      "context_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "issued_at": 1760000000,
      "expires_at": 1760000300,
      "verdict": "deny",
      "reason_id": "QWG_DEVICE_COMPROMISED",
      "confidence": 92,
      "facts": {
        "device_integrity": "fail",
        "jailbreak_detected": true,
        "risk_score": 97
      }
    }
  ]
}
```

---

## 8. Change control

- Additive fields are **not allowed** in v3 (deny-by-default).
- New capabilities require `v4`.

---

## 9. Attribution

**Author:** DarekDGB  
**License:** MIT
