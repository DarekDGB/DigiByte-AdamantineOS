# DigiByte AdamantineOS Milestone 19 — Tag Decision

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Public project name: **DigiByte AdamantineOS**  
Current package version: `v2.2.0`  
Candidate tag: `v3.0.0`  
Decision status: **pending**

---

## 1. Purpose

This document records the Milestone 19 tag decision boundary.

It does not create a tag. It does not approve release by itself. It defines what must be true before AdamantineOS can be tagged.

---

## 2. Candidate tag

The candidate AdamantineOS tag is:

```text
v3.0.0
```

This candidate is under review because the completed Milestone 18 runtime hardening converted AdamantineOS into a live final-policy authority boundary with full per-source evidence-level deny wiring.

---

## 3. Why v3.0.0 is defensible

`v3.0.0` is defensible as a major AdamantineOS release boundary because the repository now contains:

```text
- Shield v3.2.0 baseline evidence through AdamantineOS boundaries
- final AdamantineOS policy engine wired into live runtime execution
- legacy v1 executor path gated by final policy
- per-source deny wiring for Q-ID, Shield, WSQK, wallet_policy/EQC, replay, and human gates
- no-debt red-team closure for F1-F8 and N1-N8
- 925 passing tests
- 100.00% coverage
```

This is a major authority-boundary change compared with the locked `v2.2.0` WSQK v2 release state.

---

## 4. Compatibility boundary

The following compatibility decisions remain locked unless a later controlled refactor explicitly changes them:

```text
Internal package distribution name: adamantine-wallet-os
Python import paths: unchanged
Public project name: DigiByte AdamantineOS
Repository name: DigiByte-AdamantineOS
```

The internal package distribution name is preserved for CI/package compatibility and does not define the public project name.

---

## 5. Decision rule

The tag decision remains blocked until all of the following are true:

```text
[ ] Milestone 19 final release gate document copied into the repository
[ ] Build ledger updated with Milestone 19 gate state
[ ] Final proof-pack index copied into the repository
[ ] Fresh post-copy repository ZIP inspected
[ ] Tests pass after post-copy inspection
[ ] Coverage remains 100.00%
[ ] No docs/package/import mismatch is introduced
[ ] Maintainer explicitly approves tag creation
```

---

## 6. Current decision

Current decision:

```text
Tag v3.0.0: NOT APPROVED YET
Release: NOT APPROVED YET
Version bump: NOT APPLIED YET
```

AdamantineOS remains `v2.2.0` and untagged until the final Milestone 19 gate is completed and verified.
