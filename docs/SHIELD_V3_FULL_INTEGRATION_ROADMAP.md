# AdamantineOS Full Shield v3 Integration Roadmap v1.1

Author attribution: DarekDGB  
Status: Final roadmap baseline before implementation  
Supersedes:

- `AdamantineOS_Full_Shield_v3_Integration_Roadmap.md`
- `AdamantineOS_Full_Shield_v3_Integration_Roadmap_Amendment_1.md`

## Important

This is the roadmap to save and use going forward.

It includes the original full Shield v3 → AdamantineOS integration roadmap plus the accepted pre-implementation hardening amendment:

1. The combined AdamantineOS context hash contract must be written before any Phase 2 implementation.
2. The integration harness scope contract must be written before any Phase 8 implementation.

No AdamantineOS tag is allowed until this roadmap is complete, tested, audited, and approved.

---

## Locked Pre-Implementation Gate

Before writing integration code, the following must be complete:

```text
[ ] Shield v3.2.0 tagged across six Shield repositories
[ ] AdamantineOS remains v2.2.0
[ ] latest ZIP baselines archived
[ ] docs/ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md drafted and approved
[ ] docs/ADAMANTINEOS_INTEGRATION_HARNESS_SCOPE.md drafted and approved
[ ] implementation branch created
[ ] no code written before the two contracts above are locked
```

## New Required Contract Documents

Before implementation begins, create and approve:

```text
docs/ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md
docs/ADAMANTINEOS_INTEGRATION_HARNESS_SCOPE.md
```

These are release-safety gates, not optional notes.

---

## Main Roadmap

Author attribution: DarekDGB  
Prepared after Shield v3.2.0 tagging across the six Shield repositories and after reviewing the latest fresh ZIP baseline.

## Purpose

This roadmap defines the next stage:

**Full Shield v3 integration into AdamantineOS.**

Shield v3.2.0 is now tagged across the six Shield repositories:

1. `DGB-Wallet-Guardian`
2. `DigiByte-ADN`
3. `DGB-Sentinel-AI`
4. `DigiByte-Quantum-Shield-Network`
5. `DGB-Quantum-Wallet-Guard`
6. `DGB-Quantum-Shield-Orchestrator`

AdamantineOS is **not** tagged as part of Shield v3.2.0.

AdamantineOS remains on its own release line:

```text
v2.2.0 — WSQK v2 Quantum-Aware Upgrade
```

AdamantineOS must only be tagged after Shield v3 is fully integrated, tested, audited, and approved under the AdamantineOS release checklist.

---

## Current Baseline

### Shield Baseline

Shield v3.2.0 is the current locked Shield release.

It includes:

- component manifests
- reason ID registries
- evidence-family registries
- canonical component verdict locks
- fail-closed validation
- deterministic Shield Orchestrator receipt validation
- release status documentation
- Red Team / bypass review confirmation

The Shield Orchestrator is the only valid Shield handoff boundary for AdamantineOS.

### AdamantineOS Baseline

AdamantineOS currently contains only the Shield v3.2.0 receipt handoff preparation:

```text
docs/SHIELD_V3_2_ORCHESTRATOR_HANDOFF.md
src/adamantine/v1/contracts/shield_orchestrator_receipt.py
tests/contracts/test_shield_orchestrator_receipt_boundary.py
src/adamantine/v1/contracts/__init__.py
```

This is a compatibility boundary only.

It is **not** full Shield integration.

It is **not** an AdamantineOS v3.2.0 release.

---

## Non-Negotiable Integration Rules

## 1. Orchestrator-Only Shield Handoff

AdamantineOS must consume Shield only through the deterministic Shield Orchestrator receipt.

AdamantineOS must not consume raw component outputs directly.

Forbidden direct authority paths:

```text
Guardian Wallet → AdamantineOS final authority
QWG → AdamantineOS final authority
ADN → AdamantineOS final authority
DQSN → AdamantineOS final authority
Sentinel AI → AdamantineOS final authority
AI Gateway → AdamantineOS final authority
Adaptive Core → AdamantineOS final authority
Q-ID → AdamantineOS final authority
```

