# AdamantineOS Remaining Boundary Integration Plan

Author attribution: DarekDGB  
Repository: `DigiByte-Adamantine-Wallet-OS`  
Status: Milestone 10 planning document  
AdamantineOS version boundary: `v2.2.0` remains unchanged  
Shield baseline: Shield v3.2.0 remains external and unchanged  
Tag status: no AdamantineOS tag yet

---

## 1. Purpose

This document locks the remaining boundary-integration order before implementation continues.

Milestones 1-9 locked the Shield v3 receiving side inside AdamantineOS:

- combined context hash contract
- fixture and negative-test plan
- combined context hash implementation
- Shield receipt adapter
- Shield receipt verifier
- Level 2 AdamantineOS adapter harness
- Level 3 Shield Orchestrator boundary harness
- public full integration build ledger

This document answers the next required question:

> What remains before full multi-repo integration begins?

The answer is that AdamantineOS still needs explicit, deterministic boundaries for:

1. WSQK v2
2. Q-ID
3. Adaptive Core
4. AI Gateway
5. final AdamantineOS policy-engine decision order

Only after those boundaries are locked should the project move into carefully scoped full multi-repo integration.

---

## 2. Hard Rules

The following rules remain active:

1. AdamantineOS remains `v2.2.0`.
2. No AdamantineOS tag is created during this planning phase.
3. Shield v3.2.0 repositories remain unchanged unless a real defect is found.
4. Every evidence source is treated as evidence only.
5. AdamantineOS remains the final fail-closed decision boundary.
6. `ALLOW` from any upstream source is never final approval by itself.
7. Any `DENY`, malformed evidence, missing evidence, stale evidence, context mismatch, replay risk, or unknown authority field must terminate evaluation fail-closed.
8. No full 10-repo live harness starts until the remaining boundaries and policy-engine order are locked.
9. Negative tests must be written before happy-path expansion.
10. CI must remain green with 100% coverage after each implementation milestone.

---

## 3. Current Repository Inspection Findings

The latest AdamantineOS ZIP already contains existing code for several boundaries. Milestone 10 must not duplicate what already exists.

### 3.1 Existing WSQK v2 Code

Observed files:

```text
src/adamantine/v1/wsqk/issuer_v2.py
src/adamantine/v1/wsqk/qid_binding.py
src/adamantine/v1/contracts/authority.py
docs/CONTRACTS/wsqk_authority_v2.md
```

Observed tests include:

```text
tests/test_wsqk_issuer_v2.py
tests/test_wsqk_qid_binding.py
tests/test_wsqk_v2_orchestrator_runtime.py
tests/test_wsqk_v2_phase7_regression_locks.py
tests/test_wsqk_v2_reason_ids.py
tests/test_wsqk_v2_tva_enforcement.py
```

Existing WSQK v2 appears to provide deterministic authority issuance with:

- `wallet_id`
- `action`
- `context_hash`
- `issued_at`
- `expires_at`
- `nonce`
- `required_evidence_families`
- `quantum_posture`
- `proof_bindings_hash`

Existing reject/failure behavior uses structured reason IDs through `TVAError` / `ReasonId`, not a plain boolean.

### 3.2 Existing Q-ID Code

Observed files:

```text
src/adamantine/v1/contracts/qid.py
src/adamantine/v1/integrations/qid_adapter.py
src/adamantine/v1/wsqk/qid_binding.py
docs/CONTRACTS/qid_linkage_v1.md
```

Observed tests include:

```text
tests/contracts/test_qid_contracts.py
tests/integrations/test_qid_adapter.py
tests/integrations/test_qid_replay_proof_adapter.py
tests/test_coverage_boost_qid_adapter_shape_b_v2.py
tests/test_v2_runtime_host_qid_verifier_wiring.py
```

Existing Q-ID adapter already provides:

