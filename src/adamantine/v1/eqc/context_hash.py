from __future__ import annotations

import hashlib


class ContextHashError(ValueError):
    """Fail-closed: the context hash input was structurally ambiguous."""


def _reject_control_chars(value: str, *, field: str) -> None:
    if not isinstance(value, str):
        raise ContextHashError(f"{field} must be str")
    for ch in value:
        o = ord(ch)
        if o < 0x20 or o == 0x7F:
            raise ContextHashError(f"{field} contains a forbidden control character")


def compute_context_hash(*, wallet_id: str, action: str, fields: dict[str, str] | None = None) -> str:
    """
    Deterministic context hash.

    Canonical form:
      wallet_id=<...>\n
      action=<...>\n
      <sorted fields as key=value>\n
    Properties:
      - No randomness
      - No time
      - Stable ordering
      - Injection-resistant: control characters are rejected in every input, and
        "=" is rejected inside field keys, so the canonical encoding is
        unambiguous and two distinct contexts cannot collide to one hash.

    Fail-closed: raises ContextHashError (a ValueError subclass) on ambiguous input.
    """
    _reject_control_chars(wallet_id, field="wallet_id")
    _reject_control_chars(action, field="action")

    f = fields or {}
    parts: list[str] = [f"wallet_id={wallet_id}", f"action={action}"]
    for k in sorted(f.keys()):
        _reject_control_chars(k, field="field key")
        if "=" in k:
            raise ContextHashError("field key must not contain '='")
        v = f[k]
        _reject_control_chars(v, field="field value")
        parts.append(f"{k}={v}")
    canonical = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
