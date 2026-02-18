from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from adamantine.v1.execution import fixture_harness


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _canon_sha256(obj: Any) -> str:
    s = fixture_harness.canonical_json_dumps(obj)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_load_canonical_json_rejects_duplicate_keys(tmp_path: Path) -> None:
    p = tmp_path / "dup.json"
    _write(p, '{"a":1,"a":2}')
    with pytest.raises(fixture_harness.DuplicateKeyError):
        fixture_harness.load_canonical_json(p)


def test_load_canonical_json_rejects_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    _write(p, "{not-json}")
    with pytest.raises(fixture_harness.CanonicalJSONError):
        fixture_harness.load_canonical_json(p)


def test_load_canonical_json_missing_file_errors(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    with pytest.raises(fixture_harness.CanonicalJSONError):
        fixture_harness.load_canonical_json(p)


def test_fixture_dir_missing_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)
    with pytest.raises(fixture_harness.CanonicalJSONError):
        fixture_harness.verify_manifest_strict_for("no_such_pack")


def test_manifest_must_be_object(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "pack"
    base.mkdir(parents=True)
    _write(base / "manifest.json", "[]")
    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)
    with pytest.raises(fixture_harness.CanonicalJSONError, match="manifest must be a JSON object"):
        fixture_harness.verify_manifest_strict_for("pack")


def test_manifest_must_map_string_to_string(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "pack"
    base.mkdir(parents=True)
    _write(base / "manifest.json", json.dumps({"a.json": 1}))
    _write(base / "a.json", "{}")
    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)
    with pytest.raises(fixture_harness.CanonicalJSONError, match="manifest must map string->string"):
        fixture_harness.verify_manifest_strict_for("pack")


def test_manifest_fixture_set_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "pack"
    base.mkdir(parents=True)
    _write(base / "a.json", "{}")
    _write(base / "manifest.json", json.dumps({"b.json": _canon_sha256({})}))
    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)
    with pytest.raises(fixture_harness.CanonicalJSONError, match="manifest fixture set mismatch"):
        fixture_harness.verify_manifest_strict_for("pack")


def test_manifest_hash_mismatch_includes_suggested_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "pack"
    base.mkdir(parents=True)
    _write(base / "a.json", json.dumps({"x": 1}))
    _write(base / "manifest.json", json.dumps({"a.json": "0" * 64}))
    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)

    with pytest.raises(fixture_harness.CanonicalJSONError) as e:
        fixture_harness.verify_manifest_strict_for("pack")

    msg = str(e.value)
    assert "SUGGESTED manifest.json contents" in msg
    assert "a.json" in msg


def test_run_fixture_calls_orchestrator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "pack"
    base.mkdir(parents=True)

    payload_obj: Dict[str, Any] = {"hello": "world"}
    _write(base / "p.json", json.dumps(payload_obj))
    _write(base / "manifest.json", json.dumps({"p.json": _canon_sha256(payload_obj)}))

    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)

    captured: Dict[str, Any] = {}

    def _fake_orchestrate_execution_v2(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(fixture_harness, "orchestrate_execution_v2", _fake_orchestrate_execution_v2)

    out = fixture_harness.run_fixture("pack", "p.json", now=123)
    assert out == {"ok": True}
    assert captured["payload"] == payload_obj
    assert captured["now"] == 123


def test_run_all_iterates_all_fixtures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = tmp_path / "pack"
    base.mkdir(parents=True)

    a = {"a": 1}
    b = {"b": 2}
    _write(base / "a.json", json.dumps(a))
    _write(base / "b.json", json.dumps(b))
    _write(base / "manifest.json", json.dumps({"a.json": _canon_sha256(a), "b.json": _canon_sha256(b)}))

    monkeypatch.setattr(fixture_harness, "_FIXTURES_BASE", tmp_path)

    def _fake_run_fixture(pack_dirname: str, fixture_name: str, *, now: int) -> Dict[str, Any]:
        return {"fixture": fixture_name, "now": now}

    monkeypatch.setattr(fixture_harness, "run_fixture", _fake_run_fixture)

    out = fixture_harness.run_all("pack", now=9)
    assert sorted(out.keys()) == ["a.json", "b.json"]
    assert out["a.json"]["now"] == 9
    assert out["b.json"]["now"] == 9
