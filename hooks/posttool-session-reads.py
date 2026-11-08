#!/usr/bin/env python3
# hook-version: 2.2.0
"""
PostToolUse Hook: Session Read Tracker

Tracks files read during the session by appending JSONL entries
({"ts", "session", "path"}) to .claude/session-reads.txt. This provides a
lightweight record of files the parent (main) thread has seen, used by the
warmstart hook to give subagents context about what's already been read.

v2 (session scoping): entries carry the session id and a UTC timestamp so
the warmstart reader can restrict itself to the current session. Writes
prune entries older than RETENTION_DAYS and drop v1 legacy plain-path
lines, so the file cannot accumulate cross-session state indefinitely.
Credential-shaped paths (.ssh/, .env, *.pem, ...) are never recorded.

v2.1 (Bash reads): a Bash command that starts with a read-only pager
(cat, sed, head, tail, less, bat) also records every argument that resolves
to an existing file under cwd, capped at MAX_BASH_PATHS. Codex cannot
intercept the built-in Read tool, so this keeps the warm-start file list
populated there. Commands containing rm, mv, cp, or a redirect are ignored.

v2.1.3 (parallel writers): the rewrite holds a bounded lock on
.claude/session-reads.lock and goes through a per-writer temp file, so hooks
running in parallel no longer drop each other's entries or crash on a
shared temp name. The lock wait is capped; a stuck holder means an unlocked
write, never a stalled tool call.

v2.2.0 (parent reads only): Claude Code puts a non-empty agent_id on hook
events only when the tool call runs inside a subagent. Such reads are
written with an "agent" field, and the warmstart reader skips them, so one
subagent's reads never reach a sibling subagent's warmstart block. A
main-thread read of a path a subagent already logged replaces that entry
with an untagged one, so dedupe on (session, path) never hides a parent read.

Design Principles:
- SILENT output (no context injection)
- Non-blocking (always exits 0)
- Processes Read tool results and read-only Bash commands
- Deduplicates (session, path) pairs
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
import shlex
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error, is_sensitive_path
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

SESSION_READS_FILE = ".claude/session-reads.txt"
# Hooks run in parallel, so every read-modify-write of SESSION_READS_FILE holds
# an exclusive lock on this sidecar file (the data file itself is replaced).
SESSION_READS_LOCK_FILE = ".claude/session-reads.lock"
# A writer holds the lock for one small rewrite. Waiting longer than this means
# the holder is stuck, and the write then goes ahead unlocked: a stuck writer
# must never stall the tool call.
_LOCK_WAIT_SECONDS = 1.0
_LOCK_POLL_SECONDS = 0.01

# Entries older than this are pruned on every write.
RETENTION_DAYS = 7

# Bash commands that read files without changing them.
_READ_CMD_RE = re.compile(r"^\s*(cat|sed|head|tail|less|bat)\b")
# Any of these anywhere in the command means it may write or move; skip it.
_MUTATING_RE = re.compile(r"(^|[\s;&|])(rm|mv|cp)\b|>")
MAX_BASH_PATHS = 20


def bash_read_paths(command: str, cwd: Path | None = None) -> list[str]:
    """Return file paths a read-only Bash command touches, in argument order.

    Only commands that open with cat/sed/head/tail/less/bat qualify. Commands
    that mention rm, mv, cp, or a `>` redirect return nothing. Each argument
    is kept when it names an existing file under cwd; the result is capped
    at MAX_BASH_PATHS. Credential-shaped paths are dropped.
    """
    if not isinstance(command, str) or not _READ_CMD_RE.match(command):
        return []
    if _MUTATING_RE.search(command):
        return []
    try:
        args = shlex.split(command)
    except ValueError:
        return []
    if args and args[0] == "sed" and any(a.startswith("-i") or a == "--in-place" for a in args[1:]):
        return []  # in-place edit, not a read
    base = (cwd or Path.cwd()).resolve()
    paths: list[str] = []
    for arg in args[1:]:
        if not arg or arg.startswith("-"):
            continue
        try:
            candidate = (base / arg).resolve()
            if not candidate.is_file() or not candidate.is_relative_to(base):
                continue
        except (OSError, ValueError):
            continue
        rel = str(candidate.relative_to(base))
        if is_sensitive_path(rel) or rel in paths:
            continue
        paths.append(rel)
        if len(paths) >= MAX_BASH_PATHS:
            break
    return paths


def event_paths(event: dict) -> list[str]:
    """Paths to record for one event: Read file_path, or read-only Bash args."""
    tool_input = event.get("tool_input", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(tool_input, dict):
        return []
    if event.get("tool_name") == "Bash":
        return bash_read_paths(str(tool_input.get("command", "")))
    file_path = tool_input.get("file_path", "")
    if not file_path or is_sensitive_path(file_path):
        return []
    return [str(file_path)]


def _parse_entry(line: str) -> dict | None:
    """Parse one JSONL entry; None for blank, legacy plain-path, or bad lines."""
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None  # v1 legacy plain-path line — dropped by design
    if not isinstance(entry, dict) or not entry.get("path"):
        return None
    return entry


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
def _bounded_lock(lock_path: Path):
    """Hold an exclusive lock on *lock_path* for the body, waiting at most
    _LOCK_WAIT_SECONDS. On timeout, or where locking is unavailable, the body
    runs unlocked. Closing the descriptor releases the lock."""
    fd = None
    try:
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


def _write_atomic(path: Path, text: str) -> None:
    """Replace *path* with *text* through a temp file no other writer shares."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".session-reads-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _fresh(entry: dict, cutoff: datetime) -> bool:
    """True when the entry's timestamp parses and is at or after cutoff."""
    try:
        ts = datetime.fromisoformat(entry["ts"])
    except (KeyError, TypeError, ValueError):
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts >= cutoff


