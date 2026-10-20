#!/usr/bin/env python3
"""Tests for scripts/review-record.py: when mark writes a record and when it refuses.

Run with: python3 -m pytest scripts/tests/test_review_record.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "review-record.py"


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("one\n")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-q", "-m", "one")
    _git(path, "remote", "add", "origin", "https://github.com/sapcc/limes.git")
    return path


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(repo.parent / "home")}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--repo-dir", str(repo)], capture_output=True, text=True, env=env
    )


def findings_file(repo: Path, text: str = "## Critical\nnone\n") -> Path:
    path = repo.parent / "findings.md"
    path.write_text(text)
    return path


def mark(repo: Path, *extra: str, critical: str = "0", important: str = "0", summary: str = "clean", findings=None):
    if findings is None:
        findings = findings_file(repo)
    args = ["--summary", summary, "--critical", critical, "--important", important, "--findings-file", str(findings)]
    return run(repo, "mark", *args, *extra)


def test_mark_then_check_head(repo: Path):
    proc = mark(repo)
    assert proc.returncode == 0, proc.stderr
    record = json.loads(Path(json.loads(proc.stdout)["path"]).read_text())
    assert record["sha"] == _git(repo, "rev-parse", "HEAD")
    assert record["summary"] == "clean"
    assert record["remotes"] == {"origin": "https://github.com/sapcc/limes.git"}
    assert record["reviewed_at"]
    assert record["version"] == 2
    assert record["findings_sha256"] == hashlib.sha256(b"## Critical\nnone\n").hexdigest()
    assert run(repo, "check").returncode == 0


def test_check_fails_for_new_commit(repo: Path):
    assert mark(repo).returncode == 0
    (repo / "a.txt").write_text("two\n")
    _git(repo, "commit", "-q", "-am", "two")
    proc = run(repo, "check")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["reviewed"] is False


@pytest.mark.parametrize(("critical", "important"), [("1", "0"), ("0", "2")])
def test_mark_refuses_open_findings(repo: Path, critical: str, important: str):
    proc = mark(repo, critical=critical, important=important)
    assert proc.returncode == 1 and "refused" in proc.stderr
    assert run(repo, "check").returncode == 1


def test_mark_refuses_dirty_tree_for_head(repo: Path):
    (repo / "a.txt").write_text("uncommitted\n")
    proc = mark(repo)
    assert proc.returncode == 1 and "commit the changes" in proc.stderr


def test_mark_refuses_empty_summary(repo: Path):
    assert mark(repo, summary="  ").returncode == 1


def test_mark_rejects_unknown_rev(repo: Path):
    assert mark(repo, "--sha", "no-such-branch").returncode == 2


def test_mark_outside_repo(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert mark(plain).returncode == 2


def test_mark_refuses_missing_findings_file(repo: Path):
    proc = mark(repo, findings=repo.parent / "nope.md")
    assert proc.returncode == 1 and "does not exist" in proc.stderr


def test_mark_refuses_empty_findings_file(repo: Path):
    proc = mark(repo, findings=findings_file(repo, "  \n"))
    assert proc.returncode == 1 and "is empty" in proc.stderr


def test_mark_refuses_findings_older_than_commit(repo: Path):
    old = findings_file(repo)
    ct = int(_git(repo, "show", "-s", "--format=%ct", "HEAD"))
    os.utime(old, (ct - 60, ct - 60))
    proc = mark(repo, findings=old)
    assert proc.returncode == 1 and "older than commit" in proc.stderr


def test_mark_requires_findings_flag(repo: Path):
    proc = run(repo, "mark", "--summary", "x", "--critical", "0", "--important", "0")
    assert proc.returncode == 2 and "--findings-file" in proc.stderr
