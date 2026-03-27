#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Gentle Lint Reminder

After Write or Edit operations, provides a subtle reminder about
linting if the file type has an available linter.

Design Principles:
- SILENT by default (only speaks when relevant)
- Non-blocking (suggestions, not requirements)
- Respects user flow (doesn't interrupt multi-file edits)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# File extensions and their linters
LINTERS = {
    ".py": "ruff check --fix",
    ".go": "gofmt -w",
    ".ts": "biome check --write",
    ".tsx": "biome check --write",
    ".js": "biome check --write",
    ".jsx": "biome check --write",
}

# Track files modified in this session (hint once per extension)
# Use PID to avoid conflicts between concurrent Claude instances
SEEN_EXTENSIONS_FILE = Path(f"/tmp/claude_lint_hints_seen_{os.getppid()}.txt")


def get_seen_extensions() -> set:
    """Get extensions we've already hinted about."""
    try:
        if SEEN_EXTENSIONS_FILE.exists():
            return set(SEEN_EXTENSIONS_FILE.read_text().strip().split("\n"))
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[lint-hint] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    return set()


def mark_extension_seen(ext: str):
    """Mark an extension as hinted."""
    try:
        seen = get_seen_extensions()
        seen.add(ext)
        SEEN_EXTENSIONS_FILE.write_text("\n".join(seen))
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[lint-hint] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


def main():
    """Process PostToolUse hook event."""
    try:
        event_data = read_stdin(timeout=2)
        event = json.loads(event_data)

        # tool_name/event_type filters removed — matcher "Write|Edit" in settings.json
        # prevents this hook from spawning for non-matching tools.

        # Get the file path from tool input
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path:
            return

        # Check if this file type has a linter
        ext = Path(file_path).suffix.lower()
        if ext not in LINTERS:
            return

        # Only hint once per extension per session
        seen = get_seen_extensions()
        if ext in seen:
            return

        mark_extension_seen(ext)

        # Gentle, non-intrusive hint
        linter = LINTERS[ext]
        filename = Path(file_path).name
        print(f"[lint-hint] {filename} modified. Consider: {linter}")

    except (json.JSONDecodeError, Exception) as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[lint-hint] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)


if __name__ == "__main__":
    main()