def event_agent_id(event: dict) -> str:
    """Subagent id for this event, or "" for a main-thread call.

    Claude Code sets agent_id only when the hook fires inside a subagent;
    agent_type alone also appears on a main thread started with --agent,
    so it is not used here.
    """
    agent_id = event.get("agent_id")
    return agent_id.strip() if isinstance(agent_id, str) else ""


_BYPASS_ENV = "POSTTOOL_SESSION_READS_BYPASS"


def main() -> None:
    """Record Read tool file paths and read-only Bash paths for this session.

    Flow:
    1. Read stdin JSON; extract file_path (Read) or command paths (Bash)
    2. Skip credential-shaped paths entirely
    3. Rewrite .claude/session-reads.txt: fresh entries + the new one,
       deduplicated on (session, path); subagent reads carry "agent", and
       a main-thread read replaces a subagent-tagged entry
    4. Exit silently (no context injection)
    """
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[posttool-session-reads] Bypassed via POSTTOOL_SESSION_READS_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # The settings.json matcher ("Read" or "Bash") limits which tools
        # spawn this hook; event_paths() decides what each event records.
        if not isinstance(event, dict):
            return
        new_paths = event_paths(event)
        if not new_paths:
            return

        session_id = get_session_id(event)
        agent_id = event_agent_id(event)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=RETENTION_DAYS)

        reads_path = Path(SESSION_READS_FILE)
        reads_path.parent.mkdir(parents=True, exist_ok=True)

        # One lock around the whole read-modify-write, so parallel writers
        # cannot drop each other's entries.
        with _bounded_lock(Path(SESSION_READS_LOCK_FILE)):
            entries: list[dict] = []
            seen: set[tuple[str, str]] = set()
            if reads_path.is_file():
                try:
                    for line in reads_path.read_text(encoding="utf-8").splitlines():
                        entry = _parse_entry(line)
                        if entry is None or not _fresh(entry, cutoff):
                            continue
                        key = (str(entry.get("session", "")), str(entry["path"]))
                        if key in seen:
                            continue
                        seen.add(key)
                        entries.append(entry)
                except OSError:
                    pass

            for file_path in new_paths:
                key = (session_id, file_path)
                if key in seen:
                    if agent_id:
                        continue  # any existing entry already covers a subagent read
                    # A main-thread read upgrades a subagent-tagged entry: drop
                    # it and append an untagged one below. seen holds one
                    # entry per key, so at most one entry matches.
                    idx = next(
                        (i for i, e in enumerate(entries) if (str(e.get("session", "")), str(e["path"])) == key),
                        None,
                    )
                    if idx is None or not entries[idx].get("agent"):
                        continue
                    del entries[idx]
                seen.add(key)
                entry = {"ts": now.isoformat(), "session": session_id, "path": file_path}
                if agent_id:
                    entry["agent"] = agent_id
                entries.append(entry)

            _write_atomic(reads_path, "".join(json.dumps(e) + "\n" for e in entries))

        # Silent output — no context injection
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("posttool-session-reads", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
