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

# Runs feature-state.py main() with record_learning failing on write number
# $FAIL_ON_WRITE (1-based; 0 never fails), to simulate "database is locked".
_FAILING_DRIVER = """
import importlib.util, os, sqlite3, sys
spec = importlib.util.spec_from_file_location("fs_driver", sys.argv[1])
fs = importlib.util.module_from_spec(spec)
sys.modules["fs_driver"] = fs
spec.loader.exec_module(fs)
real = fs._load_learning_db()
fail_on = int(os.environ.get("FAIL_ON_WRITE", "0"))
calls = [0]

class Proxy:
    def __getattr__(self, name):
        return getattr(real, name)

    def record_learning(self, **kwargs):
        calls[0] += 1
        if calls[0] == fail_on:
            raise sqlite3.OperationalError("database is locked")
        return real.record_learning(**kwargs)

fs._load_learning_db = Proxy
sys.argv = sys.argv[1:]
sys.exit(fs.main())
"""

# Stand-in learning_db_v2 that proves which hooks/lib directory was imported.
_STUB_LIB = """
from pathlib import Path

def get_db_path():
    return Path("/nonexistent/stub.db")

def record_learning(**kwargs):
    raise RuntimeError("STUB_LIB_USED")
"""


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _rows(learning_dir: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(learning_dir / "learning.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT topic, key, value, confidence, tags, source, source_detail, project_path, observation_count "
            "FROM learnings",
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


def _run_failing(cwd: Path, env: dict[str, str], fail_on: int, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _FAILING_DRIVER, str(_SCRIPT), *args],
        cwd=cwd,
        env={**env, "FAIL_ON_WRITE": str(fail_on)},
        capture_output=True,
        text=True,
        check=False,
    )


def _isolated_script(base: Path) -> Path:
    """Copy feature-state.py to a dir with no sibling hooks/lib."""
    scripts = base / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "feature-state.py"
    shutil.copy2(_SCRIPT, script)
    return script


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """Environment with an isolated learning dir."""
    learning_dir = tmp_path / "learning"
    return {**os.environ, "CLAUDE_LEARNING_DIR": str(learning_dir)}


def test_adhoc_writes_db_not_repo(tmp_path: Path, env: dict[str, str]) -> None:
    """retro-record-adhoc records in learning.db, reports JSON, and creates no retro/ dir."""
    repo = _git_repo(tmp_path / "other-repo")
    subdir = repo / "pkg"
    subdir.mkdir()

    result = _run(_SCRIPT, subdir, env, "retro-record-adhoc", "go-patterns", "some-key", "a specific finding")

    assert result.returncode == 0, result.stderr
    assert not (repo / "retro").exists()
    assert not (subdir / "retro").exists()
    out = json.loads(result.stdout)
    assert out["recorded"] is True
    assert out["is_new"] is True
    assert (out["topic"], out["key"], out["project_path"]) == ("go-patterns", "some-key", str(repo))
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
    out = json.loads(result.stdout)
    assert (out["is_new"], out["observation_count"]) == (False, 2)
    assert _rows(Path(env["CLAUDE_LEARNING_DIR"]))[0]["observation_count"] == 2


def test_adhoc_reports_stored_project_path(tmp_path: Path, env: dict[str, str]) -> None:
    """A second repo recording the same topic/key sees the first repo's stored project_path."""
    repo_a = _git_repo(tmp_path / "internal-repo")
    repo_b = _git_repo(tmp_path / "public-repo")
    assert _run(_SCRIPT, repo_a, env, "retro-record-adhoc", "go-patterns", "wrap-errors", "v").returncode == 0

    result = _run(_SCRIPT, repo_b, env, "retro-record-adhoc", "go-patterns", "wrap-errors", "v")

    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["project_path"] == str(repo_a)
    assert str(repo_b) not in result.stdout


def test_adhoc_db_failure_exits_nonzero(tmp_path: Path) -> None:
    """A DB write failure is reported as JSON on stderr with exit 1, not swallowed."""
    repo = _git_repo(tmp_path / "repo")
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(blocker)}

    result = _run(_SCRIPT, repo, env, "retro-record-adhoc", "testing", "k", "v")

    assert result.returncode == 1
    assert json.loads(result.stderr)["error"].startswith("retro-record-adhoc:")
    assert result.stdout == ""
    assert not (repo / "retro").exists()


def _no_lib_env(tmp_path: Path, env: dict[str, str]) -> dict[str, str]:
    """HOME with no ~/.claude/hooks/lib and no PYTHONPATH that could supply learning_db_v2."""
    home = tmp_path / "empty-home"
    home.mkdir()
    return {k: v for k, v in {**env, "HOME": str(home)}.items() if k != "PYTHONPATH"}