- `parse_qid_session(...)`
- support for existing Adamantine session proof shape
- support for Q-ID Adamantine evidence v2 shape
- expiry / not-yet-valid rejection
- proof hash mismatch rejection
- replay-proof parsing
- wallet binding
- subject binding
- proof-hash binding
- device binding
- session nonce binding
- freshness flag rejection

### 3.3 Existing Adaptive Core Code

Observed files:

```text
src/adamantine/v1/integrations/adaptive_core_adapter.py
src/adamantine/v1/integrations/adaptive_core_oracle_v3_adapter.py
src/adamantine/v1/contracts/adaptive_core_oracle_v3.py
src/adamantine/v1/contracts/risk.py
src/adamantine/v1/policy/risk_policy.py
```

Observed tests include:

```text
tests/integrations/test_adaptive_core_adapter.py
tests/integrations/test_adaptive_core_oracle_v3_adapter.py
tests/integrations/test_adaptive_core_oracle_v3_adapter_branch_coverage.py
tests/contracts/test_adaptive_core_oracle_v3_contract.py
```

Existing Adaptive Core adapters already provide:

- risk report parsing
- oracle v3 parsing
- context hash binding
- generated-at validation
- issued/expires validation
- reason-map validation
- optional external reason registry validation
- unknown reason fail-closed behavior
- score threshold interaction through policy

### 3.4 Existing AI Gateway Repository Baseline

Observed repository:

```text
adamantine-ai-gateway-main(2).zip
```

Observed contracts:

```text
contracts/AI_GATEWAY_OUTPUT_V1.md
contracts/AI_GATEWAY_RECEIPT_V1.md
contracts/AI_GATEWAY_HANDOFF_V1.md
contracts/AI_GATEWAY_ENVELOPE_V1.md
contracts/ADAPTER_MANIFEST_V1.md
contracts/POLICYPACK_V1.md
contracts/DETERMINISM_RULES.md
```

The AI Gateway already defines deterministic evidence artifacts:

- output: `ai_gateway_output_v1`
- receipt: `ai_gateway_receipt_v1`
- handoff: `ai_gateway_handoff_v1`

The AI Gateway receipt explicitly says it is evidence only and does not grant execution authority.

---

## 4. Claude Review Questions Answered

### 4.1 WSQK v2: What does a WSQK reject look like?

A WSQK reject must be represented as a structured deterministic failure, not as a boolean.

The policy engine must consume WSQK evidence through a normalized boundary object with at least:

```text
source = "wsqk_v2"
outcome = "ALLOW_EVIDENCE" | "DENY" | "HUMAN_REVIEW_REQUIRED"
reason_id = explicit ReasonId string
context_hash = expected combined context hash
wallet_id = expected wallet id
action = expected action
nonce = explicit nonce / replay reference
proof_hash = deterministic binding hash
```

Current WSQK code raises `TVAError` with explicit `ReasonId` values such as:

```text
WSQK_MISSING_WALLET_ID
WSQK_MISSING_ACTION
WSQK_MISSING_CONTEXT_HASH
WSQK_MISSING_NOW
WSQK_INVALID_TTL
WSQK_INVALID_NONCE
WSQK_V2_INVALID_EVIDENCE_FAMILIES
WSQK_V2_UNKNOWN_EVIDENCE_FAMILY
WSQK_V2_INVALID_QUANTUM_POSTURE
WSQK_QID_POSTURE_MISMATCH
WSQK_QID_HYBRID_REQUIRED
```

Policy-engine rule:

```text
Any WSQK exception or invalid WSQK evidence becomes DENY with the explicit WSQK reason ID.
```

No boolean-only WSQK result is allowed.

### 4.2 Q-ID: What exists and what gap remains?

Q-ID already provides strong adapter-level parsing and replay-proof validation.

Existing capability:

- parse session proof
- parse Q-ID evidence v2
- verify proof hash
- reject expired / not-yet-valid sessions
- validate replay proof
- bind wallet ID
- bind subject
- bind device
- bind proof hash
- bind session nonce
- reject stale replay flag

Remaining integration gap:

```text
Q-ID must be promoted from standalone adapter evidence into the final AdamantineOS policy-engine order.
```

