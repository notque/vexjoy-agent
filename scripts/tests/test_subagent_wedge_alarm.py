"""Tests for subagent-wedge-alarm script."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib

wedge_alarm = importlib.import_module("subagent-wedge-alarm")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(wedge_alarm, "_STATE_FILE", tmp_path / "subagent-registry.json")
    yield tmp_path


class TestNoStateFile:
    def test_clean_output(self, capsys):
        wedge_alarm.main()
        assert "No subagent registry" in capsys.readouterr().out


class TestAllCompleted:
    def test_no_alarm(self, _isolate, capsys):
        state = {
            "session_id": "s1",
            "agents": {
                "a1": {"type": "gp", "status": "completed", "started": "2026-01-01T00:00:00+00:00"},
                "a2": {"type": "gp", "status": "completed", "started": "2026-01-01T00:00:00+00:00"},
            },
            "summary": {"total": 2, "completed": 2, "failed": 0, "active": 0},
        }
        wedge_alarm._STATE_FILE.write_text(json.dumps(state))
        wedge_alarm.main()
        assert "No wedged agents" in capsys.readouterr().out


class TestWedgedAgent:
    def test_alarm_triggered(self, _isolate, capsys, monkeypatch):
        monkeypatch.setenv("VEXJOY_WEDGE_THRESHOLD_MINUTES", "30")
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        state = {
            "session_id": "s1",
            "agents": {
                "a1": {
                    "type": "golang-general-engineer",
                    "status": "active",
                    "started": old_time,
                    "task": "Fix race condition",
                },
            },
            "summary": {"total": 1, "completed": 0, "failed": 0, "active": 1},
        }
        wedge_alarm._STATE_FILE.write_text(json.dumps(state))
        wedge_alarm.main()
        out = capsys.readouterr().out
        assert "WEDGE ALARM" in out
        assert "golang-general-engineer" in out

    def test_recent_active_no_alarm(self, _isolate, capsys):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        state = {
            "session_id": "s1",
            "agents": {
                "a1": {"type": "gp", "status": "active", "started": recent},
            },
            "summary": {"total": 1, "completed": 0, "failed": 0, "active": 1},
        }
        wedge_alarm._STATE_FILE.write_text(json.dumps(state))
        wedge_alarm.main()
        assert "No wedged agents" in capsys.readouterr().out


class TestExitCode:
    def test_always_zero(self):
        """Script always exits 0."""
        result = __import__("subprocess").run(
            [sys.executable, str(Path(__file__).parent.parent / "subagent-wedge-alarm.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
