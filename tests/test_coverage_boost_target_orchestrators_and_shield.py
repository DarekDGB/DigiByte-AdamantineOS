from __future__ import annotations

from typing import Any, Mapping

import pytest

from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.execution import orchestrator_v1 as o1
from adamantine.v1.execution import orchestrator_v2 as o2
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3


def test_orchestrator_v1_extract_wsqk_authority_fail_closed_matrix() -> None:
    # Covers the individual early-return lines in _extract_wsqk_authority
    base = {
        "wsqk": {
            "wallet_id": "w",
            "action": "sign",
            "context_hash": "c" * 64,
            "issued_at": 1,
            "expires_at": 2,
            "nonce": "n",
        }
    }

    assert (
        o1._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs=None,
        )
        is None
    )

    assert (
        o1._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs={},
        )
        is None
    )

    # wrong types / empty
    for patch in [
        {"wallet_id": ""},
        {"action": ""},
        {"context_hash": ""},
        {"issued_at": "1"},
        {"nonce": ""},
    ]:
        wsqk = dict(base["wsqk"])
        wsqk.update(patch)
        assert (
            o1._extract_wsqk_authority(
                wallet_id="w",
                action="sign",
                context_hash="c" * 64,
                nonce_value="n",
                issued_at=1,
                expires_at=2,
                authority_proofs={"wsqk": wsqk},
            )
            is None
        )

    # binding mismatches
    assert (
        o1._extract_wsqk_authority(
            wallet_id="other",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs=base,
        )
        is None
    )
    assert (
        o1._extract_wsqk_authority(
            wallet_id="w",
            action="other",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs=base,
        )
        is None
    )
    assert (
        o1._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="d" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs=base,
        )
        is None
    )
    assert (
        o1._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="c" * 64,
            nonce_value="other",
            issued_at=1,
            expires_at=2,
            authority_proofs=base,
        )
        is None
    )
    assert (
        o1._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=999,
            expires_at=2,
            authority_proofs=base,
        )
        is None
    )


def test_orchestrator_v2_coerce_reason_id_invalid_string_hits_except() -> None:
    # Covers the try/except branch in _coerce_reason_id (lines 57-58)
    assert o2._coerce_reason_id("NOT_A_REASON") == ReasonId.DENY_SCHEMA_INVALID


def test_orchestrator_v2_extract_wsqk_authority_fail_closed_matrix() -> None:
    base = {
        "wsqk": {
            "wallet_id": "w",
            "action": "sign",
            "context_hash": "c" * 64,
            "issued_at": 1,
            "expires_at": 2,
            "nonce": "n",
        }
    }

    assert (
        o2._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs=None,
        )
        is None
    )

    assert (
        o2._extract_wsqk_authority(
            wallet_id="w",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs={},
        )
        is None
    )

    for patch in [
        {"wallet_id": ""},
        {"action": ""},
        {"context_hash": ""},
        {"issued_at": "1"},
        {"nonce": ""},
    ]:
        wsqk = dict(base["wsqk"])
        wsqk.update(patch)
        assert (
            o2._extract_wsqk_authority(
                wallet_id="w",
                action="sign",
                context_hash="c" * 64,
                nonce_value="n",
                issued_at=1,
                expires_at=2,
                authority_proofs={"wsqk": wsqk},
            )
            is None
        )

    assert (
        o2._extract_wsqk_authority(
            wallet_id="other",
            action="sign",
            context_hash="c" * 64,
            nonce_value="n",
            issued_at=1,
            expires_at=2,
            authority_proofs=base,
        )
        is None
    )


# ---- Shield v3 adapter missing branches ----


def _reason_map(*, include_ok: bool = True) -> ExternalReasonMap:
    # ExternalReasonMap.validate() requires a non-empty tuple.
    entries = [ExternalReasonMapEntry(external_id="some_other", internal_reason_id=ReasonId.DENY_POLICY.value)]
    if include_ok:
        entries.append(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.DENY_POLICY.value))
    return ExternalReasonMap(entries=tuple(entries))


def _reason_registry(*, allow_ok: bool = True) -> ExternalReasonRegistryV1:
    allowlists = []
    if allow_ok:
        allowlists.append(ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("ok",)))
    return ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("oracle_ok",),
        shield_layer_allowlists=tuple(allowlists),
    )


