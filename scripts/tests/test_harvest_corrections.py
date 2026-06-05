#!/usr/bin/env python3
"""Tests for scripts/harvest-corrections.py and the route-health correction rate.

ADR: correction-harvesting. The harvester reads user-correction rows and
routing rows from learning.db, clusters corrections by session-joined domain,
and emits a digest (human / json). It opens no PR and writes no DB column —
report-only. route-health gains two informational lines (correction rate +
unattributed count); read-only, never gates.

Throwaway DB via CLAUDE_LEARNING_DIR; rows seeded with record_learning.

Run with: python3 -m pytest scripts/tests/test_harvest_corrections.py -v
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
LIB_DIR = REPO_ROOT / "hooks" / "lib"
HARVEST_PATH = SCRIPTS_DIR / "harvest-corrections.py"
LEARNING_DB_PATH = SCRIPTS_DIR / "learning-db.py"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point learning.db at a throwaway dir and reset the init cache."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    yield {"db_dir": db_dir, "ldb": ldb}


def _load(path: Path, name: str):
    """Load a hyphen-named script as an importable module."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_correction(ldb, *, session_id, value, confidence=0.70, key=None, last_seen=None):
    """Seed one user-correction row; optionally back-date last_seen."""
    key = key or f"corr-{session_id}-{abs(hash(value)) % 100000}"
    ldb.record_learning(
        topic="user-correction",
        key=key,
        value=value,
        category="correction",
        confidence=confidence,
        source="hook:user-correction-capture",
        session_id=session_id,
    )
    if last_seen is not None:
        with ldb.get_connection() as conn:
            conn.execute(
                "UPDATE learnings SET last_seen = ? WHERE topic = ? AND key = ?",
                (last_seen, "user-correction", key),
            )
            conn.commit()


def _seed_route(ldb, *, session_id, agent, skill, last_seen=None):
    """Seed one routing row keyed agent:skill in a session."""
    key = f"{agent}:{skill}"
    ldb.record_learning(
        topic="routing",
        key=key,
        value=f"routing-decision: agent={agent} skill={skill} request: do work",
        category="effectiveness",
        source="hook:routing-decision-recorder",
        session_id=session_id,
    )
    if last_seen is not None:
        with ldb.get_connection() as conn:
            conn.execute(
                "UPDATE learnings SET last_seen = ? WHERE topic = ? AND key = ?",
                (last_seen, "routing", key),
            )
            conn.commit()


