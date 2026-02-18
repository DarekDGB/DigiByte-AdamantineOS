from __future__ import annotations

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.qid import QIDReplayProof, QIDSessionProof
from adamantine.v1.contracts.risk import RiskReport
from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3


def test_adaptive_core_oracle_v3_validate_error_paths() -> None:
    rr = RiskReport(context_hash="c" * 64, signals=tuple(), overall_score=1, generated_at=1)

    o = AdaptiveCoreOracleV3(context_hash="c" * 64, issued_at=1, expires_at=2, report=rr)
    with pytest.raises(ValueError, match="now must be int"):
        o.validate(now="nope")  # type: ignore[arg-type]

    o3 = AdaptiveCoreOracleV3(context_hash="c" * 64, issued_at=1, expires_at="2", report=rr)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="issued_at/expires_at must be int"):
        o3.validate(now=1)

    o4 = AdaptiveCoreOracleV3(context_hash="c" * 64, issued_at=2, expires_at=1, report=rr)
    with pytest.raises(ValueError, match="expires_at"):
        o4.validate(now=1)

    o5 = AdaptiveCoreOracleV3(context_hash="c" * 64, issued_at=1, expires_at=2, report="nope")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="report must be RiskReport"):
        o5.validate(now=1)

    rr_bad = RiskReport(context_hash="c" * 64, signals=tuple(), overall_score=-1, generated_at=1)
    o6 = AdaptiveCoreOracleV3(context_hash="c" * 64, issued_at=1, expires_at=2, report=rr_bad)
    with pytest.raises(ValueError):
        o6.validate(now=1)


def test_qid_session_proof_validate_error_paths() -> None:
    ok = QIDSessionProof(subject="s", issued_at=1, expires_at=3, proof_hash="h")

    with pytest.raises(ValueError, match="now must be int"):
        ok.validate(now="nope")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="subject must be non-empty"):
        QIDSessionProof(subject="", issued_at=1, expires_at=3, proof_hash="h").validate(now=2)

    with pytest.raises(ValueError, match="proof_hash must be non-empty"):
        QIDSessionProof(subject="s", issued_at=1, expires_at=3, proof_hash="").validate(now=2)

    with pytest.raises(ValueError, match="issued_at and expires_at must be int"):
        QIDSessionProof(subject="s", issued_at="1", expires_at=3, proof_hash="h").validate(now=2)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="timestamps must be positive"):
        QIDSessionProof(subject="s", issued_at=0, expires_at=3, proof_hash="h").validate(now=2)

    with pytest.raises(ValueError, match="expires_at must be greater"):
        QIDSessionProof(subject="s", issued_at=3, expires_at=3, proof_hash="h").validate(now=3)

    with pytest.raises(ValueError, match="session is not valid"):
        QIDSessionProof(subject="s", issued_at=10, expires_at=11, proof_hash="h").validate(now=2)

    with pytest.raises(ValueError, match="device_binding must be str"):
        QIDSessionProof(subject="s", issued_at=1, expires_at=3, proof_hash="h", device_binding=123).validate(now=2)  # type: ignore[arg-type]


def test_qid_replay_proof_validate_error_paths() -> None:
    base = dict(
        proof_version="1",
        wallet_id="w",
        subject="s",
        proof_hash="h",
        session_nonce="n",
        registry_commitment="c",
        fresh=True,
    )

    with pytest.raises(ValueError, match="proof_version"):
        QIDReplayProof(**{**base, "proof_version": ""}).validate()

    with pytest.raises(ValueError, match="wallet_id"):
        QIDReplayProof(**{**base, "wallet_id": ""}).validate()

    with pytest.raises(ValueError, match="subject"):
        QIDReplayProof(**{**base, "subject": ""}).validate()

    with pytest.raises(ValueError, match="proof_hash"):
        QIDReplayProof(**{**base, "proof_hash": ""}).validate()

    with pytest.raises(ValueError, match="session_nonce"):
        QIDReplayProof(**{**base, "session_nonce": ""}).validate()

    with pytest.raises(ValueError, match="registry_commitment"):
        QIDReplayProof(**{**base, "registry_commitment": ""}).validate()

    with pytest.raises(ValueError, match="fresh must be bool"):
        QIDReplayProof(**{**base, "fresh": "yes"}).validate()  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="device_binding"):
        QIDReplayProof(**{**base, "device_binding": ""}).validate()


def test_shield_bundle_v3_validate_error_paths() -> None:
    sig = ShieldSignal(source=ShieldSource.SENTINEL, severity=0, reason_ids=("OK_ALLOW",))

    with pytest.raises(ValueError, match="bundle_id"):
        ShieldBundleV3(
            bundle_id="",
            context_hash="c" * 64,
            issued_at=1,
            expires_at=2,
            required_layers=("sentinel_ai",),
            signals=(sig,),
        ).validate()

    with pytest.raises(ValueError, match="context_hash"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="x",
            issued_at=1,
            expires_at=2,
            required_layers=("sentinel_ai",),
            signals=(sig,),
        ).validate()

    with pytest.raises(ValueError, match="issued_at/expires_at"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="c" * 64,
            issued_at=1,
            expires_at="2",  # type: ignore[arg-type]
            required_layers=("sentinel_ai",),
            signals=(sig,),
        ).validate()

    with pytest.raises(ValueError, match="expires_at"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="c" * 64,
            issued_at=2,
            expires_at=1,
            required_layers=("sentinel_ai",),
            signals=(sig,),
        ).validate()

    with pytest.raises(ValueError, match="required_layers must be a non-empty tuple"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="c" * 64,
            issued_at=1,
            expires_at=2,
            required_layers=(),
            signals=(sig,),
        ).validate()

    with pytest.raises(ValueError, match="required_layers entries"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="c" * 64,
            issued_at=1,
            expires_at=2,
            required_layers=("",),
            signals=(sig,),
        ).validate()

    with pytest.raises(ValueError, match="signals must be a non-empty tuple"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="c" * 64,
            issued_at=1,
            expires_at=2,
            required_layers=("sentinel_ai",),
            signals=(),
        ).validate()

    with pytest.raises(ValueError, match="signals must contain ShieldSignal"):
        ShieldBundleV3(
            bundle_id="b1",
            context_hash="c" * 64,
            issued_at=1,
            expires_at=2,
            required_layers=("sentinel_ai",),
            signals=("nope",),  # type: ignore[arg-type]
        ).validate()


def test_shield_bundle_v3_valid() -> None:
    sig = ShieldSignal(source=ShieldSource.SENTINEL, severity=0, reason_ids=("OK_ALLOW",))
    ShieldBundleV3(
        bundle_id="b1",
        context_hash="c" * 64,
        issued_at=1,
        expires_at=2,
        required_layers=("sentinel_ai",),
        signals=(sig,),
    ).validate()
