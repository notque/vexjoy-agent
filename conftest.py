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

import os
import subprocess
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


# Inherited from a live agent session or a developer shell. CI never sets them,
# so tests must not see them either:
# - session ids: hooks key /tmp state on CLAUDE_SESSION_ID (pretool-file-backup
#   writes /tmp/.claude-backups/<sid>/), so an inherited id makes tests write
#   into the live session's backup dir and collide across parallel runs;
# - API keys: with a real key, default Jev/text-model helpers make live network
#   calls from tests that are meant to be offline.
# A test that needs one sets it itself with monkeypatch.setenv.
_LIVE_ENV_VARS = (
    "CLAUDE_SESSION_ID",
    "JEV_SESSION_ID",
    "JEV_AGENT_ID",
    "TYPESAFE_API_KEY",
    "AI_GATEWAY_API_KEY",
    "TEXT_MODEL_API_KEY",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def isolate_live_session_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip live-session ids and API keys so every test runs with CI's environment."""
    for name in _LIVE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


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


# Terminal and session state the host shell sets. Hooks read these to report
# to a live terminal multiplexer (herdr) or to detect an away-from-keyboard
# session; a test that inherits them talks to the real host or takes a
# different branch than CI. Tests that need one set it with monkeypatch.
_HOST_ENV_PREFIXES = ("HERDR_",)
_HOST_ENV = ("SSH_CONNECTION", "SSH_TTY", "SSH_CLIENT", "TMUX", "STY")


@pytest.fixture(autouse=True)
def isolate_host_session_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear host terminal/session variables so tests run the same on any shell."""
    for name in list(os.environ):
        if name in _HOST_ENV or name.startswith(_HOST_ENV_PREFIXES):
            monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# Public skill and agent index, built into tmp (shared by hooks/tests and
# scripts/tests). The checkout's INDEX.json files are generated and gitignored:
# a fresh clone has none, and a dev clone may hold a stale or private-inclusive
# copy. Tests that need the real catalogue read this build instead.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def public_index_dir(tmp_path_factory) -> Path:
    """Public skill and agent indexes built from this checkout: ``skills.json``, ``agents.json``.

    ``skills/INDEX.json`` and ``agents/INDEX.json`` are generated and gitignored.
    A fresh checkout has none (CI generates them first), and a dev checkout may
    hold a stale copy plus a private-inclusive ``INDEX.local.json``. Tests that
    need the real catalogue read this build instead of the working tree.
    """
    out = tmp_path_factory.mktemp("public-index")
    for kind in ("skill", "agent"):
        subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / f"generate-{kind}-index.py"),
                "--repo-root",
                str(_REPO_ROOT),
                "--output",
                str(out / f"{kind}s.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    return out


@pytest.fixture
def use_public_index(public_index_dir, monkeypatch) -> Path:
    """Point routing readers (build-dispatch, hooks) at ``public_index_dir``.

    ``VEXJOY_INDEX_DIR`` takes precedence over the installed and repo indexes
    and skips the ``INDEX.local.json`` overlay; subprocesses inherit it.
    """
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(public_index_dir))
    return public_index_dir


@pytest.fixture(scope="session")
def public_index_repo(public_index_dir, tmp_path_factory) -> Path:
    """Repo-shaped tmp root for tools that take ``--repo-root`` and read INDEX files.

    Holds ``skills/INDEX.json`` and ``agents/INDEX.json`` from ``public_index_dir``,
    a copy of the tracked pipeline index, and read-only symlinks to
    ``skills/shared-patterns`` and ``hooks``. Pointing such tools at the checkout
    fails on a fresh clone, and some generate the missing index in place.
    """
    root = tmp_path_factory.mktemp("public-index-repo")
    (root / "skills").mkdir()
    (root / "agents").mkdir()
    (root / "skills" / "INDEX.json").write_bytes((public_index_dir / "skills.json").read_bytes())
    (root / "agents" / "INDEX.json").write_bytes((public_index_dir / "agents.json").read_bytes())
    pipelines = Path("skills") / "process" / "workflow" / "references" / "pipeline-index.json"
    (root / pipelines).parent.mkdir(parents=True)
    (root / pipelines).write_bytes((_REPO_ROOT / pipelines).read_bytes())
    (root / "skills" / "shared-patterns").symlink_to(_REPO_ROOT / "skills" / "shared-patterns")
    (root / "hooks").symlink_to(_REPO_ROOT / "hooks")
    return root


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
