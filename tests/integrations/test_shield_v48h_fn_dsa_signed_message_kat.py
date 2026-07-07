from __future__ import annotations

import hashlib
import json
from pathlib import Path

from adamantine.v1.integrations.shield_v4_real_crypto_backend import build_real_crypto_signature_input

FIXTURES = Path(__file__).resolve().parents[2] / "src" / "adamantine" / "v1" / "fixtures" / "shield_v4"


def test_v48h_fn_dsa_signed_message_kat_binds_falcon1024_standard_profile() -> None:
    kat = json.loads((FIXTURES / "fn_dsa_signed_message_draft_profile_kat.json").read_text(encoding="utf-8"))
    assert kat["author_attribution"] == "DarekDGB"
    assert kat["schema_version"] == "adamantineos.shield_v4.8h.fn_dsa_signed_message_kat.v1"

    for vector in kat["vectors"]:
        message = build_real_crypto_signature_input(
            algorithm=vector["algorithm"],
            standard_profile=vector["standard_profile"],
            domain_tag=vector["domain_tag"],
            signed_payload_hash=vector["signed_payload_hash"],
            key_id=vector["key_id"],
            key_version=vector["key_version"],
        )
        assert vector["algorithm"] == "fn-dsa"
        assert vector["standard_profile"] == "fips206-draft-falcon1024-v1"
        assert vector["falcon_parameter_set"] == "Falcon-1024"
        assert message.decode("utf-8") == vector["message_utf8"]
        assert message.hex() == vector["message_hex"]
        assert hashlib.sha256(message).hexdigest() == vector["message_sha256"]
