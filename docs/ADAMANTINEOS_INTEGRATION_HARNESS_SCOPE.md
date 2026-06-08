# AdamantineOS Integration Harness Scope

Author attribution: **DarekDGB**  
Status: **Milestone 1 contract — pre-implementation lock**  
AdamantineOS release boundary: **v2.2.0 — WSQK v2 Quantum-Aware Upgrade**  
External Shield baseline: **Shield v3.2.0 tagged across the six Shield repositories**

## 1. Purpose

This document locks the scope of the AdamantineOS full Shield v3 integration harness before implementation begins.

The purpose is to prevent an unsafe unbounded live integration across many repositories at the start.

The harness must begin with deterministic fixtures, fail-closed boundaries, and negative tests before expanding toward live dependencies.

## 2. Core rule

```text
Contract first.
Fixture first.
Negative tests first.
Live integration later.
```

AdamantineOS must not start with a broad ten-repository live harness.

The integration harness is split into four levels.

## 3. Version and authority boundary

1. Shield v3.2.0 is the external Shield baseline.
2. AdamantineOS remains `v2.2.0` until full Shield integration is complete, tested, audited, and approved.
3. AdamantineOS must not be tagged during harness setup.
4. Shield outputs are evidence only.
5. The Shield Orchestrator receipt is the only valid Shield handoff boundary.
6. Raw component verdicts must be rejected as bypass attempts.
7. Shield `ALLOW` only permits AdamantineOS to continue its own checks.
8. Shield `DENY` must block.
9. `HUMAN_REVIEW_REQUIRED` must not become autonomous allow.

## 4. Repositories in the wider ecosystem

The wider integration ecosystem may eventually touch:

1. `DigiByte-Adamantine-Wallet-OS`
2. `DGB-Quantum-Shield-Orchestrator`
3. `DGB-Wallet-Guardian`
4. `DGB-Quantum-Wallet-Guard`
5. `DigiByte-ADN`
6. `DigiByte-Quantum-Shield-Network`
7. `DGB-Sentinel-AI`
8. `DigiByte-Q-ID`
9. `DigiByte-Adaptive-Core`
10. `adamantine-ai-gateway`

The first harness must not import or run all of these live.

## 5. Harness level overview

| Level | Name | Live dependencies | Purpose |
|---:|---|---|---|
| 1 | Fixture-only contract harness | AdamantineOS local code only | Prove boundary behavior using frozen JSON fixtures |
| 2 | AdamantineOS adapter harness | AdamantineOS adapter code only | Prove mapping from Shield receipt evidence into AdamantineOS internal states |
| 3 | Selected live Shield Orchestrator harness | AdamantineOS + live Shield Orchestrator only | Prove AdamantineOS can consume real Orchestrator-built receipts |
| 4 | Full multi-repo harness | Deferred | Expand carefully only after Levels 1–3 pass |

## 6. Level 1 — Fixture-only contract harness

### 6.1 Purpose

Level 1 proves AdamantineOS boundary behavior using frozen JSON fixtures.

It must not depend on live Shield repositories.

It must use known-good and known-bad fixtures representing Shield v3.2.0 Orchestrator receipts and bypass attempts.

### 6.2 Allowed scope

Level 1 may use:

- local AdamantineOS validation code
- local AdamantineOS test fixtures
- frozen JSON fixtures
- deterministic expected outputs
- local pytest execution

Level 1 must not use:

- live Shield Orchestrator package
- live Shield component packages
- Q-ID live package
- Adaptive Core live package
- AI Gateway live package
- network access
- blockchain access
- secrets
- wall-clock time
- randomness
- local machine state

### 6.3 Required fixture categories

Level 1 fixtures must include at minimum:

