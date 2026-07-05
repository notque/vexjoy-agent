#!/usr/bin/env python3
"""Tests for scripts/pr-risk-classify.py — PR risk classification.

Covers: path classification (high/medium/low), size tier mapping, risk
resolution rules (path dominance, size escalation), recommend_split,
review lane assignment, numstat parsing, and CLI contract.
"""

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "pr-risk-classify.py"

# Import the module directly for unit-level tests of pure helpers.
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("pr_risk_classify", SCRIPT)
prc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prc)


# --- Path classification -----------------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        # HIGH paths
        ("hooks/pre-check.py", "high"),
        ("hooks/lib/utils.py", "high"),
        (".github/workflows/test.yml", "high"),
        (".github/pull_request_template.md", "high"),
        ("install.sh", "high"),
        ("scripts/sync-to-user-claude.py", "high"),
        ("scripts/sync-hooks.py", "high"),
        (".claude/settings.json", "high"),
        (".claude/settings.local.json", "high"),
        ("CLAUDE.md", "high"),
        # LOW paths
        ("docs/PHILOSOPHY.md", "low"),
        ("docs/what-didnt-work.md", "low"),
        ("adr/001-routing.md", "low"),
        ("skills/meta/do/references/routing.md", "low"),
        ("agents/INDEX.json", "low"),
        ("INDEX.json", "low"),
        ("agents/golang-general-engineer/references/idioms.md", "low"),
        # MEDIUM paths
        ("scripts/right-size-review.py", "medium"),
        ("agents/toolkit-governance-engineer.md", "medium"),
        ("skills/meta/do/SKILL.md", "medium"),
        ("src/server.go", "medium"),
        ("pyproject.toml", "medium"),
    ],
)
def test_classify_path(path, expected):
    assert prc.classify_path(path) == expected


def test_root_markdown_is_high_only_for_claude_md():
    """Root CLAUDE.md is high; other root .md files are medium (not low)."""
    assert prc.classify_path("CLAUDE.md") == "high"
    # Root markdown that is not CLAUDE.md: _ROOT_MD match prevents LOW.
    assert prc.classify_path("README.md") == "medium"
    assert prc.classify_path("CONTRIBUTING.md") == "medium"


def test_skill_md_is_medium():
    """SKILL.md files are medium, not low (they define skill interfaces)."""
    assert prc.classify_path("skills/meta/do/SKILL.md") == "medium"
    assert prc.classify_path("skills/process/pr-workflow/SKILL.md") == "medium"


def test_nested_markdown_classification():
    """Reference markdown is low; agent definitions and other .md are medium."""
    assert prc.classify_path("agents/golang-general-engineer/references/idioms.md") == "low"
    assert prc.classify_path("docs/router-ab-runbook.md") == "low"
    # Agent definition files are medium (they define agent interfaces).
    assert prc.classify_path("agents/golang-general-engineer.md") == "medium"
    # Non-reference markdown in agent dirs is medium.
    assert prc.classify_path("agents/golang-general-engineer/notes.md") == "medium"


# --- Size tier ----------------------------------------------------------------


@pytest.mark.parametrize(
    "lines,expected",
    [
        (0, "small"),
        (1, "small"),
        (200, "small"),
        (201, "medium"),
        (800, "medium"),
        (801, "large"),
        (5000, "large"),
    ],
)
def test_size_tier(lines, expected):
    assert prc.size_tier(lines) == expected


# --- Risk resolution rules ----------------------------------------------------


def test_high_risk_path_dominates():
    """Any HIGH path => risk HIGH regardless of size."""
    files = [("hooks/pre-check.py", 5), ("docs/readme.md", 10)]
    result = prc.classify(files)
    assert result["risk"] == "high"
    assert result["review_lane"] == "full-roster-plus-sign-off"
    assert "hooks/pre-check.py" in result["high_risk_files"]


def test_all_low_small_is_low():
    """All LOW paths + small size => LOW risk."""
    files = [("docs/guide.md", 30), ("adr/002-hooks.md", 20)]
    result = prc.classify(files)
    assert result["risk"] == "low"
    assert result["review_lane"] == "quick-single"


def test_all_low_medium_size_escalates_to_medium():
    """All LOW paths but medium size => MEDIUM risk."""
    files = [("docs/guide.md", 250), ("docs/other.md", 100)]
    result = prc.classify(files)
    assert result["risk"] == "medium"
    assert result["review_lane"] == "full-roster"


def test_all_low_large_size_escalates_to_high():
    """All LOW paths but large size => HIGH risk."""
    files = [("docs/guide.md", 500), ("docs/other.md", 400)]
    result = prc.classify(files)
    assert result["risk"] == "high"
    assert result["review_lane"] == "full-roster-plus-sign-off"


