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


def test_mark_refuses_non_review_content(repo: Path):
    bad = findings_file(repo, "just some text without any review structure\n")
    proc = mark(repo, findings=bad)
    assert proc.returncode == 1
    assert "missing review structure" in proc.stderr


def test_mark_refuses_blocking_verdict(repo: Path):
    blocked = findings_file(repo, "## Verdict: BLOCK\n\n## Scope\nReviewed changes.\n")
    proc = mark(repo, findings=blocked)
    assert proc.returncode == 1
    assert "blocking verdict" in proc.stderr


@pytest.mark.parametrize(
    "line",
    ["VERDICT: NEEDS_CHANGES", "7. VERDICT: REQUEST_CHANGES", "Verdict: REQUEST-CHANGES"],
)
def test_mark_refuses_non_pass_verdicts(repo: Path, line: str):
    proc = mark(repo, findings=findings_file(repo, f"## Scope\nReviewed changes.\n\n{line}\n"))
    assert proc.returncode == 1
    assert "blocking verdict" in proc.stderr


SYSTEMATIC_PASS = (
    "## Summary\nReviewed the token module and its callers end to end.\n\n"
    "SUGGESTIONS:\n  1. Name the 3600 constant - internal/auth/token.go:62\n\n"
    "Risk Level: LOW\n\nVerdict: PASS\nRationale: Only an optional rename.\n"
)


def test_mark_with_type_accepts_valid_review(repo: Path):
    pytest.importorskip("jsonschema", exc_type=ImportError)
    body = SYSTEMATIC_PASS.encode()
    proc = mark(repo, "--type", "systematic", findings=findings_file(repo, SYSTEMATIC_PASS))
    assert proc.returncode == 0, proc.stderr
    record = json.loads(Path(json.loads(proc.stdout)["path"]).read_text())
    assert record["findings_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["version"] == 2


# The review skill's Phase 4 template (skills/review/review/SKILL.md): label
# lines only, no markdown headings.
PHASE4_PASS = (
    "Review Summary:\n  Files Reviewed: 3 | Lines Changed: +10/-2\n  Test Status: PASS\n  Risk Level: LOW\n\n"
    "BLOCKING: none\nSHOULD FIX: none\nSUGGESTIONS:\n  1. Name the 3600 constant - internal/auth/token.go:62\n\n"
    "Verdict: PASS\nRationale: Only an optional rename.\n"
)


@pytest.mark.parametrize("typed", [False, True])
def test_mark_accepts_the_review_skill_label_template(repo: Path, typed: bool):
    if typed:
        pytest.importorskip("jsonschema", exc_type=ImportError)
    extra = ("--type", "systematic") if typed else ()
    proc = mark(repo, *extra, findings=findings_file(repo, PHASE4_PASS))
    assert proc.returncode == 0, proc.stderr


def test_mark_with_type_lists_schema_errors(repo: Path):
    pytest.importorskip("jsonschema", exc_type=ImportError)
    text = SYSTEMATIC_PASS.replace("Risk Level: LOW\n\n", "")
    proc = mark(repo, "--type", "systematic", findings=findings_file(repo, text))
    assert proc.returncode == 1
    assert "systematic schema" in proc.stderr
    assert "MISSING: risk_level" in proc.stderr


def _isolated_recorder(tmp_path: Path, validator_source: str | None) -> Path:
    """Copy review-record.py next to a stand-in validator (or none)."""
    scripts = tmp_path / "iso" / "scripts"
    scripts.mkdir(parents=True)
    (tmp_path / "iso" / "hooks").mkdir()
    (tmp_path / "iso" / "hooks" / "lib").symlink_to(SCRIPT.parent.parent / "hooks" / "lib")
    script = scripts / "review-record.py"
    script.write_text(SCRIPT.read_text())
    if validator_source is not None:
        (scripts / "validate-review-output.py").write_text(validator_source)
    return script


@pytest.mark.parametrize(
    ("validator_source", "message"),
    [
        ("raise SystemExit(3)\n", "exited 3"),
        ("raise RuntimeError('boom')\n", "RuntimeError: boom"),
        (None, "is missing"),
        (
            "def parse_markdown(content, review_type):\n    raise ValueError('bad table')\n"
            "def validate_structure(data, review_type):\n    return []\n",
            "ValueError: bad table",
        ),
    ],
)
def test_mark_with_type_refuses_when_validator_cannot_run(
    repo: Path, tmp_path: Path, validator_source: str | None, message: str
):
    script = _isolated_recorder(tmp_path, validator_source)
    findings = findings_file(repo, SYSTEMATIC_PASS)
    env = {**os.environ, "HOME": str(repo.parent / "home")}
    args = ["--summary", "clean", "--critical", "0", "--important", "0", "--findings-file", str(findings)]
    proc = subprocess.run(
        [sys.executable, str(script), "mark", *args, "--type", "systematic", "--repo-dir", str(repo)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 1, proc.stdout
    assert "refused" in proc.stderr and message in proc.stderr
    assert run(repo, "check").returncode == 1


def test_mark_without_type_does_not_need_the_validator(repo: Path, tmp_path: Path):
    script = _isolated_recorder(tmp_path, "raise SystemExit(3)\n")
    findings = findings_file(repo)
    env = {**os.environ, "HOME": str(repo.parent / "home")}
    args = ["--summary", "clean", "--critical", "0", "--important", "0", "--findings-file", str(findings)]
    proc = subprocess.run(
        [sys.executable, str(script), "mark", *args, "--repo-dir", str(repo)], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr


def test_records_root_respects_antigravity_runtime(monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "hooks" / "lib"))
    import review_record

    monkeypatch.setenv("VEXJOY_HOOK_RUNTIME", "antigravity")
    assert ".gemini" in str(review_record.records_root())


def test_read_record_cross_runtime_fallback(tmp_path: Path, monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "hooks" / "lib"))
    import review_record

    # Set up mock home directory with .claude records
    mock_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(mock_home))
    repo_id = "/path/to/repo"
    key = hashlib.sha256(repo_id.encode("utf-8")).hexdigest()[:16]
    claude_records = mock_home / ".claude" / "state" / "review-records" / key
    claude_records.mkdir(parents=True)
    record_data = {
        "version": 2,
        "repo": repo_id,
        "sha": "1234567890123456789012345678901234567890",
        "reviewed_at": "2026-10-26T12:00:00Z",
        "summary": "clean",
        "critical": 0,
        "important": 0,
        "findings_sha256": "a" * 64,
        "findings_path": "/tmp/f.md",
        "remotes": {},
    }
    (claude_records / f"{record_data['sha']}.json").write_text(json.dumps(record_data))

    # When running under antigravity, records_root() is .gemini, but read_record finds .claude
    monkeypatch.setenv("VEXJOY_HOOK_RUNTIME", "antigravity")
    read = review_record.read_record(repo_id, record_data["sha"])
    assert read is not None
    assert read["sha"] == record_data["sha"]
