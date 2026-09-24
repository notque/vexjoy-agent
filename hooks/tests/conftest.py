"""Shared pytest fixtures for hook tests.

Isolates per-hook on-disk dedup state so that tests which reuse an identical
working-tree diff (and therefore an identical DiffDedup signature) don't
contaminate one another through the real ~/.claude/state/ directory.

The fixture is autouse but inert for any test module that does not expose a hook
`mod` with `_STATE_DIR` / `_STATE_FILE`: it reaches the hook module via the
requesting test module's `mod` attribute (the importlib-loaded module under
test) and redirects its state to a fresh tmp dir per test. Other hook test files
that don't bind a `mod` with those attributes are unaffected.
"""

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "hooks" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import hook_utils
import telemetry_capture


@pytest.fixture(autouse=True)
def _isolate_hook_error_log(tmp_path, monkeypatch):
    """Keep hook failures raised by tests out of production telemetry."""
    path = tmp_path / "hook-errors.jsonl"
    monkeypatch.setattr(hook_utils, "_DEFAULT_HOOK_ERRORS_PATH", path)
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))


@pytest.fixture(autouse=True)
def _isolate_hook_dedup_state(request, tmp_path, monkeypatch):
    """Point a hook's dedup state at a fresh tmp dir for each test.

    No-op unless the requesting test module exposes `mod._STATE_DIR`. Tests that
    patch `_STATE_DIR` / `_STATE_FILE` themselves (e.g. TestDedup) take
    precedence — their `with patch.object(...)` block is entered later and
    restored on exit.
    """
    mod = getattr(request.module, "mod", None)
    if mod is not None and hasattr(mod, "_STATE_DIR"):
        state_dir = tmp_path / "hook-dedup-state"
        monkeypatch.setattr(mod, "_STATE_DIR", state_dir, raising=False)
        monkeypatch.setattr(mod, "_STATE_FILE", state_dir / "last-diff-hash.json", raising=False)
    yield


@pytest.fixture(autouse=True)
def _reset_learning_db_init_flag():
    """Re-run schema setup for each test's database.

    ``learning_db_v2`` creates its tables once per process. A test that points
    the module at a fresh database needs that setup to run again.
    """
    ldb = sys.modules.get("learning_db_v2")
    if ldb is not None and hasattr(ldb, "_initialized"):
        ldb._initialized = False
    yield
    ldb = sys.modules.get("learning_db_v2")
    if ldb is not None and hasattr(ldb, "_initialized"):
        ldb._initialized = False


@pytest.fixture(autouse=True)
def _isolate_installed_index(tmp_path, monkeypatch):
    """Pin routing readers to their repo/fixture index (installer spec 7.2).

    ``VEXJOY_INDEX_DIR`` set to an absent dir makes ``resolve_index`` skip the
    real ``~/.claude/vexjoy/index`` and fall back to the tracked + legacy local
    index each test supplies. Tests of the resolver override this.
    """
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(tmp_path / "no-installed-index"))
    monkeypatch.delenv("VEXJOY_INDEX_TARGET", raising=False)


@pytest.fixture(autouse=True)
def _isolate_telemetry_state(tmp_path, monkeypatch):
    """Keep the per-session git-SHA cache out of the real ``~/.claude/state/telemetry``.

    The routing recorder caches HEAD there by session id; tests that drive it
    in-process wrote those files under the real HOME and read them back.
    """
    monkeypatch.setattr(telemetry_capture, "_STATE_DIR", tmp_path / "telemetry-state")


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
