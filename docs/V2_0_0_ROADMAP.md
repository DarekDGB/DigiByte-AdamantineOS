# Adamantine Wallet OS — v2.0.0 Roadmap (Phase A–E)

**License:** MIT — **Author:** DarekDGB  
**Scope:** v2.0.0 reference runtime host + production envelope proof pack.

This roadmap is intentionally **invariants-first**:
no new runtime code until the boundary is frozen in docs.

---

## Phase A — v2.0.0 Constitution Docs

**Goal:** Freeze what “runtime separation + production envelope” means so we don’t drift later.

**Deliverables**
- `docs/CONTRACTS/runtime_host_boundary_v1.md` (reference host contract)
- `docs/CONTRACTS/runtime_artifact_log_v1.md` (what runtime may/may not emit)
- `docs/V2_RUNTIME_UNTRUSTED_MODEL.md` (runtime cannot weaken deny; invariants)

**Exit criteria**
- Docs present, consistent with existing v1.5.0 contracts
- No new code yet (pure spec freeze)

---

## Phase B — Reference Runtime Host (Minimal)

**Goal:** Implement a tiny reference host that integrators can copy.

**Deliverables**
- `src/adamantine/v2/runtime_host/...` (versioned)
- One function/class that:
  - accepts `MobileExecutionCall v2`
  - runs `orchestrator_v2`
  - if **ALLOW** → calls injected executor exactly once
  - returns response v2 (core unchanged) + executor result out-of-band

**Exit criteria**
- New unit tests for allow/deny paths pass
- Deterministic output (no time/random/global state)

---

## Phase C — Untrusted Runtime Test Pack (Fail-Closed Proof)

**Goal:** Prove runtime cannot bypass or mutate authority/decision.

**Test locks**
- DENY → executor never called
- ALLOW → executor called exactly once
- runtime cannot override:
  - verdict, reason_id, context_hash, protection_mode
- nonce consumed only on allow, exactly once
- hostile runtime artifacts ignored/fail-closed

**Exit criteria**
- All invariants covered by tests (negative-first)
- Multi-run determinism test for runtime host (50–100 repeats)

---

## Phase D — Production Envelope + Proof Pack v2.0.0

**Goal:** Seal “production-ready integration” with fixtures + hash lock.

**Deliverables**
- `src/adamantine/.../fixtures/v2_0_0_runtime/`
  - allow fixture(s)
  - deny fixture(s)
  - hostile fixture(s)
- `manifest.json` hash lock
- Conformance tests:
  - strict schema validation
  - exact fixture set enforcement
  - hash mismatch → CI fail

**Exit criteria**
- Proof pack tests pass
- Any payload drift breaks CI deterministically

---

## Phase E — Coverage Tightening + Release

**Goal:** Make “v2.0.0 complete” undeniable.

**Rule**
- ✅ No tag until: tests + proof pack + coverage target are green in CI.

**Coverage focus**
- runtime host
- envelope / boundary
- TVA + nonce enforcement interactions
- “if allow then execute” path

**Exit criteria before tag**
- CI green
- Coverage ≥ target (aim ~93–95% actual; keep fail-under stable unless safe)
- Proof pack locked
- Docs finalized

Then:
- Update `CHANGELOG.md` for v2.0.0
- Tag `v2.0.0`

---
