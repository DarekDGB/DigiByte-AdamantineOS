from __future__ import annotations

from pathlib import Path


def test_reproducible_audit_guide_is_public_professional_and_indexed() -> None:
    doc_path = Path("docs/ADAMANTINEOS_REPRODUCIBLE_AUDIT_GUIDE.md")
    index_path = Path("docs/INDEX.md")

    doc = doc_path.read_text()
    index = index_path.read_text()

    assert "# AdamantineOS Reproducible Audit Guide" in doc
    assert "maintainers, reviewers, auditors, and downstream integrators" in doc
    assert "clean checkout of a named commit" in doc
    assert "source archive whose filename and origin are recorded" in doc
    assert "not verified from the reviewed source" in doc
    assert "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest -q" in doc
    assert "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest --no-cov" in doc
    assert "does not satisfy final coverage proof by itself" in doc
    assert "Targeted runs do not replace the full verification command" in doc
    assert "ADAMANTINEOS_REPRODUCIBLE_AUDIT_GUIDE.md" in index


def test_reproducible_audit_guide_avoids_ai_instruction_tone() -> None:
    doc = Path("docs/ADAMANTINEOS_REPRODUCIBLE_AUDIT_GUIDE.md").read_text()
    forbidden_public_tone = (
        "AI instructions",
        "ChatGPT",
        "Claude",
        "old ZIPs",
        "Do not rely on old ZIPs",
        "previous audit assumptions",
    )

    for phrase in forbidden_public_tone:
        assert phrase not in doc
