#!/usr/bin/env python3
"""Tests for the learning telemetry envelope (ADR: learning-telemetry-envelope).

Covers the ADR Validation Requirements:
1. Migration on an existing v4 DB: bumps to v5, adds telemetry_runs, keeps old rows.
2. Insert with envelope: record_telemetry_run writes one row, NULL best-effort fields.
3. End-to-end capture: the recorder writes one telemetry_runs row on a /do-marked
   dispatch (non-NULL git_sha, session_id, run_id); zero rows on a no-marker event.
4. Time-series correctness: route-stats --by week|day groups rows by period.
5. Delta correctness: route-delta --from A --to B reports the hand-computed delta.
6. NULL tolerance: route-delta --metric tokens reports n=0, never counts NULL as 0.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_telemetry_envelope.py -v
"""

import importlib.util
import json
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
REPO_ROOT = HOOKS_DIR.parent
A_PATH = HOOKS_DIR / "routing-decision-recorder.py"
CLI_PATH = REPO_ROOT / "scripts" / "learning-db.py"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB at a throwaway location and force fresh init."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    yield {"db_dir": db_dir, "db_path": ldb.get_db_path()}


def _ldb():
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    return ldb


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _run_cli(env_dir, *cli_args):
    """Run scripts/learning-db.py as a subprocess against the throwaway DB."""
    import os

    env = dict(os.environ)
    env["CLAUDE_LEARNING_DIR"] = str(env_dir)
    # Force UTF-8 stdout so the CLI's box-drawing chars don't crash on a Windows
    # cp1252 console (CI runs UTF-8 Linux; this keeps the test cross-platform).
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *cli_args],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# 1. Migration on an existing DB
# ---------------------------------------------------------------------------