def _base_signal(*, ctx: str, issued_at: int = 10, expires_at: int = 20) -> dict[str, Any]:
    return {
        "v": "shield_signal_v3",
        "layer": "qwg",
        "signal_id": "qwg-1",
        "context_hash": ctx,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "verdict": "allow",
        "reason_id": "ok",
        "confidence": 100,
        "facts": {"k": "v"},
    }


def _base_bundle(*, ctx: str, sigs: list[Mapping[str, Any]], issued_at: int = 10, expires_at: int = 20) -> dict[str, Any]:
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": ctx,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "required_layers": ["qwg"],
        "signals": sigs,
    }


def test_shield_v3_facts_and_meta_edge_paths() -> None:
    ctx = "a" * 64

    # facts key too long (line 150)
    sig = _base_signal(ctx=ctx)
    sig["facts"] = {"x" * 300: "v"}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # facts list string value too long (line 166)
    sig = _base_signal(ctx=ctx)
    sig["facts"] = {"k": ["x" * 300]}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # facts list contains int (valid branch `continue` at line 169)
    sig = _base_signal(ctx=ctx)
    sig["facts"] = {"k": [1]}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    out = parse_shield_bundle_v3(
        payload=b,
        now=15,
        expected_context_hash=ctx,
        reason_map=_reason_map(),
        reason_registry=_reason_registry(),
    )
    assert out.context_hash == ctx

    # facts value is unsupported type (line 173)
    sig = _base_signal(ctx=ctx)
    sig["facts"] = {"k": {"nested": True}}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # meta blank key (line 187)
    sig = _base_signal(ctx=ctx)
    sig["meta"] = {"": "v"}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # meta key too long (line 189)
    sig = _base_signal(ctx=ctx)
    sig["meta"] = {"x" * 300: "v"}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # meta blank value (line 191)
    sig = _base_signal(ctx=ctx)
    sig["meta"] = {"k": ""}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # meta value too long (line 193)
    sig = _base_signal(ctx=ctx)
    sig["meta"] = {"k": "x" * 300}
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )


def test_shield_v3_signal_time_verdict_confidence_and_mapping_paths() -> None:
    ctx = "a" * 64

    # signal.expires_at < issued_at (line 252)
    sig = _base_signal(ctx=ctx, issued_at=20, expires_at=10)
    b = _base_bundle(ctx=ctx, sigs=[sig], issued_at=10, expires_at=30)
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # signal.issued_at < bundle_issued_at (line 255)
    sig = _base_signal(ctx=ctx, issued_at=9, expires_at=20)
    b = _base_bundle(ctx=ctx, sigs=[sig], issued_at=10, expires_at=30)
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # signal.expires_at > bundle_expires_at (line 257)
    sig = _base_signal(ctx=ctx, issued_at=10, expires_at=31)
    b = _base_bundle(ctx=ctx, sigs=[sig], issued_at=10, expires_at=30)
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # verdict invalid (line 261)
    sig = _base_signal(ctx=ctx)
    sig["verdict"] = "maybe"
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # confidence out of range (line 265)
    sig = _base_signal(ctx=ctx)
    sig["confidence"] = 101
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # unmapped external reason (line 289) but registry allows it
    sig = _base_signal(ctx=ctx)
    b = _base_bundle(ctx=ctx, sigs=[sig])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(include_ok=False),  # no "ok" mapping
            reason_registry=_reason_registry(allow_ok=True),  # "ok" is allowed by registry
        )
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_shield_v3_bundle_ctx_and_required_layers_entry_paths() -> None:
    ctx = "a" * 64

    # bundle context_hash not hex-64 (line 357)
    sig = _base_signal(ctx=ctx)
    b = _base_bundle(ctx="b" * 64, sigs=[sig])
    b["context_hash"] = "not-hex"
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )

    # required_layers entry blank (line 376)
    sig = _base_signal(ctx=ctx)
    b = _base_bundle(ctx=ctx, sigs=[sig])
    b["required_layers"] = [""]
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=b,
            now=15,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=_reason_registry(),
        )