Specifically, the policy engine still needs a deterministic Q-ID evidence boundary that says:

- Q-ID evidence is mandatory for relevant execution paths
- Q-ID session subject must bind to the request authority
- Q-ID replay proof must bind to the same request / wallet / nonce
- Q-ID posture must bind to WSQK quantum posture
- Q-ID failure must terminate evaluation before later gates

### 4.3 Adaptive Core: What exists and what gap remains?

Adaptive Core already provides risk report and oracle v3 adapters.

Existing capability:

- parse risk report
- parse oracle v3 report
- verify context hash binding
- validate issued/expires window
- validate score range
- validate signals
- validate external reason mapping
- optionally validate reason registry
- reject unknown external reasons
- apply policy threshold through `RiskPolicy`

Remaining integration gap:

```text
Adaptive Core must be positioned as advisory evidence inside the final policy-engine order, never as final authority.
```

The policy engine must lock:

- Adaptive Core report is required at the Adaptive gate
- context hash must match the combined context hash
- stale / future / invalid report denies
- low score denies
- unknown external reason denies
- Adaptive Core cannot override an earlier Shield / WSQK / Q-ID deny

### 4.4 AI Gateway: What evidence format does it produce and how is it validated?

AI Gateway is the most sensitive boundary because it is the ingress point for untrusted work.

Existing AI Gateway contracts define these evidence formats:

```text
ai_gateway_output_v1
ai_gateway_receipt_v1
ai_gateway_handoff_v1
```

The policy engine must not trust raw AI output.

AdamantineOS should consume only a normalized AI Gateway evidence object derived from validated AI Gateway handoff / receipt data.

Minimum required AI Gateway evidence boundary:

```text
source = "ai_gateway_v1"
handoff_version = "ai_gateway_handoff_v1"
receipt_version = "ai_gateway_receipt_v1"
adapter = non-empty string
task_type = non-empty string
policy_decision = "accepted" | "rejected"
reason_id = explicit string
envelope_hash = 64-char lowercase SHA-256
output_hash = 64-char lowercase SHA-256
context_hash = expected combined context hash
```

Validation must reject:

- raw model output
- missing handoff
- missing receipt
- unknown fields
- non-canonical values
- invalid hashes
- mismatched envelope hash
- mismatched output hash
- mismatched policy decision
- mismatched context hash
- `policy_decision = rejected`
- any hidden authority field
- any attempt to grant final approval

Policy-engine rule:

```text
AI Gateway evidence is evidence only. It cannot approve execution. It can only pass its evidence gate or cause DENY / HUMAN_REVIEW_REQUIRED.
```

### 4.5 Policy Engine: What decision order must be locked?

The final AdamantineOS policy-engine order must be deterministic and fail-closed.

Locked order:

```text
1. Shield receipt gate
2. WSQK v2 gate
3. Q-ID authentication / replay / posture gate
4. Adaptive Core advisory gate
5. AI Gateway evidence gate
6. replay / nonce gate
7. wallet policy gate
8. human gate
9. final AdamantineOS decision
```

Decision-order invariant:

```text
DENY at any earlier gate terminates evaluation immediately.
```

`ALLOW` from an evidence source means only:

```text
this evidence gate did not deny
```

It does not mean final execution approval.

---

## 5. Remaining Milestone Order

The remaining implementation sequence should be:

### Milestone 11 â WSQK v2 Policy Evidence Boundary

Repository touched:

```text
DigiByte-Adamantine-Wallet-OS only
```

Purpose:

- normalize WSQK success/failure into policy-engine evidence
- preserve explicit WSQK reason IDs
- prove WSQK failure terminates fail-closed
- prove WSQK success does not grant final approval

No Q-ID / Adaptive / AI Gateway implementation in this milestone.

### Milestone 12 â Q-ID Policy Binding Boundary

Repository touched:

```text
DigiByte-Adamantine-Wallet-OS only
```

Purpose:

- connect existing Q-ID adapter outputs into policy evidence
- lock subject / wallet / nonce / device / proof-hash binding
- lock WSQK quantum posture to Q-ID posture interaction
- prove Q-ID deny terminates before Adaptive / AI Gateway

No full multi-repo harness yet.

### Milestone 13 â Adaptive Core Policy Evidence Boundary

Repositories:

```text
DigiByte-Adamantine-Wallet-OS modified
DigiByte-Adaptive-Core inspected only if needed
```

Purpose:

- consume existing Adaptive Core adapter outputs as advisory evidence
- enforce context binding
- enforce score threshold
- enforce unknown reason fail-closed behavior
- prove Adaptive Core cannot override earlier deny

No Adaptive Core repository change unless a real defect is found.

### Milestone 14 â AI Gateway Evidence Boundary

Repositories:

```text
DigiByte-Adamantine-Wallet-OS modified
adamantine-ai-gateway inspected only
```

Purpose:

- define / implement AdamantineOS validator for AI Gateway handoff/receipt evidence
- reject raw AI output
- enforce envelope hash / output hash / decision linkage
- enforce context hash binding
- reject hidden authority fields
- prove AI Gateway cannot approve execution

No AI Gateway repository change unless a real defect is found.

### Milestone 15 â Final AdamantineOS Policy Engine Merge

Repository touched:

```text
DigiByte-Adamantine-Wallet-OS only
```

Purpose:

- merge Shield, WSQK, Q-ID, Adaptive Core, AI Gateway, replay, wallet policy, and human gate into one deterministic policy engine order
- enforce early DENY termination
- preserve explicit reason IDs
- prove all evidence sources are evidence-only

### Milestone 16 â Carefully Scoped Multi-Repo Integration Harness

Repositories inspected / potentially used:

```text
DigiByte-Adamantine-Wallet-OS
DGB-Quantum-Shield-Orchestrator
DGB-Wallet-Guardian
DigiByte-ADN
DGB-Sentinel-AI
DigiByte-Quantum-Shield-Network
DGB-Quantum-Wallet-Guard
DigiByte-Q-ID
DigiByte-Adaptive-Core
adamantine-ai-gateway
```

Purpose:

- start full integration only after all internal boundaries are locked
- use scoped harnesses, not uncontrolled imports
- test cross-repo evidence compatibility
- keep AdamantineOS as final decision boundary

### Milestone 17 â Proof Pack / Docs Alignment

Purpose:

- map invariants to tests
- map contracts to tests
- update build ledger
- update README / SECURITY / CHANGELOG if needed

### Milestone 18 â Authorized Red-Team Review

Purpose:

- attempt safe authorized attacks against architecture bypass, replay, receipt tampering, AI authority bypass, governance reuse, stale evidence, and docs-vs-tests mismatch

### Milestone 19 â Final Release Gate

Purpose:

- final review before version bump / tag
- no tag until all gates are green

---

## 6. Full Integration Start Gate

Full multi-repo integration does not start until all of the following are complete:

```text
Shield receipt boundary complete â
WSQK v2 policy evidence boundary complete â³
Q-ID policy binding boundary complete â³
Adaptive Core policy evidence boundary complete â³
AI Gateway evidence boundary complete â³
Final AdamantineOS policy engine order complete â³
```

Only then does the project enter:

```text
Milestone 16 â Carefully Scoped Multi-Repo Integration Harness
```

---

## 7. No-Tag Reminder

AdamantineOS must not be tagged yet.

The correct state remains:

```text
AdamantineOS version = 2.2.0
Shield v3.2.0 = external baseline
AdamantineOS tag = not created
Full integration = not started yet
```

---

## 8. Summary

Milestone 10 locks the remaining route.

The next implementation milestone is not full integration.

The next implementation milestone should be:

```text
Milestone 11 â WSQK v2 Policy Evidence Boundary
```

That milestone should consume existing WSQK v2 authority behavior deterministically and convert WSQK success/failure into structured policy evidence with explicit reason IDs.
