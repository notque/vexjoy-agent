#!/usr/bin/env python3
"""
Tests for scripts/audit-trigger-ambiguity.py (report-only collision auditor).

ADR: trigger-ambiguity-audit. The audit must ALWAYS exit 0 (advisory, non-blocking).

Run with: python3 -m pytest scripts/tests/test_audit_trigger_ambiguity.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "audit-trigger-ambiguity.py"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def write_index(path: Path, kind: str, entries: dict) -> None:
    """Write a minimal INDEX.json. kind is 'skills' or 'agents'."""
    path.write_text(json.dumps({"version": "x", kind: entries}), encoding="utf-8")


def run(skills_path: Path, agents_path: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skills-index",
            str(skills_path),
            "--agents-index",
            str(agents_path),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def run_json(skills_path: Path, agents_path: Path, *extra: str) -> dict:
    proc = run(skills_path, agents_path, "--json", *extra)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def make_indexes(tmp_path: Path, skills: dict, agents: dict) -> tuple[Path, Path]:
    sp = tmp_path / "skills_INDEX.json"
    ap = tmp_path / "agents_INDEX.json"
    write_index(sp, "skills", skills)
    write_index(ap, "agents", agents)
    return sp, ap


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_exact_collision_neither_has_not_for(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"a": {"triggers": ["foo"]}},
        agents={"b": {"triggers": ["foo"]}},
    )
    data = run_json(sp, ap)
    assert data["totals"]["undisambiguated"] == 1
    report = data["reportable"]
    assert len(report) == 1
    row = report[0]
    assert row["kind"] == "exact"
    assert row["trigger"] == "foo"
    assert set(row["owners"]) == {"skill:a", "agent:b"}
    assert row["any_not_for"] is False


def test_collision_disambiguated_on_one_side_excluded(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"a": {"triggers": ["foo"], "not_for": "not the other thing"}},
        agents={"b": {"triggers": ["foo"]}},
    )
    data = run_json(sp, ap)
    # Still counted as a collision, but excluded from reportable.
    assert data["totals"]["collisions"] >= 1
    assert data["totals"]["undisambiguated"] == 0
    assert data["reportable"] == []


def test_near_duplicate_via_article(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"skill-creator": {"triggers": ["create skill"]}},
        agents={"toolkit-governance-engineer": {"triggers": ["create a skill"]}},
    )
    data = run_json(sp, ap)
    assert data["totals"]["undisambiguated"] == 1
    assert data["reportable"][0]["kind"] == "near-dup"


def test_near_duplicate_via_edit_distance(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"a": {"triggers": ["phpunit"]}},
        agents={"b": {"triggers": ["phpun1t"]}},
    )
    data = run_json(sp, ap)
    assert data["totals"]["undisambiguated"] == 1
    assert data["reportable"][0]["kind"] == "near-dup"


def test_no_collision(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"a": {"triggers": ["alpha"]}},
        agents={"b": {"triggers": ["zulu"]}},
    )
    proc = run(sp, ap, "--json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["totals"]["undisambiguated"] == 0
    assert data["reportable"] == []


def test_ranking_owner_count_desc(tmp_path: Path) -> None:
    # 3-owner exact collision on "big"; 2-owner exact collision on "small".
    sp, ap = make_indexes(
        tmp_path,
        skills={
            "a": {"triggers": ["big"]},
            "b": {"triggers": ["big", "small"]},
            "d": {"triggers": ["small"]},
        },
        agents={"c": {"triggers": ["big"]}},
    )
    data = run_json(sp, ap)
    report = data["reportable"]
    assert report[0]["trigger"] == "big"
    assert report[0]["owner_count"] == 3
    assert report[1]["trigger"] == "small"
    assert report[1]["owner_count"] == 2


def test_always_exits_zero_with_reportable(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"a": {"triggers": ["foo"]}},
        agents={"b": {"triggers": ["foo"]}},
    )
    proc = run(sp, ap)  # human mode, has a reportable collision
    assert proc.returncode == 0


def test_missing_index_file_exits_zero(tmp_path: Path) -> None:
    ap = tmp_path / "agents_INDEX.json"
    write_index(ap, "agents", {"b": {"triggers": ["foo"]}})
    proc = run(tmp_path / "nonexistent.json", ap)
    assert proc.returncode == 0
    assert "ERROR:" in proc.stderr


def test_malformed_index_json_exits_zero(tmp_path: Path) -> None:
    sp = tmp_path / "skills_INDEX.json"
    ap = tmp_path / "agents_INDEX.json"
    sp.write_text("{ this is not json", encoding="utf-8")
    write_index(ap, "agents", {"b": {"triggers": ["foo"]}})
    proc = run(sp, ap)
    assert proc.returncode == 0
    assert "ERROR:" in proc.stderr


def test_json_shape(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={"a": {"triggers": ["foo"]}},
        agents={"b": {"triggers": ["foo"]}},
    )
    data = run_json(sp, ap)
    assert data["schema"] == "trigger-ambiguity-audit/v1"
    assert "generated" in data
    for key in ("collisions", "undisambiguated", "skills_indexed", "agents_indexed"):
        assert key in data["totals"]
    assert isinstance(data["reportable"], list)


def test_top_does_not_truncate_json(tmp_path: Path) -> None:
    sp, ap = make_indexes(
        tmp_path,
        skills={
            "a": {"triggers": ["foo"]},
            "c": {"triggers": ["bar"]},
        },
        agents={
            "b": {"triggers": ["foo"]},
            "d": {"triggers": ["bar"]},
        },
    )
    # JSON is always full regardless of --top.
    data = run_json(sp, ap, "--top", "1")
    assert len(data["reportable"]) == 2
