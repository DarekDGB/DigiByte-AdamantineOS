# Runtime Artifact Log v1 (Contract Freeze)

**License:** MIT — **Author:** DarekDGB  
**Stability level:** **FROZEN** (breaking change requires `runtime_artifact_log_v2`)  
**Scope:** What an untrusted runtime host **may/may not** emit as runtime-side artifacts.

Runtime artifacts are **observability-only**.
They are **not** part of Adamantine’s deterministic decision, and must never be used to weaken denial.

---

## 1. Core Rule

**Runtime artifacts MUST be treated as untrusted input.**

- They may be logged for debugging / audits.
- They MUST NOT influence:
  - verdict
  - reason_id
  - context_hash
  - protection_mode
  - deterministic `artifacts` emitted by core

---

## 2. Allowed Artifact Shape

A runtime artifact record is a JSON object:

- `type` (string, required): short event type, e.g. `executor_called`, `executor_error`, `host_parse_error`
- `message` (string, optional): human-readable summary
- `details` (object, optional): structured fields (strings/numbers/bools only; no nested arrays of objects)
- `severity` (string, optional): `debug` | `info` | `warn` | `error`

### Size & Safety Limits

Runtime host MUST enforce:

- max artifacts per call: **25**
- max serialized bytes per artifact: **4 KB**
- total artifacts bytes per call: **32 KB**
- forbidden content:
  - private keys, seed phrases, mnemonics
  - raw signatures or full transaction hex (hash-only is OK)
  - personally identifying info (PII)
  - device identifiers beyond what is already allowed by the call contracts

If limits are exceeded, host MUST truncate or drop artifacts deterministically.

---

## 3. Recommended Event Types

- `host_received_call_v2`
- `host_rejected_call_v2`
- `core_called_orchestrator_v2`
- `core_returned_allow`
- `core_returned_deny`
- `executor_called`
- `executor_succeeded`
- `executor_failed`

---

## 4. Separation From Core Artifacts

Core `execution_response_v2.artifacts` are **deterministic** and contract-governed.

Runtime artifacts MUST be:
- stored separately (log sink, file, telemetry)
- or returned in a **separate** response channel that is explicitly labeled untrusted

Runtime MUST NOT merge runtime artifacts into core response artifacts.

---

## 5. Canonicalization & Determinism Guidance

Runtime artifacts are not required to be deterministic.

However, to make testability and audits easier:
- prefer stable `type` strings
- avoid timestamps in records that are asserted by tests
- if you include timestamps, treat them as informational only and never part of the core context hash

---
