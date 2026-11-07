#!/usr/bin/env python3
# hook-version: 1.1.0
"""
SessionStart + PostToolUse + SubagentStop Hook: Durable Inter-Session Task Registry

SessionStart: inject incomplete tasks from previous sessions dispatched in the
last INCOMPLETE_MAX_AGE_DAYS days (older entries stay in the file).
PostToolUse (Agent): record dispatches that carry a [do-route] marker.
SubagentStop: update task status to completed or failed.

State: ~/.claude/state/task-registry.json (atomic writes, chmod 0600). Each
load-modify-save holds a bounded lock on task-registry.json.lock.
The [do-route] parser comes from scripts/lib; an install without it records
the ImportError with hook_error and exits 0.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

sys.path.insert(0, str(Path(__file__).parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
from hook_utils import context_output, hook_error
from stdin_timeout import read_stdin

REGISTRY_PATH = Path.home() / ".claude" / "state" / "task-registry.json"
MAX_TASKS = 500
MAX_INCOMPLETE_INJECT = 10
# SessionStart injects only incomplete tasks dispatched within this window. The
# registry keeps older entries; they just stop showing up in every session.
INCOMPLETE_MAX_AGE_DAYS = 7

# Every load-modify-save holds an exclusive lock on "<registry>.lock" (the
# registry itself is replaced on save). Hooks run in parallel; without the lock
# concurrent dispatches overwrote each other's entries. The wait is capped: a
# stuck holder means an unlocked write, never a stalled tool call.
_LOCK_SUFFIX = ".lock"
_LOCK_WAIT_SECONDS = 1.0
_LOCK_POLL_SECONDS = 0.01

_DO_ROUTE_RE = None


def _do_route_re():
    global _DO_ROUTE_RE
    if _DO_ROUTE_RE is None:
        from route_types import DO_ROUTE_MARKER_RE

        _DO_ROUTE_RE = DO_ROUTE_MARKER_RE
    return _DO_ROUTE_RE


def _try_lock(fd: int) -> bool:
    """One non-blocking exclusive-lock attempt; True when the lock is held."""
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except BlockingIOError:
        return False
    except OSError:
        if fcntl is not None:
            raise  # locking unsupported here: the caller goes ahead unlocked
        return False  # msvcrt reports contention as a plain OSError
    return True


@contextmanager
def _registry_lock():
    """Hold the registry lock for one load-modify-save, waiting at most
    _LOCK_WAIT_SECONDS. On timeout, or where locking is unavailable, the body
    runs unlocked. Closing the descriptor releases the lock."""
    fd = None
    try:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = REGISTRY_PATH.with_name(REGISTRY_PATH.name + _LOCK_SUFFIX)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        while not _try_lock(fd) and time.monotonic() < deadline:
            time.sleep(_LOCK_POLL_SECONDS)
    except OSError:
        pass
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)


def _dispatched_at(task: dict) -> datetime | None:
    """The task's dispatch time (UTC), or None when missing or unreadable."""
    raw = task.get("dispatched_at")
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _load_registry() -> dict:
    """Load task registry. Return empty structure on any error."""
    try:
        if REGISTRY_PATH.exists():
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                return data
    except Exception:
        pass
    return {"version": 1, "tasks": []}


def _save_registry(registry: dict) -> None:
    """Atomic write with chmod 0600."""
    import tempfile

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(REGISTRY_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(REGISTRY_PATH))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _next_task_id(tasks: list) -> str:
    """Generate YYMMDD-NNN id."""
    today = datetime.now(tz=timezone.utc).strftime("%y%m%d")
    today_ids = [t["id"] for t in tasks if isinstance(t.get("id"), str) and t["id"].startswith(today + "-")]
    seq = len(today_ids) + 1
    return f"{today}-{seq:03d}"


def _prune(registry: dict) -> None:
    """Cap at MAX_TASKS. Remove oldest completed first."""
    tasks = registry["tasks"]
    if len(tasks) <= MAX_TASKS:
        return
    completed = [t for t in tasks if t.get("status") == "completed"]
    incomplete = [t for t in tasks if t.get("status") != "completed"]
    keep_completed = max(0, MAX_TASKS - len(incomplete))
    registry["tasks"] = incomplete + completed[-keep_completed:]


