from __future__ import annotations

from pathlib import Path

import adamantine.v1.execution as execution_surface
import adamantine.v1.execution.boundary as boundary
import adamantine.v1.execution.orchestrator_v1 as legacy_v1


def _truncated_pytest_files(repo_root: Path) -> list[str]:
    tests_root = repo_root / "tests"
    return sorted(
        path.relative_to(repo_root).as_posix()
        for path in tests_root.rglob("test_*.p*")
        if path.suffix != ".py" and "__pycache__" not in path.parts
    )


def test_aos_rt_003_no_truncated_pytest_files_remain() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert _truncated_pytest_files(repo_root) == []


def test_aos_rt_003_guard_recurses_into_nested_test_directories(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    nested_tests = repo_root / "tests" / "integrations"
    nested_tests.mkdir(parents=True)
    truncated_stub = nested_tests / "test_nested_escape.p"
    truncated_stub.write_text("def test_escape():\n    assert False\n", encoding="utf-8")

    assert _truncated_pytest_files(repo_root) == ["tests/integrations/test_nested_escape.p"]


def test_aos_rt_003_guard_ignores_python_bytecode_cache(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    cache_dir = repo_root / "tests" / "__pycache__"
    cache_dir.mkdir(parents=True)
    bytecode_cache = cache_dir / "test_example.cpython-313.pyc"
    bytecode_cache.write_bytes(b"not-source")

    assert _truncated_pytest_files(repo_root) == []


def test_aos_rt_004_orchestrator_v1_is_marked_internal_deprecated() -> None:
    assert legacy_v1.ORCHESTRATOR_V1_DEPRECATED_INTERNAL_ONLY is True
    assert legacy_v1.ORCHESTRATOR_V1_PUBLIC_ENTRYPOINT is False
    assert "Deprecated internal compatibility path" in (legacy_v1.orchestrate_execution_v1.__doc__ or "")


def test_aos_rt_004_orchestrator_v1_is_not_exported_runtime_surface() -> None:
    exported = tuple(getattr(execution_surface, "__all__", ()))

    assert "orchestrate_execution_v1" not in exported
    assert not hasattr(execution_surface, "orchestrate_execution_v1")


def test_aos_rt_004_integrator_docs_lock_v1_out_of_production() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    external = (repo_root / "docs" / "EXTERNAL_INTERFACES.md").read_text(encoding="utf-8")
    mobile_v1 = (repo_root / "docs" / "CONTRACTS" / "mobile_execution_call_v1.md").read_text(encoding="utf-8")

    assert "orchestrator_v1.py` module is an internal legacy compatibility harness only" in external
    assert "Production integrations MUST use the v2 runtime host" in external
    assert "AOS-RT-004 legacy-entrypoint lock" in mobile_v1
    assert "not a production integration entrypoint" in mobile_v1


def test_step10_2_orchestrator_v1_synthetic_evidence_is_documented() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    external = (repo_root / "docs" / "EXTERNAL_INTERFACES.md").read_text(encoding="utf-8")
    mobile_v1 = (repo_root / "docs" / "CONTRACTS" / "mobile_execution_call_v1.md").read_text(encoding="utf-8")
    module_doc = legacy_v1.__doc__ or ""
    runtime_doc = legacy_v1.orchestrate_execution_v1.__doc__ or ""

    required_phrases = (
        "synthesize",
        "v1:no_shield_contract",
        "v1:qid_absent_allowed",
        "v1:risk_absent_allowed",
        "v1:ai_gateway_not_required",
        "not active Shield/Q-ID/Adaptive/AI-Gateway protection",
    )

    combined_docs = "\n".join((external, mobile_v1))
    for phrase in required_phrases:
        assert phrase in combined_docs

    assert "synthesizes legacy placeholder evidence" in module_doc
    assert "MUST NOT be described as active Shield/Q-ID" in module_doc
    assert "synthesizes legacy placeholder evidence" in runtime_doc
    assert "MUST NOT be used or documented as live production protection" in runtime_doc



def test_step10_3_run_with_tva_is_marked_internal_test_only() -> None:
    assert boundary.RUN_WITH_TVA_INTERNAL_TEST_ONLY is True
    assert boundary.RUN_WITH_TVA_PUBLIC_ENTRYPOINT is False
    assert "internal TVA-only test harness" in boundary.RUN_WITH_TVA_WARNING
    assert "final policy engine boundary" in boundary.RUN_WITH_TVA_WARNING

    doc = boundary.run_with_tva.__doc__ or ""
    assert "Internal TVA-only test harness" in doc
    assert "not a production integration entrypoint" in doc
    assert "final policy engine returns ALLOW" in doc


def test_step10_3_run_with_tva_docs_lock_out_direct_integrator_use() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    external = (repo_root / "docs" / "EXTERNAL_INTERFACES.md").read_text(encoding="utf-8")
    mobile_v1 = (repo_root / "docs" / "CONTRACTS" / "mobile_execution_call_v1.md").read_text(encoding="utf-8")

    combined_docs = "\n".join((external, mobile_v1))
    required_phrases = (
        "Internal TVA-only harness lock",
        "run_with_tva` is an internal TVA-only test harness",
        "does not evaluate the full final policy engine",
        "Integrators MUST NOT call `run_with_tva` directly",
        "Production integrations MUST use `RuntimeHostV2` / `orchestrator_v2`",
        "ALLOW_FINAL_ADAMANTINEOS_DECISION",
    )

    for phrase in required_phrases:
        assert phrase in combined_docs
