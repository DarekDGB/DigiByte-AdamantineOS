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
