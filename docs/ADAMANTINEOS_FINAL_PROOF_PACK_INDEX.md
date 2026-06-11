# DigiByte AdamantineOS Final Proof Pack Index

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Public project name: **DigiByte AdamantineOS**  
Current package version: `v3.0.0`  
Tag status: **approved v3.0.0 after release-stamp copy-back, CI green, and final fresh-ZIP verification**  
Milestone: **19 final release gate**

---

## 1. Purpose

This index maps the final AdamantineOS release-gate evidence set for the approved `v3.0.0` release tag.

It is a proof index for the final gate and must be verified again after copy-back before the tag command is run.

---

## 2. Primary evidence set

| Evidence area | Repository artifact |
| --- | --- |
| Full integration ledger | `docs/ADAMANTINEOS_FULL_INTEGRATION_BUILD_LEDGER.md` |
| Milestone 16 scope lock | `docs/ADAMANTINEOS_MILESTONE_16_LEVEL4_MULTI_REPO_SCOPE_LOCK.md` |
| Milestone 16B receipt harness | `docs/ADAMANTINEOS_MILESTONE_16B_SHIELD_ORCHESTRATOR_RECEIPT_CONTRACT_HARNESS.md` |
| Milestone 16C Shield baseline through orchestrator | `docs/ADAMANTINEOS_MILESTONE_16C_SHIELD_COMPONENT_BASELINE_THROUGH_ORCHESTRATOR.md` |
| Milestone 16D Q-ID external baseline | `docs/ADAMANTINEOS_MILESTONE_16D_Q_ID_EXTERNAL_BASELINE_COMPATIBILITY.md` |
| Milestone 16E Adaptive Core external baseline | `docs/ADAMANTINEOS_MILESTONE_16E_ADAPTIVE_CORE_EXTERNAL_BASELINE_COMPATIBILITY.md` |
| Milestone 16F AI Gateway external baseline | `docs/ADAMANTINEOS_MILESTONE_16F_AI_GATEWAY_EXTERNAL_BASELINE_COMPATIBILITY.md` |
| Milestone 16G full negative matrix | `docs/ADAMANTINEOS_MILESTONE_16G_FULL_LEVEL4_NEGATIVE_TEST_MATRIX.md` |
| Milestone 17 rebrand/proof/docs alignment | `docs/ADAMANTINEOS_MILESTONE_17_REBRAND_PROOF_PACK_AND_DOCS_ALIGNMENT.md` |
| Milestone 18 authorized findings | `docs/ADAMANTINEOS_MILESTONE_18_AUTHORIZED_RED_TEAM_FINDINGS.md` |
| Milestone 18 final closure report archive | `docs/RED_TEAM/ADAMANTINEOS_MILESTONE_18_FINAL_CLOSURE_REVIEW.docx` |
| Milestone 18 final closure report Markdown | `docs/RED_TEAM/ADAMANTINEOS_MILESTONE_18_FINAL_CLOSURE_REVIEW.md` |
| Milestone 19 final release gate | `docs/ADAMANTINEOS_MILESTONE_19_FINAL_RELEASE_GATE.md` |
| Milestone 19 tag decision | `docs/ADAMANTINEOS_MILESTONE_19_TAG_DECISION.md` |
| v3.0.0 release notes | `docs/ADAMANTINEOS_V3_0_0_RELEASE_NOTES.md` |

---

## 3. Runtime authority evidence

Milestone 19 relies on the following runtime authority evidence being present and regression-locked:

```text
- final policy engine is on the live runtime path
- legacy v1 executor path is final-policy gated
- Q-ID reject reaches final policy engine and denies
- Shield reject reaches final policy engine and denies
- WSQK reject reaches final policy engine and denies
- wallet_policy / EQC reject reaches final policy engine and denies
- replay / nonce reject reaches final policy engine and denies
- human gate reject reaches final policy engine and denies
- executor runs only after ALLOW_FINAL_ADAMANTINEOS_DECISION
- reject branch unexpected engine ALLOW fails closed
```

---

## 4. Test evidence

Latest inspected source evidence before release-stamp package copy-back:

```text
PYTHONPATH=src python -m pytest -q
925 passed
100.00% coverage
TOTAL 4097 statements, 0 missed
```

This proof was repeated after maintainer copy-back and fresh ZIP inspection. It must remain true after this release-stamp package is copied back before the tag command is run.

---

## 5. Release gate evidence rule

The final proof pack is valid only if:

```text
[x] Milestone 19 docs are copied back
[x] Fresh post-copy ZIP is inspected
[x] Tests pass again
[x] Coverage remains 100.00%
[x] Ledger and release gate agree
[x] Tag decision document remains explicit
[x] Maintainer explicitly approves tag creation after final copied-repo verification
```

AdamantineOS remains untagged until this release-stamp update is copied into the repository, CI remains green, and the final copied-repo ZIP is inspected. The approved tag is `v3.0.0`.
