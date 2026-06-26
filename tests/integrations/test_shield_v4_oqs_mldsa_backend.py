from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest

import adamantine.v1.integrations.shield_v4_oqs_mldsa_backend as oqs_backend_module
from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import ORCHESTRATOR_RECEIPT_DOMAIN
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import TrustedShieldV4Key
from adamantine.v1.integrations.shield_v4_oqs_mldsa_backend import (
    OQS_ML_DSA_MECHANISM,
    OqsMlDsaVerifierBackend,
)
from adamantine.v1.integrations.shield_v4_real_crypto_backend import (
    ShieldV4RealCryptoBackendError,
    ShieldV4RealCryptoBackendUnavailable,
    build_real_crypto_signature_input,
    decode_binary_signature_material,
    encode_binary_signature_material,
    verify_signature_entry_with_real_backend,
)

PAYLOAD_HASH = "d" * 64
PUBLIC_KEY_BYTES = b"adamantineos-real-ml-dsa-public-key"


class FakeOqsSignature:
    def __init__(self, mechanism: str, secret_key: bytes | None = None) -> None:
        self.mechanism = mechanism
        self.secret_key = secret_key

    def __enter__(self) -> "FakeOqsSignature":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        assert self.mechanism == OQS_ML_DSA_MECHANISM
        expected = hashlib.sha256(b"oqs-sign|" + public_key + message).digest()
        return signature == expected


class NativeOqsError(RuntimeError):
    pass


class NativeVerifyFailure(FakeOqsSignature):
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        raise NativeOqsError("native verify rejected material")


class NonBoolVerify(FakeOqsSignature):
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> object:
        return 1


@dataclass(frozen=True)
class FakeOqsModule:
    enabled: tuple[str, ...] = (OQS_ML_DSA_MECHANISM,)
    signature_cls: type[FakeOqsSignature] = FakeOqsSignature

    def get_enabled_sig_mechanisms(self) -> tuple[str, ...]:
        return self.enabled

    def oqs_version(self) -> str:
        return "fake-liboqs"

    def oqs_python_version(self) -> str:
        return "fake-liboqs-python"

    @property
    def Signature(self) -> type[FakeOqsSignature]:
        return self.signature_cls


class VersionDiscoveryFailureModule(FakeOqsModule):
    def oqs_version(self) -> str:
        raise NativeOqsError("native version discovery failure")


class MechanismDiscoveryFailureModule(FakeOqsModule):
    def get_enabled_sig_mechanisms(self) -> tuple[str, ...]:
        raise NativeOqsError("native mechanism discovery failure")


class SignatureConstructorFailureModule(FakeOqsModule):
    @property
    def Signature(self) -> type[FakeOqsSignature]:
        raise NativeOqsError("native signature constructor lookup failure")


def trusted_key() -> TrustedShieldV4Key:
    return TrustedShieldV4Key(
        role="shield_orchestrator",
        key_id="shield_orchestrator-ml-dsa-v1",
        key_version=1,
        algorithm="ml-dsa",
        not_before="2026-06-21T00:00:00Z",
        not_after="2026-06-21T00:05:00Z",
        status="active",
        public_key=encode_binary_signature_material(PUBLIC_KEY_BYTES, field="public_key"),
    )


def signature_entry() -> dict[str, object]:
    message = build_real_crypto_signature_input(
        algorithm="ml-dsa",
        domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN,
        signed_payload_hash=PAYLOAD_HASH,
        key_id="shield_orchestrator-ml-dsa-v1",
        key_version=1,
    )
    signature = hashlib.sha256(b"oqs-sign|" + PUBLIC_KEY_BYTES + message).digest()
    return {
        "algorithm": "ml-dsa",
        "key_id": "shield_orchestrator-ml-dsa-v1",
        "key_version": 1,
        "signed_payload_hash": PAYLOAD_HASH,
        "domain_tag": ORCHESTRATOR_RECEIPT_DOMAIN,
        "signature": encode_binary_signature_material(signature, field="signature"),
    }


def test_v48d_adamantineos_oqs_mldsa_verifier_accepts_real_b64u_signature() -> None:
    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule())

    assert "fake-liboqs" in backend.backend_version
    assert verify_signature_entry_with_real_backend(signature_entry(), trusted_key(), backend=backend) is True

    tampered = signature_entry()
    tampered["signature"] = encode_binary_signature_material(b"wrong-signature", field="signature")
    assert verify_signature_entry_with_real_backend(tampered, trusted_key(), backend=backend) is False


def test_v48d_adamantineos_oqs_mldsa_verifier_rejects_wrong_algorithm_and_mechanism() -> None:
    with pytest.raises(ShieldV4RealCryptoBackendError, match="ML-DSA-65"):
        OqsMlDsaVerifierBackend(mechanism="ML-DSA-44")

    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule())
    with pytest.raises(ShieldV4RealCryptoBackendUnavailable, match="ml-dsa"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"sig", field="signature"),
        )


def test_v48d_adamantineos_oqs_mldsa_verifier_fails_closed_when_oqs_missing_or_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = OqsMlDsaVerifierBackend()
    monkeypatch.setattr(
        oqs_backend_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError(name)),
    )
    with pytest.raises(ShieldV4RealCryptoBackendUnavailable, match="import oqs"):
        _ = backend.backend_version

    disabled_backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(enabled=("FN-DSA-512",)))
    with pytest.raises(ShieldV4RealCryptoBackendUnavailable, match="not enabled"):
        disabled_backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"sig", field="signature"),
        )


