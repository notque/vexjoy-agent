"""Tests for task-status.py."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

# Import the module under test (hyphenated filename)
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
task_status = importlib.import_module("task-status")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def status_file(tmp_path: Path) -> Path:
    """Return a temporary status file path."""
    return tmp_path / "tasks.json"


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


class TestStart:
    """Tests for the start subcommand."""

    def test_creates_task(self, status_file: Path) -> None:
        task_status.cmd_start("review", "Wave 1: 11 agents", path=status_file)

        data = json.loads(status_file.read_text())
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["name"] == "review"
        assert data["tasks"][0]["status"] == "Wave 1: 11 agents"
        assert data["tasks"][0]["completed"] is False
        assert data["tasks"][0]["started"]  # non-empty timestamp

    def test_overwrites_existing(self, status_file: Path) -> None:
        task_status.cmd_start("review", "first", path=status_file)
        task_status.cmd_start("review", "second", path=status_file)

        data = json.loads(status_file.read_text())
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["status"] == "second"


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    """Tests for the update subcommand."""

    def test_modifies_status(self, status_file: Path) -> None:
        task_status.cmd_start("review", "initial", path=status_file)
        task_status.cmd_update("review", "6/11 agents returned", path=status_file)

        data = json.loads(status_file.read_text())
        assert data["tasks"][0]["status"] == "6/11 agents returned"

    def test_creates_if_missing(self, status_file: Path) -> None:
        task_status.cmd_update("new-task", "running", path=status_file)

        data = json.loads(status_file.read_text())
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["name"] == "new-task"
        assert data["tasks"][0]["status"] == "running"


# ---------------------------------------------------------------------------
# done
# ---------------------------------------------------------------------------


class TestDone:
    """Tests for the done subcommand."""

    def test_sets_completed_and_elapsed(self, status_file: Path) -> None:
        task_status.cmd_start("review", "running", path=status_file)
        task_status.cmd_done("review", "11/11 complete", path=status_file)

        data = json.loads(status_file.read_text())
        task = data["tasks"][0]
        assert task["completed"] is True
        assert task["ended"] is not None
        assert task["elapsed_seconds"] is not None
        assert task["elapsed_seconds"] >= 0
        assert task["status"] == "11/11 complete"

    def test_done_creates_if_missing(self, status_file: Path) -> None:
        task_status.cmd_done("new-task", "finished", path=status_file)

        data = json.loads(status_file.read_text())
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["completed"] is True


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


class TestShow:
    """Tests for the show subcommand."""

    def test_filters_completed_by_default(self, status_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        task_status.cmd_start("active-task", "running", path=status_file)
        task_status.cmd_start("done-task", "running", path=status_file)
        task_status.cmd_done("done-task", "finished", path=status_file)

        task_status.cmd_show(path=status_file)
        output = capsys.readouterr().out

        assert "active-task" in output
        assert "done-task" not in output

    def test_include_completed_shows_all(self, status_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        task_status.cmd_start("active-task", "running", path=status_file)
        task_status.cmd_start("done-task", "running", path=status_file)
        task_status.cmd_done("done-task", "finished", path=status_file)

        task_status.cmd_show(include_completed=True, path=status_file)
        output = capsys.readouterr().out

        assert "active-task" in output
        assert "done-task" in output
        assert "COMPLETED" in output

    def test_json_output_valid(self, status_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        task_status.cmd_start("task-a", "step 1", path=status_file)
        task_status.cmd_start("task-b", "step 2", path=status_file)

        task_status.cmd_show(as_json=True, path=status_file)
        output = capsys.readouterr().out

        data = json.loads(output)
        assert "tasks" in data
        assert len(data["tasks"]) == 2
        # Active tasks should have computed elapsed_seconds
        for task in data["tasks"]:
            assert "elapsed_seconds" in task
            assert task["elapsed_seconds"] >= 0

    def test_json_filters_completed(self, status_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        task_status.cmd_start("active", "running", path=status_file)
        task_status.cmd_start("done", "running", path=status_file)
        task_status.cmd_done("done", "finished", path=status_file)

        task_status.cmd_show(as_json=True, path=status_file)
        output = capsys.readouterr().out

        data = json.loads(output)
        names = [t["name"] for t in data["tasks"]]
        assert "active" in names
        assert "done" not in names

    def test_empty_shows_no_active(self, status_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        task_status.cmd_show(path=status_file)
        output = capsys.readouterr().out
        assert "No active pipelines" in output


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    """Tests for the clear subcommand."""

    def test_removes_all_tasks(self, status_file: Path) -> None:
        task_status.cmd_start("task-a", "running", path=status_file)
        task_status.cmd_start("task-b", "running", path=status_file)
        assert status_file.exists()

        task_status.cmd_clear(path=status_file)
        assert not status_file.exists()

    def test_clear_nonexistent_file(self, status_file: Path) -> None:
        # Should not raise
        result = task_status.cmd_clear(path=status_file)
        assert result == 0


# ---------------------------------------------------------------------------
# Elapsed computation
# ---------------------------------------------------------------------------


class TestElapsed:
    """Tests for elapsed time computation."""

    def test_active_task_elapsed_computed(self, status_file: Path) -> None:
        # Set start time 10 seconds in the past
        store = task_status.TaskStore()
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        ts = past.strftime("%Y-%m-%dT%H:%M:%SZ")
        store.tasks.append(task_status.Task(name="old-task", status="running", started=ts))
        task_status._save(store, status_file)

        loaded = task_status._load(status_file)
        elapsed = task_status._elapsed_seconds(loaded.tasks[0].started)
        assert elapsed >= 9  # Allow 1s tolerance for test execution

    def test_format_duration_seconds(self) -> None:
        assert task_status._format_duration(45) == "45s"

    def test_format_duration_minutes(self) -> None:
        assert task_status._format_duration(135) == "2m 15s"

    def test_format_duration_hours(self) -> None:
        assert task_status._format_duration(3723) == "1h 2m"
