# AdamantineOS Shield v3 Fixture and Negative Test Plan

Author attribution: **DarekDGB**  
Status: **Milestone 2 planning contract — pre-implementation**  
AdamantineOS release boundary: **v2.2.0 — WSQK v2 Quantum-Aware Upgrade**  
External Shield baseline: **Shield v3.2.0 tagged across the six Shield repositories**  
Depends on:

- `docs/ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md`
- `docs/ADAMANTINEOS_INTEGRATION_HARNESS_SCOPE.md`

## 1. Purpose

This document defines the first fixture pack and negative-test plan for AdamantineOS full Shield v3 integration.

It exists before implementation so the test boundary is locked before any adapter, hasher, harness, or live integration code is written.

The purpose is to make the first implementation step small, deterministic, reviewable, and fail-closed.

## 2. Non-negotiable rule

```text
Contract first.
Fixture first.
Negative tests first.
Happy path later.
Live integration later.
```

This document does not authorize code changes.

This document does not authorize live Shield integration.

This document does not authorize AdamantineOS tagging.

## 3. Version and authority boundary

1. AdamantineOS remains `v2.2.0`.
2. Shield v3.2.0 remains an external baseline.
3. Shield Orchestrator output is evidence only.
4. Shield `ALLOW` is not AdamantineOS final approval.
5. Shield `DENY` must fail closed.
6. `HUMAN_REVIEW_REQUIRED` must not become autonomous allow.
7. Raw Shield component verdicts must be rejected as bypass attempts.
8. Unknown, malformed, missing, unsupported, or nondeterministic input must reject.
9. No Shield repository may be changed unless a real defect is proven with a minimal failing case.

## 4. Scope for Milestone 2

Milestone 2 creates the fixture and negative-test plan only.

Allowed work:

- define fixture directory names
- define fixture manifest shape
- define valid fixture categories
- define invalid fixture categories
- define expected outcomes
- define fail-closed reason semantics
- define CI/audit gates for fixture-only tests

Forbidden work:

- no implementation code
- no adapter code
- no hash function code
- no live Shield Orchestrator import
- no live multi-repo harness
- no package restructuring
- no AdamantineOS version bump
- no AdamantineOS tag
- no Shield repo changes

## 5. Proposed fixture directory layout

The first implementation step should place fixtures under a deterministic local path.

Recommended layout:

```text
tests/fixtures/shield_v3_integration/
  manifest.json
  combined_context_hash/
    valid_combined_context_hash_v1.json
    valid_combined_context_hash_v1_reordered.json
    invalid_missing_contract.json
    invalid_missing_version.json
    invalid_missing_domain.json
    invalid_missing_request_id.json
    invalid_missing_wallet_context_hash.json
    invalid_missing_transaction_context_hash.json
    invalid_missing_qid_auth_context_hash.json
    invalid_missing_wsqk_posture_context_hash.json
    invalid_missing_policy_context_hash.json
    invalid_missing_replay_context_ref.json
    invalid_missing_shield_receipt_context_hash.json
    invalid_unknown_top_level_field.json
    invalid_forbidden_authority_field.json
    invalid_null_required_field.json
    invalid_version_string.json
    invalid_version_float.json
    invalid_uppercase_hash.json
    invalid_short_hash.json
    invalid_non_hex_hash.json
    invalid_empty_request_id.json
    invalid_empty_replay_context_ref.json
    invalid_non_ascii_string.json
    invalid_leading_trailing_whitespace.json
    invalid_control_character.json
    invalid_array_value.json
    invalid_nested_object_value.json
    invalid_boolean_value.json
    invalid_timestamp_field.json
    invalid_randomness_field.json
    invalid_duplicate_key.json
    invalid_top_level_array.json
  shield_receipts/
    valid_orchestrator_receipt_allow.json
    valid_orchestrator_receipt_deny.json
    valid_orchestrator_receipt_human_review.json
    invalid_raw_component_verdict_bypass.json
    invalid_tampered_receipt_hash.json
    invalid_context_hash_mismatch.json
    invalid_replay_reference_mismatch.json
    invalid_qid_context_mismatch.json
    invalid_wsqk_posture_mismatch.json
    invalid_unknown_reason_id.json
    invalid_unknown_evidence_family.json
    invalid_duplicate_evidence_family.json
    invalid_fail_closed_false.json
    invalid_shield_deny_with_handoff_allowed.json
    invalid_human_review_with_autonomous_handoff.json
    invalid_ai_authority_bypass_attempt.json
```

