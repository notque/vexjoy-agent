#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: ADR Session Health Check

Detects orphaned .adr-session.json files at session start.
An orphaned session is one where .adr-session.json exists but the
referenced adr_file path does not exist on disk.

This is an ADVISORY injection — no deny, no block. Surfaces the issue
in additionalContext before the synthesis gate has a chance to deadlock.

Detection logic:
- .adr-session.json exists in CLAUDE_PROJECT_DIR
- The adr_file (or adr_path) field references a path that does not exist

Injection conditions:
- Orphaned: injects a warning with the stale path and instructions to clear it
- Healthy with active session: injects a brief status line (domain + adr_path)
- No .adr-session.json: silent (empty output)

Design:
- Non-blocking (always exits 0)
- Fast execution (<50ms — pure file reads, no subprocess)
- Stderr-only debugging
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output

EVENT_NAME = "SessionStart"


def _load_session(project_dir: Path) -> dict | None:
    """Load .adr-session.json from project_dir. Returns None if absent or malformed."""
    session_path = project_dir / ".adr-session.json"
    if not session_path.is_file():
        return None
    try:
        return json.loads(session_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _resolve_adr_path(session: dict, project_dir: Path) -> tuple[str | None, bool]:
    """Return (adr_path_str, exists_on_disk).

    Checks both 'adr_path' and 'adr_file' keys (different versions of the schema
    use different field names). Resolves relative paths against project_dir.
    Returns (None, False) if no path field found.
    """
    raw_path = session.get("adr_path") or session.get("adr_file")
    if not raw_path:
        return None, False

    adr_path = Path(raw_path)
    if not adr_path.is_absolute():
        adr_path = project_dir / adr_path

    return str(raw_path), adr_path.exists()


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    # Resolve project directory: CLAUDE_PROJECT_DIR > cwd
    project_dir_str = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    project_dir = Path(project_dir_str).resolve()

    session = _load_session(project_dir)
    if session is None:
        if debug:
            print("[adr-health-check] No .adr-session.json found — silent pass", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    adr_path_raw, adr_exists = _resolve_adr_path(session, project_dir)
    domain = session.get("domain", "")
    registered_at = session.get("registered_at", "")

    if debug:
        print(
            f"[adr-health-check] session found: domain={domain!r} adr_path={adr_path_raw!r} exists={adr_exists}",
            file=sys.stderr,
        )

    if adr_path_raw is None:
        # Session exists but has no adr_path / adr_file field — unusual schema
        msg = (
            "[adr-health-check] WARNING: .adr-session.json exists but has no adr_path or adr_file field. "
            "The synthesis gate may behave unexpectedly. "
            "Clear it with: rm .adr-session.json"
        )
        context_output(EVENT_NAME, msg).print_and_exit()
        return

    if not adr_exists:
        # Orphaned session — the referenced ADR file is gone
        msg = (
            f"[adr-health-check] WARNING: Orphaned .adr-session.json detected.\n"
            f"  Referenced ADR path does not exist: {adr_path_raw}\n"
            f"  Domain: {domain or '(unknown)'}\n"
            f"  Registered at: {registered_at or '(unknown)'}\n"
            f"\n"
            f"  The pretool-synthesis-gate will block all agents/ and skills/ writes "
            f"until this is resolved.\n"
            f"\n"
            f"  To clear the orphaned session:\n"
            f"    rm {project_dir}/.adr-session.json\n"
            f"\n"
            f"  If this ADR is still active, restore the ADR file at:\n"
            f"    {adr_path_raw}"
        )
        print(f"[adr-health-check] ORPHANED session: {adr_path_raw} does not exist", file=sys.stderr)
        context_output(EVENT_NAME, msg).print_and_exit()
        return

    # Healthy active session — surface a brief status line
    status = f"[adr-health-check] Active ADR session: domain={domain!r} adr={adr_path_raw}"
    if debug:
        print(status, file=sys.stderr)
    context_output(EVENT_NAME, status).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[adr-health-check] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # Crashed hook must fail open — never block session start.
    finally:
        sys.exit(0)
