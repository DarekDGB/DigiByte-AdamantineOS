# OS Proof Pack — v1.3.0

**Path:** docs/OS_PROOF_PACK_v1_3_0.md\
**Release:** v1.3.0 — Shield Interfaces Frozen + Posture Locked

---
Author: DarekDGB\
License: MIT
------------------------------------------------------------------------

## Purpose

v1.3.0 extends the OS Proof Pack with a strict, deterministic freeze of the **Shield v3 evidence interface**
and an auditable output field: **protection_mode**.

This release is designed to last for years without security regressions:
- strict schema enforcement for Shield v3
- stable reason identifiers and governance mapping
- posture outputs that cannot silently downgrade
- regression tests that permanently prevent “weakening” changes

------------------------------------------------------------------------

## What Is Locked

### 1) Shield v3 Interface (strict mode)

Locked rules (enforced when `require_versions=True`):
- `shield_bundle_version` is required and must be semver `X.Y.Z`
- each signal must include `layer_version` and must be semver `X.Y.Z`
- `signals` must be sorted by `(layer, signal_id)`
- `required_layers` must follow the canonical order and contain no duplicates
- unknown fields are rejected (bundle + signals)
- duplicate layer signals are rejected
- required layers must be present exactly

### 2) Protection Mode Output

Execution responses include:
- `protection_mode: legacy | minimal | full`

Deterministic semantics:
- `legacy`: protected call not requested OR Q-ID invalid/missing
- `minimal`: Q-ID valid but Oracle and/or Shield invalid/missing
- `full`: Q-ID valid + Oracle valid + Shield valid (as configured)

A full truth-table regression test locks these semantics permanently.

### 3) No Silent Downgrade (Policy Latches)

Policy can enforce strict posture:
- `require_protected_call=True` → deny if protected request is missing
- `require_full_mode=True` → deny if full mode is impossible

### 4) Never-Weaken Regression Lock

A regression test locks:
- If Shield evidence causes DENY, adding more allow evidence or reordering signals can never flip to ALLOW.

------------------------------------------------------------------------

## Where It Lives In Repo

Fixtures:
- `src/adamantine/v1/fixtures/v1_3_0/`

Strict manifest enforcement:
- `src/adamantine/v1/execution/fixture_harness.py`

Tests:
- `tests/test_os_proof_pack_v1_3_0.py`
- `tests/test_step4_posture_enforcement.py`
- `tests/test_shield_never_weaken_regression_lock.py`
- `tests/test_protection_mode_matrix_regression.py`

------------------------------------------------------------------------

## Contract Notes

v1.3.0 is additive:
- no breaking changes to existing contracts
- response adds `protection_mode` for auditability and deterministic posture reporting

See also:
- `docs/CONTRACTS/mobile_decision_result_v1.md`
- `INVARIANTS.md`
- `GOVERNANCE.md`
