"""Tests for routing outcome recording subcommands.

Covers record-routing-outcome, backfill-routing-outcomes, and route-health.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import pytest

# Ensure repo hooks/lib takes priority over ~/.claude/hooks/lib
_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")

# Import the CLI module under test
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
learning_db = importlib.import_module("learning-db")
sys.path.pop(0)

# Force-reload learning_db_v2 from the repo (not from ~/.claude/hooks/lib)
sys.path.insert(0, _repo_hooks_lib)
if "learning_db_v2" in sys.modules:
    del sys.modules["learning_db_v2"]
import learning_db_v2 as _ld2_repo

# Patch the CLI module's references to point to the repo version
for attr_name in dir(_ld2_repo):
    if hasattr(learning_db, attr_name) and not attr_name.startswith("__"):
        try:
            setattr(learning_db, attr_name, getattr(_ld2_repo, attr_name))
        except (AttributeError, TypeError):
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point learning DB to a temp directory so tests never touch real data."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)

    return db_dir


def _ns(**kwargs: object) -> argparse.Namespace:
    """Build a minimal namespace for command functions."""
    return argparse.Namespace(**kwargs)


def _seed_routing_entry(key: str, value: str = "agent: test | skill: test") -> None:
    """Seed a routing entry in the learnings table."""
    from learning_db_v2 import record_learning

    record_learning(
        topic="routing",
        key=key,
        value=value,
        category="effectiveness",
        source="test:routing",
    )


# ---------------------------------------------------------------------------
# record-routing-outcome
# ---------------------------------------------------------------------------


class TestRecordRoutingOutcome:
    """Test the record-routing-outcome subcommand."""

    def test_success_boosts_confidence(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("golang-general-engineer:go-patterns")
        args = _ns(
            agent_skill="golang-general-engineer:go-patterns",
            success=True,
            failure=False,
            reason=None,
        )
        learning_db.cmd_record_routing_outcome(args)
        output = capsys.readouterr().out

        assert "success" in output
        assert "0.5500" in output  # 0.50 + 0.05

    def test_failure_decays_confidence(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("python-general-engineer:python-quality-gate")
        args = _ns(
            agent_skill="python-general-engineer:python-quality-gate",
            success=False,
            failure=True,
            reason=None,
        )
        learning_db.cmd_record_routing_outcome(args)
        output = capsys.readouterr().out

        assert "failure" in output
        assert "0.4200" in output  # 0.50 - 0.08

    def test_reason_appended_to_value(self, isolated_db: Path) -> None:
        _seed_routing_entry("test-agent:test-skill", value="agent: test-agent")
        args = _ns(
            agent_skill="test-agent:test-skill",
            success=False,
            failure=True,
            reason="user re-routed",
        )
        learning_db.cmd_record_routing_outcome(args)

        from learning_db_v2 import get_connection, init_db

        init_db()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM learnings WHERE topic = 'routing' AND key = ?",
                ("test-agent:test-skill",),
            ).fetchone()
        assert "outcome_reason: user re-routed" in row["value"]

    def test_nonexistent_key_exits_with_error(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from learning_db_v2 import init_db

        init_db()
        args = _ns(
            agent_skill="nonexistent-agent:nonexistent-skill",
            success=True,
            failure=False,
            reason=None,
        )
        with pytest.raises(SystemExit, match="1"):
            learning_db.cmd_record_routing_outcome(args)
        output = capsys.readouterr().err

        assert "WARNING" in output
        assert "never recorded" in output


# ---------------------------------------------------------------------------
# backfill-routing-outcomes
# ---------------------------------------------------------------------------


class TestBackfillRoutingOutcomes:
    """Test the backfill-routing-outcomes subcommand."""

    def test_decays_tool_errors(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("agent-a:skill-a", value="agent: a | tool_errors=1")
        args = _ns()
        learning_db.cmd_backfill_routing_outcomes(args)
        output = capsys.readouterr().out

        assert "Decayed:   1" in output

        from learning_db_v2 import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT confidence FROM learnings WHERE topic = 'routing' AND key = ?",
                ("agent-a:skill-a",),
            ).fetchone()
        assert row["confidence"] == pytest.approx(0.42, abs=0.01)

    def test_decays_user_rerouted(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("agent-b:skill-b", value="agent: b | user_rerouted=1")
        args = _ns()
        learning_db.cmd_backfill_routing_outcomes(args)
        output = capsys.readouterr().out

        assert "Decayed:   1" in output

    def test_boosts_committed_and_pushed(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("agent-c:skill-c", value="agent: c | outcome=committed_and_pushed")
        args = _ns()
        learning_db.cmd_backfill_routing_outcomes(args)
        output = capsys.readouterr().out

        assert "Boosted:   1" in output

        from learning_db_v2 import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT confidence FROM learnings WHERE topic = 'routing' AND key = ?",
                ("agent-c:skill-c",),
            ).fetchone()
        assert row["confidence"] == pytest.approx(0.55, abs=0.01)

    def test_mixed_entries(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("e1", value="tool_errors=1")
        _seed_routing_entry("e2", value="outcome=committed_and_pushed")
        _seed_routing_entry("e3", value="agent: x | skill: y")
        _seed_routing_entry("e4", value="user_rerouted=1")

        args = _ns()
        learning_db.cmd_backfill_routing_outcomes(args)
        output = capsys.readouterr().out

        assert "Boosted:   1" in output
        assert "Decayed:   2" in output
        assert "Skipped:   0" in output
        assert "Unchanged: 1" in output

    def test_idempotent_skips_already_scored(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Running backfill twice should skip already-scored entries."""
        _seed_routing_entry("e1", value="tool_errors=1")
        _seed_routing_entry("e2", value="outcome=committed_and_pushed")

        args = _ns()
        # First run
        learning_db.cmd_backfill_routing_outcomes(args)
        capsys.readouterr()  # discard first output

        # Second run — should skip both
        learning_db.cmd_backfill_routing_outcomes(args)
        output = capsys.readouterr().out

        assert "Skipped:   2" in output
        assert "Boosted:   0" in output
        assert "Decayed:   0" in output


