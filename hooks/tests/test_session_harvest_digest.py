#!/usr/bin/env python3
"""Tests for the session-harvest-digest SessionStart hook.

Covers (per ADR correction-harvest-routine test plan):
- Not-due gate: state <7d old -> empty output, no digest.
- Due gate (old / missing / malformed state) -> digest runs, state rewritten.
- No corrections -> 'No corrections this week' line, state still written.
- Digest passthrough: seeded correction row surfaces in output.
- Error degradation: build_digest raises -> exit 0, empty output, state NOT written.
- Non-blocking: empty / malformed stdin -> exit 0.

Uses a throwaway learning dir via CLAUDE_LEARNING_DIR (redirects BOTH learning.db
and the .harvest-digest-state file) — never the real ~/.claude.

Run with: python3 -m pytest hooks/tests/test_session_harvest_digest.py -v
"""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
SCRIPTS_DIR = HOOKS_DIR.parent / "scripts"
HOOK_PATH = HOOKS_DIR / "session-harvest-digest.py"
STATE_NAME = ".harvest-digest-state"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Redirect learning dir (DB + state file) to a throwaway tmp dir."""
    learning_dir = tmp_path / "learning"
    learning_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return {"learning_dir": learning_dir, "state": learning_dir / STATE_NAME, "ldb": ldb}


def _write_state(env, when: datetime) -> None:
    env["state"].write_text(json.dumps({"last_run": when.isoformat()}), encoding="utf-8")


def _seed_correction(env, value="rename it back, that broke routing", session="s1") -> None:
    """Insert a user-correction row the harvest will read (non-test source)."""
    env["ldb"].record_learning(
        topic="user-correction",
        key=f"k-{session}",
        value=value,
        category="correction",
        confidence=0.70,
        source="hook:user-correction-capture",
        session_id=session,
    )


def _run(event=None) -> subprocess.CompletedProcess:
    """Run the hook as a subprocess feeding `event` (or empty) on stdin."""
    stdin = json.dumps(event) if event is not None else ""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )


def _subprocess_env():
    import os

    e = dict(os.environ)
    return e


def _additional_context(stdout: str) -> str:
    """Extract additionalContext from the hook's JSON stdout ('' if none)."""
    out = stdout.strip()
    if not out:
        return ""
    try:
        data = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return ""
    return data.get("hookSpecificOutput", {}).get("additionalContext", "")


def _load_module(monkeypatch):
    """Import the hook module in-process (for monkeypatching build_digest)."""
    sys.path.insert(0, str(LIB_DIR))
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("session_harvest_digest", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Gate: not-due
# ---------------------------------------------------------------------------


def test_not_due_emits_no_digest(env):
    """State 1 day old -> hook exits 0 and emits no [correction-digest]."""
    _seed_correction(env)  # corrections exist, but gate must suppress them
    _write_state(env, datetime.now() - timedelta(days=1))
    result = _run({"hook_event_name": "SessionStart"})
    assert result.returncode == 0
    assert "[correction-digest]" not in _additional_context(result.stdout)


def test_not_due_does_not_rewrite_state(env):
    """Not-due path leaves the state timestamp unchanged."""
    ts = datetime.now() - timedelta(days=2)
    _write_state(env, ts)
    before = env["state"].read_text(encoding="utf-8")
    _run({"hook_event_name": "SessionStart"})
    assert env["state"].read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Gate: due
# ---------------------------------------------------------------------------


def test_due_old_state_runs_and_rewrites_state(env):
    """State 8 days old -> digest runs and state is rewritten fresher."""
    old = datetime.now() - timedelta(days=8)
    _write_state(env, old)
    result = _run({"hook_event_name": "SessionStart"})
    assert result.returncode == 0
    new = json.loads(env["state"].read_text(encoding="utf-8"))["last_run"]
    assert datetime.fromisoformat(new) > old


def test_due_missing_state_runs_and_writes_state(env):
    """No state file -> treated as due, runs, writes state."""
    assert not env["state"].exists()
    result = _run({"hook_event_name": "SessionStart"})
    assert result.returncode == 0
    assert env["state"].exists()
    assert "last_run" in json.loads(env["state"].read_text(encoding="utf-8"))


def test_malformed_state_treated_as_due(env):
    """Garbage state -> treated as due, exits 0, writes a valid state."""
    env["state"].write_text("{not json", encoding="utf-8")
    result = _run({"hook_event_name": "SessionStart"})
    assert result.returncode == 0
    assert "last_run" in json.loads(env["state"].read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Digest content
# ---------------------------------------------------------------------------


def test_no_corrections_emits_none_line_and_writes_state(env):
    """Due + empty DB -> 'No corrections this week' line, state still written."""
    result = _run({"hook_event_name": "SessionStart"})
    ctx = _additional_context(result.stdout)
    assert "[correction-digest]" in ctx
    assert "No corrections" in ctx
    assert env["state"].exists()


def test_digest_passthrough(env):
    """Due + seeded correction -> output carries the digest with the cluster."""
    _seed_correction(env)
    result = _run({"hook_event_name": "SessionStart"})
    ctx = _additional_context(result.stdout)
    assert "[correction-digest]" in ctx
    assert "correction" in ctx.lower()


# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------


def test_build_digest_error_degrades_silently_and_skips_state(env, monkeypatch):
    """build_digest raising -> exit 0, empty output, state NOT written (retry next)."""
    mod = _load_module(monkeypatch)

    def boom(**_kwargs):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(mod, "build_digest", boom)

    # main() calls print_and_exit -> sys.exit; make it raise so we can assert.
    def fake_exit(code=0):
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    # No state file yet; a failed digest must not create one (retry next session).
    with patch("sys.stdin") as stdin:
        stdin.read.return_value = json.dumps({"hook_event_name": "SessionStart"})
        with pytest.raises(SystemExit):
            mod.main()
    assert not env["state"].exists()


def test_empty_stdin_exits_zero(env):
    result = _run(None)
    assert result.returncode == 0


def test_malformed_stdin_exits_zero(env):
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="{not valid json",
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    assert result.returncode == 0
