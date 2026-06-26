# AdamantineOS Shield v4 Test Matrix

Author attribution: DarekDGB
Status: Shield v4 V4.8G real-backend integration hardening lock
Scope: AdamantineOS Shield v4 contract, verifier, final-policy v4-required tests, and real-backend verifier interface proofs

## 1. Current Shield v4 test files

| Area | Test file | Purpose |
| --- | --- | --- |
| Contract and fixtures | `tests/contracts/test_shield_orchestrator_receipt_v4_contract.py` | Locks Shield v4 receipt shape, hashes, component verdict shape, downgrade rejection, and authority-bypass rejection. |
| Verifier and trust registry | `tests/integrations/test_shield_orchestrator_receipt_v4_verifier.py` | Locks verifier acceptance/rejection, trusted key registry behavior, replay rejection, freshness, key role binding, and signature-summary behavior. |
| Final policy v4-required mode | `tests/policy/test_final_policy_engine_shield_v4_required.py` | Locks AdamantineOS final policy enforcement when `shield_v4_required=True`. |
| Documentation lock | `tests/test_adamantineos_shield_v4_docs_lock.py` | Locks required Shield v4 documentation and boundary wording. |
| Real backend interface contract | `tests/integrations/test_shield_v4_real_crypto_backend_contract.py` | Locks real verifier backend input validation, `b64u:` material, strict bool returns, and fail-closed backend exception behavior. |
| OQS ML-DSA adapter contract | `tests/integrations/test_shield_v4_oqs_mldsa_backend.py` | Locks optional OQS `ML-DSA-65` verify-only adapter behavior with deterministic fakes and native-exception wrapping. |
| V4.8G real-backend interface integration | `tests/integrations/test_shield_v4_real_backend_integration_hardening.py` | Locks real-backend interface wiring with deterministic backends, test-only fallback rejection, tamper rejection, and evidence-only AdamantineOS behavior. |
| V4.8G live liboqs gated proof | `tests/integrations/test_shield_v48g_real_oqs_mldsa_backend.py` | Skipped by default; in a dedicated `SHIELD_V4_REAL_OQS=1` job with installed `oqs`/liboqs, proves live `ML-DSA-65` verify-only behavior and wrong-length fail-closed handling. |

## 2. Contract matrix

| Control | Expected result | Locked by |
| --- | --- | --- |
| Valid `shield.receipt.v2` ALLOW receipt | Accepted as verified evidence shape | `test_shield_v4_accepts_valid_allow_fixture_contract_boundary` |
| Valid DENY receipt | Accepted but no handoff authority | `test_shield_v4_accepts_valid_deny_fixture_without_granting_execution_authority` |
| v3 receipt submitted where v4 is required | Rejected fail-closed | `test_shield_v4_rejects_downgrade_and_tampered_signature_fixtures` |
| Tampered signature fixture | Rejected fail-closed | `test_shield_v4_rejects_downgrade_and_tampered_signature_fixtures` |
| Wrong schema or contract version | Rejected fail-closed | `test_shield_v4_contract_rejects_non_dict_and_bad_schema_fields` |
| Wrong canonicalization profile | Rejected fail-closed | `test_shield_v4_contract_rejects_non_dict_and_bad_schema_fields` |
| Wrong signature policy | Rejected fail-closed | `test_shield_v4_contract_rejects_non_dict_and_bad_schema_fields` |
| Context hash mismatch | Rejected fail-closed | `test_shield_v4_contract_rejects_context_and_receipt_hash_mismatches` |
| Receipt hash mismatch | Rejected fail-closed | `test_shield_v4_contract_rejects_context_and_receipt_hash_mismatches` |
| Signed payload hash mismatch | Rejected fail-closed | `test_shield_v4_contract_rejects_context_and_receipt_hash_mismatches` |
| Forbidden authority fields | Rejected fail-closed | `test_shield_v4_contract_rejects_handoff_authority_and_non_allow_handoff_true` |
| Non-ALLOW receipt with `handoff_allowed=true` | Rejected fail-closed | `test_shield_v4_contract_rejects_handoff_authority_and_non_allow_handoff_true` |
| Missing or invalid component signature results | Rejected fail-closed | `test_shield_v4_contract_rejects_component_result_errors` |
| Missing, duplicate, or unknown component verdicts | Rejected fail-closed | `test_shield_v4_contract_rejects_component_verdict_errors` |

## 3. Verifier and trust-registry matrix

