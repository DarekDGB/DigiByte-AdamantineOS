from __future__ import annotations

import hashlib


def compute_context_hash(*, wallet_id: str, action: str, fields: dict[str, str] | None = None) -> str:
    """
    Deterministic context hash.

    Canonical form:
      wallet_id=<...>\n
      action=<...>\n
      <sorted fields as key=value>\n

    - No randomness
    - No time
    - Stable ordering
    """
    f = fields or {}
    parts: list[str] = [f"wallet_id={wallet_id}", f"action={action}"]
    for k in sorted(f.keys()):
        parts.append(f"{k}={f[k]}")
    canonical = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
