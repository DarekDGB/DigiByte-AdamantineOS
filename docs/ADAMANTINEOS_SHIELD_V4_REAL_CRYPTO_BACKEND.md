# AdamantineOS Shield v4 Real Crypto Backend Contract

Author attribution: DarekDGB

## Status

This document locks the AdamantineOS real-crypto verification boundary for Shield v4.
It connects AdamantineOS Shield v4 receipt verification to deployment-controlled real
signature backends without making AdamantineOS a transaction signer.

## Boundary lock

AdamantineOS remains the final execution boundary.

AdamantineOS verifies Shield v4 evidence, but it must not:

- sign Shield receipts;
- sign DigiByte transactions;
- broadcast transactions;
- change DigiByte consensus;
- accept Shield evidence as final approval.

A verified Shield v4 `ALLOW` receipt remains evidence only. AdamantineOS continues its
own final policy checks after evidence verification.

## Algorithm lock

Shield v4 policy `policy.v1` requires:

- `classical-ed25519`;
- `ml-dsa`, formerly CRYSTALS-Dilithium.

`fn-dsa`, based on Falcon, is optional evidence only. FN-DSA/Falcon is not ML-DSA and
must never override failure of the required algorithms.

## Verify-only adapter

AdamantineOS exposes a verify-only backend contract in:

```text
src/adamantine/v1/integrations/shield_v4_real_crypto_backend.py
```

The adapter is intentionally verify-only. It contains no signing method because
AdamantineOS must not become a Shield signer or transaction signer.

The optional OQS ML-DSA verify-only backend lives in:

```text
src/adamantine/v1/integrations/shield_v4_oqs_mldsa_backend.py
```

It lazily imports `oqs` only when used, so normal CI and non-OQS deployments do not
silently depend on local machine crypto state. If OQS is missing, disabled, or lacks
the locked mechanism, AdamantineOS fails closed.

## OQS ML-DSA mapping

For Shield v4 `policy.v1`, the optional OQS backend maps:

```text
Shield algorithm: ml-dsa
OQS mechanism:    ML-DSA-65
```

The mechanism is deliberately locked for this backend. A caller cannot silently swap
`ML-DSA-44`, `ML-DSA-87`, Falcon/FN-DSA, or another mechanism behind the Shield
policy name.

## Frozen real-signature input

Every real signature is verified over the exact byte string:

```text
DGB-SHIELD-V4-REAL-CRYPTO-SIGNATURE-INPUT
<domain_tag>
<signed_payload_hash>
<algorithm>
<key_id>
<key_version>
```

Rules:

- UTF-8 encoding only;
- line separator is LF (`\n`);
- no trailing newline;
- `signed_payload_hash` must be lowercase SHA-256 hex;
- `domain_tag` must be one of the frozen Shield v4 signing domains;
- `algorithm`, `key_id`, and `key_version` must match the trusted registry entry.

## Binary encoding lock

Real ML-DSA signatures and public keys are binary. AdamantineOS real backend adapters
use explicit unpadded base64url encoding with the prefix:

```text
b64u:<unpadded-base64url-bytes>
```

Rules:

- real binary signatures use `b64u:`;
- real OQS public keys use `b64u:` in the trust registry;
- padding characters (`=`) are rejected;
- malformed base64url is rejected before calling a crypto backend;
- historical 64-character deterministic test digests remain test fixtures only.

## Fail-closed material boundary

AdamantineOS real verification must reject deterministic test material before calling
a production backend.

Rejected examples include:

- key ids beginning with `test-`;
- public keys containing `TEST-ONLY`.

There is no fallback from real verification mode to TEST-ONLY deterministic HMAC
verification.

## Third-party attribution

When a real backend is selected, repository-level attribution belongs in:

```text
THIRD_PARTY_NOTICES.md
```

The notice must identify the backend family, clarify that no third-party PQC source is
vendored unless explicitly stated, and keep author attribution as DarekDGB.
