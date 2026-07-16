from __future__ import annotations

import re
from typing import Any, Mapping, NoReturn, Sequence

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

# Phase A: canonical ordering for required_layers (enforced only when require_versions=True)
_CANONICAL_LAYER_ORDER: tuple[str, ...] = (
    "sentinel_ai",
    "adn",
    "dqsn",
    "qwg",
    "guardian_wallet",
)

# Phase A: allow new version fields (enforced only when require_versions=True)
_SIGNAL_ALLOWED_KEYS = {
    "v",
    "layer",
    "signal_id",
    "context_hash",
    "issued_at",
    "expires_at",
    "verdict",
    "reason_id",
    "confidence",
    "facts",
    "meta",
    "layer_version",  # Phase A
}

_BUNDLE_ALLOWED_KEYS = {
    "v",
    "bundle_id",
    "context_hash",
    "issued_at",
    "expires_at",
    "signals",
    "required_layers",
    "meta",
    "shield_bundle_version",  # Phase A
}

# ---- Deterministic Size Caps (v1.3.0 hardening) ----
_MAX_REQUIRED_LAYERS = 8
_MAX_SIGNALS = 32

_MAX_FACTS_ENTRIES = 32
_MAX_META_ENTRIES = 32
_MAX_LIST_LEN = 32

_MAX_STR = 256
_MAX_LAYER_STR = 64
_MAX_ID_STR = 128
_MAX_VERSION_STR = 64

# NOTE: facts allow str/int/bool scalars and lists of those (bounded).
_FACT_SCALAR_TYPES = (str, int, bool)

_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _is_semver(s: Any) -> bool:
    return isinstance(s, str) and bool(_SEMVER_RE.match(s.strip()))


def _fail(metrics: Metrics | None, rid: ReasonId, msg: str) -> NoReturn:
    if metrics is not None:
        metrics.inc(rid.value)
    raise AdapterError(rid, msg)


def _is_hex_64(s: Any) -> bool:
    if not isinstance(s, str) or len(s) != 64:
        return False
    for ch in s:
        if ch not in "0123456789abcdef":
            return False
    return True


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


def _require_str_max(
    metrics: Metrics | None,
    m: Mapping[str, Any],
    key: str,
    *,
    rid: ReasonId,
    name: str,
    max_len: int,
    label: str,
) -> str:
    v = _require_str(metrics, m, key, rid, name)
    if len(v) > max_len:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{label} too long")
    return v


def _require_int(metrics: Metrics | None, m: Mapping[str, Any], key: str, rid: ReasonId, name: str) -> int:
    v = m.get(key)
    if type(v) is not int:
        _fail(metrics, rid, f"{name}.{key} must be int")
    return v


def _validate_facts(metrics: Metrics | None, facts: Any) -> None:
    if not isinstance(facts, Mapping):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts must be object")

    if len(facts) > _MAX_FACTS_ENTRIES:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts too many entries")

    for k, v in facts.items():
        if not isinstance(k, str) or not k.strip():
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts keys must be non-empty str")
        if len(k) > _MAX_STR:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts key too long")

        if isinstance(v, str):
            if len(v) > _MAX_STR:
                _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts string value too long")
            continue

        if isinstance(v, (int, bool)):
            continue

        if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
            if len(v) > _MAX_LIST_LEN:
                _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts list too long")
            for item in v:
                if isinstance(item, str):
                    if len(item) > _MAX_STR:
                        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts list string value too long")
                    continue
                if isinstance(item, (int, bool)):
                    continue
                _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts list values must be str/int/bool")
            continue

        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.facts values must be str/int/bool or list[str|int|bool]")


def _validate_meta(metrics: Metrics | None, meta: Any, *, name: str) -> None:
    if meta is None:
        return
    if not isinstance(meta, Mapping):
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{name}.meta must be object when present")

    if len(meta) > _MAX_META_ENTRIES:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{name}.meta too many entries")

    for k, v in meta.items():
        if not isinstance(k, str) or not k.strip():
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{name}.meta keys must be non-empty str")
        if len(k) > _MAX_STR:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{name}.meta key too long")
        if not isinstance(v, str) or not v.strip():
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{name}.meta values must be non-empty str")
        if len(v) > _MAX_STR:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"{name}.meta value too long")


