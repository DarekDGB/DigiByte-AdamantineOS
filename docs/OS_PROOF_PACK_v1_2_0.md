# OS Proof Pack --- v1.2.0

**Path:** docs/OS_PROOF_PACK_v1_2\_0.md\
**Release:** v1.2.0 --- Integration Harness Sealed
---
Author: DarekDGB
License: MIT
------------------------------------------------------------------------

## Purpose

v1.2.0 introduces the first sealed deterministic proof pack for
AdamantineOS.

This release locks the execution boundary using canonical JSON fixtures,
strict manifest enforcement, and deterministic end-to-end verification.

Same input → identical response (including reason_id and context_hash)
across all environments and repeated runs.

------------------------------------------------------------------------

## Fixture Location

All v1.2.0 proof pack fixtures live here:

src/adamantine/v1/fixtures/v1_2\_0/

Contents:

-   allow.json
-   deny.json
-   manifest.json

------------------------------------------------------------------------

## Manifest Enforcement

manifest.json contains SHA256 hashes of each fixture.

Properties:

-   Hash is computed over canonical JSON
-   Whitespace does not affect the hash
-   Fixture set must match manifest exactly
-   Any mismatch fails CI immediately

If a fixture changes intentionally, CI prints:

expected=`<hash>`{=html} actual=`<hash>`{=html}

Update manifest.json using the new canonical hash.

------------------------------------------------------------------------

## Determinism Guarantees

The v1.2.0 harness enforces:

-   Stable response envelope shape
-   Stable reason_id
-   Stable context_hash
-   Stable artifacts structure
-   50-run deterministic verification
-   Fail-closed behavior

------------------------------------------------------------------------

## Verified Paths

### Allow Path

-   Valid Q-ID session
-   Valid Shield v3 bundle
-   Valid Adaptive Core oracle response
-   EQC threshold satisfied

### Deny Path

-   Adapter-valid evidence bundle
-   Oracle overall_score below threshold
-   Deny reason: EQC_RISK_SCORE_BELOW_THRESHOLD

------------------------------------------------------------------------

## Architectural Impact

This release establishes:

-   A reproducible execution contract
-   A sealed integration harness
-   A stable base for future layer freezing (v1.3.0)
-   Protection against silent behavioral drift

------------------------------------------------------------------------

## Important Rule

If you modify any fixture:

1.  Ensure the behavior change is intentional.
2.  Update the canonical hash in manifest.json.
3.  Confirm CI determinism tests pass.
4.  Never bypass manifest enforcement.

------------------------------------------------------------------------

AdamantineOS v1.2.0 is the first release where the execution
contract is cryptographically sealed.