def test_missing_learning_db_module_exits_nonzero(tmp_path: Path, env: dict[str, str]) -> None:
    """With learning_db_v2 importable from neither lookup, adhoc exits 1 with a clear error."""
    script = _isolated_script(tmp_path / "bare")
    repo = _git_repo(tmp_path / "repo")

    result = _run(script, repo, _no_lib_env(tmp_path, env), "retro-record-adhoc", "testing", "k", "v")

    assert result.returncode == 1
    assert "cannot import learning_db_v2" in json.loads(result.stderr)["error"]
    assert result.stdout == ""


def test_missing_learning_db_module_complete_keeps_state(tmp_path: Path, env: dict[str, str]) -> None:
    """With learning_db_v2 missing, complete aborts, saves nothing, and keeps the state file."""
    script = _isolated_script(tmp_path / "bare")
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    feature_state.save_state(
        feature_dir,
        feature_state.FeatureState(name="f", retro_records={"k": {"value": "v", "confidence": "high"}}),
    )

    result = _run(script, repo, _no_lib_env(tmp_path, env), "complete", "f")

    assert result.returncode == 1
    assert "0 of 1 learnings saved: cannot import learning_db_v2" in json.loads(result.stderr)["error"]
    assert (feature_dir / "state" / "f.json").exists()
    assert not (feature_dir / "state" / "completed").exists()


def test_home_lib_used_when_script_has_no_sibling_lib(tmp_path: Path, env: dict[str, str]) -> None:
    """A script with no sibling hooks/lib falls back to ~/.claude/hooks/lib.

    The real installed layout (~/.claude/scripts) cannot tell the two lookups
    apart, because its sibling hooks/lib IS ~/.claude/hooks/lib. So this test
    removes the sibling lib and checks the home fallback alone.
    """
    home = tmp_path / "home"
    shutil.copytree(_REPO_ROOT / "hooks" / "lib", home / ".claude" / "hooks" / "lib")
    script = _isolated_script(tmp_path / "bare")
    repo = _git_repo(tmp_path / "repo")
    run_env = {k: v for k, v in {**env, "HOME": str(home)}.items() if k != "PYTHONPATH"}

    result = _run(script, repo, run_env, "retro-record-adhoc", "go-patterns", "k", "v")

    assert result.returncode == 0, result.stderr
    assert _rows(Path(env["CLAUDE_LEARNING_DIR"]))[0]["project_path"] == str(repo)


def test_sibling_lib_wins_over_home_lib(tmp_path: Path, env: dict[str, str]) -> None:
    """The hooks/lib next to the script is imported ahead of ~/.claude/hooks/lib."""
    home = tmp_path / "home"
    shutil.copytree(_REPO_ROOT / "hooks" / "lib", home / ".claude" / "hooks" / "lib")
    checkout = tmp_path / "checkout"
    script = _isolated_script(checkout)
    (checkout / "hooks" / "lib").mkdir(parents=True)
    (checkout / "hooks" / "lib" / "learning_db_v2.py").write_text(_STUB_LIB)
    repo = _git_repo(tmp_path / "repo")

    result = _run(script, repo, {**env, "HOME": str(home)}, "retro-record-adhoc", "go-patterns", "k", "v")

    assert result.returncode == 1
    assert "STUB_LIB_USED" in result.stderr
    assert not (Path(env["CLAUDE_LEARNING_DIR"]) / "learning.db").exists()


