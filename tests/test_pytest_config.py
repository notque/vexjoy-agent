"""Contract tests for repository-wide pytest collection settings."""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Full-repo mirrors. Their test_*.py copies share basenames with the real
# tests, so collecting one aborts the whole run with import errors.
MIRROR_DIRS = [".claude", ".codex"]


def test_local_tmp_tree_is_not_collected(pytestconfig):
    assert "tmp" in pytestconfig.getini("norecursedirs"), (
        "tmp/ holds local scratch projects, so collecting it makes the suite depend on untracked artifacts"
    )


@pytest.mark.parametrize("mirror", MIRROR_DIRS)
def test_repo_mirror_dir_is_not_collected(pytestconfig, mirror):
    assert mirror in pytestconfig.getini("norecursedirs"), (
        f"{mirror}/ mirrors the whole repo, so collecting it aborts the run with duplicate-basename errors"
    )


def test_install_e2e_and_performance_tests_are_deselected_by_default(pytestconfig):
    """The default run must skip the install.sh e2e files and the benchmarks."""
    addopts = " ".join(pytestconfig.getini("addopts"))
    assert "not (slow and integration)" in addopts, "the install.sh e2e files must stay out of the default run"
    assert "not performance" in addopts, "the timing benchmarks must stay out of the default run"


def _workflow() -> str:
    return (_REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")


def test_ci_fast_tier_runs_default_markers_in_parallel():
    """PR CI runs the default filter under xdist."""
    assert "- run: python -m pytest --tb=short -q -n auto --dist loadfile\n" in _workflow(), (
        "the fast CI tier must run the default marker set with xdist"
    )


def test_ci_full_tier_runs_everything_the_default_filter_drops():
    """A non-PR CI job must run every marker, so nothing the default filter drops goes unrun."""
    workflow = _workflow()
    assert "test-full:" in workflow and "if: github.event_name != 'pull_request'" in workflow
    assert '-m "not performance" -n auto --dist loadfile' in workflow, (
        "the full tier lost the slow+integration tests (they only run where the default filter is cleared)"
    )
    assert "- run: python -m pytest --tb=short -q -m performance -n 0\n" in workflow, (
        "the full tier lost the timing benchmarks"
    )
    assert "schedule:" in workflow, "the full tier must also run nightly"


def test_default_run_is_parallel_by_file(pytestconfig):
    """The default run uses xdist with per-file distribution."""
    addopts = pytestconfig.getini("addopts")
    assert "-n" in addopts and "auto" in addopts and "loadfile" in addopts
