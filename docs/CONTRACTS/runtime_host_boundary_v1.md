# Runtime Host Boundary v1 (Contract Freeze)

**License:** MIT — **Author:** DarekDGB  
**Stability level:** **FROZEN** (breaking change requires `runtime_host_boundary_v2`)  
**Scope:** Reference runtime host responsibilities for executing **MobileExecutionCall v2** safely.

This contract freezes what “**runtime separation + production envelope**” means for AdamantineOS v2.0.0+.

Adamantine core remains **pure and deterministic**.
The runtime host is **untrusted**.

---

## 1. Version

- **Interface name:** `runtime_host_boundary_v1`
- **Input call contract:** `mobile_execution_call_v2`
- **Decision engine entry:** `orchestrator_v2`
- **Core response shape:** `execution_response_v2` (decision + deterministic artifacts)

---

## 2. Definitions

- **Core (trusted):** Adamantine decision engine (`orchestrator_v2` + EQC/TVA gates), deterministic, fail-closed.
- **Runtime host (untrusted):** code that embeds the core and (optionally) executes actions when the core returns **ALLOW**.
- **Executor (untrusted):** injected function/implementation that performs the action (sign/broadcast/etc). It is **never** allowed to run on **DENY**.
- **Replay registry / nonce authority (trusted only when explicitly integrated):** stateful service or store that decides whether a Q-ID session nonce is fresh and emits the `registry_commitment` for that decision. Runtime glue MUST NOT replace this with a local boolean.

---

## 3. Hard Invariants (Non-Negotiable)

The runtime host **MUST**:

1. **Parse + validate input strictly**
   - Accept only the `mobile_execution_call_v2` shape.
   - Reject unknown top-level fields unless the contract explicitly allows them.
   - Fail-closed with deterministic error mapping.

2. **Run core exactly once per call**
   - The host must call `orchestrator_v2` exactly once for a given call payload.

3. **Respect ALLOW/DENY**
   - If core verdict is **DENY**: the host **MUST NOT** call the executor.
   - If core verdict is **ALLOW**: the host **MUST** call the executor **exactly once**.

4. **Never mutate core outputs**
   The host **MUST NOT** override or modify any of:
   - `verdict`
   - `reason_id`
   - `context_hash`
   - `protection_mode`
   - deterministic `artifacts` (as defined by core)

5. **Nonce consumption rules**
   - Any nonce consumption tied to replay protection **MUST** be performed in the trusted path.
   - The host **MUST NOT** “pre-consume” nonces before a successful ALLOW decision.
   - On ALLOW: nonce is consumed **exactly once**.
   - On DENY: nonce is **not** consumed (unless the existing core contract explicitly states otherwise).

6. **No hidden authority**
   - The host must not introduce alternate allowlists, “emergency allow”, silent downgrade, or bypass modes.

---

## 4. Minimal Reference Host API

A compliant reference host can be as small as:

- **Input:** `MobileExecutionCall v2` payload (mapping / dict)
- **Dependencies:** injected `Executor` (callable or interface), required `NonceStore`, an integrator-provided `qid_verifier` for Q-ID v2 evidence, and a trusted replay registry/nonce authority when Q-ID replay freshness is claimed
- **Behavior:**
  1. Parse call
  2. Run `orchestrator_v2` to obtain an `execution_response_v2`
  3. If `verdict == ALLOW` → call executor exactly once
  4. Return the core `execution_response_v2` (unchanged) plus the executor result *out-of-band*

**Important:** executor results and runtime logs are **untrusted** and **MUST NOT** be merged into core deterministic `artifacts`.

---

## 5. Forbidden Behaviors

The runtime host **MUST NEVER**:

- call the executor on **DENY** (even “dry run”, “preview”, “simulate”, or “best effort”)
- call the executor more than once for a single ALLOW
- rewrite or replace `reason_id`, `context_hash`, or `protection_mode`
- inject runtime-generated artifacts into core `artifacts`
- rely on wall-clock time or randomness to produce output fields that are asserted in tests
- store secrets or keys inside Adamantine core objects
- treat Q-ID `proof_hash` as signature/authenticity proof; Q-ID v2 evidence requires injected verifier wiring
- treat Q-ID `fresh = true` or `registry_commitment` as trustworthy when they were produced by untrusted runtime glue instead of a stateful replay registry

---

## 6. Conformance & Proof

A compliant integration **MUST** be provable with tests that lock:

- DENY → executor never called
- ALLOW → executor called exactly once
- hostile runtime attempts to override decision fields are ignored/fail-closed
- Q-ID replay freshness is not accepted as a real guarantee unless it is sourced from a trusted replay registry/nonce authority
- determinism across repeated runs (recommended 50–100 runs)

See also:
- `docs/V2_RUNTIME_UNTRUSTED_MODEL.md`
- `docs/CONTRACTS/runtime_artifact_log_v1.md`

---
