from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class QIDSessionProof:
    """
    Immutable Q-ID session proof contract.

    This structure represents validated identity/session evidence.
    Cryptographic verification is external; this contract enforces shape and bounds only.
    """

    subject: str
    issued_at: int
    expires_at: int
    proof_hash: str
    device_binding: Optional[str] = None
    issuer_version: Optional[str] = None

    def validate(self, *, now: int) -> None:
        if not isinstance(now, int):
            raise ValueError("now must be int")

        if not self.subject:
            raise ValueError("subject must be non-empty")

        if not self.proof_hash:
            raise ValueError("proof_hash must be non-empty")

        if not isinstance(self.issued_at, int) or not isinstance(self.expires_at, int):
            raise ValueError("issued_at and expires_at must be int")

        if self.issued_at <= 0 or self.expires_at <= 0:
            raise ValueError("timestamps must be positive")

        if self.issued_at >= self.expires_at:
            raise ValueError("expires_at must be greater than issued_at")

        if not (self.issued_at <= now < self.expires_at):
            raise ValueError("session is not valid at current time")

        if self.device_binding is not None and not isinstance(self.device_binding, str):
            raise ValueError("device_binding must be str or None")