All component outputs are evidence only.

## 2. Shield ALLOW Is Not Final Signing Authority

A Shield `ALLOW` receipt only permits AdamantineOS to continue its own checks.

It does not:

- sign
- broadcast
- approve final execution
- bypass WSQK
- bypass wallet policy
- bypass human gates
- bypass replay protection
- bypass AdamantineOS fail-closed checks

AdamantineOS remains the final wallet execution boundary.

## 3. DENY Dominates

If Shield returns `DENY`, AdamantineOS must block.

No later AdamantineOS rule may silently convert Shield `DENY` into allow.

Any future override path would require a separate governance contract, explicit tests, and a versioned security review.

## 4. Human Review Must Bind to Exact Context

If Shield returns `HUMAN_REVIEW_REQUIRED`, any human approval must bind to the exact execution context.

Approval must not be reusable across:

- different transaction context
- different wallet context
- different request ID
- different context hash
- different Shield receipt hash

## 5. Replay / Freshness Must Be AdamantineOS-Enforced

Shield v3.2.0 binds receipts and verdicts to `context_hash`.

AdamantineOS must enforce stateful freshness / replay protection through its own durable execution-boundary rules.

Replay protection must not be weakened during integration.

---

## Integration Architecture

## Required Flow

```text
Wallet / execution request
        ↓
AdamantineOS canonical context builder
        ↓
Shield component evidence generation
        ↓
Shield Orchestrator aggregation
        ↓
Deterministic Shield Orchestrator receipt
        ↓
AdamantineOS receipt validator
        ↓
AdamantineOS WSQK / Q-ID / policy / replay / human-gate checks
        ↓
Final AdamantineOS decision
        ↓
Execution allowed only if all gates pass
```

## Forbidden Flow

```text
Shield component output
        ↓
AdamantineOS execution approval
```

That path must always reject.

---

## Phase 0 — Baseline Freeze

## Goal

Freeze the exact integration baseline before writing new integration code.

## Inputs

Use the latest fresh ZIPs:

```text
DGB-Wallet-Guardian
DigiByte-ADN
DGB-Sentinel-AI
DigiByte-Quantum-Shield-Network
DGB-Quantum-Wallet-Guard
DGB-Quantum-Shield-Orchestrator
DigiByte-Adamantine-Wallet-OS
DigiByte-Q-ID
DigiByte-Adaptive-Core
adamantine-ai-gateway
```

## Required Actions

- Confirm all Shield repos are tagged `v3.2.0`.
- Confirm AdamantineOS remains `v2.2.0`.
- Confirm all CI workflows are green.
- Confirm latest ZIPs match tagged GitHub state.
- Create an AdamantineOS integration branch.
- Do not start feature expansion before baseline is recorded.

## Exit Criteria

```text
[ ] Six Shield repos tagged v3.2.0
[ ] AdamantineOS not tagged
[ ] Latest ZIPs archived as integration baseline
[ ] All existing tests green
[ ] Integration branch created
```

---

## Phase 1 — AdamantineOS Shield Receipt Adapter

## Goal

Turn the current receipt boundary into a complete AdamantineOS-side adapter.

## Required Work

Create or finalize an AdamantineOS adapter layer that:

- accepts only Shield Orchestrator receipts
- rejects raw component verdicts
- validates schema
- validates contract version
- validates receipt hash
- validates context hash
- validates final Shield outcome
- maps Shield outcome into AdamantineOS internal decision state
- never signs, broadcasts, or final-approves by itself

## Expected Files

Candidate paths:

```text
src/adamantine/v1/contracts/shield_orchestrator_receipt.py
src/adamantine/v1/adapters/shield_v3_adapter.py
tests/contracts/test_shield_orchestrator_receipt_boundary.py
tests/adapters/test_shield_v3_adapter.py
```

Use exact paths only after inspecting current AdamantineOS package layout.

## Required Tests