```text
valid_orchestrator_receipt_allow.json
valid_orchestrator_receipt_deny.json
valid_orchestrator_receipt_human_review.json
raw_component_verdict_bypass.json
tampered_receipt_hash.json
context_hash_mismatch.json
missing_required_field.json
unknown_top_level_field.json
unsupported_schema_version.json
unsupported_contract_version.json
fail_closed_false.json
shield_deny_with_handoff_allowed.json
human_review_with_autonomous_handoff.json
replay_reference_mismatch.json
qid_context_mismatch.json
wsqk_posture_mismatch.json
ai_authority_bypass_attempt.json
```

File names may be adjusted during implementation, but the categories must remain represented.

### 6.4 Required Level 1 tests

Level 1 must test:

- valid Orchestrator receipt accepted as evidence only
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
- missing required fields reject
- unknown fields reject
- unsupported versions reject
- `fail_closed != true` rejects

### 6.5 Level 1 exit criteria

```text
[ ] Fixture directory exists
[ ] Fixture manifest exists
[ ] Negative fixtures outnumber happy-path fixtures
[ ] Every fixture has an expected result
[ ] Raw component bypass is rejected
[ ] DENY dominates
[ ] HUMAN_REVIEW_REQUIRED cannot auto-allow
[ ] ALLOW is not final approval
[ ] Harness runs in CI
[ ] Failure output identifies the failed boundary
```

## 7. Level 2 — AdamantineOS adapter harness

### 7.1 Purpose

Level 2 imports AdamantineOS adapter code and validates how Shield Orchestrator receipt evidence maps into AdamantineOS internal decision states.

This is still AdamantineOS-only.

It must not import all Shield repositories.

### 7.2 Allowed scope

Level 2 may use:

- AdamantineOS Shield receipt adapter
- AdamantineOS combined context hash implementation
- AdamantineOS WSQK/Q-ID/policy/replay boundary mocks or fixtures
- frozen Shield v3.2.0 fixture outputs

Level 2 must not use:

- live Shield component packages
- full live Orchestrator dependency unless Level 3 has begun
- network access
- blockchain access
- secrets
- nondeterministic runtime state

### 7.3 Required Level 2 tests

Level 2 must test:

- Shield `ALLOW` maps only to continue-checks state
- Shield `DENY` maps to AdamantineOS block state
- Shield `HUMAN_REVIEW_REQUIRED` maps to review-required state
- reason IDs propagate deterministically
- unknown reason IDs fail closed unless explicitly mapped by contract
- evidence-family handling is deterministic
- adapter rejects missing evidence families where required
- adapter rejects duplicate evidence where forbidden
- adapter rejects context mismatch
- adapter rejects receipt hash mismatch
- adapter rejects raw component bypass
- adapter has no hidden fallback to allow
- AdamantineOS final decision still requires WSQK, Q-ID, policy, replay/freshness, and human-gate checks where applicable

### 7.4 Required internal state meaning

The adapter may produce internal states, but their meaning must be stable.

Minimum semantic states:

```text
SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS
SHIELD_BLOCK_DENY_DOMINATES
SHIELD_REVIEW_REQUIRED
SHIELD_REJECTED_INVALID_RECEIPT
SHIELD_REJECTED_CONTEXT_MISMATCH
SHIELD_REJECTED_RAW_COMPONENT_BYPASS
SHIELD_REJECTED_TAMPERED_RECEIPT
```

Names may change during implementation, but semantic coverage must not weaken.

### 7.5 Level 2 exit criteria

```text
[ ] Adapter harness exists
[ ] Adapter mapping is deterministic
[ ] Negative tests outnumber happy-path tests
[ ] No Shield ALLOW can final-approve execution
[ ] No raw component bypass path exists
[ ] Failure reason IDs are stable
[ ] Harness runs in CI
```

## 8. Level 3 — Selected live Shield Orchestrator harness

### 8.1 Purpose

Level 3 introduces the real Shield Orchestrator as the first live Shield dependency.

It still uses fixture component verdicts.

It proves that AdamantineOS can consume a receipt produced by the real Shield Orchestrator without giving raw components direct authority.