def _time_ago(iso_str: str) -> str:
    """Human-readable time delta from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(tz=timezone.utc) - dt
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            minutes = int(delta.total_seconds() // 60)
            return f"{minutes}m ago"
        if hours < 48:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return "unknown"


def handle_session_start() -> None:
    """Inject incomplete tasks from previous sessions dispatched in the last
    INCOMPLETE_MAX_AGE_DAYS days. Older ones stay in the registry but are not
    shown again; a task with no readable dispatch time is not shown either."""
    registry = _load_registry()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=INCOMPLETE_MAX_AGE_DAYS)
    recent = []
    for t in registry["tasks"]:
        if not isinstance(t, dict) or t.get("status") not in ("dispatched", "failed"):
            continue
        dispatched = _dispatched_at(t)
        if dispatched is not None and dispatched >= cutoff:
            recent.append((dispatched, t))
    if not recent:
        return
    recent.sort(key=lambda pair: pair[0], reverse=True)
    incomplete = [t for _, t in recent[:MAX_INCOMPLETE_INJECT]]

    lines = [
        f"[task-registry] {len(incomplete)} incomplete task(s) from previous sessions "
        f"in the last {INCOMPLETE_MAX_AGE_DAYS} days:"
    ]
    for t in incomplete:
        ago = _time_ago(t.get("dispatched_at", ""))
        lines.append(
            f"- {t.get('id', '?')}: {t.get('summary', '(no summary)')} "
            f"(dispatched {ago}, status: {t.get('status', '?')})"
        )
    lines.append("Use /retro or re-dispatch to continue.")
    context_output("SessionStart", "\n".join(lines)).print_and_exit()


def handle_post_tool_use(event: dict) -> None:
    """Record a dispatch from a [do-route] marker."""
    tool_name = event.get("tool_name") or event.get("tool", "")
    if tool_name != "Agent":
        return

    tool_input = event.get("tool_input") or event.get("input") or {}
    prompt = tool_input.get("prompt") or ""
    if "[do-route]" not in prompt.lower():
        return

    m = _do_route_re().search(prompt)
    if not m:
        return

    agent = m.group(1).strip().lower()
    skill_raw = (m.group(2) or "").strip().lower()
    skill = "" if skill_raw == "-" else skill_raw

    cm = re.search(r"\bcomplexity=([a-z0-9-]+)", prompt, re.IGNORECASE)
    complexity = cm.group(1).lower() if cm else ""

    description = tool_input.get("description") or ""
    summary = (description or prompt)[:120].replace("\n", " ").strip()
    session_id = event.get("session_id") or ""

    with _registry_lock():
        registry = _load_registry()
        task = {
            "id": _next_task_id(registry["tasks"]),
            "agent": agent,
            "skill": skill,
            "complexity": complexity,
            "summary": summary,
            "dispatched_at": datetime.now(tz=timezone.utc).isoformat(),
            "completed_at": None,
            "status": "dispatched",
            "session_id": session_id,
        }
        registry["tasks"].append(task)
        _prune(registry)
        _save_registry(registry)


def handle_subagent_stop(event: dict) -> None:
    """Update the most recent dispatched task for this session."""
    session_id = event.get("session_id") or ""
    has_error = False
    try:
        from hook_utils import get_tool_result, is_tool_error

        has_error = is_tool_error(get_tool_result(event))
    except Exception:
        pass

    with _registry_lock():
        registry = _load_registry()
        for task in reversed(registry["tasks"]):
            if task.get("session_id") == session_id and task.get("status") == "dispatched":
                task["status"] = "failed" if has_error else "completed"
                task["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
                _save_registry(registry)
                return


_BYPASS_ENV = "SESSION_TASK_REGISTRY_BYPASS"


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[session-task-registry] Bypassed via SESSION_TASK_REGISTRY_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        raw = read_stdin(timeout=2)

        if not raw or raw.strip() in ("", "{}"):
            handle_session_start()
            return

        event = json.loads(raw)
        hook_event = event.get("hook_event_name") or ""
        tool_name = event.get("tool_name") or event.get("tool", "")

        if hook_event == "SessionStart" or (not tool_name and not hook_event):
            handle_session_start()
        elif hook_event == "SubagentStop":
            handle_subagent_stop(event)
        elif tool_name == "Agent":
            handle_post_tool_use(event)

    except Exception as e:
        hook_error("session-task-registry", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
