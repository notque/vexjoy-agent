#!/usr/bin/env python3
# hook-version: 1.0.0
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
- /tmp/ clears on reboot — no active cleanup needed

Performance target: <10ms (single file copy, no compression).

ADR: adr/020-pre-edit-file-backup.md
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# 10 MB limit — skip larger files silently
_MAX_FILE_SIZE = 10 * 1024 * 1024

# Session ID from environment, fall back to PID
_SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", str(os.getpid()))

_BACKUP_ROOT = Path("/tmp/.claude-backups") / _SESSION_ID


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name != "Edit":
        sys.exit(0)

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

    # Create backup directory
    _BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    # Timestamp-prefixed filename for ordering
    timestamp_ms = int(time.time() * 1000)
    backup_name = f"{timestamp_ms}-{src.name}"
    dest = _BACKUP_ROOT / backup_name

    # Copy file — silently ignore failures
    try:
        shutil.copy2(str(src), str(dest))
    except (OSError, shutil.Error):
        pass

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail OPEN — never block edits due to backup failure.
        sys.exit(0)