- accepts valid Orchestrator receipt
- rejects missing receipt
- rejects malformed receipt
- rejects unsupported contract version
- rejects receipt hash mismatch
- rejects context hash mismatch
- rejects raw component verdict payload
- rejects unknown final authority claims
- maps `DENY` to AdamantineOS block
- maps `HUMAN_REVIEW_REQUIRED` to AdamantineOS review-required state
- maps `ALLOW` only to continue-checks state, not final approval

## Exit Criteria

```text
[ ] Adapter exists
[ ] Raw component bypass tests pass
[ ] Receipt hash tests pass
[ ] Context hash tests pass
[ ] DENY dominates tests pass
[ ] ALLOW is not final approval tests pass
```

---

## Phase 2 — Canonical AdamantineOS Context Binding

## Goal

Ensure AdamantineOS and Shield evaluate the same canonical execution context.

## Required Work

Define a canonical AdamantineOS execution context containing:

- request ID
- wallet context hash
- transaction context hash
- Q-ID auth context hash
- WSQK posture context hash
- policy context hash
- replay / nonce context reference
- final combined context hash

The Shield receipt must bind to the AdamantineOS expected context hash.

## Required Tests

- same context produces same hash
- field order does not change hash
- missing required context field rejects
- extra authority-bearing field rejects
- context hash mismatch blocks execution
- receipt from one context cannot be reused in another context

## Exit Criteria

```text
[ ] Canonical context builder exists
[ ] Context hash is deterministic
[ ] Shield receipt binds to AdamantineOS context
[ ] Context mismatch rejects fail-closed
```

---

## Phase 3 — WSQK v2 Interaction Gate

## Goal

Preserve AdamantineOS v2.2.0 WSQK v2 authority during Shield integration.

## Required Work

Shield must not bypass WSQK.

AdamantineOS final decision must require:

```text
Shield receipt valid
AND WSQK posture valid
AND wallet policy valid
AND replay/freshness valid
AND human gate satisfied where required
```

Shield `ALLOW` is only one input.

## Required Tests

- Shield `ALLOW` + WSQK reject = final reject
- Shield `ALLOW` + WSQK escalate = final review required
- Shield `DENY` + WSQK allow = final reject
- Shield `HUMAN_REVIEW_REQUIRED` + WSQK allow = review required
- unsupported WSQK posture rejects
- quantum-risk mismatch rejects

## Exit Criteria

```text
[ ] WSQK remains enforced after Shield adapter
[ ] Shield cannot bypass WSQK
[ ] WSQK cannot override Shield DENY silently
```

---

## Phase 4 — Q-ID Authentication Binding

## Goal

Bind Shield/AdamantineOS execution to verified Q-ID authentication facts without giving Q-ID final signing authority.

## Required Work

Q-ID should provide authentication evidence only.

AdamantineOS must validate:

- Q-ID auth status
- Q-ID mode
- Q-ID identity/session binding
- Q-ID context hash
- required step-up state
- mismatch rejection

Q-ID must not become final signing authority.

## Required Tests

- verified Q-ID context accepted as evidence
- unverified Q-ID context rejects or escalates
- Q-ID context hash mismatch rejects
- Q-ID step-up required maps to review/step-up state
- Q-ID output alone cannot approve execution
- Q-ID bypass payload rejects

## Exit Criteria

```text
[ ] Q-ID evidence binds to AdamantineOS context
[ ] Q-ID cannot approve final execution alone
[ ] Q-ID mismatch tests pass
```

---

## Phase 5 — Adaptive Core Advisory Binding

## Goal

Integrate Adaptive Core only as advisory / policy evidence.

## Required Work

Adaptive Core may provide policy posture or advisory context.

It must not:

- override Shield DENY
- override WSQK reject
- final-approve signing
- create hidden fallback allow

## Required Tests

- Adaptive Core advisory allow cannot approve execution alone
- Adaptive Core advisory deny/escalate influences final policy correctly
- Adaptive Core context hash mismatch rejects
- missing Adaptive Core evidence behavior is explicit
- no silent fallback if Adaptive Core unavailable

## Exit Criteria

```text
[ ] Adaptive Core remains advisory
[ ] No Adaptive Core authority bypass
[ ] Fail-closed unavailable behavior is explicit
```

