from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import (
    ALLOWED_ALGORITHMS,
    COMPONENT_VERDICT_DOMAIN,
    ORCHESTRATOR_RECEIPT_DOMAIN,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import TrustedShieldV4Key

REAL_CRYPTO_SIGNATURE_INPUT_PREFIX = "DGB-SHIELD-V4-REAL-CRYPTO-SIGNATURE-INPUT"
_ALLOWED_DOMAIN_TAGS = frozenset({COMPONENT_VERDICT_DOMAIN, ORCHESTRATOR_RECEIPT_DOMAIN})
_TEST_ONLY_MARKERS = ("test-only",)
_TEST_ONLY_PREFIXES = ("test-",)


class ShieldV4RealCryptoBackendError(ValueError):
    """Base fail-closed error for AdamantineOS Shield v4 real-crypto verification."""


class ShieldV4RealCryptoBackendUnavailable(ShieldV4RealCryptoBackendError):
    """Raised when the configured production verifier lacks a required algorithm."""


class ShieldV4RealCryptoMaterialError(ShieldV4RealCryptoBackendError):
    """Raised when test-only material reaches the AdamantineOS real verifier boundary."""


class ShieldV4RealCryptoVerifierBackend(Protocol):
    """AdamantineOS verify-only backend contract for Shield v4 signatures.

    AdamantineOS does not sign Shield receipts or transactions. Implementations
    only expose verification for deployment-controlled real crypto backends.
    """

    backend_name: str
    backend_version: str
    supported_algorithms: tuple[str, ...]

    def verify_signature(
        self,
        *,
        algorithm: str,
        public_key: str,
        message: bytes,
        signature: str,
    ) -> bool:
        """Return True only when the signature verifies under the supplied public key."""


RealCryptoSignatureVerifier = Callable[[Mapping[str, Any], TrustedShieldV4Key], bool]


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ShieldV4RealCryptoBackendError(f"{field} must be non-empty string")
    return value.strip()


def _require_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ShieldV4RealCryptoBackendError(f"{field} must be positive integer")
    return value


def _require_hash(value: Any, *, field: str) -> str:
    clean = _require_non_empty_str(value, field=field)
    if len(clean) != 64:
        raise ShieldV4RealCryptoBackendError(f"{field} must be 64-character sha256 hex")
    try:
        int(clean, 16)
    except ValueError as exc:
        raise ShieldV4RealCryptoBackendError(f"{field} must be sha256 hex") from exc
    if clean != clean.lower():
        raise ShieldV4RealCryptoBackendError(f"{field} must be lowercase sha256 hex")
    return clean


def _require_supported_algorithm(value: Any) -> str:
    algorithm = _require_non_empty_str(value, field="algorithm")
    if algorithm not in ALLOWED_ALGORITHMS:
        raise ShieldV4RealCryptoBackendError("algorithm must be supported by Shield v4 policy")
    return algorithm


def _reject_test_only_text(value: str, *, field: str) -> None:
    clean = value.strip().lower()
    if any(marker in clean for marker in _TEST_ONLY_MARKERS) or any(
        clean.startswith(prefix) for prefix in _TEST_ONLY_PREFIXES
    ):
        raise ShieldV4RealCryptoMaterialError(f"{field} must not contain test-only material")


def reject_test_only_key_material(key: TrustedShieldV4Key) -> None:
    """Fail closed if deterministic-test keys reach AdamantineOS real verification."""

    _reject_test_only_text(key.key_id, field="key_id")
    _reject_test_only_text(key.public_key, field="public_key")


def build_real_crypto_signature_input(
    *,
    algorithm: str,
    domain_tag: str,
    signed_payload_hash: str,
    key_id: str,
    key_version: int,
) -> bytes:
    """Build the exact production-verification message bytes for Shield v4."""

    clean_algorithm = _require_supported_algorithm(algorithm)
    clean_domain = _require_non_empty_str(domain_tag, field="domain_tag")
    if clean_domain not in _ALLOWED_DOMAIN_TAGS:
        raise ShieldV4RealCryptoBackendError("domain_tag must be a Shield v4 signing domain")
    clean_hash = _require_hash(signed_payload_hash, field="signed_payload_hash")
    clean_key_id = _require_non_empty_str(key_id, field="key_id")
    clean_key_version = _require_positive_int(key_version, field="key_version")
    return "\n".join(
        (
            REAL_CRYPTO_SIGNATURE_INPUT_PREFIX,
            clean_domain,
            clean_hash,
            clean_algorithm,
            clean_key_id,
            str(clean_key_version),
        )
    ).encode("utf-8")


def _require_backend_supports_algorithm(backend: ShieldV4RealCryptoVerifierBackend, algorithm: str) -> None:
    supported = tuple(getattr(backend, "supported_algorithms", ()))
    if algorithm not in supported:
        raise ShieldV4RealCryptoBackendUnavailable("real crypto backend does not support required algorithm")


def verify_signature_entry_with_real_backend(
    entry: Mapping[str, Any],
    key: TrustedShieldV4Key,
    *,
    backend: ShieldV4RealCryptoVerifierBackend,
) -> bool:
    """Verify one Shield v4 signature entry with AdamantineOS real crypto backend."""

    reject_test_only_key_material(key)
    algorithm = _require_supported_algorithm(entry.get("algorithm"))
    key_id = _require_non_empty_str(entry.get("key_id"), field="key_id")
    key_version = _require_positive_int(entry.get("key_version"), field="key_version")
    if (key.algorithm, key.key_id, key.key_version) != (algorithm, key_id, key_version):
        raise ShieldV4RealCryptoBackendError("signature entry does not match trusted key")
    _require_backend_supports_algorithm(backend, algorithm)
    message = build_real_crypto_signature_input(
        algorithm=algorithm,
        domain_tag=_require_non_empty_str(entry.get("domain_tag"), field="domain_tag"),
        signed_payload_hash=_require_hash(entry.get("signed_payload_hash"), field="signed_payload_hash"),
        key_id=key_id,
        key_version=key_version,
    )
    signature = _require_non_empty_str(entry.get("signature"), field="signature")
    return bool(
        backend.verify_signature(
            algorithm=algorithm,
            public_key=key.public_key,
            message=message,
            signature=signature,
        )
    )


def make_real_crypto_signature_verifier(
    backend: ShieldV4RealCryptoVerifierBackend,
) -> RealCryptoSignatureVerifier:
    """Adapt a real verifier backend to AdamantineOS Shield v4 verifier injection."""

    def _verify(entry: Mapping[str, Any], key: TrustedShieldV4Key) -> bool:
        return verify_signature_entry_with_real_backend(entry, key, backend=backend)

    return _verify
