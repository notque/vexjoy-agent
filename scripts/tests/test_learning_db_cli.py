#!/usr/bin/env python3
"""Tests for scripts/learning-db.py read-side subcommands.

Covers `handoff-report`:
- Empty table prints "no scored dispatches yet" and exits 0.
- Six scored rows produce the 0-7 histogram with the right counts, the
  prompt_chars median/p25, the underspecified rate per score, and the top
  spec_missing strings.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR. Never the real DB.

Run with: python3 -m pytest scripts/tests/test_learning_db_cli.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "scripts" / "learning-db.py"
LIB_DIR = REPO_ROOT / "hooks" / "lib"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB at a throwaway location and init it there."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return db_dir


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )


# (spec_score, spec_missing, prompt_chars, outcome_basis)
SIX_ROWS = (
    (7, "", 9000, None),
    (7, "", 8000, None),
    (3, "Request (verbatim),Decisions,Prior results,## Repo state", 3000, "route_fit:underspecified"),
    (3, "Request (verbatim),Decisions,Prior results,## Repo state", 3500, None),
    (
        0,
        "Request (verbatim),Intent,Acceptance criteria,Relevant file locations,Decisions,Prior results,## Repo state",
        400,
        "route_fit:underspecified",
    ),
    (5, "Request (verbatim),Prior results", 6000, None),
)


def _seed(rows) -> None:
    import learning_db_v2 as ldb

    for i, (score, missing, chars, basis) in enumerate(rows):
        ldb.record_evidence_route_decision(
            session_id="s1",
            agent="python-general-engineer",
            skill="test-driven-development",
            decision_id=f"s1:{i}",
            outcome="failure" if basis else None,
            outcome_basis=basis,
            spec_score=score,
            spec_missing=missing,
            prompt_chars=chars,
        )


class TestHandoffReport:
    def test_empty_table(self, db_env):
        result = _run_cli("handoff-report")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "no scored dispatches yet"

    def test_unscored_rows_count_as_empty(self, db_env):
        # A pre-migration or non-/do row has NULL spec_score and is not scored.
        import learning_db_v2 as ldb

        ldb.record_evidence_route_decision(session_id="s1", agent="claude", skill=None)
        result = _run_cli("handoff-report")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "no scored dispatches yet"

    def test_six_rows_histogram(self, db_env):
        _seed(SIX_ROWS)
        result = _run_cli("handoff-report", "--json")
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["scored"] == 6
        assert report["first"] and report["last"]
        assert report["histogram"] == {"0": 1, "1": 0, "2": 0, "3": 2, "4": 0, "5": 1, "6": 0, "7": 2}
        assert report["prompt_chars_median"] == 3500
        assert report["prompt_chars_p25"] == 3000
        by_score = report["underspecified_by_score"]
        assert by_score["0"] == {"n": 1, "underspecified": 1, "rate_pct": 100.0}
        assert by_score["3"] == {"n": 2, "underspecified": 1, "rate_pct": 50.0}
        assert by_score["7"] == {"n": 2, "underspecified": 0, "rate_pct": 0.0}
        top = report["top_missing"]
        assert top[0] == {"spec_missing": "", "count": 2}
        assert top[1] == {
            "spec_missing": "Request (verbatim),Decisions,Prior results,## Repo state",
            "count": 2,
        }
        assert len(top) == 4

    def test_six_rows_text_output(self, db_env):
        _seed(SIX_ROWS)
        result = _run_cli("handoff-report")
        assert result.returncode == 0, result.stderr
        out = result.stdout
        assert "Scored dispatches: 6 (" in out
        assert "  7  ##                   2" in out
        assert "  3  ##                   2" in out
        assert "  0  #                    1" in out
        assert "  1                       0" in out
        assert "prompt_chars: median 3500, p25 3000" in out
        assert "  3  1/2 (50.0%)" in out
        assert "   2  (none missing)" in out
        # Read-only: no write left behind for the seeded rows.
        import sqlite3

        import learning_db_v2 as ldb

        conn = sqlite3.connect(ldb.get_db_path())
        try:
            assert conn.execute("SELECT COUNT(*) FROM evidence_route_decisions").fetchone()[0] == 6
        finally:
            conn.close()


class TestPruneCommand:
    def test_prune_deletes_old_ancillary_rows_and_preserves_fresh(self, db_env):
        import sqlite3

        import learning_db_v2 as ldb

        conn = sqlite3.connect(ldb.get_db_path())
        try:
            conn.execute(
                "INSERT INTO jev_calls (ts, script, ok) VALUES ('2020-01-01T00:00:00+00:00', 'jev-route.py', 1)"
            )
            conn.execute("INSERT INTO jev_calls (ts, script, ok) VALUES (datetime('now'), 'jev-route.py', 1)")
            conn.execute(
                "INSERT INTO telemetry_runs (run_id, topic, key, recorded_at, source)"
                " VALUES ('old-run', 't', 'k', '2020-01-01 00:00:00', 'hook')"
            )
            conn.execute(
                "INSERT INTO telemetry_runs (run_id, topic, key, recorded_at, source)"
                " VALUES ('new-run', 't', 'k', datetime('now'), 'hook')"
            )
            conn.execute(
                "INSERT INTO evidence_route_decisions (decision_id, session_id, route_key, agent, created_at, updated_at)"
                " VALUES ('old-dec', 's1', 'k', 'general-purpose', '2020-01-01 00:00:00', '2020-01-01 00:00:00')"
            )
            conn.execute(
                "INSERT INTO evidence_route_decisions (decision_id, session_id, route_key, agent, created_at, updated_at)"
                " VALUES ('new-dec', 's1', 'k', 'general-purpose', datetime('now'), datetime('now'))"
            )
            conn.commit()
        finally:
            conn.close()

        result = _run_cli("prune", "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["pruned"]["jev_calls"] == 1
        assert payload["pruned"]["telemetry_runs"] == 1
        assert payload["pruned"]["evidence_route_decisions"] == 1
        assert payload["total"] >= 3

        conn = sqlite3.connect(ldb.get_db_path())
        try:
            assert conn.execute("SELECT COUNT(*) FROM jev_calls").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM telemetry_runs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM evidence_route_decisions").fetchone()[0] == 1
        finally:
            conn.close()