def _iso_hours_ago(hours: float) -> str:
    return (datetime.now() - timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# harvest-corrections.py — clustering + digest
# ---------------------------------------------------------------------------


def test_cluster_by_joined_domain(db_env):
    """3 corrections in s1 + a planning route in s1 -> one skill:planning cluster."""
    ldb = db_env["ldb"]
    for i in range(3):
        _seed_correction(ldb, session_id="s1", value=f"no, planning is for software {i}", key=f"c{i}")
    _seed_route(ldb, session_id="s1", agent="planning-agent", skill="planning")

    mod = _load(HARVEST_PATH, "harvest_corrections")
    digest = mod.build_digest(since_hours=168, min_confidence=0.65, limit_examples=3)

    clusters = digest["clusters"]
    assert len(clusters) == 1
    c = clusters[0]
    assert c["domain"] == "skill:planning"
    assert c["count"] == 3
    assert c["suggested_target"].endswith("planning/SKILL.md")


def test_unattributed_path(db_env):
    """A correction with no routing row in its session lands unattributed, null target."""
    ldb = db_env["ldb"]
    _seed_correction(ldb, session_id="sX", value="that is wrong", key="cx")

    mod = _load(HARVEST_PATH, "harvest_corrections")
    digest = mod.build_digest(since_hours=168, min_confidence=0.65, limit_examples=3)

    c = next(c for c in digest["clusters"] if c["domain"] == "unattributed")
    assert c["count"] == 1
    assert c["suggested_target"] is None


def test_since_hours_filter(db_env):
    """One 200h-old, one 10h-old correction; --since-hours 168 keeps only the recent."""
    ldb = db_env["ldb"]
    _seed_correction(ldb, session_id="s1", value="old correction", key="old", last_seen=_iso_hours_ago(200))
    _seed_correction(ldb, session_id="s1", value="new correction", key="new", last_seen=_iso_hours_ago(10))

    mod = _load(HARVEST_PATH, "harvest_corrections")
    digest = mod.build_digest(since_hours=168, min_confidence=0.65, limit_examples=3)

    assert digest["total_corrections"] == 1


def test_min_confidence_filter(db_env):
    """0.50 correction excluded at --min-confidence 0.65; 0.70 included."""
    ldb = db_env["ldb"]
    _seed_correction(ldb, session_id="s1", value="low conf", key="lo", confidence=0.50)
    _seed_correction(ldb, session_id="s1", value="high conf", key="hi", confidence=0.70)

    mod = _load(HARVEST_PATH, "harvest_corrections")
    digest = mod.build_digest(since_hours=168, min_confidence=0.65, limit_examples=3)

    assert digest["total_corrections"] == 1


def test_limit_examples_newest_first(db_env):
    """5 corrections in one cluster, --limit-examples 2 -> 2 snippets, newest first."""
    ldb = db_env["ldb"]
    for i in range(5):
        _seed_correction(
            ldb,
            session_id="s1",
            value=f"correction number {i}",
            key=f"c{i}",
            last_seen=_iso_hours_ago(50 - i),  # higher i => more recent
        )

    mod = _load(HARVEST_PATH, "harvest_corrections")
    digest = mod.build_digest(since_hours=168, min_confidence=0.65, limit_examples=2)

    c = digest["clusters"][0]
    assert len(c["examples"]) == 2
    assert c["examples"][0] == "correction number 4"
    assert c["examples"][1] == "correction number 3"


def test_json_shape(db_env, capsys):
    """--format json parses and carries the documented top-level + cluster keys."""
    ldb = db_env["ldb"]
    _seed_correction(ldb, session_id="s1", value="a correction", key="c1")
    _seed_route(ldb, session_id="s1", agent="planning-agent", skill="planning")

    mod = _load(HARVEST_PATH, "harvest_corrections")
    rc = mod.main(["--format", "json"])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    for key in ("generated", "window_hours", "min_confidence", "total_corrections", "clusters"):
        assert key in out
    for ckey in ("domain", "count", "suggested_target", "examples"):
        assert ckey in out["clusters"][0]


def test_empty_db(db_env, capsys):
    """No corrections: exit 0, human says no corrections, json clusters empty."""
    mod = _load(HARVEST_PATH, "harvest_corrections")

    rc = mod.main([])
    assert rc == 0
    assert "no corrections in window" in capsys.readouterr().out.lower()

    rc = mod.main(["--format", "json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["clusters"] == []
    assert out["total_corrections"] == 0


def test_agent_only_target(db_env):
    """An agent-only route (skill empty) targets agents/<agent>.md."""
    ldb = db_env["ldb"]
    _seed_correction(ldb, session_id="s2", value="agent scoping is wrong", key="ca")
    _seed_route(ldb, session_id="s2", agent="security-engineer", skill="")

    mod = _load(HARVEST_PATH, "harvest_corrections")
    digest = mod.build_digest(since_hours=168, min_confidence=0.65, limit_examples=3)

    c = next(c for c in digest["clusters"] if c["domain"].startswith("agent:"))
    assert c["suggested_target"] == "agents/security-engineer.md"


# ---------------------------------------------------------------------------
# route-health — correction-rate lines
# ---------------------------------------------------------------------------


def test_route_health_correction_rate(db_env, capsys):
    """route-health prints correction rate over routed sessions + unattributed count."""
    ldb = db_env["ldb"]
    # Routed sessions s1, s2, s3; a correction in s1 only.
    _seed_route(ldb, session_id="s1", agent="a", skill="x")
    _seed_route(ldb, session_id="s2", agent="a", skill="y")
    _seed_route(ldb, session_id="s3", agent="b", skill="z")
    _seed_correction(ldb, session_id="s1", value="you got this wrong", key="c1")

    mod = _load(LEARNING_DB_PATH, "learning_db_cli")
    import argparse

    mod.cmd_route_health(argparse.Namespace(json=False))
    out = capsys.readouterr().out
    assert "Correction rate: 1/3" in out
    assert "33%" in out
    assert "Unattributed corrections:" in out
