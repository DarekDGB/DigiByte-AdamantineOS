# AdamantineOS Shield v4 PQC Verifier

Author attribution: DarekDGB
Status: Shield v4 V4.7D documentation lock
Scope: AdamantineOS-side Shield v4 verifier contract, not a Shield v4 release claim

## 1. Boundary statement

AdamantineOS remains the final execution boundary.

Shield v4 produces cryptographically verifiable decision evidence only. Shield v4 does not sign transactions, does not broadcast transactions, does not change DigiByte consensus, and does not grant final execution approval.

The AdamantineOS Shield v4 verifier accepts or rejects Shield v4 evidence before the final policy engine can continue. Even when Shield v4 evidence verifies, final approval can only be produced by the AdamantineOS final policy engine after all local gates have also passed.

## 2. Current implementation surface

The Shield v4 AdamantineOS boundary is currently split across these files:

- `src/adamantine/v1/contracts/shield_orchestrator_receipt_v4.py`
- `src/adamantine/v1/integrations/shield_orchestrator_receipt_v4_verifier.py`
- `src/adamantine/v1/policy/final_policy_engine.py`
- `src/adamantine/v1/fixtures/shield_v4/valid_allow_signed_receipt.json`
- `src/adamantine/v1/fixtures/shield_v4/deny_signed_receipt.json`
- `src/adamantine/v1/fixtures/shield_v4/tampered_signature_deny.json`
- `src/adamantine/v1/fixtures/shield_v4/v3_downgrade_rejected.json`

The current verifier uses TEST-ONLY deterministic signature checks for the contract phase. Production PQC backend wiring must preserve the same schema, canonicalization, domain separation, policy, trust-registry, and fail-closed behavior.

## 3. Required Shield v4 receipt contract

A Shield v4 receipt accepted by AdamantineOS must use:

- `schema_version = shield.receipt.v2`
- `contract_version = 4`
- `canonicalization_profile = shield-v4-canon.v1`
- `signature_policy = policy.v1`
- `key_registry_version` as a positive integer
- `receipt_hash` as lowercase SHA-256 hex
- `signed_payload_hash` as lowercase SHA-256 hex
- `signature_bundle.schema_version = shield.signature_bundle.v1`

A v3 receipt submitted while Shield v4 is required is a downgrade attempt and must be rejected fail-closed.

## 4. Algorithm policy

Policy `policy.v1` requires strict AND semantics for:

- `classical-ed25519`
- `ml-dsa`

`ml-dsa` means ML-DSA, formerly CRYSTALS-Dilithium.

`fn-dsa` means FN-DSA, based on Falcon. FN-DSA/Falcon is separate from ML-DSA and must never be described as ML-DSA.

`fn-dsa` is optional evidence only in the current policy. It must never override failure of a required signature path.

The verifier must reject:

- missing required algorithm entries
- duplicate algorithm entries
- unknown algorithms
- unsupported algorithms
- a weaker embedded policy than the verifier-required policy
- signature bundles that behave as first-valid-wins instead of strict AND

## 5. Domain separation and signed payload hashes

The AdamantineOS contract uses domain separation for Shield v4 signed payload hashes:

- `DGB-SHIELD-V4-ORCH-RECEIPT:shield.receipt.v2:policy.v1`
- `DGB-SHIELD-V4-COMPONENT-VERDICT:shield.verdict.v2:policy.v1`

The domain tag is part of the signed payload hash material. A component verdict signature must not verify as an Orchestrator receipt signature, and an Orchestrator receipt signature must not verify as a component verdict signature.

## 6. Trust registry checks

The verifier trust registry must bind each signature to:

- role
- key id
- key version
- algorithm
- validity window
- active or revoked status
- key registry version

A signature is rejected if:

- the key is missing from the trusted registry
- the key role does not match the artifact being verified
- the key id, version, or algorithm does not match the registry
- the key is revoked
- the key is outside its validity window
- the receipt or component verdict was produced outside the key validity window
- a registry rollback attempts to reactivate revoked authority

## 7. Freshness and replay checks

Shield v4 evidence must carry signed freshness fields:

- `request_id`
- `freshness_nonce`
- `not_before`
- `not_after`

The verifier must reject stale, not-yet-valid, malformed, or replayed receipts. Replay rejection is not optional when Shield v4 evidence is used as an AdamantineOS input.

## 8. Component requirements

The verifier requires all five Shield components:

- `adn`
- `dqsn`
- `guardian_wallet`
- `qwg`
- `sentinel_ai`

Each component must have a verified signature summary and each component summary must satisfy the required `policy.v1` algorithms.

A valid Orchestrator receipt is not enough if component verification is missing, incomplete, unsigned, downgraded, or mismatched against the expected context hash.

## 9. No upstream final authority

Shield v4 evidence must not contain final execution authority. The contract and verifier reject authority-bypass fields, including but not limited to:

- `sign`
- `broadcast`
- `override`
- `final_approval`
- `force_allow`
- `auto_approve`
- `can_sign`

`handoff_allowed` is evidence only. It is not final approval.

## 10. Final policy engine v4-required mode

`shield_v4_required=True` activates the AdamantineOS v4-required gate.

When this mode is active, the final policy engine must reject:

- unverified Shield v4 evidence
- missing v4 receipt data
- v3 downgrade receipts
- missing verification summaries
- weaker signature policy
- missing Orchestrator signature summary
- missing component signature summary
- malformed component summaries

Default compatibility mode remains `shield_v4_required=False` until a later controlled integration step enables v4-required mode for the full runtime path.

## 11. Verification order

The verifier must process checks cheap to expensive:

1. mapping/schema shape
2. schema and contract version
3. canonicalization profile
4. context hash and request id
5. freshness window
6. receipt and signed payload hashes
7. trust registry shape and version
8. key role/id/version/algorithm binding
9. test-only signature verification now, production PQC verification later
10. replay marking only after verification succeeds
11. final policy engine gates

Malformed input must be rejected before expensive signature work.

## 12. Tests that lock this boundary

The current V4.7 AdamantineOS tests are:

- `tests/contracts/test_shield_orchestrator_receipt_v4_contract.py`
- `tests/integrations/test_shield_orchestrator_receipt_v4_verifier.py`
- `tests/policy/test_final_policy_engine_shield_v4_required.py`
- `tests/test_adamantineos_shield_v4_docs_lock.py`

These tests lock contract validation, verifier behavior, trust-registry checks, downgrade rejection, and final-policy v4-required behavior.

## 13. Release status

This document does not claim Shield v4 is released.

Current status: AdamantineOS has a Shield v4 verifier boundary, fixtures, fail-closed trust-registry checks, and a v4-required final-policy gate.

Remaining later phases include full multi-repo v4 integration harness, compatibility notes for Adaptive Core and AI Gateway, final proof pack, release status docs, and final release gate.
