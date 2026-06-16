# DigiByte AdamantineOS Milestone 18 — Authorized Red-Team Findings

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Milestone: 18  
Status: hardening prepared, second red-team confirmation pending  
Version boundary: `v2.2.0` remains unchanged  
Tag status: AdamantineOS remains untagged

## Scope

This Milestone 18 review is authorized only against DarekDGB-owned uploaded repository files.

Out of scope:

```text
public network attacks
third-party targets
live wallets or user funds
credential testing
malware or persistence
destructive testing
exploit deployment
```

## Findings fixed in this hardening

### M18-F1 — Final policy engine was not live runtime authority

Status: **fixed in hardening**

The live runtime path now invokes `evaluate_final_policy_engine` before executor execution. The executor is called only after final AdamantineOS allow.

Regression proof:

```text
test_claude_f1_live_runtime_invokes_final_policy_before_executor
```

### M18-F2 — Cross-evidence context splice defense needed at final engine

Status: **fixed in hardening**

The final policy engine now requires an `expected_context_hash` and denies mismatched or missing evidence context on every evaluation.

Regression proof:

```text
test_claude_f2_cross_context_splice_denies_at_engine
```

### M18-F3 — Truthy upstream final approval bypass signal

Status: **fixed in hardening**

Any truthy upstream `final_approval` fails closed as authority bypass.

Regression proof:

```text
test_claude_f3_truthy_final_approval_and_slots_are_authority_bypass
```

### M18-F4 — DENY must dominate human review

Status: **fixed in hardening**

Rejected evidence and failed local gates are evaluated before human-review handling. A hard DENY cannot be softened into `HUMAN_REVIEW_REQUIRED`.

Regression proof:

```text
test_claude_f4_deny_dominates_over_human_review_signal
```

### M18-F5 — Hidden authority scan coverage

Status: **fixed in hardening**

The final engine scans mapping/list/tuple/set structures and object `__dict__` / `__slots__` values for forbidden authority signals.

Regression proof:

```text
test_claude_f5_slots_and_nested_containers_are_scanned
test_claude_f5_set_container_scan_branch_is_locked
test_string_slots_hidden_authority_branch_is_locked
```

### M18-F6 — Human-review detection must be exact

Status: **fixed in hardening**

Human review is detected only by exact status equality, not substring search.

Regression proof:

```text
test_claude_f6_human_review_requires_exact_status_not_substring
```

### M18-F7 — Reason ID sanitization

Status: **fixed in hardening**

Unknown evidence-supplied reason IDs are sanitized to `UNKNOWN_EXTERNAL_REASON` at the engine/runtime boundary.

Regression proof:

```text
test_claude_f7_unknown_reason_ids_are_sanitized_at_engine_layer
test_runtime_final_policy_reason_handles_non_string_reason
```

## Additional internal red-team observations

### M18-A1 — Runtime has no top-level human-review status

Decision: preserve response contract.

`execution_response_v2.status` remains one of:

```text
allow
deny
error
```

A final-policy `HUMAN_REVIEW_REQUIRED` result maps to runtime `status="deny"` with `artifacts.final_policy.outcome="HUMAN_REVIEW_REQUIRED"`. This keeps runtime fail-closed and avoids a contract-breaking status expansion.

### M18-A2 — No fake execution after TVA

Decision: executor remains blocked until final policy allow.

Milestone 18 separates TVA enforcement from executor execution. TVA may consume nonce/replay state first, then the final policy engine decides whether execution may occur.

### M18-A3 — AI Gateway live-runtime representation

Decision: live wallet/runtime requests that are not sourced from the AI Gateway are represented as `runtime_non_ai_gateway_path` evidence. This is not final approval and cannot grant authority. It only states that the live runtime path is not an AI Gateway ingress path. The final policy engine still computes final approval itself.

## Verification

Command:

```text
PYTHONPATH=src python -m pytest -q
```

Result:

```text
914 passing
100.00% coverage
```

## Exit condition

Milestone 18 must not close until:

```text
fresh hardened ZIP is uploaded back
fresh ZIP is inspected
all tests remain green
coverage remains 100.00%
Claude AI performs second red-team confirmation
all second-pass findings are fixed or explicitly accepted with rationale
AdamantineOS remains untagged
```

## Second Claude red-team confirmation triage

A second authorized Claude review returned `PASS WITH NOTES`, not a clean close. It confirmed F2-F8 were fixed and F1 was structurally fixed, but identified two new Milestone 18 blockers:

```text
N1 MEDIUM - final policy engine was fed synthetic always-ALLOW runtime evidence
N2 MEDIUM - legacy orchestrate_execution_v1 remained an executor-running path without final policy engine gating
```

At this stage, Milestone 18 remained open until these were fixed and re-reviewed. Both were later resolved through the second fix pass, Option 2 full evidence-level wiring, and final no-debt closure hardening.

### M18-N1 — Semantic runtime evidence wiring

Status: **fixed in second hardening pass**

The v2 runtime path no longer feeds `_runtime_evidence_allow()` constants into the final policy engine. The final policy inputs are now built only after the corresponding live runtime evidence boundary has accepted the request:

```text
shield       <- parsed ShieldBundleV3
wsqk_v2      <- validated WSQK authority proof
qid          <- parsed Q-ID session proof
adaptive_core<- parsed Adaptive Core oracle v3 result
ai_gateway   <- explicit not-required marker for non-AI runtime ingress
replay       <- TVA/replay gate result after enforce_tva succeeds
wallet_policy<- EQC result, including live EQC denies
human        <- explicit local human gate result
```

