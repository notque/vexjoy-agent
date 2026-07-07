#!/usr/bin/env python3
"""Tests for the agent evidence read model in learning_db_v2."""

import importlib
import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))


@pytest.fixture(autouse=True)
def isolated_learning_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    import learning_db_v2

    importlib.reload(learning_db_v2)
    learning_db_v2.init_db()
    yield learning_db_v2


def test_records_and_queries_evidence_events(isolated_learning_db):
    ldb = isolated_learning_db

    first = ldb.record_evidence_event(
        event_type="skill_invocation",
        source="test",
        session_id="s1",
        project_path="/repo",
        skill="test-driven-development",
        action="invoke",
        target="hooks/lib/learning_db_v2.py",
        success=True,
        metadata={"reason": "red-green-refactor"},
    )
    ldb.record_evidence_event(
        event_type="tool_failure",
        source="test",
        session_id="s1",
        project_path="/repo",
        tool_name="pytest",
        action="run",
        target="hooks/tests/test_agent_evidence.py",
        success=False,
        error="assertion failed",
    )

    assert first["event_type"] == "skill_invocation"
    rows = ldb.list_evidence_events(session_id="s1", limit=10)
    assert [row["event_type"] for row in rows] == ["tool_failure", "skill_invocation"]
    assert rows[1]["metadata"]["reason"] == "red-green-refactor"
    assert rows[1]["success"] is True

    failures = ldb.get_evidence_failures(limit=10)
    assert len(failures) == 1
    assert failures[0]["tool_name"] == "pytest"
    assert failures[0]["success"] is False

    history = ldb.get_evidence_file_history("hooks/lib/learning_db_v2.py", limit=10)
    assert [row["skill"] for row in history] == ["test-driven-development"]


def test_records_route_decisions_and_context(isolated_learning_db):
    ldb = isolated_learning_db

    ldb.record_evidence_route_decision(
        session_id="s1",
        agent="python-general-engineer",
        skill="test-driven-development",
        complexity="Medium",
        model="gpt-5-codex",
        request_snippet="Add a focused regression test.",
        stack=["objective-loop", "verification-before-completion"],
        health=0.82,
        n=5,
        failure=False,
        action="keep",
        outcome="success",
        outcome_basis="acceptance_detected",
    )
    ldb.record_evidence_route_decision(
        session_id="s2",
        agent="python-general-engineer",
        skill="test-driven-development",
        complexity="Medium",
        model="gpt-5-codex",
        request_snippet="Retry after a broken assertion.",
        failure=True,
        outcome="failure",
        outcome_basis="tool_errors",
    )

    context = ldb.get_evidence_route_context("python-general-engineer:test-driven-development")
    assert context["route_key"] == "python-general-engineer:test-driven-development"
    assert context["totals"]["decisions"] == 2
    assert context["totals"]["failures"] == 1
    assert context["totals"]["successes"] == 1
    assert context["recent"][0]["session_id"] == "s2"

    decision = ldb.get_evidence_decision("python-general-engineer:test-driven-development")
    assert decision["recommendation"] == "watch"
    assert any("failure rate" in reason for reason in decision["reasons"])
