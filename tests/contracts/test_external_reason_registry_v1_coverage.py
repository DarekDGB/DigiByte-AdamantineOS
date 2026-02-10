from __future__ import annotations

import pytest

from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)


def _valid_registry() -> ExternalReasonRegistryV1:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),
        ),
    )
    reg.validate()
    return reg


def test_layer_allowlist_rejects_empty_layer() -> None:
    x = ExternalReasonLayerAllowlist(layer="", allowed_external_reason_ids=("OK",))
    with pytest.raises(ValueError, match="layer must be non-empty str"):
        x.validate()


def test_layer_allowlist_rejects_non_tuple_ids() -> None:
    x = ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=["OK"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="allowed_external_reason_ids must be a non-empty tuple"):
        x.validate()


def test_layer_allowlist_rejects_empty_reason_entry() -> None:
    x = ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("",))
    with pytest.raises(ValueError, match="entries must be non-empty str"):
        x.validate()


def test_layer_allowlist_rejects_duplicate_reason_entry() -> None:
    x = ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK", "OK"))
    with pytest.raises(ValueError, match="entries must be unique"):
        x.validate()


def test_registry_rejects_oracle_allowlist_not_tuple() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=["OK"],  # type: ignore[arg-type]
        shield_layer_allowlists=(ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),),
    )
    with pytest.raises(ValueError, match="oracle_allowed_external_reason_ids must be tuple"):
        reg.validate()


def test_registry_rejects_empty_oracle_allowlist() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=(),
        shield_layer_allowlists=(ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),),
    )
    with pytest.raises(ValueError, match="oracle_allowed_external_reason_ids must be non-empty"):
        reg.validate()


def test_registry_rejects_blank_oracle_reason_id() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=(" ",),
        shield_layer_allowlists=(ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),),
    )
    with pytest.raises(ValueError, match="oracle_allowed_external_reason_ids entries must be non-empty str"):
        reg.validate()


def test_registry_rejects_duplicate_oracle_reason_id() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK", "OK"),
        shield_layer_allowlists=(ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),),
    )
    with pytest.raises(ValueError, match="oracle_allowed_external_reason_ids must be unique"):
        reg.validate()


def test_registry_rejects_shield_allowlists_not_tuple() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=[ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",))],  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="shield_layer_allowlists must be tuple"):
        reg.validate()


def test_registry_rejects_empty_shield_allowlists() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(),
    )
    with pytest.raises(ValueError, match="shield_layer_allowlists must be non-empty"):
        reg.validate()


def test_registry_rejects_shield_entry_wrong_type() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=("not-an-allowlist",),  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="entries must be ExternalReasonLayerAllowlist"):
        reg.validate()


def test_registry_rejects_duplicate_layer_entries() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),
        ),
    )
    with pytest.raises(ValueError, match="must not contain duplicate layers"):
        reg.validate()


def test_is_oracle_reason_allowed_covers_empty_input_branch() -> None:
    reg = _valid_registry()
    assert reg.is_oracle_reason_allowed("") is False


def test_is_shield_reason_allowed_covers_empty_input_branch() -> None:
    reg = _valid_registry()
    assert reg.is_shield_reason_allowed(layer="", external_reason_id="OK") is False
    assert reg.is_shield_reason_allowed(layer="qwg", external_reason_id="") is False
