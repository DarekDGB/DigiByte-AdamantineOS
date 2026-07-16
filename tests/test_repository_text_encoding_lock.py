from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

_TEXT_SUFFIXES = {
    ".cfg",
    ".gitignore",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_TEXT_FILE_NAMES = {".gitignore", "LICENSE", "Makefile"}
_SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}

_SUSPICIOUS_LEAD_CODEPOINTS = (0x00C2, 0x00C3, 0x00E2, 0x00F0)
_DECODED_BOM_MOJIBAKE = "".join(chr(codepoint) for codepoint in (0x00EF, 0x00BB, 0x00BF))
_DECODED_REPLACEMENT_MOJIBAKE = "".join(chr(codepoint) for codepoint in (0x00EF, 0x00BF, 0x00BD))

_REPAIRED_PHRASES = {
    "docs/ADAMANTINEOS_SHIELD_RUNTIME_BOUNDARY_LOCK.md": (
        'not a public "Shield live" protection claim',
    ),
    "docs/CONTRACTS/upgrade_governance_review_v1.md": (
        "If any step fails -> proposal is rejected.",
        "cross-repository compatibility",
    ),
    "docs/INDEX.md": (
        "Adaptive Core -> Adamantine Governance Flow",
        "fail-closed validation",
    ),
    "src/adamantine/v1/enforcement/tva_gate.py": (
        "TVA (Truth Vector Authority) - final enforcement gate (fail-closed).",
    ),
    "src/adamantine/v1/execution/mobile_call_v1.py": (
        "status <-> reason_id semantics + nonce/timebox safety invariants",
    ),
    "src/adamantine/v1/execution/response_v2.py": (
        'status in {"allow","deny","error"}',
        'protection_mode in {"legacy","minimal","full"}',
    ),
    "src/adamantine/v1/integrations/shield_v3_adapter.py": (
        "Correct registry API + correct reason id",
        "Correct reason map API",
    ),
    "src/adamantine/v1/runtime/runtime_adapter.py": (
        "Runtime <-> Adamantine adapter (interface only).",
    ),
    "tests/test_step11_1_authenticated_external_evidence.py": (
        'not a public "Shield live" protection claim',
    ),
}
_REQUIRED_SCAN_PATHS = frozenset(_REPAIRED_PHRASES) | {
    ".github/workflows/ci.yml",
    "README.md",
    "pyproject.toml",
    "src/adamantine/__init__.py",
}


def _is_repository_text_file(path: Path) -> bool:
    relative = path.relative_to(REPO_ROOT)
    if any(part in _SKIP_DIR_NAMES for part in relative.parts):
        return False
    return path.name in _TEXT_FILE_NAMES or path.suffix.lower() in _TEXT_SUFFIXES


def _encoding_findings(text: str) -> list[str]:
    findings: list[str] = []

    if any(0x0080 <= ord(character) <= 0x009F for character in text):
        findings.append("C1 control")
    if "\ufeff" in text:
        findings.append("U+FEFF")
    if "\ufffd" in text:
        findings.append("U+FFFD")
    if _DECODED_BOM_MOJIBAKE in text:
        findings.append("decoded UTF-8 BOM mojibake")
    if _DECODED_REPLACEMENT_MOJIBAKE in text:
        findings.append("decoded replacement-character mojibake")

    for codepoint in _SUSPICIOUS_LEAD_CODEPOINTS:
        if chr(codepoint) in text:
            findings.append(f"known mojibake lead U+{codepoint:04X}")

    return findings


def _read_strict_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def test_encoding_detector_rejects_each_governed_failure_class() -> None:
    bad_samples = (
        chr(0x0080),
        chr(0x009F),
        "\ufeff",
        "\ufffd",
        _DECODED_BOM_MOJIBAKE,
        _DECODED_REPLACEMENT_MOJIBAKE,
        *(chr(codepoint) for codepoint in _SUSPICIOUS_LEAD_CODEPOINTS),
    )

    for sample in bad_samples:
        assert _encoding_findings(f"safe{sample}text")


def test_encoding_detector_does_not_prohibit_valid_unicode_generally() -> None:
    assert _encoding_findings("valid -> \u2192 \u03bb \U0001f600") == []


def test_strict_utf8_reader_rejects_invalid_bytes(tmp_path: Path) -> None:
    invalid_text = tmp_path / "invalid.md"
    invalid_text.write_bytes(b"valid-prefix\xff")

    with pytest.raises(UnicodeDecodeError):
        _read_strict_utf8(invalid_text)


def test_repository_text_is_strict_utf8_without_known_mojibake() -> None:
    scanned_paths: list[str] = []
    failures: list[str] = []

    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or not _is_repository_text_file(path):
            continue

        relative = path.relative_to(REPO_ROOT).as_posix()
        scanned_paths.append(relative)
        try:
            text = _read_strict_utf8(path)
        except UnicodeDecodeError as exc:
            failures.append(f"{relative}: invalid UTF-8: {exc}")
            continue

        findings = _encoding_findings(text)
        if findings:
            failures.append(f"{relative}: {', '.join(findings)}")

    assert len(scanned_paths) >= 400
    assert _REQUIRED_SCAN_PATHS.issubset(scanned_paths)
    assert failures == []


def test_all_repaired_phrases_are_locked_as_ascii_text() -> None:
    assert set(_REPAIRED_PHRASES) == {
        "docs/ADAMANTINEOS_SHIELD_RUNTIME_BOUNDARY_LOCK.md",
        "docs/CONTRACTS/upgrade_governance_review_v1.md",
        "docs/INDEX.md",
        "src/adamantine/v1/enforcement/tva_gate.py",
        "src/adamantine/v1/execution/mobile_call_v1.py",
        "src/adamantine/v1/execution/response_v2.py",
        "src/adamantine/v1/integrations/shield_v3_adapter.py",
        "src/adamantine/v1/runtime/runtime_adapter.py",
        "tests/test_step11_1_authenticated_external_evidence.py",
    }

    for relative, expected_phrases in _REPAIRED_PHRASES.items():
        text = _read_strict_utf8(REPO_ROOT / relative)
        assert text.isascii(), relative
        for phrase in expected_phrases:
            assert phrase.isascii()
            assert phrase in text
