#!/usr/bin/env python3
# hook-version: 1.1.0
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
- Keyed on the event's session_id (Claude Code never sets CLAUDE_SESSION_ID),
  so one session's backups share one directory
- Retention: when a session makes its directory, session directories not
  touched for 7 days are removed. /tmp is not cleared on every machine's
  reboot, so without this they would pile up

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
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import get_session_id, hook_error
from stdin_timeout import read_stdin

# 10 MB limit — skip larger files silently
_MAX_FILE_SIZE = 10 * 1024 * 1024

_BACKUP_BASE = Path(tempfile.gettempdir()) / ".claude-backups" if os.name == "nt" else Path("/tmp/.claude-backups")

# Session directories untouched this long are removed when a new session starts backing up.
_RETENTION_SECONDS = 7 * 24 * 3600


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


def _prune_old_sessions(keep: Path) -> None:
    """Remove this user's session directories not modified within the retention window.

    Adding a backup updates its directory's mtime, so a session that still edits keeps its copies.
    Failures are ignored: pruning never affects the backup itself.
    """
    cutoff = time.time() - _RETENTION_SECONDS
    uid = os.getuid() if hasattr(os, "getuid") else None
    try:
        entries = list(_BACKUP_BASE.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry == keep or entry.is_symlink() or not entry.is_dir():
                continue
            st = entry.stat()
            if (uid is not None and st.st_uid != uid) or st.st_mtime >= cutoff:
                continue
            shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


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

    backup_root = _BACKUP_BASE / get_session_id(event)

    # Create backup directories owner-only (0700). Existing ones are not chmodded.
    _BACKUP_BASE.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        backup_root.mkdir(mode=0o700)
    except FileExistsError:
        pass
    else:
        # First backup of this session: clear out stale sessions once, not on every Edit.
        _prune_old_sessions(backup_root)

    # Timestamp-prefixed filename for ordering
    timestamp_ms = int(time.time() * 1000)
    backup_name = f"{timestamp_ms}-{src.name}"
    dest = backup_root / backup_name

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