def test_complete_archives_to_db_not_repo(tmp_path: Path, env: dict[str, str]) -> None:
    """complete records MEDIUM/HIGH retro records and context files in learning.db only."""
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    state = feature_state.FeatureState(
        name="my-feature",
        retro_records={
            "kept-high": {"value": "high value", "confidence": "high", "observations": 4},
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
    assert out["learnings_already_saved"] == 0
    assert out["retro_archived"] is True
    assert out["state_moved"] is True
    assert not (repo / "retro").exists()
    rows = {r["key"]: r for r in _rows(Path(env["CLAUDE_LEARNING_DIR"]))}
    assert set(rows) == {"kept-high", "kept-medium", "promoted-note"}
    assert rows["kept-high"]["value"] == "high value"
    assert {k: r["confidence"] for k, r in rows.items()} == {
        "kept-high": 0.85,
        "kept-medium": 0.65,
        "promoted-note": 0.65,
    }
    assert all(r["topic"] == "repo--my-feature" for r in rows.values())
    assert all(r["source"] == "feature:my-feature" and r["project_path"] == str(repo) for r in rows.values())
    assert {"kept", "high", "medium", "promoted", "note"} <= set(rows["kept-high"]["tags"].split(","))
    assert rows["kept-high"]["source_detail"] == "feature-observations=4"
    assert rows["kept-high"]["observation_count"] == 1


def test_complete_same_feature_in_two_repos_does_not_merge(tmp_path: Path, env: dict[str, str]) -> None:
    """Two repos completing a feature with the same name and key get separate rows."""
    for name in ("repo-a", "repo-b"):
        repo = _git_repo(tmp_path / name)
        feature_state.save_state(
            repo / ".feature",
            feature_state.FeatureState(
                name="auth",
                retro_records={"token-refresh": {"value": f"{name} value", "confidence": "high"}},
            ),
        )
        result = _run(_SCRIPT, repo, env, "complete", "auth")
        assert result.returncode == 0, result.stderr

    rows = sorted(
        (r["topic"], r["value"], r["project_path"], r["observation_count"])
        for r in _rows(Path(env["CLAUDE_LEARNING_DIR"]))
    )
    assert rows == [
        ("repo-a--auth", "repo-a value", str(tmp_path / "repo-a"), 1),
        ("repo-b--auth", "repo-b value", str(tmp_path / "repo-b"), 1),
    ]


def test_complete_partial_failure_then_retry_counts_once(tmp_path: Path, env: dict[str, str]) -> None:
    """If write 2 of 2 fails, the abort says 1 of 2 saved, and a retry does not re-record write 1."""
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    feature_state.save_state(
        feature_dir,
        feature_state.FeatureState(
            name="f",
            retro_records={
                "a-key": {"value": "a", "confidence": "high", "observations": 4},
                "b-key": {"value": "b", "confidence": "high"},
            },
        ),
    )

    first = _run_failing(repo, env, 2, "complete", "f")

    assert first.returncode == 1
    error = json.loads(first.stderr)["error"]
    assert "1 of 2 learnings saved" in error
    assert "database is locked" in error
    saved = json.loads((feature_dir / "state" / "f.json").read_text())["retro_records"]
    assert saved["a-key"].get("db_recorded") is True
    assert "db_recorded" not in saved["b-key"]

    retry = _run_failing(repo, env, 0, "complete", "f")

    assert retry.returncode == 0, retry.stderr
    out = json.loads(retry.stdout)
    assert (out["learnings_recorded"], out["learnings_already_saved"]) == (2, 1)
    counts = {r["key"]: r["observation_count"] for r in _rows(Path(env["CLAUDE_LEARNING_DIR"]))}
    assert counts == {"a-key": 1, "b-key": 1}
    assert not (feature_dir / "state" / "f.json").exists()


def test_complete_retry_skips_saved_context_file(tmp_path: Path, env: dict[str, str]) -> None:
    """A context-file learning saved before a failure is not re-recorded on retry."""
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    feature_state.save_state(feature_dir, feature_state.FeatureState(name="f"))
    context = feature_dir / "context" / "design"
    context.mkdir(parents=True)
    (context / "a-note.md").write_text("first note")
    (context / "b-note.md").write_text("second note")

    first = _run_failing(repo, env, 2, "complete", "f")

    assert first.returncode == 1
    assert "1 of 2 learnings saved" in json.loads(first.stderr)["error"]
    saved = json.loads((feature_dir / "state" / "f.json").read_text())["retro_records"]
    assert saved["a-note"]["db_recorded"] is True
    assert saved["a-note"]["source"] == "context"

    retry = _run_failing(repo, env, 0, "complete", "f")

    assert retry.returncode == 0, retry.stderr
    counts = {r["key"]: r["observation_count"] for r in _rows(Path(env["CLAUDE_LEARNING_DIR"]))}
    assert counts == {"a-note": 1, "b-note": 1}


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
    assert "0 of 1 learnings saved" in result.stderr
    assert (feature_dir / "state" / "f.json").exists()
    assert not (repo / "retro").exists()


def test_complete_tolerates_state_moved_by_concurrent_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """If another complete moves the state file first, complete still succeeds."""
    repo = _git_repo(tmp_path / "repo")
    feature_dir = repo / ".feature"
    feature_state.save_state(feature_dir, feature_state.FeatureState(name="f"))
    state_file = feature_dir / "state" / "f.json"

    def concurrent_move(root: Path, fdir: Path, state: object) -> tuple[int, int]:
        state_file.unlink()
        return 0, 0

    monkeypatch.chdir(repo)
    monkeypatch.setattr(feature_state, "_archive_retro_knowledge", concurrent_move)
    monkeypatch.setattr(sys, "argv", ["feature-state.py", "complete", "f"])

    assert feature_state.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state_moved"] is False


@pytest.mark.parametrize("command", ["retro-audit", "retro-candidates"])
def test_readers_tolerate_missing_retro_dir(tmp_path: Path, env: dict[str, str], command: str) -> None:
    """Legacy read-only retro subcommands succeed without creating retro/."""
    repo = _git_repo(tmp_path / "repo")

    result = _run(_SCRIPT, repo, env, command)

    assert result.returncode == 0, result.stderr
    assert "No retro/L2/ directory" in result.stdout
    assert not (repo / "retro").exists()