File names may be adjusted during implementation, but the categories must remain represented.

## 6. Fixture manifest contract

A fixture manifest must exist before fixture tests are expanded.

Recommended manifest path:

```text
tests/fixtures/shield_v3_integration/manifest.json
```

Recommended manifest shape:

```json
{
  "contract": "adamantineos.shield_v3_fixture_negative_test_plan",
  "version": 1,
  "adamantineos_boundary": "v2.2.0",
  "external_shield_baseline": "v3.2.0",
  "level": 1,
  "fixtures": [
    {
      "name": "valid_combined_context_hash_v1",
      "path": "combined_context_hash/valid_combined_context_hash_v1.json",
      "category": "combined_context_hash",
      "expected": "ACCEPT",
      "reason": "COMBINED_CONTEXT_HASH_ACCEPTED",
      "expected_hash": "30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a"
    },
    {
      "name": "invalid_raw_component_verdict_bypass",
      "path": "shield_receipts/invalid_raw_component_verdict_bypass.json",
      "category": "shield_receipt_boundary",
      "expected": "REJECT",
      "reason": "SHIELD_REJECTED_RAW_COMPONENT_BYPASS"
    }
  ]
}
```

The manifest must not contain:

- timestamps
- generated-at fields
- machine-local absolute paths
- hostnames
- usernames
- environment values
- randomness
- network references
- unpinned branch references

## 7. Expected result values

The first fixture harness should use a tiny fixed result vocabulary.

Allowed expected values:

```text
ACCEPT
REJECT
CONTINUE_CHECKS
BLOCK
HUMAN_REVIEW_REQUIRED
```

Meaning:

| Expected value | Meaning |
|---|---|
| `ACCEPT` | Fixture is structurally valid for the specific contract under test |
| `REJECT` | Fixture must fail closed before producing authority |
| `CONTINUE_CHECKS` | Shield evidence is valid but only allows AdamantineOS to continue its own checks |
| `BLOCK` | Shield or AdamantineOS boundary blocks execution |
| `HUMAN_REVIEW_REQUIRED` | Execution must not continue autonomously |

`ALLOW` must not appear as a final AdamantineOS result in the fixture plan.

## 8. Combined context hash valid fixture

The first valid combined context hash fixture must match the vector locked in `docs/ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md`.

Fixture path:

```text
tests/fixtures/shield_v3_integration/combined_context_hash/valid_combined_context_hash_v1.json
```

Fixture content:

```json
{
  "contract": "adamantineos.combined_context_hash",
  "version": 1,
  "domain": "ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1",
  "request_id": "req-000001",
  "wallet_context_hash": "1111111111111111111111111111111111111111111111111111111111111111",
  "transaction_context_hash": "2222222222222222222222222222222222222222222222222222222222222222",
  "qid_auth_context_hash": "3333333333333333333333333333333333333333333333333333333333333333",
  "wsqk_posture_context_hash": "4444444444444444444444444444444444444444444444444444444444444444",
  "policy_context_hash": "5555555555555555555555555555555555555555555555555555555555555555",
  "replay_context_ref": "replay:v1:nonce:000001",
  "shield_receipt_context_hash": "6666666666666666666666666666666666666666666666666666666666666666"
}
```

Expected hash:

```text
30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a
```

## 9. Combined context hash positive determinism fixture

A reordered copy of the valid fixture must produce the same hash.

Fixture path:

```text
tests/fixtures/shield_v3_integration/combined_context_hash/valid_combined_context_hash_v1_reordered.json
```

Expected hash:

```text
30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a
```

