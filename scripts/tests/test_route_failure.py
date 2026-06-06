"""Tests for the route-failure subcommand (orchestrator-reported route failures).

ADR orchestrator-reported-route-failures: the /do router reports routing
failures it observes. Routing-relevant failures decay the pair's weight row
(the finalizer's decay path) and append a reasoned failure event. Not-relevant
failures log an event only, never decay. One failure per dispatch key.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")

sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
learning_db = importlib.import_module("learning-db")
sys.path.pop(0)

sys.path.insert(0, _repo_hooks_lib)
if "learning_db_v2" in sys.modules:
    del sys.modules["learning_db_v2"]
import learning_db_v2 as _ld2_repo

for attr_name in dir(_ld2_repo):
    if hasattr(learning_db, attr_name) and not attr_name.startswith("__"):
        try:
            setattr(learning_db, attr_name, getattr(_ld2_repo, attr_name))
        except (AttributeError, TypeError):
            pass


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the learning DB and route-events log at a temp dir."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    return db_dir


def _ns(**kwargs: object) -> argparse.Namespace:
    base = {
        "agent_skill": "agent-x:skill-x",
        "reason": "re-route after unusable output",
        "routing_relevant": "yes",
        "session": None,
        "marker": None,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def _seed(key: str) -> None:
    from learning_db_v2 import record_learning

    record_learning(
        topic="routing",
        key=key,
        value="agent: x | skill: x",
        category="effectiveness",
        source="test:routing",
    )


def _confidence(key: str) -> float | None:
    from learning_db_v2 import get_connection, init_db

    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence FROM learnings WHERE topic = 'routing' AND key = ?",
            (key,),
        ).fetchone()
    return None if row is None else float(row["confidence"])


def _events(db_dir: Path) -> list[dict]:
    path = db_dir / "route-events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TestRoutingRelevant:
    def test_decays_weight_row(self, isolated_db: Path) -> None:
        _seed("agent-x:skill-x")
        learning_db.cmd_route_failure(_ns(routing_relevant="yes"))
        # finalizer decay path: 0.50 - 0.08
        assert _confidence("agent-x:skill-x") == pytest.approx(0.42, abs=0.001)

    def test_appends_failure_event_with_reason(self, isolated_db: Path) -> None:
        _seed("agent-x:skill-x")
        learning_db.cmd_route_failure(_ns(reason="lazy-completion re-dispatch", routing_relevant="yes"))
        events = _events(isolated_db)
        outcome = [e for e in events if e.get("type") == "outcome"]
        assert len(outcome) == 1
        assert outcome[0]["outcome"] == "failure"
        assert outcome[0]["key"] == "agent-x:skill-x"
        assert outcome[0]["reason"] == "lazy-completion re-dispatch"


class TestNotRelevant:
    def test_no_decay(self, isolated_db: Path) -> None:
        _seed("agent-x:skill-x")
        learning_db.cmd_route_failure(_ns(routing_relevant="no"))
        # weight row unchanged
        assert _confidence("agent-x:skill-x") == pytest.approx(0.50, abs=0.001)

    def test_event_still_written(self, isolated_db: Path) -> None:
        _seed("agent-x:skill-x")
        learning_db.cmd_route_failure(_ns(routing_relevant="no", reason="bad output, right route"))
        outcome = [e for e in _events(isolated_db) if e.get("type") == "outcome"]
        assert len(outcome) == 1
        assert outcome[0]["reason"] == "bad output, right route"


class TestIdempotence:
    def test_duplicate_key_is_noop(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed("agent-x:skill-x")
        args1 = _ns(session="s1", marker="m1", routing_relevant="yes")
        learning_db.cmd_route_failure(args1)
        after_first = _confidence("agent-x:skill-x")

        args2 = _ns(session="s1", marker="m1", routing_relevant="yes")
        learning_db.cmd_route_failure(args2)
        out = capsys.readouterr().out

        # second run decays nothing and writes no second event
        assert _confidence("agent-x:skill-x") == pytest.approx(after_first, abs=0.001)
        assert "duplicate" in out.lower()
        assert len([e for e in _events(isolated_db) if e.get("type") == "outcome"]) == 1

    def test_different_marker_not_deduped(self, isolated_db: Path) -> None:
        _seed("agent-x:skill-x")
        learning_db.cmd_route_failure(_ns(session="s1", marker="m1", routing_relevant="yes"))
        learning_db.cmd_route_failure(_ns(session="s1", marker="m2", routing_relevant="yes"))
        # two distinct dispatches => two decays: 0.50 - 0.08 - 0.08
        assert _confidence("agent-x:skill-x") == pytest.approx(0.34, abs=0.001)


class TestExitCodes:
    def test_duplicate_exits_zero(self, isolated_db: Path) -> None:
        _seed("agent-x:skill-x")
        learning_db.cmd_route_failure(_ns(session="s1", marker="m1"))
        # duplicate run must not raise SystemExit (exit 0)
        learning_db.cmd_route_failure(_ns(session="s1", marker="m1"))

    def test_malformed_pair_exits_nonzero(self, isolated_db: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            learning_db.cmd_route_failure(_ns(agent_skill="no-colon-here"))
        assert exc.value.code != 0
