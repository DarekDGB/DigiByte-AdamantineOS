# AdamantineOS — v1.5.0 Roadmap (Option C)

**License:** MIT — **Author:** DarekDGB  
**Scope:** v1.5.0 implementation plan for the **Mobile SDK Contract Pack** (contract-first, deterministic, fail-closed).  
**Status:** Planning document (normative exit criteria).

---

## 0. Non‑Negotiables

v1.5.0 is **not** “write some docs”. It is **integration immunity**:

- **Contract-first:** mobile teams must integrate without guessing.
- **Fail‑closed:** unknown fields, missing fields, or shape drift must be rejected deterministically.
- **Deterministic:** repeated runs produce identical outputs (reason_id, context_hash, artifacts shape, protection_mode).
- **Version discipline:** any schema break → **major version bump**, never silent.

**Option C** means: keep everything inside the Adamantine repo, but isolate it cleanly:
- `contracts/` (machine-readable contract assets)
- `src/adamantine/v1/mobile_contract/` (tiny guardrail helpers; no runtime features)
- `tests/mobile_conformance/` (fixture roundtrip + schema enforcement)

---

## 1. v1.5.0 Goal

Freeze the **mobile → Adamantine execution boundary** so mobile teams can integrate using only:
- **docs**
- **fixtures**
- **schemas**
- **conformance tests**

This aligns with the existing roadmap definition of **v1.5.0 Mobile SDK Contract Pack**, including protection_mode interpretation and fixture-based conformance. fileciteturn0file0

---

## 2. Deliverables (What “Done” Means)

### D1 — Frozen Mobile Call Contract v2 (Normative)
Create **v2** contract docs that define exact shapes and rules:

- `docs/CONTRACTS/mobile_execution_call_v2.md`
- `docs/CONTRACTS/mobile_decision_result_v2.md`

Must include:
- Required + optional fields
- Forbidden fields (reject unknown)
- Canonical ordering rules
- Canonicalization algorithm definition (bytes-level)
- Hashing rules for context_hash inputs
- Version fields and upgrade rules
- Examples for legacy/minimal/full with **protection_mode**

### D2 — Machine-Readable Schemas (Reject Unknown / Missing)
Add JSON Schema assets (strict):

- `contracts/mobile_request_v2.schema.json`
- `contracts/mobile_response_v2.schema.json`

Rules:
- `additionalProperties: false` everywhere
- Required fields explicitly listed
- Enumerations locked (including `protection_mode`)
- Schema ids include explicit version

### D3 — Golden Fixture Pack (Roundtrip Lock)
Add fixture pack:

- `fixtures/mobile/v1_5_0/request_legacy.json`
- `fixtures/mobile/v1_5_0/request_minimal.json`
- `fixtures/mobile/v1_5_0/request_full.json`

And expected outputs:

- `fixtures/mobile/v1_5_0/response_legacy.json`
- `fixtures/mobile/v1_5_0/response_minimal.json`
- `fixtures/mobile/v1_5_0/response_full_allow.json`
- `fixtures/mobile/v1_5_0/response_full_deny.json`

Plus a hash manifest:

- `fixtures/mobile/v1_5_0/manifest.json`

Manifest rule: if any fixture changes, CI fails unless manifest updated **in the same change**.

### D4 — Reason Registry for Mobile (Hash-Locked)
Create a machine-readable reason registry intended for UI mapping:

- `contracts/reason_registry_mobile_v1.json`
- `docs/CONTRACTS/reason_registry_mobile_v1.md` (human-readable companion)

Lock it with a manifest:

- `contracts/reason_registry_mobile_v1.manifest.json`

Rules:
- No deletions without major bump
- No semantic meaning change without major bump
- All reason_ids used by mobile fixtures must exist in registry

### D5 — Mobile Conformance Test Suite (Strict Equality)
Create conformance test pack:

- `tests/mobile_conformance/test_mobile_roundtrip_v1_5_0.py`

Tests must:
1. Validate request fixture against `mobile_request_v2.schema.json`
2. Execute orchestrator_v2 (same path used by existing OS proof packs)
3. Validate response against `mobile_response_v2.schema.json`
4. Compare full JSON equality against expected response fixture
5. Run determinism loop (e.g., 100 runs) and assert identical output each run
6. Assert stable `reason_id` and `context_hash` across runs

### D6 — Tiny Guardrail Helper Module (No Runtime Features)
Add minimal helpers that **only** enforce contracts:

- `src/adamantine/v1/mobile_contract/__init__.py`
- `src/adamantine/v1/mobile_contract/canonicalize.py`
- `src/adamantine/v1/mobile_contract/schema_validate.py`
- `src/adamantine/v1/mobile_contract/contract_hashes.py`

Rules:
- No network
- No time
- No randomness
- No global state
- Pure deterministic transforms / validations only

### D7 — OS Proof Pack v1.5.0 Doc
Add proof pack document:

- `docs/OS_PROOF_PACK_v1_5_0.md`

It explains what the fixture pack proves and what CI guarantees.

---

## 3. Implementation Order (Smallest Safe Steps)

### Step 1 — Inventory + Invariants (no code changes)
- Confirm existing v1 mobile docs (v1) and current orchestrator response shape
- Enumerate every field in current mobile call + result objects
- Freeze invariants for v2:
  - required fields
  - canonicalization
  - protection_mode enumeration + semantics
  - reason registry rules

### Step 2 — Write v2 Contract Docs (normative)
- Write the two v2 docs first (D1)
- Ensure they refer to existing execution envelope v2 and response conventions

### Step 3 — Add JSON Schemas
- Create strict v2 request/response schemas (D2)
- Add schema validation tests that prove:
  - unknown field → fail
  - missing required field → fail
  - wrong type → fail

### Step 4 — Add v1.5.0 Fixture Pack + Manifest
- Create request fixtures
- Generate expected response fixtures by running orchestrator deterministically
- Generate manifest hashes

### Step 5 — Mobile Conformance Tests
- Implement strict roundtrip tests (D5)
- Add determinism loop (100 runs)

### Step 6 — Add Helper Module
- Implement canonicalization and schema validation helpers (D6)
- Test helpers directly (unit tests)

### Step 7 — Documentation Index Update (optional but recommended)
- Add new v2 docs + proof pack to `docs/INDEX.md`

---

## 4. Exit Criteria (Tag Gate)

v1.5.0 is eligible for tagging only if:

- ✅ `mobile_execution_call_v2.md` and `mobile_decision_result_v2.md` exist and are complete
- ✅ strict JSON schemas exist and are enforced in tests
- ✅ fixture pack exists + manifest locks it
- ✅ conformance tests:
  - validate schemas
  - assert exact response equality
  - run ≥100 deterministic repeats
- ✅ `reason_registry_mobile_v1.json` exists and is hash-locked
- ✅ proof pack doc exists (`docs/OS_PROOF_PACK_v1_5_0.md`)
- ✅ CI green

---

## 5. Scope Guardrails

v1.5.0 must NOT:
- modify shield/adaptive/Q-ID logic
- introduce runtime features
- add new evidence types
- change reason_id semantics (unless versioned properly)

This phase is **integration contract sealing** only.

---

## 6. Next After v1.5.0

After v1.5.0, the mobile boundary is sealed. The next work (future) can safely focus on:
- production runtime separation (v2.0.0 direction)
- external builder integration without contract ambiguity

---

**End of v1.5.0 Roadmap**
