#!/usr/bin/env python3
# hook-version: 3.0.0
"""
SessionStart Hook: Retro Knowledge Auto-Injection — stub retained for settings.json compatibility.

Previously queried learning.db for top-N highest-confidence patterns and injected
them as a <retro-knowledge> block at session start (brute-force selection by confidence).

Replaced by ADR-147 Auto-Dream: the nightly dream cycle (claude -p at 2 AM) now does
ALL semantic selection work and writes a pre-built injection payload to:
  ~/.claude/state/dream-injection-{project-hash}.md

The injection of that payload is handled by session-context.py (the SessionStart hook),
which reads the pre-built file directly — pure file read, no learning.db queries.

File kept so settings.json registration does not break. Hook does nothing.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output


def main():
    empty_output("SessionStart").print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[retro-knowledge-injector] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # ALWAYS exit 0 — non-blocking requirement
