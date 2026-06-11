"""Tests for scoped-commit.py.

Covers guards (".", message-vs-path, empty message, missing path),
pathspec-scoped staging/commit, deletion staging, and --force-lock
stale index.lock handling. Each test uses a throwaway git repo.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
scoped_commit = importlib.import_module("scoped-commit")
sys.path.pop(0)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Throwaway git repo with one initial commit; cwd set inside it."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "base.txt").write_text("base\n")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _last_message(repo: Path) -> str:
    return _git(repo, "log", "-1", "--pretty=%s").stdout.strip()


class TestGuards:
    def test_rejects_dot_path(self, repo: Path, capsys: pytest.CaptureFixture) -> None:
        (repo / "a.txt").write_text("a")
        assert scoped_commit.main(["msg", "."]) == 1
        assert "list specific paths" in capsys.readouterr().err

    def test_rejects_message_that_is_a_path(self, repo: Path, capsys: pytest.CaptureFixture) -> None:
        (repo / "a.txt").write_text("a")
        assert scoped_commit.main(["a.txt", "base.txt"]) == 1
        assert "looks like a path" in capsys.readouterr().err

    def test_rejects_empty_message(self, repo: Path, capsys: pytest.CaptureFixture) -> None:
        assert scoped_commit.main(["   ", "base.txt"]) == 1
        assert "must not be empty" in capsys.readouterr().err

    def test_rejects_unknown_path(self, repo: Path, capsys: pytest.CaptureFixture) -> None:
        assert scoped_commit.main(["msg", "nope.txt"]) == 1
        assert "path not found" in capsys.readouterr().err

    def test_no_changes_fails(self, repo: Path, capsys: pytest.CaptureFixture) -> None:
        assert scoped_commit.main(["msg", "base.txt"]) == 1
        assert "no staged changes" in capsys.readouterr().err


class TestCommit:
    def test_commits_only_listed_paths(self, repo: Path) -> None:
        (repo / "a.txt").write_text("a")
        (repo / "b.txt").write_text("b")
        assert scoped_commit.main(["add a", "a.txt"]) == 0
        assert _last_message(repo) == "add a"
        status = _git(repo, "status", "--porcelain").stdout
        assert "b.txt" in status  # b stays uncommitted
        assert "a.txt" not in status

    def test_unstages_prestaged_unlisted_files(self, repo: Path) -> None:
        (repo / "a.txt").write_text("a")
        (repo / "b.txt").write_text("b")
        _git(repo, "add", "b.txt")
        assert scoped_commit.main(["add a", "a.txt"]) == 0
        show = _git(repo, "show", "--name-only", "--pretty=", "HEAD").stdout
        assert "a.txt" in show
        assert "b.txt" not in show

    def test_commits_deletion(self, repo: Path) -> None:
        (repo / "base.txt").unlink()
        assert scoped_commit.main(["remove base", "base.txt"]) == 0
        assert _last_message(repo) == "remove base"


class TestForceLock:
    def test_lock_blocks_without_flag(self, repo: Path) -> None:
        (repo / "a.txt").write_text("a")
        lock = repo / ".git" / "index.lock"
        # git add also needs the lock; stage first, then create the lock so only commit hits it.
        _git(repo, "add", "a.txt")
        lock.touch()
        try:
            assert scoped_commit.main(["msg", "a.txt"]) == 1
        finally:
            lock.unlink(missing_ok=True)
        assert _last_message(repo) == "init"

    def test_force_lock_removes_stale_lock_and_commits(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (repo / "a.txt").write_text("a")
        lock = repo / ".git" / "index.lock"
        real_git = scoped_commit._git

        def git_with_lock(args: list[str]) -> subprocess.CompletedProcess[str]:
            # Plant the lock only for the first commit attempt.
            if args[0] == "commit" and not lock.exists() and not getattr(git_with_lock, "retried", False):
                lock.touch()
                git_with_lock.retried = True
            return real_git(args)

        monkeypatch.setattr(scoped_commit, "_git", git_with_lock)
        assert scoped_commit.main(["--force-lock", "msg", "a.txt"]) == 0
        assert not lock.exists()
        assert _last_message(repo) == "msg"