### 8.2 Allowed scope

Level 3 may use:

- AdamantineOS local code
- live Shield Orchestrator package pinned to the tagged Shield v3.2.0 baseline
- fixture component verdicts accepted by the Orchestrator
- deterministic expected AdamantineOS outcomes

Level 3 must not use:

- all six Shield component repositories live at once
- Q-ID live package unless specifically added in a later boundary phase
- Adaptive Core live package unless specifically added in a later boundary phase
- AI Gateway live package unless specifically added in a later boundary phase
- network access
- blockchain access
- secrets
- wall-clock dependent behavior
- randomness

### 8.3 Required Level 3 tests

Level 3 must test:

- real Orchestrator builds a receipt from fixture component verdicts
- Orchestrator-built receipt is accepted by AdamantineOS as evidence only
- tampered Orchestrator-built receipt is rejected
- unknown registry values are rejected before AdamantineOS handoff
- unknown evidence families are rejected before AdamantineOS handoff
- direct raw component verdict still rejected by AdamantineOS
- Shield `DENY` still blocks
- Shield `ALLOW` still cannot final-approve execution
- `HUMAN_REVIEW_REQUIRED` still cannot auto-allow
- failure output identifies whether failure came from Orchestrator or AdamantineOS boundary

### 8.4 Level 3 exit criteria

```text
[ ] Live Orchestrator package path is pinned and documented
[ ] Orchestrator receipt generation is deterministic
[ ] AdamantineOS validates Orchestrator-built receipt
[ ] Tampering rejection passes
[ ] Raw component bypass rejection still passes
[ ] No final approval comes from Shield alone
[ ] CI remains stable
[ ] Runtime remains acceptable
```

## 9. Level 4 — Full multi-repo harness

### 9.1 Purpose

Level 4 is deferred until Levels 1–3 are complete and stable.

It may gradually add more live repositories, but only after package paths, contracts, fixtures, and failure output are proven.

### 9.2 Hard start gate

Level 4 must not begin until all conditions below are true:

```text
[ ] Level 1 fixture-only harness passes
[ ] Level 2 adapter harness passes
[ ] Level 3 live Orchestrator harness passes
[ ] Combined context hash tests pass
[ ] Shield receipt adapter tests pass
[ ] package/install paths are stable
[ ] tagged versions are pinned
[ ] CI runtime remains acceptable
[ ] failure output remains understandable
[ ] docs and tests agree
[ ] explicit approval is recorded
```

### 9.3 Expansion rule

Level 4 must expand one dependency group at a time.

Recommended order:

```text
1. Guardian Wallet fixture-to-live boundary
2. QWG fixture-to-live boundary
3. ADN fixture-to-live boundary
4. DQSN fixture-to-live boundary
5. Sentinel AI fixture-to-live boundary
6. Q-ID boundary
7. Adaptive Core boundary
8. AI Gateway boundary
```

The order may change if a real defect or packaging constraint is discovered, but the reason must be recorded.

### 9.4 Level 4 must not

Level 4 must not:

- start by importing all ten repositories
- run unpinned branches
- depend on network access
- depend on live blockchain state
- require secrets
- hide errors behind generic integration failure
- silently skip unavailable packages
- silently convert missing evidence to allow
- make Shield or AI final signing authority
- bypass WSQK, Q-ID, policy, replay/freshness, or human-gate checks

### 9.5 Level 4 exit criteria

```text
[ ] Each added repository has a documented reason
[ ] Each added repository has negative tests
[ ] Each added repository is pinned to an approved version or commit
[ ] Failure boundaries remain clear
[ ] No hidden authority path is introduced
[ ] Full harness runs in CI or has a separately approved CI strategy
```

## 10. Negative-test-first rule

Every harness level must add negative tests before happy-path expansion.

Minimum negative categories:

