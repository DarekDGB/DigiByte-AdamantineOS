# Adamantine Wallet OS — Changelog

License: MIT License  
Author: DarekDGB  
Repository: DigiByte Adamantine Wallet OS  
Scope: Foundation Releases and Contract History

------------------------------------------------------------------------

## v2.0.0 — Runtime Host v2 + Execution Boundary Seal

**Status:** Locked  
**Type:** Major release (runtime host + execution_response_v2 seal)  
**Compatibility:** Breaking — execution response upgraded to v2 contract

This release seals the mobile runtime host (v2) and locks deterministic execution behavior end-to-end.

### What's locked:

1. Runtime Host v2
   - `run_mobile_execution_call_v2` as authoritative execution entrypoint
   - Deterministic policy injection
   - Strict nonce store enforcement
   - Stable executor interaction boundary

2. Execution Response v2 (Contract Freeze)
   - `v: execution_response_v2`
   - Stable `decision` object structure
   - Stable `reason_id`
   - Stable `context_hash`
   - Locked `artifacts` shape
   - Deterministic `protection_mode`
   - Deterministic nonce semantics

3. Proof Pack v2_0_0_runtime
   - request_allow.json
   - request_deny.json
   - request_hostile_context_mismatch.json
   - response_allow.json
   - response_deny.json
   - response_hostile_context_mismatch.json
   - Canonical SHA256 manifest lock
   - Strict fixture-set exact-match enforcement

4. Determinism Enforcement
   - 50-run replay determinism tests (allow + hostile)
   - Stable canonical JSON dumps
   - CI fails on any payload drift

5. Fail-Closed Guarantees Reinforced
   - Adapter structural violations -> deterministic deny
   - Manifest drift -> CI failure
   - Canonical hash mismatch -> CI failure

Rule: Any change to execution_response_v2 shape requires a new major version.

------------------------------------------------------------------------

## v1.5.0 — Mobile Contract v2 + Conformance Freeze

**Status:** Locked  
**Type:** Contract extension (mobile v2 freeze + deterministic conformance pack)  
**Compatibility:** Additive — v1.4.x contracts remain valid unless mobile v2 is explicitly used

This release freezes the Mobile Integration Contract v2 and seals the OS Proof Pack for deterministic CI enforcement.

### What's locked:

1. Mobile Request Contract v2
   - Strict schema validation (unknown fields rejected)
   - Required `audit` field enforced
   - Deterministic request canonicalization
   - Explicit timebox + authority validation requirements

2. Mobile Response Contract v2
   - Stable response envelope
   - Deterministic `decision`, `reason_id`, `context_hash`
   - `protection_mode` semantics locked (legacy | minimal | full)
   - Strict response schema (no unknown fields allowed)

3. OS Proof Pack v1_5_0 (Mobile)
   - Golden roundtrip fixtures (legacy / minimal / full)
   - Canonical SHA256 manifest lock
   - Fixture set exact-match enforcement
   - Canonical JSON duplicate-key rejection

4. Determinism Enforcement
   - 100-run replay determinism tests
   - Stable ordering guarantees
   - Stable artifact shape enforcement
   - CI fails on any payload drift

5. Fail-Closed Guarantees Extended
   - Missing required request fields -> schema reject
   - Unknown request fields -> schema reject
   - Unknown response fields -> schema reject
   - Hash mismatch -> CI failure
   - Manifest drift -> CI failure

Rule: Any change to mobile request/response shape requires a major version bump.

------------------------------------------------------------------------

## v1.4.0 — Q-ID Linkage Hardened (Replay Proof Gate)

**Status:** Locked  
**Type:** Contract hardening (Q-ID binding + replay-proof validation)  
**Compatibility:** Additive — legacy/v1.3 proof packs remain valid unless policy enables the latch

### What's locked:

- Q-ID replay proof contract (`QIDReplayProof`) and deterministic adapter validation
- Distinct reason IDs for missing/invalid replay proof and binding mismatches
- Policy latch `require_qid_replay_proof` (deny-by-default; opt-in hardening)
- OS Proof Pack v1_4_0 fixtures + manifest lock (allow + fail-closed deny cases)

------------------------------------------------------------------------

## v1.3.0 — Shield Interfaces Frozen + Posture Locked

**Status:** Locked  
**Type:** Contract hardening (Shield v3 + posture + regression locks)  
**Compatibility:** Additive only — response adds `protection_mode` and new strict fixtures

This release freezes the Shield v3 external evidence interface and locks deterministic, auditable posture outputs.

1. Shield v3 Strict Interface Freeze
2. Protection Mode Output (auditable)
3. No Silent Downgrade (policy posture latches)
4. Regression Locks

------------------------------------------------------------------------

## v1.2.0 — Integration Harness Sealed

**Status:** Locked  
**Type:** Deterministic integration freeze (execution proof pack)  
**Compatibility:** Additive only — contracts unchanged

This release seals the deterministic integration harness for Adamantine Wallet OS.

Seal Statement:

As of v1.2.0, the execution integration layer is cryptographically reproducible and CI-enforced.

------------------------------------------------------------------------

## v1.0.0 — Foundation Sealed

**Status:** Locked  
**Type:** Foundation seal (contracts + deterministic reasoning + boundaries)  
**Compatibility:** Additive changes only beyond this point

This release seals the Adamantine Wallet OS foundation.

Breaking changes require a new major version.
