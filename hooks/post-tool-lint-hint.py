#!/usr/bin/env python3
"""PostToolUse hook: suggest available linters after file modifications.

Fires on Write|Edit. Checks the file extension and suggests the appropriate
linter if one exists. Only hints once per extension per session to keep noise
low. Always exits 0 — this hook is advisory only.
"""

import json
import os
import sys
from pathlib import Path

# Map file extensions to linter suggestions
LINTER_MAP = {
    ".py": "ruff check --fix {file} && ruff format {file}",
    ".go": "gofmt -w {file}",
    ".js": "biome check --write {file}",
    ".ts": "biome check --write {file}",
    ".tsx": "biome check --write {file}",
    ".jsx": "biome check --write {file}",
    ".rs": "cargo fmt",
    ".rb": "rubocop -a {file}",
    ".sh": "shellcheck {file}",
    ".bash": "shellcheck {file}",
}

# Session-scoped dedup: one hint per extension per session
SEEN_FILE = Path(f"/tmp/claude_lint_hints_seen_{os.getppid()}.txt")


def get_seen_extensions() -> set[str]:
    """Load extensions we've already hinted about this session."""
    try:
        return set(SEEN_FILE.read_text().splitlines())
    except FileNotFoundError:
        return set()


def mark_seen(ext: str) -> None:
    """Record that we've hinted about this extension."""
    seen = get_seen_extensions()
    seen.add(ext)
    SEEN_FILE.write_text("\n".join(sorted(seen)))


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    file_path = event.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    ext = Path(file_path).suffix.lower()
    if ext not in LINTER_MAP:
        return

    if ext in get_seen_extensions():
        return

    linter_cmd = LINTER_MAP[ext].format(file=file_path)
    print(f"[lint-hint] Consider running: {linter_cmd}")
    mark_seen(ext)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Advisory hook — exit 0 on all errors
