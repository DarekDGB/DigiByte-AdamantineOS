# AdamantineOS — Shield v3.2.0 Orchestrator Handoff

Author attribution: DarekDGB

## Rule

AdamantineOS consumes Shield only through one deterministic Orchestrator receipt.

Raw component verdicts are rejected as direct bypass attempts.

## Enforcement

`validate_shield_orchestrator_receipt()` rejects:

- missing receipt fields
- unknown receipt schema
- unsupported contract version
- `fail_closed != true`
- context hash mismatch
- malformed handoff object
- receipt hash mismatch
- Shield `DENY` with allowed handoff
- Shield `HUMAN_REVIEW_REQUIRED` with allowed autonomous handoff
- direct `shield.verdict.v1` component payloads

## Authority Boundary

Shield `ALLOW` only permits AdamantineOS to continue evaluating. Shield does not grant final execution authority by itself.