def _parse_signal_v3(
    *,
    signal: Mapping[str, Any],
    metrics: Metrics | None,
    expected_context_hash: str,
    bundle_issued_at: int,
    bundle_expires_at: int,
    reason_map: ExternalReasonMap,
    reason_registry: ExternalReasonRegistryV1,
    require_versions: bool,
) -> tuple[str, ShieldSignal]:
    _deny_unknown_keys(metrics, signal, _SIGNAL_ALLOWED_KEYS, ReasonId.DENY_ADAPTER_INVALID, "signal")

    v = _require_str(metrics, signal, "v", ReasonId.DENY_ADAPTER_INVALID, "signal")
    if v != "shield_signal_v3":
        _fail(metrics, ReasonId.DENY_VERSION_MISMATCH, "signal.v must be shield_signal_v3")

    layer = _require_str_max(
        metrics, signal, "layer", rid=ReasonId.DENY_ADAPTER_INVALID, name="signal", max_len=_MAX_LAYER_STR, label="signal.layer"
    )
    if layer not in _ALLOWED_LAYERS:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"unknown shield layer: {layer}")

    # Phase A (strict only)
    if require_versions:
        lv = _require_str_max(
            metrics,
            signal,
            "layer_version",
            rid=ReasonId.DENY_ADAPTER_INVALID,
            name="signal",
            max_len=_MAX_VERSION_STR,
            label="signal.layer_version",
        )
        if not _is_semver(lv):
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "signal.layer_version must be semver (X.Y.Z)")

    _require_str_max(
        metrics,
        signal,
        "signal_id",
        rid=ReasonId.DENY_ADAPTER_INVALID,
        name="signal",
        max_len=_MAX_ID_STR,
        label="signal.signal_id",
    )

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

    _validate_meta(metrics, signal.get("meta"), name="signal")

    ext_reason = _require_str_max(
        metrics,
        signal,
        "reason_id",
        rid=ReasonId.DENY_ADAPTER_INVALID,
        name="signal",
        max_len=_MAX_STR,
        label="signal.reason_id",
    )

    # Correct registry API + correct reason id
    if not reason_registry.is_shield_reason_allowed(layer=layer, external_reason_id=ext_reason):
        _fail(metrics, ReasonId.UNKNOWN_EXTERNAL_REASON, f"external reason_id not allowed for layer {layer}: {ext_reason}")

    # Correct reason map API
    mapped = reason_map.lookup(ext_reason)
    if mapped is None:
        _fail(metrics, ReasonId.UNKNOWN_EXTERNAL_REASON, f"unmapped external reason_id: {ext_reason}")

    src = _ALLOWED_LAYERS[layer]
    severity = 100 if verdict == "deny" else 0

    out = ShieldSignal(source=src, severity=severity, reason_ids=(mapped,))
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
    if type(now) is not int:
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

    # Phase A (strict only)
    if require_versions:
        bv = _require_str_max(
            metrics,
            top,
            "shield_bundle_version",
            rid=ReasonId.DENY_ADAPTER_INVALID,
            name="bundle",
            max_len=_MAX_VERSION_STR,
            label="bundle.shield_bundle_version",
        )
        if not _is_semver(bv):
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.shield_bundle_version must be semver (X.Y.Z)")

    bundle_id = _require_str_max(
        metrics,
        top,
        "bundle_id",
        rid=ReasonId.DENY_ADAPTER_INVALID,
        name="bundle",
        max_len=_MAX_ID_STR,
        label="bundle.bundle_id",
    )

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

    if len(req) > _MAX_REQUIRED_LAYERS:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers too many entries")

    required_layers: list[str] = []
    for x in req:
        if not isinstance(x, str) or not x.strip():
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers entries must be non-empty str")
        if len(x) > _MAX_LAYER_STR:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers entry too long")
        if x not in _ALLOWED_LAYERS:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"unknown required layer: {x}")
        required_layers.append(x)

    # Phase A strict: enforce canonical ordering + no duplicates
    if require_versions:
        if len(set(required_layers)) != len(required_layers):
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers must not contain duplicates")
        order_index = {name: i for i, name in enumerate(_CANONICAL_LAYER_ORDER)}
        sorted_req = sorted(required_layers, key=lambda name: order_index.get(name, 10_000))
        if required_layers != sorted_req:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.required_layers must follow canonical layer order")

    sigs = top.get("signals")
    if not isinstance(sigs, Sequence) or isinstance(sigs, (str, bytes, bytearray)) or len(sigs) == 0:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.signals must be non-empty array")

    if len(sigs) > _MAX_SIGNALS:
        _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, "bundle.signals too many entries")

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
            bundle_issued_at=issued_at,
            bundle_expires_at=expires_at,
            reason_map=reason_map,
            reason_registry=reason_registry,
            require_versions=require_versions,
        )
        if layer in seen_layers:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"duplicate layer signal in bundle: {layer}")
        seen_layers.add(layer)
        parsed.append(internal)

    for rl in required_layers:
        if rl not in seen_layers:
            _fail(metrics, ReasonId.DENY_ADAPTER_INVALID, f"missing required layer signal: {rl}")

    _validate_meta(metrics, top.get("meta"), name="bundle")

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