This proves that input field order does not affect the canonical hash.

## 10. Combined context hash negative fixtures

Every negative fixture below must reject before producing a hash.

| Fixture | Mutation | Required result | Required reason semantics |
|---|---|---|---|
| `invalid_missing_contract.json` | remove `contract` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_version.json` | remove `version` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_domain.json` | remove `domain` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_request_id.json` | remove `request_id` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_wallet_context_hash.json` | remove `wallet_context_hash` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_transaction_context_hash.json` | remove `transaction_context_hash` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_qid_auth_context_hash.json` | remove `qid_auth_context_hash` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_wsqk_posture_context_hash.json` | remove `wsqk_posture_context_hash` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_policy_context_hash.json` | remove `policy_context_hash` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_replay_context_ref.json` | remove `replay_context_ref` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_missing_shield_receipt_context_hash.json` | remove `shield_receipt_context_hash` | `REJECT` | `COMBINED_CONTEXT_HASH_MISSING_FIELD` |
| `invalid_unknown_top_level_field.json` | add unknown field | `REJECT` | `COMBINED_CONTEXT_HASH_UNKNOWN_FIELD` |
| `invalid_forbidden_authority_field.json` | add `force_allow` | `REJECT` | `COMBINED_CONTEXT_HASH_FORBIDDEN_AUTHORITY_FIELD` |
| `invalid_null_required_field.json` | set required field to `null` | `REJECT` | `COMBINED_CONTEXT_HASH_NULL_FIELD` |
| `invalid_version_string.json` | set `version` to `"1"` | `REJECT` | `COMBINED_CONTEXT_HASH_WRONG_TYPE` |
| `invalid_version_float.json` | set `version` to `1.0` | `REJECT` | `COMBINED_CONTEXT_HASH_WRONG_TYPE` |
| `invalid_uppercase_hash.json` | uppercase hash characters | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_HASH_HEX` |
| `invalid_short_hash.json` | shorten a hash | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_HASH_LENGTH` |
| `invalid_non_hex_hash.json` | use non-hex character | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_HASH_HEX` |
| `invalid_empty_request_id.json` | empty `request_id` | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_REQUEST_ID` |
| `invalid_empty_replay_context_ref.json` | empty `replay_context_ref` | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_REPLAY_REF` |
| `invalid_non_ascii_string.json` | add non-ASCII string | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_STRING` |
| `invalid_leading_trailing_whitespace.json` | add surrounding whitespace | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_STRING` |
| `invalid_control_character.json` | add newline/tab/control character | `REJECT` | `COMBINED_CONTEXT_HASH_INVALID_STRING` |
| `invalid_array_value.json` | add array value | `REJECT` | `COMBINED_CONTEXT_HASH_FORBIDDEN_TYPE` |
| `invalid_nested_object_value.json` | add nested object | `REJECT` | `COMBINED_CONTEXT_HASH_FORBIDDEN_TYPE` |
| `invalid_boolean_value.json` | add boolean value | `REJECT` | `COMBINED_CONTEXT_HASH_FORBIDDEN_TYPE` |
| `invalid_timestamp_field.json` | add timestamp field | `REJECT` | `COMBINED_CONTEXT_HASH_UNKNOWN_FIELD` |
| `invalid_randomness_field.json` | add nonce/random field outside contract | `REJECT` | `COMBINED_CONTEXT_HASH_UNKNOWN_FIELD` |
| `invalid_duplicate_key.json` | duplicate JSON key | `REJECT` | `COMBINED_CONTEXT_HASH_DUPLICATE_KEY` |
| `invalid_top_level_array.json` | top-level array instead of object | `REJECT` | `COMBINED_CONTEXT_HASH_NOT_OBJECT` |

Reason names may be finalized during implementation, but their semantic coverage must not weaken.

## 11. Combined context change-detection fixtures

The first implementation should also include mutation fixtures proving that each bound context changes the hash.

Each mutation starts from the valid fixture and changes exactly one field.

| Mutation | Expected hash |
|---|---|
| `wallet_context_hash = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `5f37bc650d63a187227222d96b3bab9b8b1e17de23e7ba1ce7f0fc31d0eee663` |
| `transaction_context_hash = bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` | `95110bdca413454f6bc8aa049a850a7d3f1305a1db45b3b7b0ddca9eacd0983f` |
| `qid_auth_context_hash = cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc` | `8c0348a34b587f8544a48a398d616df3dd2ce24d4f7b7f392b35068166ad0b90` |
| `wsqk_posture_context_hash = dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd` | `5b6bf77fb4b30f1f974dba0a4ffff5007f1b9629cae76359fb766150a2fa400d` |
| `policy_context_hash = eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee` | `a9881388d21349d6506a2e124f9fdacdca32ea122f559d643433122fdd1c39d6` |
| `replay_context_ref = replay:v1:nonce:000002` | `65c626260bc95ca40dd46633a51ad49ac0dd72e0e1e1838f4380c3077e93609d` |
| `shield_receipt_context_hash = ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff` | `a37645ddaef009481bf17fcbe75fb13ca77ebff6a2bd253c941a5b055837d278` |
| `request_id = req-000002` | `e92ccfce6c6551731cc6a4a37fd3f4b136decd3279b8761c628b9606380271c8` |