```text
raw component bypass
tampered receipt
context mismatch
unknown field
missing field
unsupported version
unknown reason ID
unknown evidence family
duplicate evidence where forbidden
Shield DENY dominance
HUMAN_REVIEW_REQUIRED auto-allow attempt
Shield ALLOW as final approval attempt
replay/freshness mismatch
Q-ID mismatch
WSQK posture mismatch
policy mismatch
AI authority bypass
network unavailable must not become allow
package unavailable must not become allow
```

A level is not complete if it only proves happy path.

## 11. CI gates

Each harness level must define a CI gate before being considered complete.

Minimum CI rules:

1. Tests must run without network access.
2. Tests must not require secrets.
3. Tests must not require local machine-specific paths.
4. Tests must not rely on wall-clock time.
5. Tests must not rely on randomness.
6. Tests must not silently skip security-critical cases.
7. Coverage must not drop below the repository threshold.
8. Failure messages must identify the violated contract or boundary.
9. CI must install the package normally, not rely on hidden `PYTHONPATH` hacks.
10. Docs and tests must use the same contract names and reason meanings.

## 12. Audit gates

Before moving from one level to the next, perform an audit against this checklist:

```text
[ ] Does this level preserve AdamantineOS v2.2.0 boundary?
[ ] Does Shield remain external evidence only?
[ ] Does Shield ALLOW remain non-final?
[ ] Does DENY dominate?
[ ] Is HUMAN_REVIEW_REQUIRED prevented from autonomous allow?
[ ] Are raw component verdicts rejected?
[ ] Are unknown fields rejected?
[ ] Are unsupported versions rejected?
[ ] Are missing/invalid fixtures rejected?
[ ] Are negative tests more numerous than happy-path tests?
[ ] Is failure output clear?
[ ] Are package paths pinned or explicitly fixture-only?
[ ] Are docs and tests aligned?
[ ] Is there any new hidden authority path?
```

If any answer is unsafe or unknown, the next level must not begin.

## 13. Fixture format

Each fixture should be represented as JSON plus an expected result entry.

Recommended manifest shape:

```json
{
  "contract": "adamantineos.integration_harness_scope",
  "version": 1,
  "level": 1,
  "fixtures": [
    {
      "name": "raw_component_verdict_bypass",
      "path": "raw_component_verdict_bypass.json",
      "expected": "REJECT",
      "reason": "SHIELD_REJECTED_RAW_COMPONENT_BYPASS"
    }
  ]
}
```

The manifest itself must be deterministic and must not include timestamps or local paths.

## 14. Failure output requirement

Harness failures must identify one of these boundary classes:

```text
CONTRACT_SCHEMA_FAILURE
CANONICAL_CONTEXT_FAILURE
SHIELD_RECEIPT_FAILURE
RAW_COMPONENT_BYPASS_FAILURE
DENY_DOMINANCE_FAILURE
HUMAN_REVIEW_GATE_FAILURE
ADAMANTINE_POLICY_FAILURE
WSQK_BOUNDARY_FAILURE
QID_BOUNDARY_FAILURE
REPLAY_FRESHNESS_FAILURE
AI_AUTHORITY_BOUNDARY_FAILURE
PACKAGE_OR_INSTALL_FAILURE
DOCS_TEST_MISMATCH
```

Names may be finalized during implementation, but this semantic coverage must remain.

## 15. No Shield repository changes by default

Shield repositories are tagged at v3.2.0 and must be treated as stable external baselines.

Do not change Shield repositories during AdamantineOS harness work unless a real defect is found.

If a real defect is found:

1. Record the defect.
2. Prove it with a minimal failing case.
3. Decide whether the fix belongs in Shield or AdamantineOS.
4. Do not silently patch around a contract defect.
5. Do not retag AdamantineOS to hide the issue.

## 16. No implementation before review

No AdamantineOS integration implementation may begin until this document and `docs/ADAMANTINEOS_COMBINED_CONTEXT_HASH_CONTRACT.md` have both been reviewed and approved.

No AdamantineOS tag is allowed from this document alone.
