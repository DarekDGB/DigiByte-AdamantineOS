# Mobile Decision Result v1 (Contract Freeze)

**License:** MIT — **DarekDGB**

This document freezes the **Adamantine → Mobile** decision output contract.

This is a **presentation contract**, not an execution contract.

Mobile apps:
- consume decisions
- explain outcomes to users
- MUST NOT execute wallet actions based on this object alone

---

## 1. Version

- **Interface name:** `mobile_decision_result_v1`
- **Stability level:** **FROZEN**
- **Breaking change rule:** requires `mobile_decision_result_v2`

---

## 2. Purpose

Provide a **safe, minimal, deterministic** object for mobile apps that:

- conveys allow / deny
- exposes a user-explainable reason code
- avoids internal leakage (no evidence structure, no thresholds, no raw ReasonId list)

---

## 3. Data model

Field | Type | Required | Notes
---|---|---:|---
`v` | `str` | ✅ | Must equal `"mobile_decision_result_v1"`
`request_id` | `str` | ✅ | Echoed from request (caller-provided)
`verdict` | `str` | ✅ | `"allow"` or `"deny"`
`reason_code` | `str` | ✅ | UX-safe reason identifier (see §4)
`context_hash` | `str` | ✅ | 64-char hex
`explainable` | `bool` | ✅ | Whether the client can show a user explanation
`confidence` | `str` | ✅ | `"high"` / `"medium"` / `"low"`

---

## 4. Reason code rules (UX-safe)

- `reason_code` MUST be stable and documented.
- `reason_code` MUST NOT expose:
  - internal `ReasonId` names
  - evidence structure (shield/oracle details)
  - security thresholds / scoring internals
  - stack traces or internal errors
- Mapping is performed inside Adamantine via a single mapping table (`reason_mapping_v1`).

---

## 5. Determinism

Given the same decision input, the mobile decision result MUST be byte-identical after canonical JSON serialization.

---

## 6. Example (non-normative)

```json
{
  "v": "mobile_decision_result_v1",
  "request_id": "req-123",
  "verdict": "deny",
  "reason_code": "SECURITY_POLICY_BLOCK",
  "context_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "explainable": true,
  "confidence": "high"
}
```

---

## 7. Change control

- Additive changes only if they do not change the meaning of existing fields.
- Any semantic change requires `mobile_decision_result_v2` + regression locks.

---

## 8. Attribution

**Author:** DarekDGB  
**License:** MIT
