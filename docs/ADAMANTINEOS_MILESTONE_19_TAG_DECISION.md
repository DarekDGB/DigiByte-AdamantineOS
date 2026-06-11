# DigiByte AdamantineOS Milestone 19 — Tag Decision

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Public project name: **DigiByte AdamantineOS**  
Release-stamped package version: `v3.0.0`  
Approved tag: `v3.0.0`  
Decision status: **approved after release-stamp copy-back, CI green, and final fresh-ZIP inspection**

---

## 1. Purpose

This document records the Milestone 19 tag decision boundary for DigiByte AdamantineOS `v3.0.0`.

It does not create the tag. It records the conditions that must be true before the maintainer runs the tag command.

---

## 2. Approved tag

```text
v3.0.0
```

---

## 3. Why v3.0.0 is defensible

`v3.0.0` is defensible as a major release because AdamantineOS has moved from the locked `v2.2.0` WSQK v2 release boundary into a fully documented final-policy runtime authority release boundary.

The repository now records:

```text
- Shield v3.2.0 baseline evidence through AdamantineOS boundaries
- final AdamantineOS policy engine wired into live runtime execution
- legacy v1 executor path gated by final policy
- per-source deny wiring for Q-ID, Shield, WSQK, wallet_policy/EQC, replay, and human gates
- reject branch divergence hardening
- no-debt red-team closure for F1-F8 and N1-N8
- 925 passing tests
- 100.00% coverage
- package version stamped as 3.0.0
```

---

## 4. Compatibility boundary

```text
Public project name: DigiByte AdamantineOS
Repository name: DigiByte-AdamantineOS
Internal package distribution name: adamantine-wallet-os
Python import paths: unchanged
```

The package distribution name is preserved for compatibility. Only the package version is bumped to `3.0.0` for the release.

---

## 5. Decision rule

The tag command remains blocked until all of the following are true:

```text
[ ] Release-stamp package copied into the repository
[ ] CI remains green
[ ] Fresh post-copy repository ZIP inspected
[ ] pyproject version confirmed as 3.0.0
[ ] README badge confirms v3.0.0
[ ] CHANGELOG contains v3.0.0 release section
[ ] Final proof-pack index confirms v3.0.0
[ ] Build ledger records v3.0.0 release stamp
[ ] Tests pass after post-copy inspection
[ ] Coverage remains 100.00%
```

---

## 6. Current decision

```text
Tag v3.0.0: APPROVED AFTER RELEASE-STAMP COPY-BACK AND FINAL FRESH-ZIP VERIFICATION
Package version: 3.0.0
Package/import rename: no
Runtime code change in release stamp: no
DigiByte consensus change: no
```
