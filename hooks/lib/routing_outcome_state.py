"""Per-session bridge between the routing decision hook and the outcome hook.

The PostToolUse:Agent hook (routing-decision-recorder.py) records the routing
decision row and appends a *pending outcome* (routing key + observed error
flag) here. The SubagentStop hook (routing-outcome-recorder.py) drains the
pending outcomes and applies boost/decay to the matching decision rows.

State lives in a per-session JSON file under /tmp. All writes are atomic
(write-to-temp-then-rename) so an interrupted hook never corrupts the file.
Every function is best-effort and swallows errors — this bridge must never
block a hook.

Concurrency: parallel same-session ``PostToolUse:Agent`` dispatches (the NORMAL
case — /do Phase 4 and pr-review both fan out agents) issue concurrent
read-modify-write cycles against the same state file. Without serialization
those cycles lose updates (two readers see the same ``pending`` list, both
append one entry, the later writer's atomic rename clobbers the earlier one →
B drains fewer outcomes than A wrote → route-health under-counts). To prevent
this, every read-modify-write holds an EXCLUSIVE ``fcntl.flock`` on a sidecar
lock file across the WHOLE load→modify→write, so appends serialize and no
outcome is lost. The lock is advisory and best-effort: if locking is
unavailable the operation still proceeds (degraded, never blocking).

File shape:
    {
      "seen": ["<dispatch-sig>", ...],     # idempotency for the decision hook
      "pending": [{"key": "agent:skill", "errors": false}, ...]
    }
"""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_STATE_DIR = Path("/tmp")


def _state_dir() -> Path:
    """Resolve the state directory. Honors CLAUDE_ROUTING_STATE_DIR so separate
    processes (real cross-process dispatch, the concurrency test) agree on one
    location; falls back to the module default otherwise."""
    override = os.environ.get("CLAUDE_ROUTING_STATE_DIR")
    return Path(override) if override else _STATE_DIR


def _state_file(session_id: str) -> Path:
    sid = session_id or "nosession"
    # Keep the filename filesystem-safe.
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sid)[:64]
    return _state_dir() / f"claude-routing-outcomes-{safe}.json"


def _lock_file(path: Path) -> Path:
    """Sidecar lock path for a state file (the state file is rename-replaced,
    so the lock must live on a stable inode that is never replaced)."""
    return path.with_suffix(path.suffix + ".lock")


@contextmanager
def _state_lock(path: Path):
    """Hold an exclusive advisory lock across a read-modify-write cycle.

    Best-effort: if the lock file cannot be opened or flock is unavailable the
    body still runs (degraded to the old unlocked behavior) so the bridge never
    blocks a hook. The lock lives on a sidecar inode because the state file
    itself is replaced via ``os.replace`` (which swaps inodes and would drop a
    lock held on the old one)."""
    lock_fd = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(_lock_file(path)), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except OSError:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                pass
            lock_fd = None
    try:
        yield
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(lock_fd)
            except OSError:
                pass


def _load(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                data.setdefault("seen", [])
                data.setdefault("pending", [])
                return data
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return {"seen": [], "pending": []}


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        # Best-effort: at worst we lose one bridge record.
        pass


def dispatch_seen(session_id: str, signature: str) -> bool:
    """Return True if this dispatch signature was already recorded this session."""
    try:
        return signature in _load(_state_file(session_id)).get("seen", [])
    except Exception:
        return False


def mark_dispatch_seen(session_id: str, signature: str) -> None:
    """Mark a dispatch signature as recorded (idempotency for the decision hook)."""
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            if signature not in data["seen"]:
                data["seen"].append(signature)
                # Bound the seen list so a long session can't grow it unbounded.
                data["seen"] = data["seen"][-500:]
                _atomic_write(path, data)
    except Exception:
        pass


def append_pending_outcome(session_id: str, key: str, errors: bool) -> None:
    """Append a pending outcome for the SubagentStop hook to drain."""
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            data["pending"].append({"key": key, "errors": bool(errors)})
            data["pending"] = data["pending"][-500:]
            _atomic_write(path, data)
    except Exception:
        pass


def drain_pending_outcomes(session_id: str) -> list[dict[str, Any]]:
    """Return and clear all pending outcomes for this session.

    Returns a list of {"key": str, "errors": bool}. Clears the pending list
    (keeps the seen list) so each pending outcome is applied at most once.
    """
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            pending = data.get("pending", [])
            if pending:
                data["pending"] = []
                _atomic_write(path, data)
        return pending
    except Exception:
        return []
