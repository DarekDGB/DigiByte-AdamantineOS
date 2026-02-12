from __future__ import annotations

import re

from typing import Any, Mapping, Sequence

from adamantine.v1.contracts.external_reason_registry import ExternalReasonRegistryV1
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.obs.metrics import Metrics


_ALLOWED_LAYERS = {
    "sentinel_ai": ShieldSource.SENTINEL,
    "adn": ShieldSource.ADN,
    "dqsn": ShieldSource.DQSN,
    "qwg": ShieldSource.QWG,
    "guardian_wallet": ShieldSource.GUARDIAN,
}

_CANONICAL_LAYER_ORDER: tuple[str, ...] = (
    "sentinel_ai",
    "adn",
    "dqsn",
    "qwg",
    "guardian_wallet",
)

_SIGNAL_ALLOWED_KEYS = {
    "v",
    "layer",
    "signal_id",
    "context_hash",
    "issued_at",
    "expires_at",
    "verdict",
    "layer_version",
    "reason_id",
    "confidence",
    "facts",
    "meta",
}

_BUNDLE_ALLOWED_KEYS = {
    "v",
    "bundle_id",
    "context_hash",
    "issued_at",
    "expires_at",
    "signals",
    "required_layers",
    "shield_bundle_version",
    "meta",
}

_FACT_SCALAR_TYPES = (str, int, bool)


def _fail(metrics: Metrics | None, rid: ReasonId, msg: str) -> "NoReturn":  # type: ignore[name-defined]
    if metrics is not None:
        metrics.inc(rid.value)
    raise AdapterError(rid, msg)


def _is_hex_64(s: Any) -> bool:
    if not isinstance(s, str) or len(s) != 64:
        return False
    for ch in s:
        if ch not in "0123456789abcdefABCDEF":
            return False
    return True


_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _is_semver(s: Any) -> bool:
    return isinstance(s, str) and bool(_SEMVER_RE.match(s.strip()))


