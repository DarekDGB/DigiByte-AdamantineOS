# Fixture Change Approval — v2.0.0 Runtime Lock

## Scope

Proof pack: `v2_0_0_runtime`

## Reason

Runtime execution boundary behavior changed intentionally during
v2.0.0 sealing. Canonical execution responses were regenerated to reflect:

- STRICT_FAIL_CLOSED policy enforcement
- Shield adapter strict validation
- Deterministic context hashing
- Full/minimal protection mode enforcement
- Nonce consumption semantics
- Stable reason_id mapping

## Action Taken

- Regenerated canonical response fixtures
- Updated `manifest.json` with new SHA-256 hashes
- Verified strict manifest enforcement
- Verified deterministic behavior across 50 runs
- CI turned red → corrected → green

## Result

Fixtures and manifest now reflect the authoritative execution contract
for v2.0.0 runtime.

This change is intentional and approved.

---

Approved by: DarekDGB  
Version: v2.0.0  
Status: Sealed