## 12. Shield receipt fixture categories

The first Shield receipt fixtures are boundary fixtures only.

They must not import live Shield repositories.

They represent the receipt shape AdamantineOS expects to receive from the Shield Orchestrator handoff boundary.

Minimum required categories:

| Fixture | Required outcome | Meaning |
|---|---|---|
| `valid_orchestrator_receipt_allow.json` | `CONTINUE_CHECKS` | Valid Shield evidence, but not final approval |
| `valid_orchestrator_receipt_deny.json` | `BLOCK` | DENY dominates and blocks |
| `valid_orchestrator_receipt_human_review.json` | `HUMAN_REVIEW_REQUIRED` | Human review cannot auto-allow |
| `invalid_raw_component_verdict_bypass.json` | `REJECT` | Raw component output cannot bypass Orchestrator receipt boundary |
| `invalid_tampered_receipt_hash.json` | `REJECT` | Receipt hash mismatch blocks |
| `invalid_context_hash_mismatch.json` | `REJECT` | Receipt not bound to current AdamantineOS context |
| `invalid_replay_reference_mismatch.json` | `REJECT` | Replay/freshness context mismatch blocks |
| `invalid_qid_context_mismatch.json` | `REJECT` | Q-ID context mismatch blocks |
| `invalid_wsqk_posture_mismatch.json` | `REJECT` | WSQK posture mismatch blocks |
| `invalid_unknown_reason_id.json` | `REJECT` | Unknown reason ID fails closed |
| `invalid_unknown_evidence_family.json` | `REJECT` | Unknown evidence family fails closed |
| `invalid_duplicate_evidence_family.json` | `REJECT` | Duplicate evidence where forbidden fails closed |
| `invalid_fail_closed_false.json` | `REJECT` | Non-fail-closed evidence is invalid |
| `invalid_shield_deny_with_handoff_allowed.json` | `REJECT` | DENY cannot be converted to allowed handoff |
| `invalid_human_review_with_autonomous_handoff.json` | `REJECT` | Human review cannot become autonomous execution |
| `invalid_ai_authority_bypass_attempt.json` | `REJECT` | AI cannot grant authority |

## 13. Minimal Shield receipt fixture shape

The exact Shield receipt schema must remain aligned with the current AdamantineOS boundary contract and `docs/SHIELD_V3_2_ORCHESTRATOR_HANDOFF.md`.

Recommended fixture shape for planning:

```json
{
  "receipt_type": "shield_orchestrator_receipt",
  "receipt_version": "3.2.0",
  "orchestrator_decision": "ALLOW",
  "fail_closed": true,
  "context_hash": "30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a",
  "receipt_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "reason_ids": [
    "SHIELD_V3_EVIDENCE_ACCEPTED"
  ],
  "evidence_families": [
    "wallet_guardian",
    "quantum_wallet_guard",
    "active_defense_network",
    "quantum_shield_network",
    "sentinel_ai"
  ]
}
```

