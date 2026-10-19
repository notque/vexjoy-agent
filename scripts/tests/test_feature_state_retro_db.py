"""Tests that feature-state.py retro commands write only to learning.db.

Regression: /pr-review in another repo created retro/L1.md and retro/L2/*.md
inside that repo. Learnings must land in learning.db (CLAUDE_LEARNING_DIR)
with project_path as metadata, and never as files in the working repo.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "feature-state.py"
if str(_SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT.parent))

feature_state = importlib.import_module("feature-state")


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _rows(learning_dir: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(learning_dir / "learning.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT topic, key, value, source, project_path, observation_count FROM learnings"
        ).fetchall()
    finally:
        conn.close()


def _run(script: Path, cwd: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """Environment with an isolated learning dir."""
    learning_dir = tmp_path / "learning"
    return {**os.environ, "CLAUDE_LEARNING_DIR": str(learning_dir)}


def test_adhoc_writes_db_not_repo(tmp_path: Path, env: dict[str, str]) -> None:
    """retro-record-adhoc records in learning.db and creates no retro/ dir."""
    repo = _git_repo(tmp_path / "other-repo")
    subdir = repo / "pkg"
    subdir.mkdir()

    result = _run(_SCRIPT, subdir, env, "retro-record-adhoc", "go-patterns", "some-key", "a specific finding")

    assert result.returncode == 0, result.stderr
    assert not (repo / "retro").exists()
    assert not (subdir / "retro").exists()
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    assert "recorded go-patterns/some-key (new)" in lines[0]
    rows = _rows(Path(env["CLAUDE_LEARNING_DIR"]))
    assert [(r["topic"], r["key"], r["value"], r["project_path"]) for r in rows] == [
        ("go-patterns", "some-key", "a specific finding", str(repo)),
    ]
    assert rows[0]["source"] == "manual:retro-record-adhoc"


def test_adhoc_repeat_increments_observations(tmp_path: Path, env: dict[str, str]) -> None:
    """Recording the same topic/key twice bumps observation_count."""
    repo = _git_repo(tmp_path / "repo")
    for _ in range(2):
        result = _run(_SCRIPT, repo, env, "retro-record-adhoc", "testing", "k", "v")
        assert result.returncode == 0, result.stderr
    assert "seen 2x" in result.stdout
    assert _rows(Path(env["CLAUDE_LEARNING_DIR"]))[0]["observation_count"] == 2


def test_adhoc_db_failure_exits_nonzero(tmp_path: Path) -> None:
    """A DB write failure is reported on stderr with exit 1, not swallowed."""
    repo = _git_repo(tmp_path / "repo")
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(blocker)}

    result = _run(_SCRIPT, repo, env, "retro-record-adhoc", "testing", "k", "v")

    assert result.returncode == 1
    assert "retro-record-adhoc:" in result.stderr
    assert result.stdout == ""
    assert not (repo / "retro").exists()


def test_adhoc_from_installed_layout(tmp_path: Path, env: dict[str, str]) -> None:
    """The script finds learning_db_v2 when run from ~/.claude/scripts."""
    home = tmp_path / "home"
    shutil.copytree(_REPO_ROOT / "hooks" / "lib", home / ".claude" / "hooks" / "lib")
    (home / ".claude" / "scripts").mkdir(parents=True)
    script = home / ".claude" / "scripts" / "feature-state.py"
    shutil.copy2(_SCRIPT, script)
    repo = _git_repo(tmp_path / "repo")

    result = _run(script, repo, {**env, "HOME": str(home)}, "retro-record-adhoc", "go-patterns", "k", "v")

    assert result.returncode == 0, result.stderr
    assert not (repo / "retro").exists()
    assert _rows(Path(env["CLAUDE_LEARNING_DIR"]))[0]["project_path"] == str(repo)


def test_complete_archives_to_db_not_repo(tmp_path: Path, env: dict[str, str]) -> None:
    """complete records MEDIUM/HIGH retro records and context files in learning.db only."""
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    state = feature_state.FeatureState(
        name="my-feature",
        retro_records={
            "kept-high": {"value": "high value", "confidence": "high"},
            "kept-medium": {"value": "medium value", "confidence": "medium"},
            "dropped-low": {"value": "low value", "confidence": "low"},
        },
    )
    feature_state.save_state(feature_dir, state)
    context = feature_dir / "context" / "implement"
    context.mkdir(parents=True)
    (context / "promoted-note.md").write_text("# Promoted\n\nnote body\n")
    (context / "kept-high.md").write_text("duplicate of a record")

    result = _run(_SCRIPT, repo, env, "complete", "my-feature")

    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["learnings_recorded"] == 3
    assert out["retro_archived"] is True
    assert not (repo / "retro").exists()
    rows = {r["key"]: r for r in _rows(Path(env["CLAUDE_LEARNING_DIR"]))}
    assert set(rows) == {"kept-high", "kept-medium", "promoted-note"}
    assert rows["kept-high"]["value"] == "high value"
    assert all(r["topic"] == "my-feature" and r["project_path"] == str(repo) for r in rows.values())


def test_complete_db_failure_keeps_state(tmp_path: Path) -> None:
    """If learnings cannot be saved, complete fails and leaves the state file in place."""
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    feature_state.save_state(
        feature_dir,
        feature_state.FeatureState(name="f", retro_records={"k": {"value": "v", "confidence": "high"}}),
    )
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")

    result = _run(_SCRIPT, repo, {**os.environ, "CLAUDE_LEARNING_DIR": str(blocker)}, "complete", "f")

    assert result.returncode == 1
    assert "learnings not saved" in result.stderr
    assert (feature_dir / "state" / "f.json").exists()
    assert not (repo / "retro").exists()


@pytest.mark.parametrize("command", ["retro-audit", "retro-candidates"])
def test_readers_tolerate_missing_retro_dir(tmp_path: Path, env: dict[str, str], command: str) -> None:
    """Read-only retro subcommands succeed without creating retro/."""
    repo = _git_repo(tmp_path / "repo")

    result = _run(_SCRIPT, repo, env, command)

    assert result.returncode == 0, result.stderr
    assert "No retro/L2/ directory" in result.stdout
    assert not (repo / "retro").exists()
