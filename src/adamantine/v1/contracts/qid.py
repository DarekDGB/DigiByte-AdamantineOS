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


@dataclass(frozen=True)
class QIDReplayProof:
    """Immutable Q-ID replay proof contract (v1.4.0).

    This structure is *evidence* supplied by an untrusted runtime to prove that a
    given session_nonce has not been observed before for the given wallet_id.

    Adamantine remains pure/stateless; it validates this proof deterministically and
    fails closed if it is missing/invalid.

    Cryptographic verification and durable storage are external.
    """

    proof_version: str
    wallet_id: str
    subject: str
    proof_hash: str
    session_nonce: str
    registry_commitment: str
    fresh: bool
    device_binding: Optional[str] = None

    def validate(self) -> None:
        if not isinstance(self.proof_version, str) or not self.proof_version:
            raise ValueError("proof_version must be non-empty str")
        if not isinstance(self.wallet_id, str) or not self.wallet_id:
            raise ValueError("wallet_id must be non-empty str")
        if not isinstance(self.subject, str) or not self.subject:
            raise ValueError("subject must be non-empty str")
        if not isinstance(self.proof_hash, str) or not self.proof_hash:
            raise ValueError("proof_hash must be non-empty str")
        if not isinstance(self.session_nonce, str) or not self.session_nonce:
            raise ValueError("session_nonce must be non-empty str")
        if not isinstance(self.registry_commitment, str) or not self.registry_commitment:
            raise ValueError("registry_commitment must be non-empty str")
        if not isinstance(self.fresh, bool):
            raise ValueError("fresh must be bool")
        if self.device_binding is not None and (not isinstance(self.device_binding, str) or not self.device_binding):
            raise ValueError("device_binding must be non-empty str or None")
