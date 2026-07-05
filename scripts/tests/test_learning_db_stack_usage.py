#!/usr/bin/env python3
"""Tests for the `stack-usage` / `backfill-stack-usage` subcommands in
scripts/learning-db.py.

Covers:
- stack-usage lists per-enhancement-skill rows (times stacked, last seen),
  most-frequent first, in both human and --json output.
- stack-usage with no data prints a friendly message (human) / `[]` (json).
- backfill-stack-usage imports historical stack={...} data from a synthetic
  route-events.jsonl, deduping repeated skills within one event.
- backfill-stack-usage is idempotent: a second run without --force is a no-op;
  --force re-runs (and re-counts).
- backfill-stack-usage handles a missing route-events.jsonl and malformed
  lines gracefully (never raises, always exit 0).

Run with: python3 -m pytest scripts/tests/test_learning_db_stack_usage.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

SCRIPT_PATH = str(_repo_root / "scripts" / "learning-db.py")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point learning.db (and route-events.jsonl) at a temp directory."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    import importlib

    import learning_db_v2

    importlib.reload(learning_db_v2)
    learning_db_v2.init_db()
    yield tmp_path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def _write_events(tmp_path: Path, lines: list[str]) -> None:
    (tmp_path / "route-events.jsonl").write_text("\n".join(lines) + "\n")


class TestStackUsageCommand:
    def test_no_data_human_message(self, isolated_db):
        p = _run_cli("stack-usage")
        assert p.returncode == 0
        assert "No stack usage recorded" in p.stdout

    def test_no_data_json_empty_list(self, isolated_db):
        p = _run_cli("stack-usage", "--json")
        assert p.returncode == 0
        assert json.loads(p.stdout) == []

    def test_lists_skills_by_frequency(self, isolated_db):
        _write_events(
            isolated_db,
            [
                json.dumps({"type": "decision", "stack": ["voice-validator"]}),
                json.dumps({"type": "decision", "stack": ["voice-validator", "joy-check"]}),
                json.dumps({"type": "decision", "stack": ["joy-check"]}),
            ],
        )
        assert _run_cli("backfill-stack-usage").returncode == 0
        p = _run_cli("stack-usage", "--json")
        assert p.returncode == 0
        rows = json.loads(p.stdout)
        by_skill = {r["skill"]: r for r in rows}
        assert by_skill["voice-validator"]["times_stacked"] == 2
        assert by_skill["joy-check"]["times_stacked"] == 2
        assert rows[0]["times_stacked"] >= rows[-1]["times_stacked"]  # sorted desc

        human = _run_cli("stack-usage")
        assert "voice-validator" in human.stdout
        assert "joy-check" in human.stdout


class TestBackfillStackUsage:
    def test_missing_events_file_is_noop_not_error(self, isolated_db):
        p = _run_cli("backfill-stack-usage")
        assert p.returncode == 0
        assert "nothing to backfill" in p.stdout
        assert json.loads(_run_cli("stack-usage", "--json").stdout) == []

    def test_dedupes_repeated_skill_within_one_event(self, isolated_db):
        _write_events(isolated_db, [json.dumps({"type": "decision", "stack": ["joy-check", "joy-check"]})])
        assert _run_cli("backfill-stack-usage").returncode == 0
        rows = json.loads(_run_cli("stack-usage", "--json").stdout)
        assert next(r for r in rows if r["skill"] == "joy-check")["times_stacked"] == 1

    def test_skips_non_decision_and_malformed_lines(self, isolated_db):
        _write_events(
            isolated_db,
            [
                json.dumps({"type": "outcome", "key": "a:b", "outcome": "success"}),
                "not valid json",
                json.dumps({"type": "decision", "stack": ["condense"]}),
                json.dumps({"type": "decision"}),  # no stack field
            ],
        )
        p = _run_cli("backfill-stack-usage")
        assert p.returncode == 0
        rows = json.loads(_run_cli("stack-usage", "--json").stdout)
        assert [r["skill"] for r in rows] == ["condense"]

    def test_second_run_without_force_is_noop(self, isolated_db):
        _write_events(isolated_db, [json.dumps({"type": "decision", "stack": ["condense"]})])
        _run_cli("backfill-stack-usage")
        second = _run_cli("backfill-stack-usage")
        assert second.returncode == 0
        assert "Already backfilled" in second.stdout
        rows = json.loads(_run_cli("stack-usage", "--json").stdout)
        assert next(r for r in rows if r["skill"] == "condense")["times_stacked"] == 1

    def test_force_rerun_recounts(self, isolated_db):
        _write_events(isolated_db, [json.dumps({"type": "decision", "stack": ["condense"]})])
        _run_cli("backfill-stack-usage")
        p = _run_cli("backfill-stack-usage", "--force")
        assert p.returncode == 0
        assert "Backfill complete" in p.stdout
        rows = json.loads(_run_cli("stack-usage", "--json").stdout)
        assert next(r for r in rows if r["skill"] == "condense")["times_stacked"] == 2