# ---------------------------------------------------------------------------
# route-health
# ---------------------------------------------------------------------------


class TestRouteHealth:
    """Test the route-health subcommand."""

    def test_no_entries(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from learning_db_v2 import init_db

        init_db()
        args = _ns()
        learning_db.cmd_route_health(args)
        output = capsys.readouterr().out

        assert "No routing entries found" in output

    def test_all_baseline(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        for i in range(5):
            _seed_routing_entry(f"route-{i}")

        args = _ns()
        learning_db.cmd_route_health(args)
        output = capsys.readouterr().out

        assert "0/5 entries have outcomes (0%)" in output
        assert "5 at baseline" in output
        assert "0 boosted" in output
        assert "0 decayed" in output
        assert "OPEN" in output

    def test_with_outcomes(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        for i in range(4):
            _seed_routing_entry(f"route-{i}")

        # Boost one, decay one
        from learning_db_v2 import boost_confidence, decay_confidence

        boost_confidence("routing", "route-0", delta=0.05)
        decay_confidence("routing", "route-1", delta=0.08)

        args = _ns()
        learning_db.cmd_route_health(args)
        output = capsys.readouterr().out

        assert "2/4 entries have outcomes (50%)" in output
        assert "2 at baseline" in output
        assert "1 boosted" in output
        assert "1 decayed" in output

    def test_format_contains_feedback_loop(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_routing_entry("single-route")

        args = _ns()
        learning_db.cmd_route_health(args)
        output = capsys.readouterr().out

        assert "Feedback loop:" in output
        assert "Route Health:" in output
        assert "Confidence:" in output
