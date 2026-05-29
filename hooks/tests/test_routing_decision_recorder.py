#!/usr/bin/env python3
"""Tests for the routing-decision-recorder (A) and routing-outcome-recorder (B) hooks.

Covers:
- A records the expected `routing` decision row from a synthetic PostToolUse:Agent event.
- A discovers the skill from the dispatch prompt; falls back to agent-only key.
- A records a rightsizing row when the banner is present (C), silent otherwise.
- A is idempotent: the same dispatch is recorded once.
- B records success (boost) / failure (decay) from drained pending outcomes.
- B NEVER crashes when the decision record is absent.
- Both hooks exit 0 on empty / malformed input.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR and a per-session bridge
file under tmp_path — never the real DB.

Run with: python3 -m pytest hooks/tests/test_routing_decision_recorder.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
A_PATH = HOOKS_DIR / "routing-decision-recorder.py"
B_PATH = HOOKS_DIR / "routing-outcome-recorder.py"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB and the bridge state dir at a throwaway location."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    # Force a fresh DB init against this tmp dir: learning_db_v2 caches
    # _initialized as a module global across in-process tests.
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    # Redirect the bridge state dir away from /tmp into tmp_path.
    import routing_outcome_state as ros

    monkeypatch.setattr(ros, "_STATE_DIR", tmp_path / "state")
    yield {"db_dir": db_dir, "state": tmp_path / "state"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


def _run_hook(path: Path, event: dict) -> subprocess.CompletedProcess:
    """Run a hook as a subprocess feeding the event on stdin. Returns the result."""
    return subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


def _agent_event(skill_prompt="", description="do work", output="ok", is_error=False, session="s1"):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": session,
        "tool_input": {
            "subagent_type": "python-general-engineer",
            "description": description,
            "prompt": skill_prompt,
        },
        "tool_result": {"output": output, "is_error": is_error},
    }


def _query_routing(db_env):
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    return ldb.query_learnings(
        topic="routing",
        category="effectiveness",
        exclude_graduated=False,
        exclude_test_sources=False,
        limit=1000,
    )


# ---------------------------------------------------------------------------
# A — routing-decision-recorder
# ---------------------------------------------------------------------------


class TestDecisionRecorder:
    def test_records_decision_row_with_skill(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a1")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "dispatch_seen", lambda *_a, **_k: False)
        monkeypatch.setattr(a, "mark_dispatch_seen", lambda *_a, **_k: None)
        event = _agent_event(skill_prompt='Skill("test-driven-development")\nWrite tests.')
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        rows = _query_routing(db_env)
        keys = {r["key"] for r in rows}
        assert "python-general-engineer:test-driven-development" in keys
        row = next(r for r in rows if r["key"] == "python-general-engineer:test-driven-development")
        assert "tool_errors=0" in row["value"]

    def test_agent_only_key_when_no_skill(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a2")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "dispatch_seen", lambda *_a, **_k: False)
        monkeypatch.setattr(a, "mark_dispatch_seen", lambda *_a, **_k: None)
        event = _agent_event(skill_prompt="Just do the thing, no skill named.")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "python-general-engineer:" in keys

    def test_error_flag_when_result_errored(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a3")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "dispatch_seen", lambda *_a, **_k: False)
        monkeypatch.setattr(a, "mark_dispatch_seen", lambda *_a, **_k: None)
        event = _agent_event(
            skill_prompt='Skill("go-patterns")',
            output="fatal: permission denied",
            is_error=True,
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:go-patterns")
        assert "tool_errors=1" in row["value"]

    def test_rightsizing_row_recorded(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a4")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "dispatch_seen", lambda *_a, **_k: False)
        monkeypatch.setattr(a, "mark_dispatch_seen", lambda *_a, **_k: None)
        event = _agent_event(
            skill_prompt='Skill("systematic-code-review")',
            output="done. rightsizing: tier=3 files=15 packages=4 agents_dispatched=17",
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "rightsizing:tier3" in keys

    def test_no_rightsizing_row_when_banner_absent(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a5")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "dispatch_seen", lambda *_a, **_k: False)
        monkeypatch.setattr(a, "mark_dispatch_seen", lambda *_a, **_k: None)
        event = _agent_event(skill_prompt='Skill("go-patterns")', output="plain output")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert not any(k.startswith("rightsizing:") for k in keys)

    def test_idempotent_same_dispatch_recorded_once(self, db_env):
        # Use the real bridge state (redirected to tmp) so dedup engages.
        a = _load(A_PATH, "rdr_a6")
        event = _agent_event(skill_prompt='Skill("go-patterns")', session="dup-session")
        for _ in range(3):
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:go-patterns")
        assert row["observation_count"] == 1

    def test_exit_zero_on_empty_and_malformed(self, db_env):
        assert _run_hook(A_PATH, {}).returncode == 0
        p = subprocess.run([sys.executable, str(A_PATH)], input="not json", capture_output=True, text=True)
        assert p.returncode == 0
        assert subprocess.run([sys.executable, str(A_PATH)], input="", capture_output=True, text=True).returncode == 0

    def test_non_agent_tool_ignored(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a7")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "dispatch_seen", lambda *_a, **_k: False)
        monkeypatch.setattr(a, "mark_dispatch_seen", lambda *_a, **_k: None)
        event = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _query_routing(db_env) == []


# ---------------------------------------------------------------------------
# B — routing-outcome-recorder
# ---------------------------------------------------------------------------


class TestOutcomeRecorder:
    def _seed_decision(self, key="python-general-engineer:go-patterns"):
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=0 user_rerouted=0",
            category="effectiveness",
            source="test",
        )
        return key

    def test_success_boosts_confidence(self, db_env, monkeypatch):
        key = self._seed_decision()
        b = _load(B_PATH, "ror_b1")
        monkeypatch.setattr(b, "drain_pending_outcomes", lambda _sid: [{"key": key, "errors": False}])
        before = next(r for r in _query_routing(db_env) if r["key"] == key)["confidence"]
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        after_row = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after_row["confidence"] > before
        assert after_row["success_count"] == 1

    def test_failure_decays_confidence(self, db_env, monkeypatch):
        key = self._seed_decision("python-general-engineer:debug")
        b = _load(B_PATH, "ror_b2")
        monkeypatch.setattr(b, "drain_pending_outcomes", lambda _sid: [{"key": key, "errors": True}])
        before = next(r for r in _query_routing(db_env) if r["key"] == key)["confidence"]
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        after_row = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after_row["confidence"] < before
        assert after_row["failure_count"] == 1

    def test_never_crashes_when_decision_record_absent(self, db_env, monkeypatch):
        # No decision row seeded — boost/decay return 0.0, hook must skip cleanly.
        b = _load(B_PATH, "ror_b3")
        monkeypatch.setattr(
            b, "drain_pending_outcomes", lambda _sid: [{"key": "ghost-agent:ghost-skill", "errors": False}]
        )
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit") as ex, patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        # No row created, no exception raised.
        assert all(r["key"] != "ghost-agent:ghost-skill" for r in _query_routing(db_env))
        ex.assert_called_with(0)

    def test_exit_zero_on_empty_and_malformed(self, db_env):
        assert _run_hook(B_PATH, {}).returncode == 0
        assert (
            subprocess.run([sys.executable, str(B_PATH)], input="not json", capture_output=True, text=True).returncode
            == 0
        )
        assert subprocess.run([sys.executable, str(B_PATH)], input="", capture_output=True, text=True).returncode == 0


# ---------------------------------------------------------------------------
# A + B integration: route-health closes the loop
# ---------------------------------------------------------------------------


class TestEndToEndLoop:
    def test_decision_then_outcome_closes_loop(self, db_env):
        # Real bridge (tmp-redirected): A writes decision + pending; B drains and scores.
        a = _load(A_PATH, "rdr_e1")
        b = _load(B_PATH, "ror_e1")
        event_a = _agent_event(skill_prompt='Skill("go-patterns")', session="loop-1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_a)):
            a.main()
        event_b = {"hook_event_name": "SubagentStop", "session_id": "loop-1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_b)):
            b.main()
        rows = _query_routing(db_env)
        decision = next(r for r in rows if r["key"] == "python-general-engineer:go-patterns")
        # Decision row exists AND has an outcome (success_count incremented) => loop closed.
        assert decision["success_count"] == 1