---

## Phase 6 — AI Gateway Evidence Boundary

## Goal

Ensure AI Gateway can contribute evidence without authority.

## Required Work

AI Gateway receipts / outputs must be treated as evidence only.

AI must not:

- sign
- approve
- override Shield DENY
- override WSQK
- bypass human review
- create missing evidence silently
- decide final execution

## Required Tests

- AI output as final authority rejects
- AI output trying to override DENY rejects
- AI output trying to bypass review rejects
- AI receipt hash mismatch rejects
- AI evidence accepted only inside allowed evidence envelope
- AI absence behavior is explicit and fail-closed where required

## Exit Criteria

```text
[ ] AI Gateway remains evidence-only
[ ] AI authority bypass tests pass
[ ] AI cannot fill missing required Shield evidence silently
```

---

## Phase 7 — Full AdamantineOS Policy Engine Merge

## Goal

Create the final AdamantineOS decision pipeline.

## Required Decision Order

Recommended order:

```text
1. Parse request
2. Canonicalize AdamantineOS context
3. Validate Shield Orchestrator receipt
4. Validate Shield outcome
5. Validate WSQK posture
6. Validate Q-ID auth evidence
7. Validate Adaptive Core advisory evidence
8. Validate AI Gateway evidence boundary
9. Validate replay / freshness
10. Apply wallet policy
11. Apply human approval if required
12. Produce final AdamantineOS execution decision
```

## Required Final Outcomes

AdamantineOS should produce a deterministic final result such as:

```text
FINAL_ALLOW_CONTINUE_TO_SIGNING_FLOW
FINAL_DENY_BLOCKED_BY_SHIELD
FINAL_DENY_BLOCKED_BY_WSQK
FINAL_DENY_CONTEXT_MISMATCH
FINAL_DENY_REPLAY_DETECTED
FINAL_REVIEW_REQUIRED
FINAL_ERROR_INVALID_RECEIPT
FINAL_ERROR_AUTH_MISMATCH
FINAL_ERROR_POLICY_MISMATCH
```

Names can change, but they must be stable and documented.

## Required Tests

- all gates allow -> final allow
- Shield deny -> final deny
- WSQK deny -> final deny
- Q-ID mismatch -> final deny or review
- Adaptive Core unavailable -> explicit behavior
- AI authority attempt -> final deny
- replay attempt -> final deny
- human review required -> no autonomous allow
- docs reason IDs match tests

## Exit Criteria

```text
[ ] Final AdamantineOS policy pipeline exists
[ ] Final reason IDs are stable
[ ] All deny/escalate paths tested
[ ] No hidden allow path remains
```

---

## Phase 8 — Integration Harness

## Goal

Create an end-to-end deterministic integration harness.

## Required Work

Build tests that simulate full flow from request to final AdamantineOS decision using fixtures from:

- Guardian Wallet
- QWG
- ADN
- DQSN
- Sentinel AI
- Shield Orchestrator
- WSQK
- Q-ID
- Adaptive Core
- AI Gateway

## Required Test Fixtures

- normal safe flow
- Shield DENY flow
- Shield HUMAN_REVIEW_REQUIRED flow
- malformed component verdict flow
- unknown registry value flow
- context hash mismatch flow
- stale/replayed receipt flow
- AI authority bypass flow
- Q-ID mismatch flow
- WSQK posture mismatch flow
- Adaptive Core unavailable flow
- docs-vs-tests alignment flow

## Exit Criteria

```text
[ ] End-to-end integration tests exist
[ ] Negative tests outnumber happy-path tests
[ ] Integration harness runs in CI
[ ] No PYTHONPATH hacks required if package layout supports clean install
```

---

## Phase 9 — Documentation Update

## Goal

Update AdamantineOS docs precisely without overwriting the current README / SECURITY / CHANGELOG blindly.

## Required Work

Do not replace existing AdamantineOS docs wholesale.

Patch them surgically.

Required docs:

```text
docs/SHIELD_V3_FULL_INTEGRATION_ROADMAP.md
docs/SHIELD_V3_INTEGRATION_CONTRACT.md
docs/SHIELD_V3_TEST_MATRIX.md
docs/SHIELD_V3_PROOF_PACK.md
docs/ADAMANTINEOS_RELEASE_STATUS_FULL_SHIELD_V3.md
```

Potential README additions:

- short Shield integration section
- version boundary note
- Orchestrator-only handoff rule
- no raw component bypass rule
- AdamantineOS remains final execution boundary

Potential SECURITY additions:

- Shield evidence boundary
- AI evidence boundary
- WSQK remains enforced
- Q-ID remains evidence/auth only
- replay/freshness requirements
- human approval context binding

Potential CHANGELOG additions:

- `Unreleased — Full Shield v3 Integration`
- not a tag until release gate passes

## Exit Criteria

```text
[ ] Docs are patched, not replaced blindly
[ ] No AdamantineOS v3.2.0 confusion
[ ] Docs match tests
[ ] Release status doc exists
```

---

## Phase 10 — Authorized Red Team / Red Hornet-Style Hardening

## Goal

Break the integrated system before release.

This phase must use the latest completed ZIPs from every repo.

## Required Attack Review

Test for:

- raw component bypass
- direct AI authority
- Q-ID authority escalation
- Adaptive Core hidden authority
- WSQK bypass
- Shield DENY override
- human approval reuse
- context hash mismatch
- replay / stale receipt
- receipt tampering
- unknown reason IDs
- unknown evidence families
- duplicate verdicts
- missing verdicts
- docs-vs-tests mismatch
- dependency / packaging weakness
- CI coverage weakness
- release checklist false-positive

## Required Report

Create:

```text
docs/ADAMANTINEOS_FULL_SHIELD_V3_RED_TEAM_REPORT.md
```

Report must include:

- attack category
- expected result
- actual result
- PASS / FAIL
- affected file/test
- fix required
- retest evidence

## Exit Criteria

```text
[ ] Red Team report complete
[ ] No critical/high findings unresolved
[ ] All fixes have regression tests
[ ] Final fresh ZIP audit passes
```

---

## Phase 11 — Final Release Gate

## Goal

Decide whether AdamantineOS can be tagged.

## Required Checklist

```text
[ ] Shield v3.2.0 repos tagged and stable
[ ] AdamantineOS integration branch complete
[ ] Full integration harness passes
[ ] CI green
[ ] Coverage gate satisfied
[ ] No raw component bypass
[ ] No Shield DENY override
[ ] No AI authority bypass
[ ] No Q-ID final authority bypass
[ ] No Adaptive Core final authority bypass
[ ] WSQK remains enforced
[ ] Replay/freshness enforced
[ ] Human review bound to exact context
[ ] Docs match tests
[ ] Security docs updated
[ ] Changelog updated
[ ] Release status doc updated
[ ] Red Team report complete
[ ] Final fresh ZIP audit complete
```

Only after all checks pass should AdamantineOS be considered for a new tag.

---

## Tagging Rule

Do not tag AdamantineOS until this roadmap is complete.

Potential future tag name must be chosen separately.

Do **not** use Shield `v3.2.0` as the AdamantineOS release tag.

AdamantineOS currently remains:

```text
v2.2.0 — WSQK v2 Quantum-Aware Upgrade
```

The future AdamantineOS release should describe full Shield v3 integration clearly, for example:

```text
AdamantineOS — Full Shield v3 Integration
```

The exact version number should be decided only after release scope is locked.

---

## Final Principle

Shield gives deterministic evidence.

The Orchestrator gives one deterministic Shield receipt.

AdamantineOS validates the receipt, then applies its own WSQK, Q-ID, Adaptive Core, AI boundary, replay, policy, and human-gate rules.

Only AdamantineOS can make the final wallet execution decision.

Slower is fastest.

Deny dominates.

Tests define truth.


---

## Integrated Amendment Notes

Author attribution: DarekDGB

## Purpose

This amendment strengthens the AdamantineOS Full Shield v3 Integration Roadmap before implementation begins.

It locks two important corrections:

