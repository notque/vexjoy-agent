"""Tests for skill-sprawl-audit.py.

Covers token math, long-description detection, near-duplicate detection,
missing-file handling, report rendering, and exit-code semantics.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "skill-sprawl-audit.py"
_spec = importlib.util.spec_from_file_location("skill_sprawl_audit", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
sys.modules["skill_sprawl_audit"] = audit
_spec.loader.exec_module(audit)


def make_repo(tmp_path: Path, skills: dict[str, dict]) -> Path:
    """Write INDEX.json plus SKILL.md files; return index path."""
    index = {"version": "2.0", "skills": {}}
    for name, spec in skills.items():
        rel = f"skills/test/{name}/SKILL.md"
        index["skills"][name] = {"file": rel, "description": spec["description"]}
        if "body" in spec:
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(spec["body"], encoding="utf-8")
    index_path = tmp_path / "skills" / "INDEX.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index), encoding="utf-8")
    return index_path


BODY_A = "---\nname: a\n---\n# A\n\nRun the linter, then fix every flagged line in order of severity.\n" * 5
BODY_B = "Completely different content about deploying web servers behind nginx on loopback only.\n" * 5


def run(tmp_path: Path, skills: dict[str, dict], **kwargs):
    index_path = make_repo(tmp_path, skills)
    return audit.run_audit(
        index_path,
        tmp_path,
        kwargs.get("context_tokens", 200_000),
        kwargs.get("budget_percent", 2.0),
        kwargs.get("max_desc_tokens", 40),
        kwargs.get("similarity", 0.85),
    )


def test_token_cost_is_ceil_bytes_over_4():
    assert audit.token_cost("abcd") == 1
    assert audit.token_cost("abcde") == 2
    assert audit.token_cost("") == 0
    # Multi-byte UTF-8 counts bytes, not characters.
    assert audit.token_cost("é" * 4) == 2


def test_budget_and_line_cost(tmp_path):
    result = run(tmp_path, {"one": {"description": "short", "body": BODY_A}})
    assert result.budget_tokens == math.floor(200_000 * 0.02)
    assert result.total_line_tokens == audit.token_cost("- one: short")
    assert result.skills[0].body_tokens > 0


def test_long_description_flagged(tmp_path):
    long_desc = "word " * 60
    result = run(
        tmp_path,
        {
            "long": {"description": long_desc, "body": BODY_A},
            "short": {"description": "tiny", "body": BODY_B},
        },
        max_desc_tokens=40,
    )
    assert [e.name for e in result.long_descriptions] == ["long"]


def test_near_duplicate_bodies_detected(tmp_path):
    result = run(
        tmp_path,
        {
            "alpha": {"description": "first", "body": BODY_A},
            "beta": {"description": "second", "body": BODY_A + "extra line\n"},
            "gamma": {"description": "third", "body": BODY_B},
        },
    )
    pairs = {(p.a, p.b) for p in result.duplicates}
    assert ("alpha", "beta") in pairs
    assert all("gamma" not in pair for pair in pairs)


def test_identical_descriptions_flagged_even_with_distinct_bodies(tmp_path):
    result = run(
        tmp_path,
        {
            "x": {"description": "same words", "body": BODY_A},
            "y": {"description": "same words", "body": BODY_B},
        },
    )
    assert any(p.same_description for p in result.duplicates)


def test_missing_skill_file_reported(tmp_path):
    result = run(tmp_path, {"ghost": {"description": "no file on disk"}})
    assert result.missing_files == ["ghost"]


def test_report_contains_sections(tmp_path):
    result = run(tmp_path, {"one": {"description": "short", "body": BODY_A}})
    report = audit.render_report(result, 40, 0.85)
    for heading in ("# Skill Sprawl Audit", "## Prompt Budget", "## Over-long Descriptions", "## Near-duplicates"):
        assert heading in report


def test_exit_codes(tmp_path, capsys):
    index_path = make_repo(
        tmp_path,
        {
            "dup1": {"description": "same", "body": BODY_A},
            "dup2": {"description": "same", "body": BODY_A},
        },
    )
    base = ["--index", str(index_path), "--root", str(tmp_path)]
    assert audit.main(base) == 0  # suggest-first: findings alone exit 0
    assert audit.main([*base, "--check"]) == 1  # CI mode: findings exit 1
    assert audit.main(["--index", str(tmp_path / "nope.json")]) == 2
    capsys.readouterr()


def test_check_passes_on_clean_index(tmp_path):
    index_path = make_repo(
        tmp_path,
        {
            "clean1": {"description": "tiny", "body": BODY_A},
            "clean2": {"description": "other", "body": BODY_B},
        },
    )
    assert audit.main(["--index", str(index_path), "--root", str(tmp_path), "--check"]) == 0


def test_output_file(tmp_path, capsys):
    index_path = make_repo(tmp_path, {"one": {"description": "short", "body": BODY_A}})
    out = tmp_path / "report.md"
    code = audit.main(["--index", str(index_path), "--root", str(tmp_path), "--output", str(out)])
    assert code == 0
    assert "# Skill Sprawl Audit" in out.read_text(encoding="utf-8")
    capsys.readouterr()
