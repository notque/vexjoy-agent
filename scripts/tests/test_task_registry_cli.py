"""Tests for the task-registry CLI script."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib

spec = importlib.util.spec_from_file_location(
    "task_registry",
    Path(__file__).resolve().parent.parent / "task-registry.py",
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def tmp_registry(tmp_path):
    registry_file = tmp_path / "task-registry.json"
    with patch.object(cli, "REGISTRY_PATH", registry_file):
        yield registry_file


def _sample_registry(n=3):
    now = datetime.now(tz=timezone.utc)
    tasks = []
    for i in range(n):
        tasks.append(
            {
                "id": f"260908-{i + 1:03d}",
                "agent": f"agent-{i}",
                "skill": "",
                "complexity": "simple",
                "summary": f"Task {i}",
                "dispatched_at": now.isoformat(),
                "completed_at": now.isoformat() if i % 2 == 0 else None,
                "status": "completed" if i % 2 == 0 else "dispatched",
                "session_id": f"s-{i}",
            }
        )
    return {"version": 1, "tasks": tasks}


def test_list_all(tmp_registry, capsys):
    tmp_registry.write_text(json.dumps(_sample_registry()))
    args = type("A", (), {"status": None, "command": "list"})()
    cli.cmd_list(args)
    out = capsys.readouterr().out
    assert "260908-001" in out
    assert "260908-002" in out


def test_list_filtered(tmp_registry, capsys):
    tmp_registry.write_text(json.dumps(_sample_registry()))
    args = type("A", (), {"status": "completed", "command": "list"})()
    cli.cmd_list(args)
    out = capsys.readouterr().out
    assert "completed" in out
    # dispatched tasks should be filtered out
    lines = [l for l in out.strip().split("\n") if l.strip()]
    for line in lines:
        assert "dispatched" not in line


def test_list_incomplete(tmp_registry, capsys):
    tmp_registry.write_text(json.dumps(_sample_registry()))
    args = type("A", (), {"status": "incomplete", "command": "list"})()
    cli.cmd_list(args)
    out = capsys.readouterr().out
    assert "dispatched" in out


def test_clear_with_age(tmp_registry, capsys):
    reg = _sample_registry()
    # Make one task old
    reg["tasks"][0]["dispatched_at"] = "2026-01-01T00:00:00+00:00"
    tmp_registry.write_text(json.dumps(reg))
    args = type("A", (), {"older_than": 30, "command": "clear"})()
    cli.cmd_clear(args)
    out = capsys.readouterr().out
    assert "Pruned 1" in out


def test_stats(tmp_registry, capsys):
    tmp_registry.write_text(json.dumps(_sample_registry()))
    args = type("A", (), {"command": "stats"})()
    cli.cmd_stats(args)
    out = capsys.readouterr().out
    assert "Total tasks: 3" in out


def test_empty_registry(tmp_registry, capsys):
    args = type("A", (), {"status": None, "command": "list"})()
    cli.cmd_list(args)
    out = capsys.readouterr().out
    assert "No tasks found" in out
