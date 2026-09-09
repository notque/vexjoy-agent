"""Tests for subagent-state-tracker hook."""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the hook module (hyphen in filename requires importlib)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

tracker = importlib.import_module("subagent-state-tracker")


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Redirect state file to tmp for each test."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(tracker, "_STATE_DIR", state_dir)
    monkeypatch.setattr(tracker, "_STATE_FILE", state_dir / "subagent-registry.json")
    yield


def _make_event(
    agent_id="agent-1",
    agent_type="general-purpose",
    session_id="sess-1",
    error=None,
    timed_out=None,
    task="Run tests",
):
    event = {
        "hook_event_name": "SubagentStop",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "session_id": session_id,
        "task": task,
    }
    if error:
        event["error"] = error
    if timed_out:
        event["timed_out"] = timed_out
    return event


class TestStateCreation:
    """Test state file creation on first SubagentStop."""

    def test_creates_state_file(self):
        """First event creates the registry file."""
        event = _make_event()
        with patch.object(tracker, "read_stdin", return_value=json.dumps(event)):
            with pytest.raises(SystemExit) as exc_info:
                tracker.main()
            assert exc_info.value.code == 0

        state = json.loads(tracker._STATE_FILE.read_text())
        assert "agent-1" in state["agents"]
        assert state["agents"]["agent-1"]["status"] == "completed"
        assert state["summary"]["total"] == 1
        assert state["summary"]["completed"] == 1


class TestStateAccumulation:
    """Test state accumulation across multiple SubagentStop events."""

    def test_accumulates_agents(self):
        """Multiple events accumulate in the registry."""
        for name in ["agent-1", "agent-2", "agent-3"]:
            event = _make_event(agent_id=name)
            with patch.object(tracker, "read_stdin", return_value=json.dumps(event)), pytest.raises(SystemExit):
                tracker.main()

        state = json.loads(tracker._STATE_FILE.read_text())
        assert state["summary"]["total"] == 3
        assert state["summary"]["completed"] == 3

    def test_session_reset(self):
        """New session ID resets the registry."""
        event1 = _make_event(session_id="sess-1")
        event2 = _make_event(agent_id="agent-2", session_id="sess-2")

        with patch.object(tracker, "read_stdin", return_value=json.dumps(event1)), pytest.raises(SystemExit):
            tracker.main()

        with patch.object(tracker, "read_stdin", return_value=json.dumps(event2)), pytest.raises(SystemExit):
            tracker.main()

        state = json.loads(tracker._STATE_FILE.read_text())
        assert state["session_id"] == "sess-2"
        assert "agent-1" not in state["agents"]
        assert state["summary"]["total"] == 1


class TestFailedAgentContext:
    """Test failed-agent context surfacing via stderr."""

    def test_failed_agent_surfaces_warning(self, capsys):
        """Failed agent prints supervision warning to stderr."""
        event = _make_event(error="something broke")
        with patch.object(tracker, "read_stdin", return_value=json.dumps(event)):
            with pytest.raises(SystemExit) as exc_info:
                tracker.main()
            assert exc_info.value.code == 0

        err = capsys.readouterr().err
        assert "subagent-supervision" in err
        assert "failed" in err

    def test_timeout_agent_surfaces_warning(self, capsys):
        """Timed-out agent prints supervision warning to stderr."""
        event = _make_event(timed_out=True)
        with patch.object(tracker, "read_stdin", return_value=json.dumps(event)):
            with pytest.raises(SystemExit) as exc_info:
                tracker.main()
            assert exc_info.value.code == 0

        err = capsys.readouterr().err
        assert "subagent-supervision" in err
        assert "timeout" in err


class TestUnknownPolicy:
    """Test 'unknown is never done' policy."""

    def test_classify_completed(self):
        assert tracker._classify_status({}) == "completed"

    def test_classify_failed(self):
        assert tracker._classify_status({"error": "boom"}) == "failed"

    def test_classify_timeout(self):
        assert tracker._classify_status({"timed_out": True}) == "timeout"


class TestNonBlocking:
    """Verify hook always exits 0."""

    def test_empty_stdin(self):
        with patch.object(tracker, "read_stdin", return_value=""):
            with pytest.raises(SystemExit) as exc_info:
                tracker.main()
            assert exc_info.value.code == 0

    def test_malformed_json(self):
        with patch.object(tracker, "read_stdin", return_value="not json"):
            with pytest.raises(SystemExit) as exc_info:
                tracker.main()
            assert exc_info.value.code == 0

    def test_wrong_event_type(self):
        with patch.object(tracker, "read_stdin", return_value=json.dumps({"hook_event_name": "Other"})):
            with pytest.raises(SystemExit) as exc_info:
                tracker.main()
            assert exc_info.value.code == 0
