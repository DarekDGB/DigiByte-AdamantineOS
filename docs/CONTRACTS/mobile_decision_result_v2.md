# Mobile Decision Result v2 (Contract)

**License:** MIT — **Author:** DarekDGB  
**Stability level:** **FROZEN** (breaking change requires `mobile_decision_result_v3`)  
**Scope:** Normative mobile interpretation contract for Adamantine decisions.

This contract defines **exactly** how mobile clients (iOS/Android) MUST interpret
Adamantine execution responses for UX, messaging, and override behavior.

It is a **pure contract**:
- no UI design requirements
- no branding requirements
- no network requirements
- deterministic interpretation only

---

## 1. Version

- **Interface name:** `mobile_decision_result_v2`
- **Input envelope:** `execution_response_v2`
- **Paired request:** `execution_request_v2`

Mobile MUST treat any other response version as **unsupported** (fail‑closed).

---

## 2. Inputs (Normative)

Mobile receives an object matching `execution_response_v2`:

Required (minimum):
- `v == "execution_response_v2"`
- `status`
- `reason_id`
- `context_hash`
- `decision` (including `protection_mode`, `gates`, `timebox`, `nonce`, `evidence`, `policy`)

If validation fails, mobile MUST treat the response as **invalid**.

---

## 3. Output Model (What Mobile Derives)

Mobile MUST derive the following **interpreted** fields from the response:

Field | Type | Required | Definition
---|---|---:|---
`ui_status` | `str` | ✅ | `"allowed"` \| `"blocked"` \| `"error"`
`ui_security_posture` | `str` | ✅ | `"legacy"` \| `"minimal"` \| `"full"`
`ui_message_key` | `str` | ✅ | Reason message key derived from `reason_id`
`ui_can_override` | `bool` | ✅ | Derived solely from `decision.policy.override_allowed` (**Option C**)
`ui_context_hash` | `str` | ✅ | Echo `context_hash`
`ui_reason_id` | `str` | ✅ | Echo `reason_id`

Mobile MUST NOT infer posture or override capability from any other fields.

---

## 4. Status Interpretation

### 4.1 `ui_status` mapping

`execution_response_v2.status` → `ui_status`

- `"allow"` → `"allowed"`
- `"deny"` → `"blocked"`
- `"error"` → `"error"`

### 4.2 Allowed invariant

If `status == "allow"`:
- `decision.allowed` MUST be `true`
- `reason_id` MUST equal `OK_ALLOW`

If these invariants are violated, mobile MUST treat as `"error"`.

---

## 5. Security Posture Interpretation (`protection_mode`)

### 5.1 Normative posture mapping

Mobile MUST use `decision.protection_mode` as the **only** posture signal:

- `"legacy"` → `ui_security_posture = "legacy"`
- `"minimal"` → `ui_security_posture = "minimal"`
- `"full"` → `ui_security_posture = "full"`

Any other value MUST be treated as `"error"`.

### 5.2 Required user-visible meaning (semantic, not visual)

Mobile MUST be able to communicate the following meanings:

Mode | Meaning (semantic)
---|---
`legacy` | Unprotected / legacy runtime posture (Adamantine not fully active or protected path not requested)
`minimal` | Protected (Q-ID active); Shield/Oracle not active or not required
`full` | Protected (Q-ID + Shield + Oracle active as configured)

Mobile MAY choose wording, but semantics MUST match.

---

## 6. Override Interpretation (Option C — Normative)

### 6.1 Source of truth

Mobile MUST set `ui_can_override` using:

```text
ui_can_override = decision.policy.override_allowed
```

**Only this field** controls override availability.  
`protection_mode` MUST NOT be used to grant or deny override.

### 6.2 Override safety requirements

If `ui_can_override == true`, mobile MUST:
- present an explicit user acknowledgement step (implementation-defined)
- log that an override was requested (local event log; no network required)
- re-submit the request with an explicit override intent field (future extension; if not present, mobile MUST NOT claim override occurred)

If override mechanics are not implemented, mobile MUST still reflect `ui_can_override` truthfully but MUST NOT pretend to execute an override.

---

## 7. Reason Mapping (Stable Keys)

Mobile MUST map `reason_id` to a user-facing message via the **Reason Registry**:

- `contracts/reason_registry_mobile_v1.json`

Rules:
- `reason_id` MUST exist in the registry; otherwise treat as `"error"`
- Mobile MUST NOT invent meanings for unknown reason_ids
- Message selection MUST be deterministic for a given `reason_id`

`ui_message_key` MUST equal the registry message key for that reason.

---

## 8. Gate Presentation Rules (Deterministic)

Mobile MAY present gate results, but if it does, it MUST:
- present `gates.tva.allowed`, `gates.eqc.allowed`, `gates.wsqk.allowed`
- use each gate’s `reason_id` for explanation (from the same registry family)
- NOT imply a gate passed if `allowed == false`

Gate interpretation MUST NOT change the allow/deny result.

---

## 9. Timebox + Nonce Presentation Rules (Deterministic)

If mobile displays timebox/nonce status, it MUST:
- use `decision.timebox.valid` and `decision.timebox.reason_id`
- use `decision.nonce.consumed` and `decision.nonce.reason_id`
- avoid displaying raw nonce value if policy requires redaction (future schema lock)

---

## 10. Failure Handling (Fail‑Closed)

Mobile MUST treat the result as `"error"` if any of these occur:
- schema validation failure
- version mismatch
- allow invariants violated
- unknown `protection_mode`
- `reason_id` missing from registry

In `"error"` state, mobile MUST NOT perform the protected action.

---

## 11. Change Control

Breaking change examples (require v3):
- new posture modes
- changing override source of truth
- altering meaning of a posture mode
- changing required field set

No silent changes.

---

## 12. Related Contracts

- `docs/CONTRACTS/mobile_execution_call_v2.md`
- `docs/CONTRACTS/execution_request_v2.md`
- `docs/CONTRACTS/execution_response_v2.md`
- `contracts/reason_registry_mobile_v1.json` (v1.5.0 deliverable)
