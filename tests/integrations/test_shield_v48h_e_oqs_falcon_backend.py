from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest

import adamantine.v1.integrations.shield_v4_oqs_falcon_backend as oqs_falcon_module
from adamantine.v1.contracts.shield_orchestrator_receipt_v4 import (
    FIPS206_DRAFT_FALCON1024_PROFILE,
    ORCHESTRATOR_RECEIPT_DOMAIN,
)
from adamantine.v1.integrations.shield_orchestrator_receipt_v4_verifier import TrustedShieldV4Key
from adamantine.v1.integrations.shield_v4_oqs_falcon_backend import (
    OQS_FALCON_MECHANISM,
    OqsFalcon1024VerifierBackend,
)
from adamantine.v1.integrations.shield_v4_real_crypto_backend import (
    ShieldV4RealCryptoBackendError,
    ShieldV4RealCryptoBackendUnavailable,
    build_real_crypto_signature_input,
    encode_binary_signature_material,
    verify_signature_entry_with_real_backend,
)

PAYLOAD_HASH = "f" * 64
PUBLIC_KEY_BYTES = b"adamantineos-real-falcon1024-public-key"


class FakeOqsSignature:
    details: dict[str, int] | str | None = None

    def __init__(self, mechanism: str, secret_key: bytes | None = None) -> None:
        self.mechanism = mechanism
        self.secret_key = secret_key

    def __enter__(self) -> "FakeOqsSignature":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        assert self.mechanism == OQS_FALCON_MECHANISM
        expected = hashlib.sha256(b"oqs-falcon-sign|" + public_key + message).digest()
        return signature == expected


@dataclass(frozen=True)
class FakeOqsModule:
    enabled: tuple[str, ...] = (OQS_FALCON_MECHANISM,)
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


class NativeOqsError(RuntimeError):
    pass


class VersionDiscoveryFailureModule(FakeOqsModule):
    def oqs_version(self) -> str:
        raise NativeOqsError("native version discovery failure")


class MechanismDiscoveryFailureModule(FakeOqsModule):
    def get_enabled_sig_mechanisms(self) -> tuple[str, ...]:
        raise NativeOqsError("native mechanism discovery failure")


class NativeVerifyFailure(FakeOqsSignature):
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        raise NativeOqsError("native verify rejected material")


class NonBoolVerify(FakeOqsSignature):
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> object:
        return 1


class SignatureConstructorFailureModule(FakeOqsModule):
    @property
    def Signature(self) -> type[FakeOqsSignature]:  # type: ignore[override]
        raise NativeOqsError("native signature constructor lookup failure")


class LengthCheckedOqsSignature(FakeOqsSignature):
    details = {
        "length_public_key": len(PUBLIC_KEY_BYTES),
        # liboqs Falcon-1024 reports a maximum signature buffer length.
        # Actual Falcon signatures are variable-length and may be shorter.
        "length_signature": hashlib.sha256(b"").digest_size + 8,
    }


class NonMappingDetailsOqsSignature(FakeOqsSignature):
    details = "bad-details"


class MissingLengthDetailsOqsSignature(FakeOqsSignature):
    details: dict[str, int] = {}


class InvalidLengthDetailsOqsSignature(FakeOqsSignature):
    details = {"length_public_key": True, "length_signature": hashlib.sha256(b"").digest_size}


def trusted_key() -> TrustedShieldV4Key:
    return TrustedShieldV4Key(
        role="shield_orchestrator",
        key_id="prod-shield_orchestrator-fn-dsa-v1",
        key_version=1,
        algorithm="fn-dsa",
        not_before="2026-06-21T00:00:00Z",
        not_after="2026-06-21T00:05:00Z",
        status="active",
        public_key=encode_binary_signature_material(PUBLIC_KEY_BYTES, field="public_key"),
    )


def signature_message() -> bytes:
    return build_real_crypto_signature_input(
        algorithm="fn-dsa",
        standard_profile=FIPS206_DRAFT_FALCON1024_PROFILE,
        domain_tag=ORCHESTRATOR_RECEIPT_DOMAIN,
        signed_payload_hash=PAYLOAD_HASH,
        key_id="prod-shield_orchestrator-fn-dsa-v1",
        key_version=1,
    )


def signature_entry() -> dict[str, object]:
    signature = hashlib.sha256(b"oqs-falcon-sign|" + PUBLIC_KEY_BYTES + signature_message()).digest()
    return {
        "algorithm": "fn-dsa",
        "standard_profile": FIPS206_DRAFT_FALCON1024_PROFILE,
        "key_id": "prod-shield_orchestrator-fn-dsa-v1",
        "key_version": 1,
        "signed_payload_hash": PAYLOAD_HASH,
        "domain_tag": ORCHESTRATOR_RECEIPT_DOMAIN,
        "signature": encode_binary_signature_material(signature, field="signature"),
    }


def test_v48h_e_adamantineos_oqs_falcon_verifier_accepts_real_b64u_signature() -> None:
    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule())

    assert "fake-liboqs" in backend.backend_version
    assert "Falcon-1024" in backend.backend_version
    assert verify_signature_entry_with_real_backend(signature_entry(), trusted_key(), backend=backend) is True

    tampered = signature_entry()
    tampered["signature"] = encode_binary_signature_material(b"wrong-signature", field="signature")
    assert verify_signature_entry_with_real_backend(tampered, trusted_key(), backend=backend) is False