A live EQC deny now reaches `evaluate_final_policy_engine()` and is stopped by the final engine at the `wallet_policy` gate before executor execution.

Regression proof:

```text
test_claude_n1_eqc_deny_reaches_final_policy_engine
```

### M18-N2 — Legacy v1 executor path fenced by final policy

Status: **fixed in second hardening pass**

`orchestrate_execution_v1` no longer calls the executor through `boundary.run_with_tva`. It enforces TVA first, then calls `evaluate_final_policy_engine()`, and only then calls `executor.execute()` if the final AdamantineOS decision is ALLOW.

The v1 runtime adapter documentation now warns that live execution must not route around the final policy engine.

Regression proof:

```text
test_claude_n2_legacy_v1_executes_only_after_final_policy
test_claude_n2_v1_final_policy_reason_sanitizes_bad_values
```

### M18-N3/N4/N5 — Documentation and placeholder clarity

Status: **updated / tracked**

- Docs now record that the second review found N1/N2 and that the second hardening pass removes the unconditional synthetic runtime evidence pattern.
- The `ai_gateway:not_required_for_runtime_path` marker is intentionally not an approval source. It means the live wallet runtime path is not AI Gateway ingress. It is still evidence-only and cannot grant final approval by itself.
- Local gates are no longer all merely decorative: EQC deny flows into the `wallet_policy` gate and TVA success feeds the `replay` gate before executor execution.

## Second-hardening verification

```text
PYTHONPATH=src python -m pytest -q
917 passed
100.00% coverage
```

Milestone 18 still must not be closed until a fresh hardened ZIP is inspected and Claude AI performs another confirmation review.
 

## Third-review residual N1 and Option 2 decision

Claude AI's third confirmation review verified N2 as fixed and found no new HIGH/MEDIUM issues, but kept N1 only partially fixed because Shield / Q-ID / WSQK failures could still deny upstream before reaching the final policy engine, while replay and human gates were still not fully runtime-fed.

Maintainer decision: **do not close Milestone 18 on accepted residual scope**. Option 2 is selected.

Option 2 fix expands runtime evidence-level wiring so each relevant live failure can be represented inside `evaluate_final_policy_engine`:

```text
qid rejected          -> stopped_at=qid
shield rejected       -> stopped_at=shield
wsqk_v2 rejected      -> stopped_at=wsqk_v2
adaptive_core rejected-> stopped_at=adaptive_core
replay rejected       -> stopped_at=replay
human rejected        -> stopped_at=human
EQC rejected          -> stopped_at=wallet_policy
```

This corrects the earlier N6 wording issue by no longer claiming only aggregate EQC wiring as full evidence wiring. Milestone 18 remains open pending fourth Claude confirmation review.


### Milestone 18 N7 closure — EQC / wallet_policy gate semantics

EQC aggregate runtime policy verdict is intentionally surfaced through the stable wallet_policy local gate. This is a contract-preserving audit note: the final policy engine keeps the stable `wallet_policy` local gate name, while docs explicitly define that live EQC aggregate policy failures are represented there.


## Fourth-review no-debt closure: N8/N7

Claude AI's fourth confirmation review returned `PASS WITH NOTES` and stated Milestone 18 can close, with only N8 and N7 remaining as non-blocking notes. The maintainer selected no-debt closure instead of carrying those notes into Milestone 19.

### N8 closure

Reject branches now explicitly fail closed if a future refactor ever makes `evaluate_final_policy_engine()` return `ALLOW_FINAL_ADAMANTINEOS_DECISION` while the runtime branch is already handling a rejected source. The runtime response remains `deny`, uses `DENY_POLICY`, and records a `final_policy_invariant` artifact.

Regression proof:

```text
test_milestone_18_n8_reject_branch_unexpected_engine_allow_fails_closed
```

### N7 closure

EQC aggregate runtime policy verdict is intentionally surfaced through the stable wallet_policy local gate. This preserves the locked final-policy local-gate contract while making the audit meaning explicit for future reviewers.

Regression proof:

```text
test_milestone_18_n7_eqc_wallet_policy_mapping_is_explicit_in_docs
```

Milestone 18 closure hardening was copied, CI stayed green, and the fresh ZIP was inspected. Milestone 18 is complete. AdamantineOS remains v2.2.0 and untagged until Milestone 19.


## Final Milestone 18 closure verification

Status: **complete**.

Final proof after no-debt N8/N7 closure:

```text
PYTHONPATH=src python -m pytest -q
925 passed
100.00% coverage
TOTAL 4097 statements, 0 missed
```

Closure result:

```text
F1-F8 resolved.
N1 fixed by full per-source evidence-level runtime wiring.
N2 fixed by final-policy gating of v1 execution.
N7 closed with explicit EQC -> wallet_policy audit semantics.
N8 fixed with reject-branch final-policy divergence hardening.
No HIGH/MEDIUM/LOW red-team finding remains open.
No known red-team note is carried forward as technical debt.
Milestone 18 complete.
AdamantineOS remains v2.2.0 and untagged.
Milestone 19 remains pending.
```

## Final external closure report

The final Claude AI closure review is preserved as:

```text
docs/RED_TEAM/ADAMANTINEOS_MILESTONE_18_FINAL_CLOSURE_REVIEW.docx
```

Final verdict:

```text
PASS - Milestone 18 can be closed
```

The final closure review verified that N1 remains fixed, N2 remains fixed, N7 is closed, N8 is fixed, and no HIGH/MEDIUM/LOW/NOTE finding remains open. No known red-team note is carried forward as technical debt.

This final closure report does not authorize release or tagging. AdamantineOS remains v2.2.0 and untagged until Milestone 19.