def test_medium_path_small_size_is_medium():
    """MEDIUM path + small size => MEDIUM."""
    files = [("scripts/validate.py", 50)]
    result = prc.classify(files)
    assert result["risk"] == "medium"
    assert result["review_lane"] == "full-roster"


def test_medium_path_large_size_stays_medium_with_split():
    """MEDIUM path + large size => MEDIUM risk but recommend_split."""
    files = [("scripts/validate.py", 900)]
    result = prc.classify(files)
    assert result["risk"] == "medium"
    assert result["recommend_split"] is True


def test_empty_diff_is_low():
    result = prc.classify([])
    assert result["risk"] == "low"
    assert result["total_lines"] == 0
    assert result["recommend_split"] is False


def test_recommend_split_at_801_lines():
    """Split recommendation triggers above 800 lines."""
    files = [("src/app.py", 801)]
    result = prc.classify(files)
    assert result["recommend_split"] is True
    assert any("800-line ceiling" in r for r in result["reasons"])


def test_no_recommend_split_at_800_lines():
    files = [("src/app.py", 800)]
    result = prc.classify(files)
    assert result["recommend_split"] is False


def test_high_risk_files_populated():
    files = [
        ("hooks/a.py", 10),
        (".github/workflows/ci.yml", 20),
        ("scripts/validate.py", 30),
    ]
    result = prc.classify(files)
    assert set(result["high_risk_files"]) == {"hooks/a.py", ".github/workflows/ci.yml"}


def test_result_json_contract():
    """All required keys present in result."""
    files = [("src/main.py", 100)]
    result = prc.classify(files)
    required_keys = {
        "risk",
        "size_tier",
        "total_lines",
        "file_count",
        "recommend_split",
        "reasons",
        "high_risk_files",
        "review_lane",
    }
    assert required_keys == set(result.keys())


# --- Numstat parsing ---------------------------------------------------------


def test_parse_numstat_normal():
    raw = "10\t5\tsrc/app.py\n3\t1\tdocs/readme.md\n"
    result = prc._parse_numstat(raw)
    assert result == [("src/app.py", 15), ("docs/readme.md", 4)]


def test_parse_numstat_binary():
    """Binary files (- - path) parse as 0 lines."""
    raw = "-\t-\timage.png\n5\t2\tsrc/app.py\n"
    result = prc._parse_numstat(raw)
    assert result == [("image.png", 0), ("src/app.py", 7)]


def test_parse_numstat_blank_lines():
    raw = "10\t5\tsrc/app.py\n\n  \n3\t1\tdocs/readme.md\n"
    result = prc._parse_numstat(raw)
    assert len(result) == 2


def test_parse_numstat_empty():
    assert prc._parse_numstat("") == []
    assert prc._parse_numstat("\n\n") == []


# --- Git integration ---------------------------------------------------------


def test_git_numstat_with_base_uses_range(monkeypatch):
    captured = {}

    def _run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return types.SimpleNamespace(stdout="10\t5\tsrc/app.py\n")

    monkeypatch.setattr(prc.subprocess, "run", _run)
    files = prc._git_numstat("main", "HEAD")
    assert captured["cmd"] == ["git", "diff", "--numstat", "main...HEAD"]
    assert files == [("src/app.py", 15)]


def test_git_numstat_without_base(monkeypatch):
    captured = {}

    def _run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return types.SimpleNamespace(stdout="3\t1\tREADME.md\n")

    monkeypatch.setattr(prc.subprocess, "run", _run)
    files = prc._git_numstat(None, "HEAD")
    assert captured["cmd"] == ["git", "diff", "--numstat", "HEAD"]
    assert files == [("README.md", 4)]


def test_git_numstat_error_returns_empty(monkeypatch):
    def _raise(*a, **k):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(prc.subprocess, "run", _raise)
    assert prc._git_numstat("main", "HEAD") == []


def test_git_numstat_missing_git(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(prc.subprocess, "run", _raise)
    assert prc._git_numstat("bad", "HEAD") == []


# --- CLI contract -------------------------------------------------------------


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_cli_exit_zero_always():
    proc = _run("--base", "main", "--head", "HEAD")
    assert proc.returncode == 0


def test_cli_emits_valid_json():
    proc = _run("--base", "main", "--head", "HEAD")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["risk"] in ("low", "medium", "high")
    assert "recommend_split" in data


def test_cli_stdin_mode():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--stdin"],
        input="10\t5\thooks/pre-check.py\n3\t1\tdocs/guide.md\n",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["risk"] == "high"
    assert "hooks/pre-check.py" in data["high_risk_files"]
    assert data["total_lines"] == 19
