#!/usr/bin/env python3
"""
Tests for scripts/detect-skill-changes.py (changed-skill -> eval mapping).

ADR: skill-eval-pr-ablation, Decision section 1 + Test Plan.

Covers the mapping resolution order (first hit wins):
  1. exact dir match: evals/<name>/
  2. -eval suffix:    evals/<name>-eval/
  3. README mention:  whole-word, case-insensitive, in any evals/*/README.md
  4. no match -> uncovered
Plus: non-SKILL.md changes ignored, exit 0 always, JSON schema + invariant,
and the required 3-skill integration test on a real git range.

Run with: python3 -m pytest scripts/tests/test_detect_skill_changes.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "detect-skill-changes.py"


def _load_module():
    """Import detect-skill-changes.py as a module to unit-test its helpers."""
    spec = importlib.util.spec_from_file_location("detect_skill_changes", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(repo: Path, base: str, head: str, fmt: str = "json") -> subprocess.CompletedProcess:
    """Run the script as a subprocess inside `repo`."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, "--head", head, "--format", fmt],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Unit tests: the mapping function against a mock evals/ tree.
# ---------------------------------------------------------------------------


def test_map_exact_dir(mock_evals):
    mod = _load_module()
    assert mod.map_skill_to_eval("planning", mock_evals) == "evals/planning"


def test_map_eval_suffix(mock_evals):
    mod = _load_module()
    assert mod.map_skill_to_eval("quick", mock_evals) == "evals/quick-eval"


def test_map_readme_mention(mock_evals):
    mod = _load_module()
    assert mod.map_skill_to_eval("skill-creator", mock_evals) == "evals/grouped"


def test_map_uncovered_returns_none(mock_evals):
    mod = _load_module()
    assert mod.map_skill_to_eval("nonexistent-skill", mock_evals) is None


def test_map_readme_whole_word_only(mock_evals):
    """A substring of a longer word in README must NOT match (whole-word rule)."""
    mod = _load_module()
    # "plan" is a substring of "planning" mentioned in evals/planning/README.md,
    # but "plan" is not a whole word there -> no README match, and no dir
    # evals/plan or evals/plan-eval -> uncovered.
    assert mod.map_skill_to_eval("plan", mock_evals) is None


def test_map_exact_dir_precedes_readme(tmp_path):
    """Resolution order: exact dir wins over a README mention elsewhere."""
    mod = _load_module()
    root = tmp_path / "r"
    (root / "evals" / "planning").mkdir(parents=True)
    (root / "evals" / "planning" / "README.md").write_text("# planning\n", encoding="utf-8")
    (root / "evals" / "other").mkdir(parents=True)
    (root / "evals" / "other" / "README.md").write_text("mentions planning here\n", encoding="utf-8")
    assert mod.map_skill_to_eval("planning", root) == "evals/planning"


# ---------------------------------------------------------------------------
# Changed-skill extraction: only skills/**/SKILL.md paths count.
# ---------------------------------------------------------------------------


def test_changed_skills_ignores_non_skill_md(mock_skill_tree):
    mod = _load_module()
    paths = [
        "skills/process/planning/SKILL.md",
        "skills/process/planning/references/foo.md",  # not SKILL.md -> ignore
        "README.md",  # not under skills/ -> ignore
        "scripts/x.py",  # ignore
    ]
    names = mod.skill_names_from_paths(paths, mock_skill_tree)
    assert names == ["planning"]


def test_changed_skills_sorted_deduped(mock_skill_tree):
    mod = _load_module()
    paths = [
        "skills/meta/skill-creator/SKILL.md",
        "skills/process/planning/SKILL.md",
        "skills/process/planning/SKILL.md",  # dup
    ]
    names = mod.skill_names_from_paths(paths, mock_skill_tree)
    assert names == ["planning", "skill-creator"]


# ---------------------------------------------------------------------------
# Integration: real git range, JSON output, schema + invariant. (REQUIRED)
# ---------------------------------------------------------------------------


def test_integration_three_skills(git_range):
    repo, base, head = git_range["repo"], git_range["base"], git_range["head"]
    res = _run(repo, base, head, "json")

    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)

    # Schema keys + types.
    assert isinstance(data["base"], str)
    assert isinstance(data["head"], str)
    assert isinstance(data["changed_skills"], list)
    assert isinstance(data["mapped"], list)
    assert isinstance(data["uncovered"], list)

    # base/head resolved to full hashes.
    assert data["base"] == base
    assert data["head"] == head

    # 3 changed skills, sorted ascending.
    assert data["changed_skills"] == ["orphan", "planning", "quick"]

    # 2 mapped, sorted by skill, correct eval_dir, no trailing slash.
    mapped = data["mapped"]
    assert len(mapped) == 2
    by_skill = {m["skill"]: m["eval_dir"] for m in mapped}
    assert by_skill == {"planning": "evals/planning", "quick": "evals/quick-eval"}
    for m in mapped:
        assert not m["eval_dir"].endswith("/")
    assert [m["skill"] for m in mapped] == sorted(m["skill"] for m in mapped)

    # 1 uncovered.
    assert data["uncovered"] == ["orphan"]

    # Invariant: every changed skill is mapped XOR uncovered.
    assert set(data["changed_skills"]) == {m["skill"] for m in mapped} | set(data["uncovered"])


def test_exit_code_always_zero_even_all_uncovered(tmp_path):
    """A range whose changed skills have no eval still exits 0 (mapper, not gate)."""
    repo = tmp_path / "repo"
    (repo / "skills" / "x" / "lonely").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    skill = repo / "skills" / "x" / "lonely" / "SKILL.md"
    skill.write_text("---\nname: lonely\nversion: 1.0.0\n---\n\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    skill.write_text("---\nname: lonely\nversion: 1.1.0\n---\n\nbody2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "head"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    res = _run(repo, base, head, "json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["changed_skills"] == ["lonely"]
    assert data["mapped"] == []
    assert data["uncovered"] == ["lonely"]


def test_human_format_runs_and_exits_zero(git_range):
    res = _run(git_range["repo"], git_range["base"], git_range["head"], "human")
    assert res.returncode == 0
    assert "planning" in res.stdout


@pytest.mark.parametrize("fmt", ["json", "human"])
def test_no_changed_skills_is_clean(tmp_path, fmt):
    """Range with no skill changes: empty lists, exit 0."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "README.md").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "head"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    res = _run(repo, base, head, fmt)
    assert res.returncode == 0
    if fmt == "json":
        data = json.loads(res.stdout)
        assert data["changed_skills"] == []
        assert data["mapped"] == []
        assert data["uncovered"] == []
