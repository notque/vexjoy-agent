#!/usr/bin/env python3
# hook-version: 1.0.2
"""
Stop Hook: Session Summary and Metrics

Generates a summary when the conversation ends and persists session metrics
to the unified learning database (learning_db_v2).

Design Principles:
- Comprehensive session tracking
- Persistent metrics storage
- Silent on empty sessions
- Non-blocking (always exits 0)
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
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import get_session_id, hook_error
from learning_db_v2 import get_stats, record_session
from stdin_timeout import read_stdin

_BYPASS_ENV = "SESSION_SUMMARY_BYPASS"


def main():
    """Generate session summary on conversation end."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[session-summary] Bypassed via SESSION_SUMMARY_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        event_data = read_stdin(timeout=2)
        cwd = os.getcwd()

        # Generate session ID
        session_id = get_session_id()

        if event_data:
            try:
                event = json.loads(event_data)
                # Extract metrics if available
                session_data = event.get("session_data", {})
                files_modified = len(session_data.get("files_modified", []))
                tools_used = len(session_data.get("tool_uses", []))
                errors = session_data.get("errors_encountered", 0)
                resolved = session_data.get("errors_resolved", 0)
            except (json.JSONDecodeError, KeyError):
                files_modified = 0
                tools_used = 0
                errors = 0
                resolved = 0
        else:
            files_modified = 0
            tools_used = 0
            errors = 0
            resolved = 0

        # Record session
        record_session(
            session_id,
            files_modified=files_modified,
            tools_used=tools_used,
            errors_encountered=errors,
            errors_resolved=resolved,
            project_path=cwd,
            end_session=True,
        )

        # Get stats
        stats = get_stats()

        total_learnings = stats.get("total_learnings", 0)
        high_conf = stats.get("high_confidence", 0)
        total_sessions = stats.get("sessions_tracked", 0)

        if total_learnings > 0 or total_sessions > 1:
            print("[session-summary] Session ended")
            print(f"[session-summary] Learning: {high_conf}/{total_learnings} high-confidence")
            print(f"[session-summary] Total sessions: {total_sessions}")

    except Exception as e:
        hook_error("session-summary", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
