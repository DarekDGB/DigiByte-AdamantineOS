# AdamantineOS Shield v4 Threat Model

Author attribution: DarekDGB
Status: Shield v4 V4.8G-R4 audit cleanup lock
Scope: AdamantineOS-side Shield v4 receipt verification and final-policy boundary

## 1. Security objective

AdamantineOS must treat Shield v4 as verifiable evidence only.

The objective is to prevent signed evidence from becoming signed execution authority. AdamantineOS remains the final execution boundary, and Shield v4 must not sign transactions, broadcast transactions, or change DigiByte consensus.

## 2. Assets protected

This boundary protects:

- AdamantineOS final policy authority
- Shield v4 receipt integrity
- component-verdict integrity
- context-hash binding
- request-id binding
- replay protection
- key-role separation
- trust-registry validity
- downgrade resistance from v4 to v3
- wallet and external-integrator safety assumptions

## 3. Trust boundaries

### 3.1 Trusted boundary

AdamantineOS local policy code, local verifier code, and the configured trusted Shield v4 key registry are inside the trusted boundary.

### 3.2 Untrusted boundary

Incoming Shield receipts, component verdicts, embedded signature policies, metadata, handoff hints, wallet UI claims, network data, AI-generated text, and upstream summaries are untrusted until verified.

### 3.3 Evidence boundary

Even after verification, Shield v4 remains evidence. It cannot produce final approval.

## 4. Attacker goals

The verifier and final policy engine must defend against:

- submitting a v3 receipt where v4 is required
- stripping ML-DSA and presenting a weaker classical-only policy
- presenting FN-DSA/Falcon evidence as if it were ML-DSA
- replaying a previously valid receipt
- changing context hash after signing
- changing request id after signing
- changing component id after signing
- changing reason ids after signing
- changing handoff state after signing
- forging or tampering with receipt hashes
- splicing valid signatures from another receipt
- using a component key as an Orchestrator key
- using an Orchestrator key as a component key
- using a revoked key
- using a key outside its validity window
- rolling back a key registry to reactivate revoked authority
- injecting `sign`, `broadcast`, `override`, or `final_approval` fields
- causing expensive PQC verification before cheap structural rejection
- relying on an implicit TEST-ONLY verifier when no signature backend is configured
- forging or drifting embedded `component_signature_results` away from AdamantineOS independent verification

## 5. Required fail-closed rules

AdamantineOS must deny when:

- the receipt is not a mapping
- the schema is not `shield.receipt.v2`
- `contract_version` is not `4`
- the canonicalization profile is not `shield-v4-canon.v1`
- `policy.v1` is not satisfied
- required signatures are missing
- signature bundles contain duplicate algorithms
- unknown algorithms appear
- the key registry is invalid
- key lookup fails
- keys are revoked
- key validity windows fail
- receipt freshness fails
- replay is detected
- the expected context hash does not match
- the expected request id does not match
- any component signature summary is missing or incomplete
- embedded `component_signature_results` do not match the independently computed AdamantineOS component verification summaries
- no explicit signature verifier backend is configured for receipt verification
- any upstream artifact tries to carry final execution authority

## 6. Algorithm threat controls

Policy `policy.v1` requires both `classical-ed25519` and `ml-dsa`.

ML-DSA is the algorithm formerly known as CRYSTALS-Dilithium.

FN-DSA is based on Falcon and is separate from ML-DSA. FN-DSA can be optional evidence, but it must never compensate for failed or missing required signatures.

This prevents algorithm-substitution and downgrade attacks.

## 7. Replay and freshness threats

Freshness fields must be signed:

- `request_id`
- `freshness_nonce`
- `not_before`
- `not_after`

Replay protection must reject duplicate request ids within the verifier's tracked window. Replay state must only be updated after a receipt verifies successfully.

## 8. Authority-bypass threats

The most dangerous attack is not a bad signature. The most dangerous attack is a valid-looking signed receipt that tricks downstream code into treating Shield as final authority.

AdamantineOS must therefore reject authority-bypass keys and preserve the rule:

`handoff_allowed` is evidence only; it is not final approval.

Final approval is only produced by the AdamantineOS final policy engine after all required evidence and local gates pass.

## 9. DoS and performance threats

PQC verification can be expensive. The verifier must reject malformed input before expensive verification.

Preferred order:

1. reject non-mapping data
2. reject wrong schema/version
3. reject bad context/request/freshness fields
4. reject bad hashes
5. reject invalid trust-registry shape
6. reject key mismatches
7. then perform signature verification

A future production PQC backend must preserve this cheap-to-expensive ordering.

## 10. Real backend proof over-claim threats

Threat: deterministic fake-backend CI is described as proof that live liboqs ML-DSA has run.

Required controls:

- default CI is described as interface-contract and fail-closed proof only;
- live liboqs ML-DSA verification is an optional gated job using `SHIELD_V4_REAL_OQS=1`;
- the gated job must use a JUnit not-skipped guard so import-skipped OQS tests cannot read as a pass;
- V4.8G-R4 adds an optional gated full-receipt proof that injects live liboqs ML-DSA signatures into every component verdict and the Orchestrator receipt, then verifies the receipt through AdamantineOS;
- release-grade real-backend proof remains part of the V4.10 proof pack before public release claims.


## 11. Out of scope

Shield v4 does not modify DigiByte consensus.

Shield v4 does not sign wallet transactions.

Shield v4 does not broadcast wallet transactions.

Shield v4 does not replace user confirmation, wallet policy, replay gates, or AdamantineOS final policy.

## 12. Current phase status

V4.8G-R4 locks the AdamantineOS-side audit cleanup for real-backend proof boundaries. The verifier now rejects an unconfigured signature backend instead of silently falling back to TEST-ONLY verification, and independently cross-checks embedded `component_signature_results` against AdamantineOS-computed component verification summaries.

This is not the final Shield v4 release gate. The remaining phases still require FN-DSA hybrid evidence work, compatibility documentation, proof-pack closure, live real-OQS workflow evidence with `skipped == 0`, and final release status.