def _require_mapping(metrics: Metrics | None, obj: Any, rid: ReasonId, name: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        _fail(metrics, rid, f"{name} must be object")
    return obj


def _deny_unknown_keys(metrics: Metrics | None, m: Mapping[str, Any], allowed: set[str], rid: ReasonId, name: str) -> None:
    unknown = set(m.keys()) - allowed
    if unknown:
        _fail(metrics, rid, f"{name} contains unknown fields: {sorted(unknown)}")


def _require_str(metrics: Metrics | None, m: Mapping[str, Any], key: str, rid: ReasonId, name: str) -> str:
    v = m.get(key)
    if not isinstance(v, str) or not v.strip():
        _fail(metrics, rid, f"{name}.{key} must be non-empty str")
    return v


def _require_int(metrics: Metrics | None, m: Mapping[str, Any], key: str, rid: ReasonId, name: str) -> int:
    v = m.get(key)
    if not isinstance(v, int):
        _fail(metrics, rid, f"{name}.{key} must be int")
    return v


def _validate_facts(metrics: Metrics | None, facts: Any) -> None:
    if not isinstance(facts, Mapping):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts must be object")

    for k, v in facts.items():
        if not isinstance(k, str) or not k.strip():
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts keys must be non-empty str")

        if isinstance(v, _FACT_SCALAR_TYPES):
            continue

        if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
            for item in v:
                if not isinstance(item, _FACT_SCALAR_TYPES):
                    _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts list values must be str/int/bool")
            continue

        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts values must be str/int/bool or list[str|int|bool]")


def _parse_signal_v3(
    *,
    signal: Mapping[str, Any],
    metrics: Metrics | None,
    expected_context_hash: str,
    require_versions: bool,
    bundle_issued_at: int,
    bundle_expires_at: int,
    reason_map: ExternalReasonMap,
    reason_registry: ExternalReasonRegistryV1,
) -> tuple[str, ShieldSignal]:
    _deny_unknown_keys(metrics, signal, _SIGNAL_ALLOWED_KEYS, ReasonId.DENY_ADAPTER_INVALID, "signal")

    v = _require_str(metrics, signal, "v", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if v != "shield_signal_v3":
        _fail(metrics, ReasonId.DENY_VERSION_MISMATCH, "signal.v must be shield_signal_v3")

    layer = _require_str(metrics, signal, "layer", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if layer not in _ALLOWED_LAYERS:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"unknown shield layer: {layer}")

    if require_versions:
        lv = _require_str(metrics, signal, "layer_version", ReasonId.DENY_ADAPTER_INVALID, "signal")
        if not _is_semver(lv):
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.layer_version must be semver (X.Y.Z)")

    signal_id = _require_str(metrics, signal, "signal_id", ReasonId.DENY_ADAPTER_INVALID, "signal")

    ctx_hash = _require_str(metrics, signal, "context_hash", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if not _is_hex_64(ctx_hash):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.context_hash must be 64-char hex")
    if ctx_hash != expected_context_hash:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.context_hash mismatch")

    issued_at = _require_int(metrics, signal, "issued_at", ReasonId.DENY_ADAPTER_INVALID, "signal")
    expires_at = _require_int(metrics, signal, "expires_at", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if expires_at < issued_at:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.expires_at must be >= issued_at")

    if issued_at < bundle_issued_at:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.issued_at must be >= bundle.issued_at")
    if expires_at > bundle_expires_at:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.expires_at must be <= bundle.expires_at")

    verdict = _require_str(metrics, signal, "verdict", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if verdict not in ("allow", "deny"):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.verdict must be allow|deny")

    confidence = _require_int(metrics, signal, "confidence", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if not (0 <= confidence <= 100):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.confidence must be 0..100")

    facts = signal.get("facts")
    _validate_facts(metrics, facts)

    ext_reason = _require_str(metrics, signal, "reason_id", ReasonId.DENY_ADAPTER_INVALID, "signal")
    try:
        reason_registry.assert_allowed(layer=layer, external_reason_id=ext_reason)
    except Exception:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.reason_id not allowed by registry")

    internal_rids = reason_map.map_external_reason_ids((ext_reason,))
    if len(internal_rids) != 1:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.reason_id mapping produced unexpected count")

    internal_reason = internal_rids[0]
    src = _ALLOWED_LAYERS[layer]
    severity = 100 if verdict == "deny" else 0

    out = ShieldSignal(source=src, severity=severity, reason_ids=(internal_reason,))
    out.validate()
    return (layer, out)


def parse_shield_bundle_v3(
    *,
    payload: Mapping[str, Any],
    now: int,
    expected_context_hash: str,
    reason_map: ExternalReasonMap,
    reason_registry: ExternalReasonRegistryV1,
    require_versions: bool = False,
    metrics: Metrics | None = None,
) -> ShieldBundleV3:
    if not isinstance(now, int):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "now must be int")

    if not isinstance(expected_context_hash, str) or not expected_context_hash.strip():
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "expected_context_hash must be non-empty str")

    if not isinstance(reason_map, ExternalReasonMap):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "reason_map must be ExternalReasonMap")
    reason_map.validate()

    try:
        reason_registry.validate()
    except Exception:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "reason_registry invalid")

    top = _require_mapping(metrics, payload, ReasonId.DENY_ADAPTER_INVALID, "bundle")
    _deny_unknown_keys(metrics, top, _BUNDLE_ALLOWED_KEYS, ReasonId.DENY_ADAPTER_INVALID, "bundle")

    v = _require_str(metrics, top, "v", ReasonId.DENY_ADAPTER_INVALID, "bundle")
    if v != "shield_bundle_v3":
        _fail(metrics, ReasonId.DENY_VERSION_MISMATCH, "bundle.v must be shield_bundle_v3")

    if require_versions:
        bv = _require_str(metrics, top, "shield_bundle_version", ReasonId.DENY_ADAPTER_INVALID, "bundle")
        if not _is_semver(bv):
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.shield_bundle_version must be semver (X.Y.Z)")

    bundle_id = _require_str(metrics, top, "bundle_id", ReasonId.DENY_ADAPTER_INVALID, "bundle")

    ctx_hash = _require_str(metrics, top, "context_hash", ReasonId.DENY_ADAPTER_INVALID, "bundle")
    if not _is_hex_64(ctx_hash):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.context_hash must be 64-char hex")
    if ctx_hash != expected_context_hash:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.context_hash mismatch")

    issued_at = _require_int(metrics, top, "issued_at", ReasonId.DENY_ADAPTER_INVALID, "bundle")
    expires_at = _require_int(metrics, top, "expires_at", ReasonId.DENY_ADAPTER_INVALID, "bundle")
    if expires_at < issued_at:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.expires_at must be >= issued_at")

    req = top.get("required_layers")
    if not isinstance(req, Sequence) or isinstance(req, (str, bytes, bytearray)) or len(req) == 0:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers must be non-empty array")

    required_layers: list[str] = []
    for x in req:
        if not isinstance(x, str) or not x.strip():
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers entries must be non-empty str")
        if x not in _ALLOWED_LAYERS:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"unknown required layer: {x}")
        required_layers.append(x)

    if require_versions:
        order_index = {name: i for i, name in enumerate(_CANONICAL_LAYER_ORDER)}
        sorted_req = sorted(required_layers, key=lambda x: order_index.get(x, 10_000))
        if required_layers != sorted_req:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers must follow canonical layer order")
        if len(set(required_layers)) != len(required_layers):
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers must not contain duplicates")

    sigs = top.get("signals")
    if not isinstance(sigs, Sequence) or isinstance(sigs, (str, bytes, bytearray)) or len(sigs) == 0:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.signals must be non-empty array")

    def _key(raw: Any) -> tuple[str, str]:
        if not isinstance(raw, Mapping):
            return ("", "")
        layer = raw.get("layer")
        sid = raw.get("signal_id")
        return (str(layer or ""), str(sid or ""))

    sorted_sigs = sorted(list(sigs), key=_key)
    if list(sigs) != sorted_sigs:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.signals must be sorted by (layer, signal_id)")

    seen_layers: set[str] = set()
    parsed: list[ShieldSignal] = []
    for raw in sigs:
        sig_map = _require_mapping(metrics, raw, ReasonId.DENY_ADAPTER_INVALID, "signal")
        layer, internal = _parse_signal_v3(
            signal=sig_map,
            metrics=metrics,
            expected_context_hash=expected_context_hash,
            require_versions=require_versions,
            bundle_issued_at=issued_at,
            bundle_expires_at=expires_at,
            reason_map=reason_map,
            reason_registry=reason_registry,
        )
        if layer in seen_layers:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"duplicate layer signal in bundle: {layer}")
        seen_layers.add(layer)
        parsed.append(internal)

    for rl in required_layers:
        if rl not in seen_layers:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"missing required layer signal: {rl}")

    meta = top.get("meta")
    if meta is not None and not isinstance(meta, Mapping):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.meta must be object when present")

    out = ShieldBundleV3(
        bundle_id=bundle_id,
        context_hash=expected_context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        required_layers=tuple(required_layers),
        signals=tuple(parsed),
    )
    out.validate()
    return out