| Control | Expected result | Locked by |
| --- | --- | --- |
| Valid Shield v4 receipt with trusted registry | Verification succeeds | `tests/integrations/test_shield_orchestrator_receipt_v4_verifier.py` |
| Wrong expected context hash | Rejected fail-closed | verifier negative tests |
| Wrong expected request id | Rejected fail-closed | verifier negative tests |
| Stale or not-yet-valid receipt | Rejected fail-closed | verifier freshness tests |
| Duplicate request id / replay | Rejected fail-closed | verifier replay tests |
| Wrong registry version or rollback | Rejected fail-closed | verifier registry tests |
| Missing trusted key | Rejected fail-closed | verifier registry tests |
| Revoked trusted key | Rejected fail-closed | verifier registry tests |
| Signature outside key validity window | Rejected fail-closed | verifier key-window tests |
| Wrong key role | Rejected fail-closed | verifier key-role tests |
| Tampered Orchestrator signature | Rejected fail-closed | verifier signature tests |
| Tampered component signature | Rejected fail-closed | verifier signature tests |
| Real-backend verifier exception | Rejected fail-closed through Shield v4 error hierarchy | `test_shield_v48g_verifier_catches_signature_backend_exceptions_and_non_bool_results` |
| Truthy non-bool verifier result | Rejected fail-closed; no truthy coercion | `test_shield_v48g_real_backend_truthy_non_bool_result_rejected` |
| Test-only verifier fallback in real mode | Rejected fail-closed | `test_shield_v48g_rejects_test_only_fallback_for_real_fixture` |

## 4. Final policy v4-required matrix

| Control | Expected result | Locked by |
| --- | --- | --- |
| Verified v4 receipt and local gates pass | AdamantineOS final decision can allow | `test_shield_v4_required_accepts_verified_v4_receipt_before_local_gates` |
| `shield_v4_required` is malformed | Rejected before evidence evaluation | `test_shield_v4_required_rejects_invalid_mode_shape_before_evidence` |
| Shield evidence is unverified | Rejected fail-closed | `test_shield_v4_required_rejects_unverified_result` |
| Missing v4 receipt | Rejected fail-closed | `test_shield_v4_required_rejects_missing_v4_receipt` |
| v3 downgrade receipt | Rejected fail-closed | `test_shield_v4_required_rejects_v3_downgrade_receipt` |
| Missing verification summary | Rejected fail-closed | `test_shield_v4_required_rejects_missing_verification_summary` |
| Weak policy | Rejected fail-closed | `test_shield_v4_required_rejects_weak_policy` |
| Missing Orchestrator required algorithm | Rejected fail-closed | `test_shield_v4_required_rejects_missing_orchestrator_algorithm` |
| Missing component summary | Rejected fail-closed | `test_shield_v4_required_rejects_missing_component_signature_summary` |
| Component summary missing required algorithms | Rejected fail-closed | `test_shield_v4_required_rejects_component_summary_without_required_algorithms` |
| Default v3-compatible mode | Existing normalized Shield evidence can still pass | `test_default_mode_still_allows_legacy_normalized_shield_evidence` |

## 5. Algorithm matrix

| Algorithm label | Meaning | Current role |
| --- | --- | --- |
| `classical-ed25519` | classical test-only signature path | required in `policy.v1` |
| `ml-dsa` | ML-DSA, formerly CRYSTALS-Dilithium | required in `policy.v1` |
| `fn-dsa` | FN-DSA, based on Falcon | optional evidence only |

FN-DSA/Falcon must never be treated as ML-DSA and must never override failure of a required path.

## 6. Real backend proof levels

| Proof level | CI behavior | Claim allowed |
| --- | --- | --- |
| Default package CI | Uses deterministic verifier backends and fake OQS modules | Proves interface contract, fail-closed behavior, parser hardening, and AdamantineOS evidence-only integration. |
| Gated live liboqs job | Requires `SHIELD_V4_REAL_OQS=1`, installed `oqs`/liboqs, JUnit output, and `scripts/assert_real_oqs_junit_not_skipped.py` with `skipped == 0` | Proves live liboqs `ML-DSA-65` verification through the AdamantineOS verify-only backend. |
| V4.10 release gate | Final multi-repo proof pack | Release-grade public claims about real-backend proof. |

AdamantineOS remains verify-only for this path. The real-backend adapter has no `sign_message`, no private-key resolver, and no private-key reference.

## 7. Negative tests still carried into later phases

The following remain important for the full Shield v4 release gate and multi-repo harness:

- full all-component signed ALLOW path across five component repos, Orchestrator, and AdamantineOS
- one component signature missing across the integration harness
- one component wrong key across the integration harness
- one component wrong context hash across the integration harness
- one component v3 downgrade attempt across the integration harness
- Orchestrator receipt signature tampered across the integration harness
- receipt hash tampered but signature valid-looking across the integration harness
- signature valid but signed payload hash mismatch across the integration harness
- replay/stale receipt rejected by injected replay state across the integration harness

V4.8G covers the real-backend interface-contract hardening and gated live-liboqs proof hooks. Final public release claims remain gated by the V4.10 proof pack and a live-liboqs job that passes with `skipped == 0`.
