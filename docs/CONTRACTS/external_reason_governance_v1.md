# External Reason Governance v1 (Contract)

**License:** MIT — **DarekDGB**

This contract freezes how **external reason IDs** (strings coming from external systems) are governed and admitted into Adamantine.

It prevents silent semantic drift where an upstream Shield/Oracle source introduces a new free-form reason string that is accidentally accepted.

---

## 1. Scope

This contract applies to:

- **Shield v3** (`shield_signal_v3.reason_id`)
- **Adaptive Core Oracle v3** (`signals[].reason_ids[]` inside `adaptive_core_oracle_v3`)

It does **not** change internal reason identifiers (`ReasonId` enum). Internal reasons are already closed and versioned.

---

## 2. Definitions

### 2.1 External reason ID

A string provided by an upstream system (Shield / Oracle) indicating why it produced a signal.

Examples:
- `OK`
- `AC_OK`
- `SUSPECT_SIM_SWAP`

### 2.2 Internal reason ID

A stable Adamantine reason identifier (`ReasonId.*`).

External reason IDs are **mapped** into internal reason IDs through a deterministic mapping table.

---

## 3. Governance rules (fail-closed)

### Rule G1 — Deny-by-default registry

Adamantine maintains a registry of allowed external reason IDs.

- If a source/layer is not present in the registry, **all reasons from it are rejected**.
- If an external reason ID is not allowlisted for that source/layer, **it is rejected**.

### Rule G2 — Mapping is required

An external reason ID must also be present in the mapping table.

- If there is no mapping entry, the reason is rejected.

### Rule G3 — Layer-specific allowlists for Shield

Shield v3 allowlists are **per layer**:

- `sentinel_ai`
- `adn`
- `dqsn`
- `qwg`
- `guardian_wallet`

Each layer has its own allowlist.

### Rule G4 — Oracle allowlist

Oracle v3 uses an allowlist for its `signals[].reason_ids[]` values.

(Oracle signal `source` strings are not used for governance in v1; governance is applied to the external reason ID values themselves.)

---

## 4. Registry interface (data contract)

### 4.1 Data model

A registry is represented as:

- `oracle_allowed_external_reason_ids: tuple[str, ...]`
- `shield_layer_allowlists: tuple[{layer: str, allowed_external_reason_ids: tuple[str, ...]}, ...]`

Additional constraints:

- All tuples must be deterministic, stable order.
- No duplicates.
- Shield layers must be from the canonical set:
  - `sentinel_ai`, `adn`, `dqsn`, `qwg`, `guardian_wallet`

### 4.2 Validation

The registry must be validated before use.

If invalid:
- The system fails closed.

---

## 5. Change control

### 5.1 Adding a new external reason ID

To add a new external reason ID, you must:

1. Update the registry allowlist for the relevant source/layer.
2. Add or update the explicit mapping entry (external → internal `ReasonId`).
3. Add a test proving:
   - the new reason is accepted when allowlisted + mapped
   - the new reason is rejected when not allowlisted

### 5.2 Breaking changes

Any change that loosens governance rules is a **breaking contract change** and must:

- bump the contract version (v2)
- ship with negative-first tests

---

## 6. Security properties

This contract guarantees:

- **No free-form reason strings** can silently enter the system.
- New external reason IDs require an explicit, reviewed, test-locked change.
- Shield layer semantics cannot be blurred by a global allowlist.

---

## 7. Non-goals

- Defining a full canonical taxonomy of all possible reasons.
- Governing internal `ReasonId` values.
- Enforcing per-oracle-source reason constraints beyond the allowlist (reserved for v2).