def test_v48h_e_adamantineos_oqs_falcon_verifier_rejects_wrong_algorithm_mechanism_disabled_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ShieldV4RealCryptoBackendError, match="Falcon-1024"):
        OqsFalcon1024VerifierBackend(mechanism="Falcon-512")

    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule())
    with pytest.raises(ShieldV4RealCryptoBackendUnavailable, match="fn-dsa"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"sig", field="signature"),
        )

    disabled = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(enabled=("ML-DSA-65",)))
    with pytest.raises(ShieldV4RealCryptoBackendUnavailable, match="not enabled"):
        disabled.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"sig", field="signature"),
        )

    backend = OqsFalcon1024VerifierBackend()
    monkeypatch.setattr(
        oqs_falcon_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError(name)),
    )
    with pytest.raises(ShieldV4RealCryptoBackendUnavailable, match="import oqs"):
        _ = backend.backend_version


def test_v48h_e_adamantineos_oqs_falcon_verifier_fails_closed_on_bad_material() -> None:
    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="message"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"",
            signature=signature_entry()["signature"],
        )
    with pytest.raises(ShieldV4RealCryptoBackendError, match="public_key"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key="not-b64u",
            message=b"message",
            signature=signature_entry()["signature"],
        )
    with pytest.raises(ShieldV4RealCryptoBackendError, match="signature"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature="b64u:bad=",
        )


def test_v48h_e_adamantineos_oqs_falcon_verifier_wraps_native_exception_surfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OqsFalcon1024VerifierBackend()
    monkeypatch.setattr(
        oqs_falcon_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(NativeOqsError("native import failure")),
    )
    with pytest.raises(ShieldV4RealCryptoBackendError, match="import failed closed") as import_error:
        _ = backend.backend_version
    assert isinstance(import_error.value.__cause__, NativeOqsError)

    failing = OqsFalcon1024VerifierBackend(oqs_module=VersionDiscoveryFailureModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="version discovery failed closed") as version_error:
        _ = failing.backend_version
    assert isinstance(version_error.value.__cause__, NativeOqsError)

    failing = OqsFalcon1024VerifierBackend(oqs_module=MechanismDiscoveryFailureModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="mechanism discovery failed closed") as mechanism_error:
        failing.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"sig", field="signature"),
        )
    assert isinstance(mechanism_error.value.__cause__, NativeOqsError)

    failing = OqsFalcon1024VerifierBackend(oqs_module=SignatureConstructorFailureModule())
    with pytest.raises(ShieldV4RealCryptoBackendError, match="verify failed closed") as constructor_error:
        failing.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )
    assert isinstance(constructor_error.value.__cause__, NativeOqsError)

    failing = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(signature_cls=NativeVerifyFailure))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="verify failed closed") as verify_error:
        failing.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )
    assert isinstance(verify_error.value.__cause__, NativeOqsError)


def test_v48h_e_adamantineos_oqs_falcon_verifier_rejects_truthy_non_bool_verify() -> None:
    non_bool = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(signature_cls=NonBoolVerify))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="verify must return bool"):
        non_bool.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"short-signature", field="signature"),
        )


def test_v48h_e_adamantineos_oqs_falcon_verifier_rejects_wrong_binary_lengths_before_native_verify() -> None:
    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(signature_cls=LengthCheckedOqsSignature))

    with pytest.raises(ShieldV4RealCryptoBackendError, match="public_key byte length"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=encode_binary_signature_material(PUBLIC_KEY_BYTES[:-1], field="public_key"),
            message=b"message",
            signature=encode_binary_signature_material(b"0" * hashlib.sha256(b"").digest_size, field="signature"),
        )

    assert backend.verify_signature(
        algorithm="fn-dsa",
        public_key=trusted_key().public_key,
        message=b"message",
        signature=encode_binary_signature_material(b"short-signature", field="signature"),
    ) is False

    with pytest.raises(ShieldV4RealCryptoBackendError, match="signature byte length"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(
                b"0" * (hashlib.sha256(b"").digest_size + 9),
                field="signature",
            ),
        )


def test_v48h_e_adamantineos_oqs_falcon_verifier_validates_optional_backend_length_metadata() -> None:
    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(signature_cls=NonMappingDetailsOqsSignature))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="details must be a mapping"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"0" * hashlib.sha256(b"").digest_size, field="signature"),
        )

    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(signature_cls=InvalidLengthDetailsOqsSignature))
    with pytest.raises(ShieldV4RealCryptoBackendError, match="length_public_key"):
        backend.verify_signature(
            algorithm="fn-dsa",
            public_key=trusted_key().public_key,
            message=b"message",
            signature=encode_binary_signature_material(b"0" * hashlib.sha256(b"").digest_size, field="signature"),
        )

    backend = OqsFalcon1024VerifierBackend(oqs_module=FakeOqsModule(signature_cls=MissingLengthDetailsOqsSignature))
    assert backend.verify_signature(
        algorithm="fn-dsa",
        public_key=trusted_key().public_key,
        message=signature_message(),
        signature=str(signature_entry()["signature"]),
    ) is True
