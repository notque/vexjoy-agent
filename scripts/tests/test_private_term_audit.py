"""Tests for scripts/private-term-audit.py."""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path
from unittest import mock

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "private-term-audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("private_term_audit", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pta = _load_module()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


class _FakeGate:
    def __init__(self, leaves: set[str], strong: set[str]):
        self._leaves = leaves
        self._strong = strong

    def private_terms(self, repo: Path):
        return self._leaves, self._strong

    def term_pattern(self, leaves: set[str], strong: set[str]):
        all_terms = sorted(leaves | strong)
        if not all_terms:
            return None
        return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in all_terms) + r")\b", re.IGNORECASE)

    def _redact(self, s: str) -> str:
        return s[0] + "…" + s[-1]


class TestGitHelper:
    def test_scrubs_git_env_vars(self, tmp_path, monkeypatch):
        target = _init_repo(tmp_path / "target")
        (target / "clean.txt").write_text("clean content\n", encoding="utf-8")
        subprocess.run(["git", "add", "clean.txt"], cwd=target, check=True)

        decoy = _init_repo(tmp_path / "decoy")
        (decoy / "decoy.txt").write_text("secretbrand\n", encoding="utf-8")
        subprocess.run(["git", "add", "decoy.txt"], cwd=decoy, check=True)

        monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
        monkeypatch.setenv("GIT_INDEX_FILE", str(decoy / ".git" / "index"))
        monkeypatch.setenv("GIT_COMMON_DIR", str(decoy / ".git"))

        out = pta.git(target, "ls-files", "-z")
        files = [f for f in out.split("\0") if f]
        assert files == ["clean.txt"]

    def test_ls_files_exit_1_raises_runtime_error(self, tmp_path):
        fake = subprocess.CompletedProcess(["git", "ls-files"], returncode=1, stdout="", stderr="index error")
        with mock.patch.object(subprocess, "run", return_value=fake), pytest.raises(RuntimeError, match="index error"):
            pta.git(tmp_path, "ls-files", "-z")

    def test_grep_exit_1_allowed_when_allow_no_match(self, tmp_path):
        fake = subprocess.CompletedProcess(["git", "grep"], returncode=1, stdout="", stderr="")
        with mock.patch.object(subprocess, "run", return_value=fake):
            assert pta.git(tmp_path, "grep", "--file=-", input_text="needle\n", allow_no_match=True) == ""

    def test_timeout_raises_runtime_error(self, tmp_path):
        with (
            mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(["git", "grep"], 1.0)),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            pta.git(tmp_path, "grep", timeout=1.0)


class TestAuditStdinPatterns:
    def test_audit_uses_file_stdin_and_finds_matches(self, tmp_path):
        repo = _init_repo(tmp_path / "repo")
        (repo / "hit.txt").write_text("mentions acmeinternal here\n", encoding="utf-8")
        (repo / "ok.txt").write_text("nothing private\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)

        gate = _FakeGate({"acmeinternal"}, {"secretterm"})
        captured_calls = []
        orig_git = pta.git

        def spy_git(r, *args, **kwargs):
            captured_calls.append((args, kwargs))
            return orig_git(r, *args, **kwargs)

        with mock.patch.object(pta, "git", side_effect=spy_git):
            lines = pta.audit(repo, gate)

        assert lines == ["hit.txt  [content]"]
        grep_calls = [(a, kw) for a, kw in captured_calls if a and a[0] == "grep"]
        assert len(grep_calls) == 1
        grep_args, grep_kwargs = grep_calls[0]
        assert "-f" in grep_args and "-" in grep_args
        assert "-e" not in grep_args
        assert "acmeinternal" in grep_kwargs["input_text"]
        assert "secretterm" in grep_kwargs["input_text"]
        assert grep_kwargs["allow_no_match"] is True
