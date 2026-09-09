#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SubagentStop Hook: State Tracker

Records subagent final state to a JSON registry. Detects failed and unknown
agents. Injects context for actionable states (failed, blocked, unknown).

Policy table:
  blocked  -> actionable: inject investigation context
  working  -> absorb: no action
  idle/done -> defer
  unknown  -> never treat as done: flag for investigation
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

_EVENT_NAME = "SubagentStop"
_STATE_DIR = Path.home() / ".claude" / "state"
_STATE_FILE = _STATE_DIR / "subagent-registry.json"
_DEBUG_LOG = Path("/tmp/claude_hook_debug.log")


def _debug(msg: str) -> None:
    try:
        with open(_DEBUG_LOG, "a") as f:
            f.write(f"[subagent-state-tracker] {time.time():.3f} {msg}\n")
    except Exception:
        pass


def _ensure_state_dir() -> None:
    """Create state directory with restricted permissions if needed."""
    if not _STATE_DIR.exists():
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(str(_STATE_DIR), 0o700)


def _load_state() -> dict:
    """Load current state file, return empty structure on any error."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        _debug("state file corrupt or unreadable, starting fresh")
    return {
        "session_id": "",
        "agents": {},
        "summary": {"total": 0, "completed": 0, "failed": 0, "active": 0},
    }


def _save_state(state: dict) -> None:
    """Atomic write: temp file then rename."""
    _ensure_state_dir()
    fd, tmp_path = tempfile.mkstemp(dir=str(_STATE_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.rename(tmp_path, str(_STATE_FILE))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _recompute_summary(state: dict) -> None:
    """Recompute summary counts from agent entries."""
    agents = state.get("agents", {})
    summary = {"total": len(agents), "completed": 0, "failed": 0, "active": 0}
    for entry in agents.values():
        s = entry.get("status", "unknown")
        if s == "completed":
            summary["completed"] += 1
        elif s in ("failed", "timeout"):
            summary["failed"] += 1
        elif s == "active":
            summary["active"] += 1
    state["summary"] = summary


def _classify_status(event: dict) -> str:
    """Classify the subagent's final status from event data."""
    if event.get("error"):
        return "failed"
    if event.get("timed_out"):
        return "timeout"
    return "completed"


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            sys.exit(0)

        event = json.loads(raw)

        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != _EVENT_NAME:
            sys.exit(0)

        agent_id = event.get("agent_id", "") or event.get("subagent_id", "") or f"unknown-{int(time.time())}"
        agent_type = event.get("agent_type", "unknown")
        session_id = event.get("session_id", "")
        now_iso = datetime.now(timezone.utc).isoformat()
        status = _classify_status(event)
        task = event.get("task", "") or event.get("description", "") or ""

        # Truncate task to keep state file small
        if len(task) > 200:
            task = task[:197] + "..."

        state = _load_state()

        # Reset state if session changed
        if session_id and state.get("session_id") != session_id:
            state = {
                "session_id": session_id,
                "agents": {},
                "summary": {"total": 0, "completed": 0, "failed": 0, "active": 0},
            }

        state["session_id"] = session_id
        state["agents"][agent_id] = {
            "type": agent_type,
            "started": event.get("start_time", now_iso),
            "ended": now_iso,
            "status": status,
            "task": task,
        }

        _recompute_summary(state)
        _save_state(state)

        _debug(f"recorded agent={agent_id} type={agent_type} status={status}")

        # Policy: surface actionable states via stderr
        # (SubagentStop does not support hookSpecificOutput/additionalContext)
        if status in ("failed", "timeout"):
            print(
                f"[subagent-supervision] Agent '{agent_type}' ({agent_id}) {status}. "
                f"Task: {task or 'unknown'}. Consider re-dispatch or investigation.",
                file=sys.stderr,
            )

        if status == "unknown":
            print(
                f"[subagent-supervision] Agent '{agent_type}' ({agent_id}) ended "
                f"with unknown status. Unknown is never done -- investigate.",
                file=sys.stderr,
            )

        sys.exit(0)

    except (json.JSONDecodeError, KeyError, TypeError):
        sys.exit(0)
    except Exception as e:
        hook_error("subagent-state-tracker", e)


if __name__ == "__main__":
    main()
