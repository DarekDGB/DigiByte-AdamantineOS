# DigiByte AdamantineOS Milestone 18 — Second Red-Team Handoff

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Milestone: 18  
Status: handoff document for second Claude AI review  
Version boundary: `v2.2.0` remains unchanged  
Tag status: AdamantineOS remains untagged

## Purpose

After the Milestone 18 hardening patch is applied and tests pass, this document should be given to Claude AI for a second red-team confirmation.

The requested review is not a general compliment pass. It should specifically try to falsify whether F1-F7 were really fixed and whether the new runtime wiring introduced any new bypass.

## Ask Claude AI to verify

```text
Please perform a second authorized Milestone 18 red-team review of this fresh DigiByte-AdamantineOS ZIP.

Focus on the fixes for:
F1 final policy engine live runtime wiring
F2 cross-evidence context binding
F3 truthy final_approval bypass
F4 DENY vs HUMAN_REVIEW_REQUIRED ordering
F5 hidden authority scan over __slots__ and nested containers
F6 exact human-review detection
F7 reason-ID sanitization at engine/runtime boundary

Also check whether the Milestone 18 patch introduced any new fail-open behavior, fake authority, executor-before-final-policy path, docs-vs-tests mismatch, or release-gate overclaim.

AdamantineOS must remain v2.2.0 and untagged.
Milestone 19 must remain blocked until this second red-team confirmation is clean or all new findings are fixed.
```

## Evidence to inspect

```text
src/adamantine/v1/policy/final_policy_engine.py
src/adamantine/v1/execution/orchestrator_v2.py
tests/test_milestone_18_authorized_red_team_review.py
docs/ADAMANTINEOS_MILESTONE_18_CLAUDE_REVIEW_TRIAGE.md
docs/ADAMANTINEOS_MILESTONE_18_AUTHORIZED_RED_TEAM_FINDINGS.md
docs/ADAMANTINEOS_FULL_INTEGRATION_BUILD_LEDGER.md
```

## Current local proof before second review

```text
PYTHONPATH=src python -m pytest -q
914 passing
100.00% coverage
```

## Maintainer rule

A clean local test run does not automatically close Milestone 18. Milestone 18 closes only after fresh ZIP inspection and second red-team confirmation.

## Third confirmation request after N1/N2 second patch

Claude's second review found N1 and N2. The second Milestone 18 patch claims to fix them.

Ask Claude to verify specifically:

```text
Please perform a third authorized Milestone 18 confirmation review of the fresh DigiByte-AdamantineOS ZIP.

Previous second-review blockers:
N1 MEDIUM - final policy engine was fed synthetic always-ALLOW runtime evidence.
N2 MEDIUM - legacy orchestrate_execution_v1 was an executor-running path without final policy engine gating.

New fix claims:
- orchestrator_v2 no longer feeds unconditional always-ALLOW runtime constants into evaluate_final_policy_engine.
- v2 final-policy inputs are derived after real runtime evidence boundaries accept Shield, Q-ID, Adaptive Core oracle, WSQK authority, EQC, TVA/replay, wallet_policy, and human gate status.
- a live EQC deny now reaches evaluate_final_policy_engine and stops at the wallet_policy gate before executor execution.
- orchestrator_v1 no longer uses boundary.run_with_tva as an executor-running shortcut; it enforces TVA, then calls evaluate_final_policy_engine, then executes only after final ALLOW.
- runtime_adapter docs no longer instruct implementers to wire live execution around the final policy engine.

Please try to break these claims. Confirm whether N1 and N2 are fixed, partially fixed, or still open. Also look for any new bypass, fail-open path, executor-before-final-policy path, synthetic evidence overclaim, v1/v2 shadowing trap, docs-vs-tests mismatch, or release-gate overclaim.

Do not approve tagging. AdamantineOS must remain v2.2.0 and untagged. Milestone 19 remains blocked unless this review is clean.
```

Current local proof before this third review:

```text
PYTHONPATH=src python -m pytest -q
917 passed
100.00% coverage
```


## Fourth confirmation request after Option 2 full evidence-level wiring

Claude's third review left N1 partially fixed and offered two options. The maintainer selected **Option 2**: full evidence-level wiring instead of accepted residual scope.

Ask Claude to verify specifically:

```text
Please perform a fourth authorized Milestone 18 confirmation review of the fresh DigiByte-AdamantineOS ZIP.

Previous third-review residual:
N1 was partially fixed because only EQC denial reached the final policy engine, while Shield / Q-ID / WSQK structural rejects still denied upstream, and replay/human gates were not fully runtime-fed.

New Option 2 fix claims:
- Q-ID adapter/verifier failures now reach evaluate_final_policy_engine as rejected qid evidence.
- Q-ID replay proof failures now reach evaluate_final_policy_engine as rejected qid evidence and failed replay gate.
- Adaptive Core oracle failures now reach evaluate_final_policy_engine as rejected adaptive_core evidence.
- Shield adapter, structural, context, and required-layer failures now reach evaluate_final_policy_engine as rejected shield evidence.
- Missing/invalid WSQK authority now reaches evaluate_final_policy_engine as rejected wsqk_v2 evidence.
- TVA / nonce replay failure now reaches evaluate_final_policy_engine as a failed replay local gate.
- Human confirmation failure now reaches evaluate_final_policy_engine as a failed human local gate.
- EQC deny still reaches evaluate_final_policy_engine as wallet_policy failure.
- Executor execution still occurs only after ALLOW_FINAL_ADAMANTINEOS_DECISION.
- No source rejection should bypass the final policy engine unless the envelope itself cannot be parsed.

Regression tests added:
test_milestone_18_option2_qid_reject_reaches_final_policy_engine
test_milestone_18_option2_shield_reject_reaches_final_policy_engine
test_milestone_18_option2_wsqk_reject_reaches_final_policy_engine
test_milestone_18_option2_replay_gate_reject_reaches_final_policy_engine
test_milestone_18_option2_human_gate_reject_reaches_final_policy_engine
test_milestone_18_outer_tva_error_path_remains_fail_closed_for_bad_wsqk_v2_scope

Please try to break these claims. Confirm whether N1 is now fixed, partially fixed, or still open. Also look for any new bypass, fail-open path, executor-before-final-policy path, synthetic evidence overclaim, v1/v2 shadowing trap, docs-vs-tests mismatch, package/CI reality gap, reason-ID drift, replay/nonce assumption, or release-gate overclaim.

Do not approve tagging. AdamantineOS must remain v2.2.0 and untagged. Milestone 19 remains blocked unless this review is clean.
```

Current local proof before fourth review:

```text
PYTHONPATH=src python -m pytest -q
923 passed
100.00% coverage
```
