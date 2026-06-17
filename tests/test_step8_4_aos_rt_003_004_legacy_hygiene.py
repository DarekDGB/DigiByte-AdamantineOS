from __future__ import annotations

from pathlib import Path

import adamantine.v1.execution as execution_surface
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
