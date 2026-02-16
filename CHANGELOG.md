# Adamantine Wallet OS --- Changelog

License: MIT License\
Author: DarekDGB\
Repository: DigiByte Adamantine Wallet OS\
Scope: Foundation Releases and Contract History

v1.5.0 --- Mobile Contract v2 + Conformance Freeze

Status: Locked\
Type: Contract extension (mobile v2 freeze + deterministic conformance
pack)\
Compatibility: Additive --- v1.4.x contracts remain valid unless mobile
v2 is explicitly used

This release freezes the Mobile Integration Contract v2 and seals the OS
Proof Pack for deterministic CI enforcement.

What's locked:

1.  Mobile Request Contract v2
    -   Strict schema validation (unknown fields rejected)
    -   Required `audit` field enforced
    -   Deterministic request canonicalization
    -   Explicit timebox + authority validation requirements
2.  Mobile Response Contract v2
    -   Stable response envelope
    -   Deterministic `decision`, `reason_id`, `context_hash`
    -   `protection_mode` semantics locked (legacy \| minimal \| full)
    -   Strict response schema (no unknown fields allowed)
3.  OS Proof Pack v1_5\_0 (Mobile)
    -   Golden roundtrip fixtures:
        -   request_legacy.json
        -   request_minimal.json
        -   request_full_allow.json
        -   request_full_deny.json
        -   response_legacy.json
        -   response_minimal.json
        -   response_full_allow.json
        -   response_full_deny.json
    -   Canonical SHA256 manifest lock
    -   Fixture set exact-match enforcement
    -   Canonical JSON duplicate-key rejection
4.  Determinism Enforcement
    -   100-run replay determinism tests
    -   Stable ordering guarantees
    -   Stable artifact shape enforcement
    -   CI-fail on any payload drift
5.  Fail-Closed Guarantees Extended
    -   Missing required request fields â schema reject
    -   Unknown request fields â schema reject
    -   Unknown response fields â schema reject
    -   Hash mismatch â CI failure
    -   Manifest drift â CI failure

Rule: Any change to mobile request/response shape requires a major
version bump.

v1.4.0 --- Q-ID Linkage Hardened (Replay Proof Gate)

Status: Locked\
Type: Contract hardening (Q-ID binding + replay-proof validation)\
Compatibility: Additive --- legacy/v1.3 proof packs remain valid unless
policy enables the latch

What's locked: - New Q-ID replay proof contract (`QIDReplayProof`) and
deterministic adapter validation\
- Distinct reason IDs for missing/invalid replay proof and binding
mismatches\
- New policy latch `require_qid_replay_proof` (deny-by-default; opt-in
hardening)\
- New OS Proof Pack v1_4\_0 fixtures + manifest lock (allow +
fail-closed deny cases)

v1.3.0 --- Shield Interfaces Frozen + Posture Locked

Status: Locked\
Type: Contract hardening (Shield v3 + posture + regression locks)\
Compatibility: Additive only --- response adds `protection_mode` and new
strict fixtures

This release freezes the Shield v3 external evidence interface and locks
deterministic, auditable posture outputs.

1.  Shield v3 Strict Interface Freeze
    -   Global `shield_bundle_version` (strict only)
    -   Per-signal `layer_version` (strict only)
    -   Deterministic ordering rules:
        -   signals sorted by (layer, signal_id)
        -   required_layers canonical order (strict only)
    -   Unknown fields rejected (bundle + signal)
    -   Duplicates denied (layers/signals)
2.  Protection Mode Output (auditable)
    -   Execution response includes
        `protection_mode: legacy | minimal | full`
    -   Deterministic semantics locked by tests
3.  No Silent Downgrade (policy posture latches)
    -   `require_protected_call` and `require_full_mode` policy latches
        added
    -   Hard-deny when requested posture cannot be satisfied
4.  Regression Locks
    -   Shield can only strengthen deny (never-weaken invariant)
    -   Protection mode matrix regression lock

See: docs/OS_PROOF_PACK_v1_3\_0.md

------------------------------------------------------------------------

v1.2.0 --- Integration Harness Sealed

Status: Locked\
Type: Deterministic integration freeze (execution proof pack)\
Compatibility: Additive only --- contracts unchanged

This release seals the deterministic integration harness for Adamantine
Wallet OS.

1.  Canonical Fixture System
    -   Canonical JSON parsing (duplicate-key rejection enforced)
    -   Whitespace-independent SHA256 hashing
    -   Strict fixture manifest enforcement
    -   Manifest must exactly match fixture set (no silent drift)
    -   Hash mismatch prints canonical value for deterministic updates

Rule: Formatting changes cannot alter semantic fixture identity.

2.  Golden End-to-End Execution Fixtures
    -   allow.json golden execution request
    -   deny.json golden execution request
    -   Stable execution_response_v1 shape
    -   Stable reason_id and context_hash
    -   Deterministic artifacts structure
3.  Determinism Enforcement
    -   50-run replay determinism tests (allow + deny)
    -   Stable response ordering guarantees
    -   CI-locked proof pack validation
    -   Reproducible execution across environments
4.  Verified Deny Path
    -   EQC threshold-driven deny confirmed
    -   Stable EQC_RISK_SCORE_BELOW_THRESHOLD semantics
    -   Adapter behavior locked against drift
5.  Security Guarantees Reinforced
    -   No silent fixture modification possible
    -   No hidden behavioral drift in execution layer
    -   Contract surfaces unchanged from v1.0.0
    -   Test coverage â¥90% maintained on security-critical paths

Seal Statement:

As of v1.2.0, the execution integration layer is cryptographically
reproducible and CI-enforced.

Future changes must: - update canonical hashes intentionally - preserve
deterministic semantics - maintain contract compatibility

------------------------------------------------------------------------

v1.0.0 --- Foundation Sealed

Status: Locked\
Type: Foundation seal (contracts + deterministic reasoning +
boundaries)\
Compatibility: Additive changes only beyond this point

This release seals the Adamantine Wallet OS foundation.

It freezes: - contract surfaces - fail-closed adapters - deterministic
decision semantics - authority enforcement boundaries - mobile
consumption outputs

Breaking changes require a new major version.
