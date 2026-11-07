"""Tests for the session-task-registry hook."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import importlib

# Import the module with hyphenated name
spec = importlib.util.spec_from_file_location(
    "session_task_registry",
    Path(__file__).resolve().parent.parent / "session-task-registry.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def tmp_registry(tmp_path):
    """Patch REGISTRY_PATH to a temp file."""
    registry_file = tmp_path / "task-registry.json"
    with patch.object(mod, "REGISTRY_PATH", registry_file):
        yield registry_file


def test_empty_registry_creation(tmp_registry):
    """Loading a non-existent registry returns empty structure."""
    reg = mod._load_registry()
    assert reg == {"version": 1, "tasks": []}


def test_task_recording_from_do_route_marker(tmp_registry):
    """PostToolUse records a task when [do-route] marker is present."""
    event = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "[do-route] agent=python-general-engineer skill=test-driven-development complexity=medium\nFix the bug",
            "description": "Fix the test bug",
        },
        "session_id": "test-session-1",
    }
    mod.handle_post_tool_use(event)

    reg = mod._load_registry()
    assert len(reg["tasks"]) == 1
    task = reg["tasks"][0]
    assert task["agent"] == "python-general-engineer"
    assert task["skill"] == "test-driven-development"
    assert task["complexity"] == "medium"
    assert task["status"] == "dispatched"
    assert task["session_id"] == "test-session-1"
    assert "Fix the test bug" in task["summary"]


def test_session_start_injection_with_incomplete(tmp_registry, capsys):
    """SessionStart injects context when incomplete tasks exist."""
    registry = {
        "version": 1,
        "tasks": [
            {
                "id": "260908-001",
                "agent": "golang-general-engineer",
                "skill": "go-patterns",
                "complexity": "medium",
                "summary": "Fix Go test race condition",
                "dispatched_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
                "completed_at": None,
                "status": "dispatched",
                "session_id": "old-session",
            }
        ],
    }
    tmp_registry.write_text(json.dumps(registry))

    with pytest.raises(SystemExit):
        mod.handle_session_start()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "[task-registry]" in ctx
    assert "260908-001" in ctx
    assert "Fix Go test race condition" in ctx


def test_subagent_stop_updates_status(tmp_registry):
    """SubagentStop updates the task status to completed."""
    registry = {
        "version": 1,
        "tasks": [
            {
                "id": "260908-001",
                "agent": "python-general-engineer",
                "skill": "",
                "complexity": "simple",
                "summary": "Quick fix",
                "dispatched_at": "2026-09-08T10:00:00+00:00",
                "completed_at": None,
                "status": "dispatched",
                "session_id": "sess-1",
            }
        ],
    }
    tmp_registry.write_text(json.dumps(registry))

    event = {"session_id": "sess-1", "hook_event_name": "SubagentStop"}
    mod.handle_subagent_stop(event)

    reg = mod._load_registry()
    assert reg["tasks"][0]["status"] == "completed"
    assert reg["tasks"][0]["completed_at"] is not None


def test_atomic_write(tmp_registry):
    """Registry file is written atomically with correct permissions."""
    registry = {"version": 1, "tasks": []}
    mod._save_registry(registry)

    assert tmp_registry.exists()
    # Check permissions (0600)
    stat = os.stat(tmp_registry)
    assert oct(stat.st_mode & 0o777) == "0o600"


def test_no_injection_when_no_incomplete(tmp_registry, capsys):
    """SessionStart produces no output when all tasks are completed."""
    registry = {
        "version": 1,
        "tasks": [
            {
                "id": "260908-001",
                "agent": "test",
                "skill": "",
                "complexity": "",
                "summary": "Done task",
                "dispatched_at": "2026-09-08T10:00:00+00:00",
                "completed_at": "2026-09-08T11:00:00+00:00",
                "status": "completed",
                "session_id": "old",
            }
        ],
    }
    tmp_registry.write_text(json.dumps(registry))

    # Should not raise SystemExit (no output)
    mod.handle_session_start()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_skip_non_do_route_agent(tmp_registry):
    """PostToolUse skips Agent dispatches without [do-route] marker."""
    event = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "Just a normal agent dispatch",
            "description": "Normal",
        },
        "session_id": "s1",
    }
    mod.handle_post_tool_use(event)
    reg = mod._load_registry()
    assert len(reg["tasks"]) == 0


def test_exit_code_zero(tmp_path):
    """Hook exits 0 on empty stdin."""
    hook_path = Path(__file__).resolve().parent.parent / "session-task-registry.py"
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input="",
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
        timeout=10,
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# B-11: stale tasks expire from the injection; parallel writers lose nothing
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).resolve().parent.parent / "session-task-registry.py"


def _task(task_id: str, status: str, dispatched_at: str | None) -> dict:
    return {
        "id": task_id,
        "agent": "python-general-engineer",
        "skill": "",
        "complexity": "simple",
        "summary": f"summary {task_id}",
        "dispatched_at": dispatched_at,
        "completed_at": None,
        "status": status,
        "session_id": "old-session",
    }


def test_incomplete_tasks_older_than_seven_days_are_not_injected_but_kept(tmp_registry, capsys):
    now = datetime.now(timezone.utc)
    tasks = [
        _task("old-dispatched", "dispatched", (now - timedelta(days=8)).isoformat()),
        _task("old-failed", "failed", (now - timedelta(days=14)).isoformat()),
        _task("recent", "dispatched", (now - timedelta(hours=1)).isoformat()),
        _task("no-time", "dispatched", None),
    ]
    tmp_registry.write_text(json.dumps({"version": 1, "tasks": tasks}))

    with pytest.raises(SystemExit):
        mod.handle_session_start()

    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "recent" in ctx
    for stale in ("old-dispatched", "old-failed", "no-time"):
        assert stale not in ctx
    assert "1 incomplete task(s)" in ctx
    # Filtered at read time only: nothing is deleted from the registry.
    assert [t["id"] for t in json.loads(tmp_registry.read_text())["tasks"]] == [t["id"] for t in tasks]


def test_only_stale_incomplete_tasks_inject_nothing(tmp_registry, capsys):
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    tmp_registry.write_text(json.dumps({"version": 1, "tasks": [_task("ancient", "dispatched", old)]}))

    mod.handle_session_start()

    assert capsys.readouterr().out == ""


def _dispatch_event(n: int) -> str:
    prompt = f"[do-route] agent=python-general-engineer skill=-\nTask number {n}"
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Agent",
            "session_id": f"sess-{n}",
            "tool_input": {"prompt": prompt, "description": f"task {n}"},
        }
    )


def _registry_at(home: Path) -> Path:
    return home / ".claude" / "state" / "task-registry.json"


def test_parallel_dispatches_are_all_recorded_with_unique_ids(tmp_path):
    writers = 6
    env = {**os.environ, "HOME": str(tmp_path)}
    procs = [
        subprocess.Popen(
            [sys.executable, str(HOOK_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=tmp_path,
        )
        for _ in range(writers)
    ]
    for n, proc in enumerate(procs):
        proc.stdin.write(_dispatch_event(n))
        proc.stdin.close()
    for proc in procs:
        assert proc.wait(timeout=30) == 0
        assert "HOOK-ERROR" not in proc.stderr.read()
        proc.stdout.close()
        proc.stderr.close()

    tasks = json.loads(_registry_at(tmp_path).read_text())["tasks"]
    assert sorted(t["session_id"] for t in tasks) == sorted(f"sess-{n}" for n in range(writers))
    assert len({t["id"] for t in tasks}) == writers


def test_a_held_registry_lock_is_waited_for_then_the_write_goes_ahead(tmp_path):
    fcntl = pytest.importorskip("fcntl")
    registry = _registry_at(tmp_path)
    registry.parent.mkdir(parents=True)
    lock_path = registry.with_name(registry.name + mod._LOCK_SUFFIX)
    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=_dispatch_event(1),
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path)},
            cwd=tmp_path,
            timeout=30,
        )
        elapsed = time.monotonic() - started
    assert result.returncode == 0
    assert elapsed >= mod._LOCK_WAIT_SECONDS
    assert [t["session_id"] for t in json.loads(registry.read_text())["tasks"]] == ["sess-1"]


def test_missing_scripts_lib_is_recorded_and_exits_zero(tmp_path):
    """Installed copies without scripts/lib must fail soft: hook_error entry, exit 0, no write."""
    hooks = tmp_path / "install" / "hooks"
    shutil.copytree(HOOK_PATH.parent / "lib", hooks / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(HOOK_PATH, hooks / HOOK_PATH.name)
    errors = tmp_path / "hook-errors.jsonl"
    home = tmp_path / "home"

    result = subprocess.run(
        [sys.executable, str(hooks / HOOK_PATH.name)],
        input=_dispatch_event(1),
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home), "CLAUDE_HOOK_ERRORS_PATH": str(errors)},
        cwd=tmp_path,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    entries = [json.loads(line) for line in errors.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [(e["hook"], e["type"]) for e in entries] == [("session-task-registry", "ModuleNotFoundError")]
    assert not _registry_at(home).exists()