1. The combined AdamantineOS context hash must be specified in a written contract before any implementation.
2. The Phase 8 integration harness must be scoped carefully before code so it does not become an unmanageable ten-repository test surface.

These are pre-implementation gates.

No integration code should begin until these gates are resolved.

---

## Amendment A — Canonical Combined Context Hash Contract Must Come Before Code

## Applies To

Roadmap Phase 2 — Canonical AdamantineOS Context Binding

## Problem

Phase 2 defines a combined context hash over multiple context domains:

- wallet context
- transaction context
- Q-ID authentication context
- WSQK posture context
- policy context
- replay / nonce context reference
- Shield receipt context

This is a security-critical canonicalization boundary.

If the canonicalization function is not specified before implementation, different components may interpret the same logical context differently.

That would create risks such as:

- mismatched hashes
- false rejects
- false accepts
- replay edge cases
- docs-vs-code mismatch
- incompatible test fixtures
- future integration drift

This is the same class of decision as the WSQK v2 `required_evidence_families` ordering rule.

The ordering and canonical form must be resolved in writing before code.

---

## Required New Pre-Phase

Add the following before Phase 2 implementation:

## Phase 2A — Combined Context Hash Contract

### Goal

Define the exact canonicalization function used to build the AdamantineOS combined context hash.

### Required Contract Document

Create:

```text
docs/ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md
```

### Contract Must Specify

The contract must define:

- canonical JSON rules
- allowed field names
- required field names
- forbidden field names
- field ordering rule
- array ordering rule
- map/object ordering rule
- null handling
- missing-field handling
- empty-object handling
- Unicode/string normalization policy
- integer handling
- decimal/float handling
- boolean handling
- timestamp policy
- randomness policy
- unknown-field policy
- domain separation string
- hash algorithm
- input envelope schema
- output format
- version field
- test vector examples

### Required Domain Separation

The combined context hash should include an explicit domain separation value, for example:

```text
ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1
```

The exact string must be locked in the contract and tests.

### Required Input Envelope

The contract should define a stable envelope similar to:

```json
{
  "contract": "adamantineos.combined_context_hash",
  "version": 1,
  "domain": "ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1",
  "request_id": "...",
  "wallet_context_hash": "...",
  "transaction_context_hash": "...",
  "qid_auth_context_hash": "...",
  "wsqk_posture_context_hash": "...",
  "policy_context_hash": "...",
  "replay_context_ref": "...",
  "shield_receipt_context_hash": "..."
}
```

This is an example only.

The final contract must define the exact schema before implementation.

### Required Test Vectors

The contract must include test vectors:

- valid full context
- same fields in different order produce same hash
- missing required field rejects
- extra unknown field rejects
- null required field rejects
- changed wallet hash changes combined hash
- changed transaction hash changes combined hash
- changed Q-ID hash changes combined hash
- changed WSQK hash changes combined hash
- changed policy hash changes combined hash
- changed replay context reference changes combined hash
- changed Shield receipt context hash changes combined hash

### Exit Criteria

```text
[ ] Combined context hash contract written
[ ] Schema locked
[ ] Canonicalization rules locked
[ ] Test vectors written
[ ] Failure cases written
[ ] No implementation begins before this contract is approved
```

---

## Amendment B — Phase 8 Integration Harness Must Be Scoped Before Code

## Applies To

Roadmap Phase 8 — Integration Harness

## Problem

Phase 8 spans up to ten repositories:

1. AdamantineOS
2. Shield Orchestrator
3. Guardian Wallet
4. QWG
5. ADN
6. DQSN
7. Sentinel AI
8. Q-ID
9. Adaptive Core
10. AI Gateway

A full live multi-repo harness can become too broad and unstable if implemented too early.

The harness must start with a strict, deterministic fixture-based scope.

It should prove boundary behavior first, not attempt to run every repository as a live integrated system on day one.

---

## Required New Pre-Phase

Add the following before Phase 8 implementation:

## Phase 8A — Integration Harness Scope Contract

### Goal

Define the exact scope of the first integration harness before code.

### Required Contract Document

Create:

```text
docs/ADAMANTINEOS_INTEGRATION_HARNESS_SCOPE.md
```

### Required Scope Levels

The harness should be split into levels.

## Level 1 — Fixture-Only Contract Harness

Purpose:

- no live cross-repo imports except AdamantineOS local code
- use frozen JSON fixtures representing valid outputs from Shield v3.2.0 components
- prove AdamantineOS boundary behavior
- prove Orchestrator receipt validation
- prove fail-closed policy

Level 1 must test:

- valid Orchestrator receipt accepted as evidence
- raw component verdict rejected
- Shield `DENY` blocks
- Shield `HUMAN_REVIEW_REQUIRED` does not auto-allow
- Shield `ALLOW` continues to AdamantineOS checks only
- context mismatch rejects
- receipt tampering rejects
- replay reference mismatch rejects
- AI authority bypass rejects
- Q-ID mismatch rejects
- WSQK posture mismatch rejects

## Level 2 — Adapter Contract Harness

Purpose:

- import AdamantineOS adapter code
- use fixture outputs from Shield v3.2.0
- validate adapter mapping to AdamantineOS internal decision states

Level 2 must test:

- Shield outcome mapping
- reason ID propagation
- evidence-family handling
- failure reason stability
- no hidden fallback

## Level 3 — Selected Live Shield Orchestrator Harness

Purpose:

- use the actual Shield Orchestrator package as one live dependency
- still use fixture component verdicts
- verify AdamantineOS can consume a receipt produced by the real Orchestrator

Level 3 must test:

- Orchestrator-built receipt accepted
- tampered Orchestrator receipt rejected
- unknown registry values rejected by Orchestrator before AdamantineOS
- AdamantineOS still rejects direct raw component bypass

## Level 4 — Full Multi-Repo Harness

Purpose:

- only after Levels 1–3 pass
- integrate more live repositories carefully
- avoid broad unstable coupling
- use pinned versions / tagged Shield v3.2.0 packages only

Level 4 must not begin until:

```text
[ ] Level 1 complete
[ ] Level 2 complete
[ ] Level 3 complete
[ ] packages/install paths are stable
[ ] CI runtime remains reasonable
[ ] failure output remains understandable
```

---

## Harness Scope Rules

The first integration harness must not:

- import all ten repositories immediately
- depend on network access
- depend on wall-clock time
- depend on randomness
- depend on local machine state
- require manual secrets
- require live blockchain access
- hide failures behind broad integration errors

The harness must:

- be deterministic
- be fixture-driven first
- be negative-test heavy
- fail closed
- explain exactly which boundary failed
- run in CI
- prove docs and tests agree

---

## Phase 8A Exit Criteria

```text
[ ] Harness scope contract written
[ ] Level 1 fixture scope defined
[ ] Level 2 adapter scope defined
[ ] Level 3 selected live Orchestrator scope defined
[ ] Level 4 full multi-repo scope deferred until safe
[ ] Test fixture format defined
[ ] No Phase 8 implementation begins before this contract is approved
```

---

## Roadmap Rule Update

Add this rule to the main roadmap:

```text
No AdamantineOS integration implementation begins until the combined context hash contract is written.

No full integration harness implementation begins until the harness scope contract is written.
```

---

## Updated Pre-Implementation Gate

Before implementation starts:

```text
[ ] Shield v3.2.0 tagged across six Shield repositories
[ ] AdamantineOS remains v2.2.0
[ ] latest ZIP baselines archived
[ ] ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md drafted and approved
[ ] ADAMANTINEOS_INTEGRATION_HARNESS_SCOPE.md drafted and approved
[ ] implementation branch created
[ ] no code written before the two contracts above are locked
```

---

## Final Note

Claude’s advice is accepted as a roadmap hardening correction.

This amendment strengthens the roadmap and prevents two dangerous mistakes:

1. implementing a security-critical hash before defining its canonical contract
2. creating an unbounded ten-repo integration harness too early

The correct path is:

- contract first
- scope first
- fixtures first
- negative tests first
- live integration later

Slower is fastest.

Deny dominates.

Tests define truth.
