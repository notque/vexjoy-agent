"""Repository-wide pytest fixtures.

Keeps every test off the production learning database at
`~/.claude/learning/learning.db`. Redirection is belt-and-braces because one
lever is not enough:

- `CLAUDE_LEARNING_DIR` covers the modules that read it (`learning_db_v2`,
  `usage_db`, `route_events`) and every child process a test spawns.
- Patching `learning_db_v2._DEFAULT_DB_DIR` covers the fallback a test reaches
  when it deliberately unsets that env var, as
  `scripts/tests/test_install_doctor.py` does.

The fixture then asserts the resolved path sits outside the real `~/.claude`,
on setup and again on teardown, so a leak fails the test that caused it instead
of silently corrupting production data.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent
_LIB_DIR = _REPO_ROOT / "hooks" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import hook_utils
import learning_db_v2

# Resolved at import time, before any test can monkeypatch HOME.
_PRODUCTION_CLAUDE_DIR = Path.home() / ".claude"


@pytest.fixture(autouse=True)
def isolate_hook_error_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep hook failures raised by tests out of production telemetry.

    Tests that drive a hook with empty or malformed stdin make it call
    `hook_utils.hook_error`, which appends to `~/.claude/learning/hook-errors.jsonl`.
    Those synthetic entries then read as production crash streaks in
    `scripts/validate-hook-health.py`. `hooks/tests/conftest.py` already isolated
    its own directory; this covers `tests/` and `scripts/tests/` too. The env var
    carries the redirect into hooks spawned as subprocesses.
    """
    path = tmp_path / "hook-errors.jsonl"
    monkeypatch.setattr(hook_utils, "_DEFAULT_HOOK_ERRORS_PATH", path)
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    return path


def _assert_db_is_isolated(phase: str) -> None:
    """Fail if the learning DB resolves inside the real ~/.claude tree."""
    resolved = learning_db_v2.get_db_path().resolve()
    assert not resolved.is_relative_to(_PRODUCTION_CLAUDE_DIR), (
        f"learning DB resolved to {resolved} at {phase}: tests must never read "
        f"or write anything under {_PRODUCTION_CLAUDE_DIR}"
    )


@pytest.fixture(autouse=True)
def isolate_learning_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the learning database at a throwaway directory for one test."""
    # Not tmp_path/"learning": several tests create that exact directory
    # themselves with a bare mkdir() and would collide with this fixture.
    db_dir = tmp_path / "isolated-learning-db"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    monkeypatch.setattr(learning_db_v2, "_DEFAULT_DB_DIR", db_dir)
    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    _assert_db_is_isolated("setup")
    yield db_dir
    _assert_db_is_isolated("teardown")


# ---------------------------------------------------------------------------
# Repo .claude/ stays install-free across the whole suite (installer spec 11).
#
# A test (or a harness it drives) that runs an installer or the sync hook with
# HOME or ~/.claude resolving to this checkout writes a runtime tree into
# repo/.claude, which Claude Code then loads as project scope. .gitignore hides
# it from `git status`, so this check compares the directory itself.
# ---------------------------------------------------------------------------

_REPO_DOTCLAUDE = _REPO_ROOT / ".claude"
_INSTALL_SHAPED = (
    "skills",
    "agents",
    "commands",
    "hooks",
    "scripts",
    "vexjoy",
    "retro",
    ".vexjoy-managed-hooks-settings",
    ".install-manifest.json",
)
_RUNTIME_ROOTS = (".codex", ".factory", ".hermes", ".reasonix")


def _install_shaped_snapshot() -> dict[str, int]:
    """Install-shaped paths under repo/.claude and runtime roots at the repo top, with mtimes."""
    paths = [_REPO_DOTCLAUDE / name for name in _INSTALL_SHAPED]
    paths += list(_REPO_DOTCLAUDE.glob("settings.json.backup.*"))
    paths += [_REPO_ROOT / name for name in _RUNTIME_ROOTS]
    out: dict[str, int] = {}
    for p in paths:
        try:
            out[str(p.relative_to(_REPO_ROOT))] = p.lstat().st_mtime_ns
        except OSError:
            continue
    return out


def pytest_sessionstart(session: pytest.Session) -> None:
    session.config._vexjoy_dotclaude = _install_shaped_snapshot()  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    before = getattr(session.config, "_vexjoy_dotclaude", None)
    if before is None or hasattr(session.config, "workerinput"):
        return
    after = _install_shaped_snapshot()
    changed = sorted(p for p, m in after.items() if before.get(p) != m)
    if changed:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        msg = f"repo install guard: the suite created or changed install-shaped paths in the checkout: {changed}"
        if reporter is not None:
            reporter.write_line(msg, red=True)
        else:
            print(msg, file=sys.stderr)
