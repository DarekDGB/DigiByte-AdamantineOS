from __future__ import annotations

import json
from datetime import datetime, timezone

from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.envelope_v2 import parse_execution_request_envelope_v2


def _iso_to_unix_seconds(s: str) -> int:
    iso = s
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp())


def test_context_fields_are_chain_agnostic() -> None:
    # Load a sealed proof-pack fixture but modify in-memory only (pack remains immutable on disk).
    with open("src/adamantine/v1/fixtures/v1_4_0/full_allow.json", "r", encoding="utf-8") as f:
        env = json.load(f)

    # Ensure the parser does not require DigiByte-specific values.
    env["context"]["fields"]["asset"] = "BTC"

    issued_at = _iso_to_unix_seconds(env["timebox"]["issued_at"])
    expires_at = _iso_to_unix_seconds(env["timebox"]["expires_at"])
    now = issued_at + 1
    assert now < expires_at

    parsed = parse_execution_request_envelope_v2(payload=env, now=now, metrics=None)

    # Context hash is computed from wallet_id + action + fields (string-only, opaque).
    expected = compute_context_hash(
        wallet_id=env["context"]["wallet_id"],
        action=env["context"]["action"],
        fields=env["context"]["fields"],
    )
    assert parsed.context.context_hash == expected
