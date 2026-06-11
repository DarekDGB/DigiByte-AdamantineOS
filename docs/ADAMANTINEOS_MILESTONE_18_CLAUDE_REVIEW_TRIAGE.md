# DigiByte AdamantineOS Milestone 18 — Claude Red-Team Review Triage

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Milestone: 18  
Status: accepted for hardening  
Version boundary: `v2.2.0` remains unchanged  
Tag status: AdamantineOS remains untagged

## Purpose

This document records the triage of the external Claude AI Milestone 18 red-team review. The review was treated as an authorized architecture/source-level review input and was validated against the fresh `DigiByte-AdamantineOS` repository after Milestone 17 completion.

The triage rule is strict:

```text
Valid findings must be fixed or explicitly re-scoped before Milestone 18 can close.
No finding may be silently ignored.
No AdamantineOS tag is allowed while Milestone 18 remains open.
```

## Finding triage

| ID | Severity | Finding | Milestone 18 decision | Resolution in this patch |
| --- | --- | --- | --- | --- |
| F1 | HIGH | Audited final policy engine was not on the live runtime decision path. | Accepted. Fix with Option A. | `orchestrator_v2` now invokes `evaluate_final_policy_engine` before executor execution. Runtime tests prove final-policy DENY blocks executor. |
| F2 | MEDIUM | No cross-evidence context binding inside the final policy engine. | Accepted. Fix. | `evaluate_final_policy_engine(..., expected_context_hash=...)` now denies mismatched/missing evidence context when a runtime context hash is supplied. |
| F3 | LOW | `final_approval` bypass guard used strict identity (`is True`). | Accepted. Fix. | Any truthy upstream `final_approval` now fails closed as authority bypass. |
| F4 | LOW | Hard DENY could be reported as `HUMAN_REVIEW_REQUIRED`. | Accepted. Fix. | Evidence/local hard DENY now dominates human-review signals. |
| F5 | LOW | Hidden-authority scan missed `__slots__` objects and some nested containers. | Accepted. Fix. | Scanner now handles mapping, list, tuple, set, `__dict__`, and `__slots__` evidence. |
| F6 | NOTE | Human-review detection relied on substring matching. | Accepted. Harden. | Human review is now exact typed/status equality only. |
| F7 | NOTE | Evidence-supplied reason IDs flowed into output unvalidated at engine layer. | Accepted. Harden. | Unknown evidence reason IDs are sanitized to `UNKNOWN_EXTERNAL_REASON` at the engine/runtime boundary. |
| F8 | NOTE | Milestone 18 was being run ahead of Milestone 17. | Resolved before patch. | Milestone 17 was completed first with proof pack, docs alignment, rebrand, and 902 passing tests. |

## Option A decision

Milestone 18 uses **Option A**:

```text
Wire the final policy engine into the live runtime path.
```

The live path is now:

```text
RuntimeHostV2
-> run_mobile_execution_call_v2
-> orchestrate_execution_v2
-> parse / adapters / EQC
-> TVA nonce/replay enforcement
-> evaluate_final_policy_engine
-> executor.execute only after final AdamantineOS allow
```

TVA enforcement is intentionally completed before final policy evaluation so replay/nonce evidence can be represented truthfully. The executor remains blocked until the final AdamantineOS policy engine returns `ALLOW_FINAL_ADAMANTINEOS_DECISION`.

## Red-team confirmation tests

The Milestone 18 regression test file is:

```text
tests/test_milestone_18_authorized_red_team_review.py
```

It proves:

```text
F1: live runtime invokes final policy before executor
F2: cross-context splice denies at the engine
F3: truthy final_approval fails closed
F4: DENY dominates HUMAN_REVIEW_REQUIRED
F5: __slots__ and nested containers are scanned
F6: human-review detection requires exact status
F7: unknown reason IDs are sanitized
```

## Current verification

Local verification after the Milestone 18 patch:

```text
PYTHONPATH=src python -m pytest -q
```

Result:

```text
914 tests collected
914 passing
100.00% coverage
```

## Release status

Milestone 18 is **not closed yet** until the maintainer applies the copy-only patch, uploads the fresh ZIP, and a second external Claude AI red-team confirmation is performed.

AdamantineOS remains:

```text
version: v2.2.0
tag status: untagged
package/import names: unchanged
Milestone 19: blocked pending second red-team confirmation
```
