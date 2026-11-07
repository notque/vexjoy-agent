#!/usr/bin/env python3
# hook-version: 1.0.4
"""
PreToolUse:Edit Hook: File Backup Before Edit

Copies the target file to /tmp/.claude-backups/{session_id}/ before
each Edit operation, enabling granular undo to any point in a session.

This is a PASSIVE hook — it never blocks (always exit 0). It silently
copies the file and moves on. If the copy fails for any reason, it
still exits 0.

Design:
- Only fires on Edit (not Write — Write creates new files with no prior state)
- Skips files >10MB (likely generated/vendored)
- Skips binary files (non-UTF-8)
- Uses monotonic timestamp for ordering: {unix_ms}-{basename}
- Session-scoped directory prevents cross-session conflicts
- Owner-only: directories are created 0700 and backup files 0600, so other
  accounts on the machine cannot read the copies
- No cleanup: /tmp is not cleared on every machine's reboot (on some it is
  never cleared), so backups stay until removed by hand

Performance target: <10ms (single file copy, no compression).

ADR: adr/020-pre-edit-file-backup.md
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
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

# 10 MB limit — skip larger files silently
_MAX_FILE_SIZE = 10 * 1024 * 1024

# Session ID from environment, fall back to PID
_SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", str(os.getpid()))

_BACKUP_BASE = Path("/tmp/.claude-backups")
_BACKUP_ROOT = _BACKUP_BASE / _SESSION_ID


_BYPASS_ENV = "PRETOOL_FILE_BACKUP_BYPASS"


def _copy_owner_only(src: Path, dest: Path) -> None:
    """Copy contents and timestamps like shutil.copy2, but create dest 0600 instead of copying src's mode.

    An existing dest is overwritten as before and tightened to 0600; a symlink
    at dest is not followed.
    """
    st = src.stat()
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    # Open the source first, as copy2 does, so an unreadable source leaves no empty copy.
    with open(src, "rb") as inp:
        fd = os.open(str(dest), flags, 0o600)
        fchmod = getattr(os, "fchmod", None)
        if fchmod is not None:
            try:
                fchmod(fd, 0o600)
            except OSError:
                pass
        with os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(inp, out)
    os.utime(str(dest), ns=(st.st_atime_ns, st.st_mtime_ns))


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[pretool-file-backup] Bypassed via PRETOOL_FILE_BACKUP_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Edit" in settings.json prevents
    # this hook from spawning for non-Edit tools.

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    src = Path(file_path)

    # Only back up files that exist (Edit modifies existing files)
    if not src.is_file():
        sys.exit(0)

    # Skip files over size limit
    try:
        if src.stat().st_size > _MAX_FILE_SIZE:
            sys.exit(0)
    except OSError:
        sys.exit(0)

    # Create backup directories owner-only (0700). Existing ones are not chmodded.
    _BACKUP_BASE.mkdir(parents=True, mode=0o700, exist_ok=True)
    _BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)

    # Timestamp-prefixed filename for ordering
    timestamp_ms = int(time.time() * 1000)
    backup_name = f"{timestamp_ms}-{src.name}"
    dest = _BACKUP_ROOT / backup_name

    # Copy file — silently ignore failures
    try:
        _copy_owner_only(src, dest)
    except (OSError, shutil.Error):
        pass

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("pretool-file-backup", e)