def test_migration_on_existing_v4_db_preserves_rows(tmp_path, monkeypatch):
    """Seed a v4 DB with a learnings row, then init: version 5, table present,
    pre-existing rows intact, zero rows lost."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    ldb = _ldb()
    monkeypatch.setattr(ldb, "_initialized", False, raising=False)

    # Build a v4 DB by hand: schema + user_version=4, with a real learnings row.
    db_path = db_dir / "learning.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(ldb._SCHEMA)
    conn.execute("PRAGMA user_version = 4")
    conn.execute(
        "INSERT INTO learnings (topic, key, value, category, source) VALUES (?,?,?,?,?)",
        ("routing", "a:b", "seed row", "effectiveness", "test"),
    )
    conn.commit()
    conn.close()

    # init_db runs migrations.
    ldb.init_db()

    version = _rows(db_path, "PRAGMA user_version")[0]["user_version"]
    assert version == 5

    tables = {r["name"] for r in _rows(db_path, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "telemetry_runs" in tables

    # Pre-existing learnings row survived.
    seeds = _rows(db_path, "SELECT value FROM learnings WHERE topic='routing' AND key='a:b'")
    assert len(seeds) == 1
    assert seeds[0]["value"] == "seed row"

    # New table starts empty (no backfill).
    assert _rows(db_path, "SELECT COUNT(*) AS n FROM telemetry_runs")[0]["n"] == 0


def test_schema_version_constant_is_5():
    ldb = _ldb()
    assert ldb._CURRENT_SCHEMA_VERSION == 5


# ---------------------------------------------------------------------------
# 2. Insert with envelope + NULL tolerance of best-effort fields
# ---------------------------------------------------------------------------


def test_record_telemetry_run_inserts_one_row_with_nulls(db_env):
    ldb = _ldb()
    rid = str(uuid.uuid4())
    ldb.record_telemetry_run(
        topic="routing",
        key="x:y",
        run_id=rid,
        source="test",
        git_sha="abc1234",
        session_id="s1",
    )
    rows = _rows(db_env["db_path"], "SELECT * FROM telemetry_runs")
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == rid
    assert row["git_sha"] == "abc1234"
    assert row["session_id"] == "s1"
    assert row["topic"] == "routing"
    assert row["key"] == "x:y"
    # Best-effort fields default to NULL, not 0.
    assert row["token_count"] is None
    assert row["wall_clock_ms"] is None
    assert row["model_id"] is None
    assert row["skill_version"] is None
    # tool_errors defaults to 0 (False).
    assert row["tool_errors"] == 0
    assert row["recorded_at"] is not None


def test_record_telemetry_run_is_append_only(db_env):
    """Same topic+key recorded twice writes two rows (never upserts)."""
    ldb = _ldb()
    for _ in range(2):
        ldb.record_telemetry_run(topic="routing", key="x:y", run_id=str(uuid.uuid4()), source="test")
    assert _rows(db_env["db_path"], "SELECT COUNT(*) AS n FROM telemetry_runs")[0]["n"] == 2


def test_record_telemetry_run_stores_tool_errors_flag(db_env):
    ldb = _ldb()
    ldb.record_telemetry_run(topic="routing", key="x:y", run_id=str(uuid.uuid4()), source="test", tool_errors=True)
    rows = _rows(db_env["db_path"], "SELECT tool_errors FROM telemetry_runs")
    assert rows[0]["tool_errors"] == 1


# ---------------------------------------------------------------------------
# 3. End-to-end capture from the recorder hook
# ---------------------------------------------------------------------------


def _agent_event(skill="go-patterns", *, marker=True, is_error=False, session="cap1"):
    prefix = f"[do-route] agent=python-general-engineer skill={skill or '-'} complexity=Medium\n" if marker else ""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": session,
        "tool_input": {
            "subagent_type": "python-general-engineer",
            "description": "do work",
            "prompt": prefix + "do work",
        },
        "tool_result": {"output": "ok", "is_error": is_error},
    }


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


def test_recorder_writes_one_envelope_row_on_marked_dispatch(db_env, tmp_path, monkeypatch):
    a = _load(A_PATH, "tel_cap1")
    monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
    monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
    # Redirect telemetry git-sha state cache into tmp so the test never reads ~/.
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")

    event = _agent_event(session="cap-marked")
    with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
        a.main()

    rows = _rows(db_env["db_path"], "SELECT * FROM telemetry_runs")
    assert len(rows) == 1
    row = rows[0]
    assert row["topic"] == "routing"
    assert row["key"] == "python-general-engineer:go-patterns"
    assert row["session_id"] == "cap-marked"
    assert row["run_id"]  # non-empty UUID
    assert row["git_sha"]  # always derivable in a git repo
    assert row["source"] == "hook:routing-decision-recorder"


def test_recorder_writes_zero_envelope_rows_without_marker(db_env, tmp_path, monkeypatch):
    a = _load(A_PATH, "tel_cap2")
    monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
    monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")

    event = _agent_event(marker=False, session="cap-nomarker")
    with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
        a.main()

    assert _rows(db_env["db_path"], "SELECT COUNT(*) AS n FROM telemetry_runs")[0]["n"] == 0


def test_recorder_envelope_records_tool_error(db_env, tmp_path, monkeypatch):
    a = _load(A_PATH, "tel_cap3")
    monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
    monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")

    event = _agent_event(is_error=True, session="cap-err")
    with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
        a.main()
    rows = _rows(db_env["db_path"], "SELECT tool_errors FROM telemetry_runs")
    assert len(rows) == 1
    assert rows[0]["tool_errors"] == 1


# ---------------------------------------------------------------------------
# telemetry_capture unit tests
# ---------------------------------------------------------------------------


def test_model_id_from_reads_event_then_env(monkeypatch):
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    assert tc.model_id_from({"model": "claude-x"}) == "claude-x"
    assert tc.model_id_from({"tool_input": {"model": "claude-y"}}) == "claude-y"
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    assert tc.model_id_from({}) is None
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-env")
    assert tc.model_id_from({}) == "claude-env"


def test_token_and_wall_clock_default_none():
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    assert tc.token_count_from({}) is None
    assert tc.wall_clock_ms_from({}) is None


def test_token_count_from_reads_usage_when_present():
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    assert tc.token_count_from({"usage": {"total_tokens": 1234}}) == 1234


def test_git_sha_cached_writes_and_reads_state(tmp_path, monkeypatch):
    sys.path.insert(0, str(LIB_DIR))
    import telemetry_capture as tc

    monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "tel")
    sha1 = tc.git_sha_cached("sess-a")
    # The state file now holds the SHA; a second call reads it (no recompute).
    state = tmp_path / "tel" / "sess-a.json"
    assert state.exists()
    sha2 = tc.git_sha_cached("sess-a")
    assert sha1 == sha2


# ---------------------------------------------------------------------------
# 4. Time-series correctness: route-stats --by week|day
# ---------------------------------------------------------------------------


def _seed_run(db_path, *, recorded_at, git_sha="sha", tool_errors=0, key="a:b", token_count=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO telemetry_runs (run_id, topic, key, git_sha, tool_errors, token_count, source, recorded_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "routing", key, git_sha, tool_errors, token_count, "test", recorded_at),
    )
    conn.commit()
    conn.close()


def test_route_stats_by_week_groups_two_periods(db_env):
    p = db_env["db_path"]
    # Week 1: 2 runs, 1 error. Week 2: 3 runs, 0 errors. (Dates a fortnight apart.)
    _seed_run(p, recorded_at="2026-01-05 10:00:00", tool_errors=1)
    _seed_run(p, recorded_at="2026-01-06 10:00:00", tool_errors=0)
    _seed_run(p, recorded_at="2026-01-19 10:00:00", tool_errors=0)
    _seed_run(p, recorded_at="2026-01-20 10:00:00", tool_errors=0)
    _seed_run(p, recorded_at="2026-01-21 10:00:00", tool_errors=0)

    res = _run_cli(db_env["db_dir"], "route-stats", "--by", "week", "--json")
    assert res.returncode == 0, res.stderr
    periods = json.loads(res.stdout)
    by_period = {row["period"]: row for row in periods}
    assert len(by_period) == 2
    week1 = by_period["2026-W01"]
    assert week1["runs"] == 2
    assert week1["errors"] == 1


def test_route_stats_by_day_groups_per_calendar_day(db_env):
    p = db_env["db_path"]
    _seed_run(p, recorded_at="2026-02-01 09:00:00", tool_errors=1)
    _seed_run(p, recorded_at="2026-02-01 11:00:00", tool_errors=1)
    _seed_run(p, recorded_at="2026-02-02 09:00:00", tool_errors=0)

    res = _run_cli(db_env["db_dir"], "route-stats", "--by", "day", "--json")
    assert res.returncode == 0, res.stderr
    by_day = {row["period"]: row for row in json.loads(res.stdout)}
    assert by_day["2026-02-01"]["runs"] == 2
    assert by_day["2026-02-01"]["errors"] == 2
    assert by_day["2026-02-02"]["runs"] == 1


def test_route_stats_existing_dimensions_unaffected(db_env):
    # The old --by agent path must still work (additive change).
    ldb = _ldb()
    ldb.record_learning(
        topic="routing",
        key="python-general-engineer:go-patterns",
        value="routing-decision: agent=python-general-engineer skill=go-patterns tool_errors=0",
        category="effectiveness",
        source="hook:routing-decision-recorder",
    )
    res = _run_cli(db_env["db_dir"], "route-stats", "--by", "agent")
    assert res.returncode == 0, res.stderr
    assert "python-general-engineer" in res.stdout


def test_route_stats_week_empty_table_message(db_env):
    res = _run_cli(db_env["db_dir"], "route-stats", "--by", "week")
    assert res.returncode == 0, res.stderr
    assert "No telemetry runs yet" in res.stdout


# ---------------------------------------------------------------------------
# 5. Delta correctness: route-delta --from A --to B
# ---------------------------------------------------------------------------


def test_route_delta_error_rate_matches_hand_computed(db_env):
    p = db_env["db_path"]
    # Cohort A (sha aaa): 4 runs, 2 errors => 50.0%.
    for err in (1, 1, 0, 0):
        _seed_run(p, recorded_at="2026-03-01 10:00:00", git_sha="aaaaaaa", tool_errors=err)
    # Cohort B (sha bbb): 4 runs, 1 error => 25.0%.
    for err in (1, 0, 0, 0):
        _seed_run(p, recorded_at="2026-03-02 10:00:00", git_sha="bbbbbbb", tool_errors=err)

    res = _run_cli(db_env["db_dir"], "route-delta", "--from", "aaaaaaa", "--to", "bbbbbbb", "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["from"]["runs"] == 4
    assert data["from"]["errors"] == 2
    assert data["from"]["error_pct"] == 50.0
    assert data["to"]["runs"] == 4
    assert data["to"]["errors"] == 1
    assert data["to"]["error_pct"] == 25.0
    # Delta = to - from = 25.0 - 50.0 = -25.0 points (improved).
    assert data["delta_pts"] == -25.0


def test_route_delta_prefix_matches_sha(db_env):
    p = db_env["db_path"]
    _seed_run(p, recorded_at="2026-03-01 10:00:00", git_sha="deadbeefcafe", tool_errors=0)
    _seed_run(p, recorded_at="2026-03-02 10:00:00", git_sha="feedface1234", tool_errors=1)
    # Use 7-char prefixes; both must resolve to the full SHA cohorts.
    res = _run_cli(db_env["db_dir"], "route-delta", "--from", "deadbee", "--to", "feedfac", "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["from"]["runs"] == 1
    assert data["to"]["runs"] == 1


def test_route_delta_key_scopes_to_one_route(db_env):
    p = db_env["db_path"]
    _seed_run(p, recorded_at="2026-03-01 10:00:00", git_sha="aaa1111", tool_errors=0, key="agentA:skill")
    _seed_run(p, recorded_at="2026-03-01 10:00:00", git_sha="aaa1111", tool_errors=1, key="agentB:skill")
    _seed_run(p, recorded_at="2026-03-02 10:00:00", git_sha="bbb2222", tool_errors=0, key="agentA:skill")

    res = _run_cli(
        db_env["db_dir"], "route-delta", "--from", "aaa1111", "--to", "bbb2222", "--key", "agentA:skill", "--json"
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["from"]["runs"] == 1  # only agentA, agentB excluded
    assert data["to"]["runs"] == 1


# ---------------------------------------------------------------------------
# 6. NULL tolerance: route-delta --metric tokens reports n, never counts NULL as 0
# ---------------------------------------------------------------------------


def test_route_delta_tokens_metric_reports_nonnull_n(db_env):
    p = db_env["db_path"]
    # Cohort A: 2 runs, both token_count NULL => non-null n=0, avg None.
    _seed_run(p, recorded_at="2026-04-01 10:00:00", git_sha="aaa3333", token_count=None)
    _seed_run(p, recorded_at="2026-04-01 11:00:00", git_sha="aaa3333", token_count=None)
    # Cohort B: 2 runs, one has token_count=100, one NULL => non-null n=1, avg 100.
    _seed_run(p, recorded_at="2026-04-02 10:00:00", git_sha="bbb4444", token_count=100)
    _seed_run(p, recorded_at="2026-04-02 11:00:00", git_sha="bbb4444", token_count=None)

    res = _run_cli(
        db_env["db_dir"], "route-delta", "--from", "aaa3333", "--to", "bbb4444", "--metric", "tokens", "--json"
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    # Cohort A: no non-null tokens => n=0, avg None (NOT 0).
    assert data["from"]["n"] == 0
    assert data["from"]["avg_tokens"] is None
    # Cohort B: one non-null token => n=1, avg 100.
    assert data["to"]["n"] == 1
    assert data["to"]["avg_tokens"] == 100.0


def test_route_delta_low_sample_warns_but_succeeds(db_env):
    p = db_env["db_path"]
    # Each cohort has 1 run (< MIN_N default 5) => low-sample WARNING, still exit 0.
    _seed_run(p, recorded_at="2026-05-01 10:00:00", git_sha="aaa5555", tool_errors=0)
    _seed_run(p, recorded_at="2026-05-02 10:00:00", git_sha="bbb6666", tool_errors=1)
    res = _run_cli(db_env["db_dir"], "route-delta", "--from", "aaa5555", "--to", "bbb6666")
    assert res.returncode == 0, res.stderr
    assert "WARNING" in res.stdout or "low" in res.stdout.lower()
