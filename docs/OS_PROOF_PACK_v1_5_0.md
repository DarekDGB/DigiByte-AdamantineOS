# OS Proof Pack v1.5.0 --- Mobile Contract Pack (Frozen)

**License:** MIT --- **Author:** DarekDGB\*\*\
**Scope:** Normative proof-pack documentation for v1.5.0 contract
freeze.

------------------------------------------------------------------------

## 1. Purpose

The OS Proof Pack exists to prove, in CI, that Adamantine evaluation is:

-   deterministic\
-   fail-closed\
-   contract-stable\
-   regression-locked

v1.5.0 seals the **mobile integration contract (v2)** so external teams
can integrate without guessing, reverse‑engineering, or relying on
implicit behavior.

This document defines the frozen proof boundary for v1.5.0.

------------------------------------------------------------------------

## 2. What v1.5.0 Seals (Contract-Level)

-   Mobile execution contract **v2**
-   Mobile decision result contract **v2** (including `protection_mode`)
-   Strict request validation (no unknown fields)
-   Strict response validation (no unknown fields)
-   Golden fixture roundtrip pack
-   Canonical JSON hash locking via `manifest.json`
-   Determinism enforcement (multi-run CI)
-   Reason registry validation for mobile mapping

No silent payload drift is permitted.

------------------------------------------------------------------------

## 3. Fixture Pack Contents (Frozen: v1_5\_0_mobile)

Location:

`src/adamantine/v1/fixtures/v1_5_0_mobile/`

### Requests

-   `request_legacy.json`
-   `request_minimal.json`
-   `request_full_allow.json`
-   `request_full_deny.json`

### Responses

-   `response_legacy.json`
-   `response_minimal.json`
-   `response_full_allow.json`
-   `response_full_deny.json`

### Lock File

-   `manifest.json`

The fixture folder must contain **exactly these files**.\
No additional JSON files are allowed.\
No files may be removed or renamed.

------------------------------------------------------------------------

## 4. Integrity Lock --- manifest.json

`manifest.json` maps:

`filename → SHA256(canonical JSON)`

Rules:

-   Canonical JSON = sorted keys + compact separators
-   The manifest must NOT include itself
-   Any semantic JSON change changes the hash
-   CI must fail on any hash mismatch

This enforces fail‑closed regression locking.

------------------------------------------------------------------------

## 5. Determinism Requirements

For each fixture, repeated evaluation MUST produce identical:

-   `decision`
-   `protection_mode`
-   `reason_id`
-   `context_hash`
-   response payload structure
-   artifacts shape

CI must execute multi-run determinism validation\
(recommended: **100 runs per fixture**).

Any variance is a contract violation.

------------------------------------------------------------------------

## 6. Fail-Closed Requirements

CI must prove:

-   Unknown request field → schema reject
-   Missing required field → schema reject
-   Wrong type → schema reject
-   Unknown response field → schema reject
-   reason_id must exist in mobile reason registry

No implicit fallback is allowed.

------------------------------------------------------------------------

## 7. Related Contracts and Specifications

-   `docs/CONTRACTS/mobile_execution_call_v2.md`
-   `docs/CONTRACTS/mobile_decision_result_v2.md`
-   `docs/CONTRACTS/execution_request_v2.md`
-   `docs/CONTEXT_HASH_SPEC.md`
-   `contracts/mobile_request_v2.schema.json`
-   `contracts/mobile_response_v2.schema.json`

These documents define the normative contract boundary sealed in v1.5.0.

------------------------------------------------------------------------

## 8. Versioning Discipline

This proof pack is frozen under v1.5.0.

Any breaking change to:

-   request schema
-   response schema
-   canonicalization rules
-   reason registry semantics
-   determinism guarantees

...requires a **major version bump**.

Per roadmap discipline, the next architectural milestone is:

**v2.0.0 --- Runtime Separation & Production Envelope**

No v1.x drift is permitted beyond this freeze.

------------------------------------------------------------------------

**End of OS Proof Pack v1.5.0**
