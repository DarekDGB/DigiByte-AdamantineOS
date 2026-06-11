# DigiByte AdamantineOS Milestone 18 — Authorized Red-Team Findings

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Milestone: 18  
Status: hardening patch prepared, second red-team confirmation pending  
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

## Findings fixed in this patch

### M18-F1 — Final policy engine was not live runtime authority

Status: **fixed in patch**

The live runtime path now invokes `evaluate_final_policy_engine` before executor execution. The executor is called only after final AdamantineOS allow.

Regression proof:

```text
test_claude_f1_live_runtime_invokes_final_policy_before_executor
```

### M18-F2 — Cross-evidence context splice defense needed at final engine

Status: **fixed in patch**

The final policy engine now accepts an `expected_context_hash` and denies mismatched/missing evidence context when supplied.

Regression proof:

```text
test_claude_f2_cross_context_splice_denies_at_engine
```

### M18-F3 — Truthy upstream final approval bypass signal

Status: **fixed in patch**

Any truthy upstream `final_approval` fails closed as authority bypass.

Regression proof:

```text
test_claude_f3_truthy_final_approval_and_slots_are_authority_bypass
```

### M18-F4 — DENY must dominate human review

Status: **fixed in patch**

Rejected evidence and failed local gates are evaluated before human-review handling. A hard DENY cannot be softened into `HUMAN_REVIEW_REQUIRED`.

Regression proof:

```text
test_claude_f4_deny_dominates_over_human_review_signal
```

### M18-F5 — Hidden authority scan coverage

Status: **fixed in patch**

The final engine scans mapping/list/tuple/set structures and object `__dict__` / `__slots__` values for forbidden authority signals.

Regression proof:

```text
test_claude_f5_slots_and_nested_containers_are_scanned
test_claude_f5_set_container_scan_branch_is_locked
test_string_slots_hidden_authority_branch_is_locked
```

### M18-F6 — Human-review detection must be exact

Status: **fixed in patch**

Human review is detected only by exact status equality, not substring search.

Regression proof:

```text
test_claude_f6_human_review_requires_exact_status_not_substring
```

### M18-F7 — Reason ID sanitization

Status: **fixed in patch**

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
fresh patched ZIP is uploaded back
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

Milestone 18 remains open until these are fixed and re-reviewed.

### M18-N1 — Semantic runtime evidence wiring

Status: **fixed in second patch**

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

Status: **fixed in second patch**

`orchestrate_execution_v1` no longer calls the executor through `boundary.run_with_tva`. It enforces TVA first, then calls `evaluate_final_policy_engine()`, and only then calls `executor.execute()` if the final AdamantineOS decision is ALLOW.

The v1 runtime adapter documentation now warns that live execution must not route around the final policy engine.

Regression proof:

```text
test_claude_n2_legacy_v1_executes_only_after_final_policy
test_claude_n2_v1_final_policy_reason_sanitizes_bad_values
```

### M18-N3/N4/N5 — Documentation and placeholder clarity

Status: **updated / tracked**

- Docs now record that the second review found N1/N2 and that the second patch removes the unconditional synthetic runtime evidence pattern.
- The `ai_gateway:not_required_for_runtime_path` marker is intentionally not an approval source. It means the live wallet runtime path is not AI Gateway ingress. It is still evidence-only and cannot grant final approval by itself.
- Local gates are no longer all merely decorative: EQC deny flows into the `wallet_policy` gate and TVA success feeds the `replay` gate before executor execution.

## Second-patch verification

```text
PYTHONPATH=src python -m pytest -q
917 passed
100.00% coverage
```

Milestone 18 still must not be closed until a fresh patched ZIP is inspected and Claude AI performs another confirmation review.
 

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
