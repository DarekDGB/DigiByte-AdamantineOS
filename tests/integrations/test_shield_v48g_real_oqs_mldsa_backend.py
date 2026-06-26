from __future__ import annotations

import os

import pytest

if os.environ.get("SHIELD_V4_REAL_OQS") != "1":
    pytest.skip("set SHIELD_V4_REAL_OQS=1 to run the real liboqs ML-DSA proof", allow_module_level=True)

try:
    oqs = pytest.importorskip("oqs")
except SystemExit as exc:
    pytest.skip(f"could not import oqs/liboqs: {exc}", allow_module_level=True)
except Exception as exc:
    pytest.skip(f"could not import oqs/liboqs: {exc}", allow_module_level=True)

from adamantine.v1.integrations.shield_v4_oqs_mldsa_backend import (  # noqa: E402
    OQS_ML_DSA_MECHANISM,
    OqsMlDsaVerifierBackend,
)
from adamantine.v1.integrations.shield_v4_real_crypto_backend import (  # noqa: E402
    ShieldV4RealCryptoBackendError,
    encode_binary_signature_material,
)

MESSAGE = b"DGB Shield v4.8G real liboqs ML-DSA proof: adamantineos"


def _generate_mldsa65_signature() -> tuple[bytes, bytes, bytes, bytes]:
    with oqs.Signature(OQS_ML_DSA_MECHANISM) as signer:
        public_key = signer.generate_keypair()
        secret_key = signer.export_secret_key()
        signature = signer.sign(MESSAGE)
    with oqs.Signature(OQS_ML_DSA_MECHANISM) as other_signer:
        other_public_key = other_signer.generate_keypair()
    assert isinstance(public_key, bytes) and public_key
    assert isinstance(secret_key, bytes) and secret_key
    assert isinstance(signature, bytes) and signature
    assert isinstance(other_public_key, bytes) and other_public_key
    return public_key, secret_key, signature, other_public_key


def _tamper(signature: bytes) -> bytes:
    tampered = bytearray(signature)
    assert tampered
    tampered[0] ^= 0x01
    return bytes(tampered)


def test_v48g_real_oqs_mldsa65_adamantineos_verify_only_backend_positive_and_negatives() -> None:
    assert OQS_ML_DSA_MECHANISM in tuple(oqs.get_enabled_sig_mechanisms())

    public_key, _secret_key, signature, other_public_key = _generate_mldsa65_signature()
    backend = OqsMlDsaVerifierBackend()
    public_key_b64u = encode_binary_signature_material(public_key, field="public_key")
    signature_b64u = encode_binary_signature_material(signature, field="signature")

    assert backend.verify_signature(
        algorithm="ml-dsa",
        public_key=public_key_b64u,
        message=MESSAGE,
        signature=signature_b64u,
    ) is True

    assert backend.verify_signature(
        algorithm="ml-dsa",
        public_key=public_key_b64u,
        message=MESSAGE,
        signature=encode_binary_signature_material(_tamper(signature), field="signature"),
    ) is False

    assert backend.verify_signature(
        algorithm="ml-dsa",
        public_key=encode_binary_signature_material(other_public_key, field="public_key"),
        message=MESSAGE,
        signature=signature_b64u,
    ) is False

    with pytest.raises(ShieldV4RealCryptoBackendError, match="public_key byte length"):
        backend.verify_signature(
            algorithm="ml-dsa",
            public_key=encode_binary_signature_material(public_key[:-1], field="public_key"),
            message=MESSAGE,
            signature=signature_b64u,
        )