This shape is not implementation authority by itself.

During implementation, the fixture shape must be reconciled with the actual AdamantineOS receipt boundary already present in the repository.

If the existing boundary contract uses different field names, implementation must follow the repository contract and update this plan only through review.

## 14. Negative tests must outnumber happy-path tests

The first fixture suite must satisfy this ratio:

```text
negative fixtures > positive fixtures
```

Minimum acceptable Milestone 2 fixture balance:

```text
positive fixtures: 2 combined context hash + 3 Shield receipt state fixtures = 5
negative fixtures: at least 30 combined context hash + at least 13 Shield receipt rejection fixtures = 43+
```

A suite that only proves valid ALLOW is incomplete and must not be accepted.

## 15. First implementation order after this plan is reviewed

Implementation must begin only after this document is reviewed.

When approved, the first implementation order should be:

```text
1. Add fixture directory only.
2. Add manifest only.
3. Add combined context hash valid fixture.
4. Add combined context hash reordered fixture.
5. Add combined context hash negative fixtures.
6. Add tests that load manifest and assert every fixture has expected result.
7. Add tests that invalid combined context fixtures reject.
8. Add tests that valid combined context fixtures hash to expected output.
9. Add change-detection tests.
10. Only then consider Shield receipt boundary fixtures.
```

Do not start with Shield live integration.

Do not start with a broad adapter.

Do not start with the Orchestrator package.

## 16. CI gate for first fixture-only implementation

The first fixture-only implementation must pass these CI gates:

```text
[ ] package installs normally
[ ] tests run without network
[ ] tests run without secrets
[ ] tests run without wall-clock dependency
[ ] tests run without randomness
[ ] tests do not require local absolute paths
[ ] fixture manifest is deterministic
[ ] duplicate-key rejection is tested
[ ] negative tests outnumber happy-path tests
[ ] failure output identifies the boundary
[ ] AdamantineOS version remains 2.2.0
[ ] AdamantineOS is not tagged
```

## 17. Audit gate before moving to adapter work

Before any Level 2 adapter implementation begins, the project must pass this audit:

```text
[ ] Both Milestone 1 contracts are present
[ ] This Milestone 2 plan is present
[ ] Combined context hash fixture categories are represented
[ ] Combined context hash rejection cases are represented
[ ] Change-detection fixtures are represented
[ ] Shield receipt boundary categories are represented or explicitly deferred
[ ] Negative tests outnumber happy-path tests
[ ] Shield ALLOW is not final approval
[ ] Shield DENY blocks
[ ] HUMAN_REVIEW_REQUIRED does not auto-allow
[ ] Raw component verdicts are rejected
[ ] Unknown fields reject
[ ] Unsupported versions reject
[ ] Missing fields reject
[ ] Duplicate keys reject
[ ] No live Shield package is imported in Level 1
[ ] No Shield repo was changed
[ ] pyproject version remains 2.2.0
[ ] no tag was created
```

If any box is not satisfied, adapter work must not begin.

## 18. Defect handling rule

If fixture planning or implementation discovers a real defect:

1. Stop expansion.
2. Record the defect.
3. Create the smallest failing fixture.
4. Identify whether the defect belongs to AdamantineOS, the Shield Orchestrator, or a Shield component.
5. Do not patch around the defect silently.
6. Do not weaken the contract to make the defect disappear.
7. Do not tag AdamantineOS until the defect is resolved and reviewed.

## 19. Review requirement

This document must be reviewed before implementation begins.

After review, implementation may begin with fixture-only combined context hash tests.

No adapter implementation, live Orchestrator import, full multi-repo harness, version bump, or tag is authorized by this document alone.

## 20. Locked next action

The next action after this document is added is review, not code.

```text
Review this plan.
Confirm fixture categories.
Confirm expected rejection semantics.
Only then begin the smallest fixture-only implementation step.
```