def test_v48d_adamantineos_oqs_mldsa_verifier_rejects_bad_binary_material() -> None:
    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="message"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"",
            signature=signature_entry()["signature"],
        )
    with pytest.raises(ShieldV4RealCryptoBackendError, match="public_key"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key="not-b64u",
            message=b"message",
            signature=signature_entry()["signature"],
        )
    with pytest.raises(ShieldV4RealCryptoBackendError, match="signature"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature="b64u:bad=",
        )


def test_v48g_adamantineos_oqs_mldsa_verifier_wraps_native_exceptions_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = OqsMlDsaVerifierBackend()
    monkeypatch.setattr(
        oqs_backend_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(NativeOqsError("native import failure")),
    )
    with pytest.raises(ShieldV4RealCryptoBackendError, match="import failed closed") as import_error:
        _ = backend.backend_version
    assert isinstance(import_error.value.__cause__, NativeOqsError)

    backend = OqsMlDsaVerifierBackend(oqs_module=VersionDiscoveryFailureModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="version discovery failed closed") as version_error:
        _ = backend.backend_version
    assert isinstance(version_error.value.__cause__, NativeOqsError)

    backend = OqsMlDsaVerifierBackend(oqs_module=MechanismDiscoveryFailureModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="mechanism discovery failed closed") as mechanism_error:
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )
    assert isinstance(mechanism_error.value.__cause__, NativeOqsError)

    backend = OqsMlDsaVerifierBackend(oqs_module=SignatureConstructorFailureModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="verify failed closed") as constructor_error:
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )
    assert isinstance(constructor_error.value.__cause__, NativeOqsError)

    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(signature_cls=NativeVerifyFailure))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="verify failed closed") as verify_error:
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )
    assert isinstance(verify_error.value.__cause__, NativeOqsError)


def test_v48g_adamantineos_oqs_mldsa_verifier_rejects_truthy_non_bool_verify_result() -> None:
    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(signature_cls=NonBoolVerify))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="verify must return bool"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )


def test_v48d_adamantineos_real_binary_encoding_helpers_are_strict() -> None:
    encoded = encode_binary_signature_material(b"abc", field="signature")
    assert encoded == "b64u:YWJj"
    assert decode_binary_signature_material(encoded, field="signature") == b"abc"

    with pytest.raises(ShieldV4RealCryptoBackendError, match="bytes"):
        encode_binary_signature_material(b"", field="signature")
    with pytest.raises(ShieldV4RealCryptoBackendError, match="b64u"):
        decode_binary_signature_material("abc", field="signature")
    with pytest.raises(ShieldV4RealCryptoBackendError, match="non-empty"):
        decode_binary_signature_material("b64u:", field="signature")
    with pytest.raises(ShieldV4RealCryptoBackendError, match="unpadded"):
        decode_binary_signature_material("b64u:YWJj=", field="signature")
    with pytest.raises(ShieldV4RealCryptoBackendError, match="invalid"):
        decode_binary_signature_material("b64u:****", field="signature")
    with pytest.raises(ShieldV4RealCryptoBackendError, match="invalid"):
        decode_binary_signature_material("b64u:A", field="signature")

class LengthCheckedOqsSignature(FakeOqsSignature):
    details = {
        "length_public_key": len(PUBLIC_KEY_BYTES),
        "length_signature": hashlib.sha256(b"").digest_size,
    }


def test_v48g_adamantineos_oqs_mldsa_verifier_rejects_wrong_binary_lengths_before_native_verify() -> None:
    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(signature_cls=LengthCheckedOqsSignature))

    with pytest.raises(ShieldV4RealCryptoBackendError, match="public_key byte length"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=encode_binary_signature_material(PUBLIC_KEY_BYTES[:-1], field="public_key"),
            message=b"message",
            signature=encode_binary_signature_material(b"0" * hashlib.sha256(b"").digest_size, field="signature"),
        )

    with pytest.raises(ShieldV4RealCryptoBackendError, match="signature byte length"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )

class NonMappingDetailsOqsSignature(FakeOqsSignature):
    details = "bad-details"


class MissingLengthDetailsOqsSignature(FakeOqsSignature):
    details: dict[str, int] = {}


class InvalidLengthDetailsOqsSignature(FakeOqsSignature):
    details = {"length_public_key": True, "length_signature": hashlib.sha256(b"").digest_size}


def test_v48g_adamantineos_oqs_mldsa_verifier_validates_optional_backend_length_metadata() -> None:
    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(signature_cls=NonMappingDetailsOqsSignature))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="details must be a mapping"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"0" * hashlib.sha256(b"").digest_size, field="signature"),
        )

    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(signature_cls=InvalidLengthDetailsOqsSignature))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="length_public_key"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"0" * hashlib.sha256(b"").digest_size, field="signature"),
        )

    backend = OqsMlDsaVerifierBackend(oqs_module=FakeOqsModule(signature_cls=MissingLengthDetailsOqsSignature))
    message = build_real_crypto_signature_input(
        algorithm="ml-dsa",
        domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN,
        signed_payload_hash=PAYLOAD_HASH,
        key_id="shield_orchestrator-ml-dsa-v1",
        key_version=1,
    )
    signature = encode_binary_signature_material(
        hashlib.sha256(b"oqs-sign|" + PUBLIC_KEY_BYTES + message).digest(),
        field="signature",
    )
    assert backend.verify_signature(
        algorithm="ml-dsa",
        public_key=trusted_key().public_key,
        message=message,
        signature=signature,
    ) is True
