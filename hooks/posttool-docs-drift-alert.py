#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Claude Code hook: Alert when documentation may be out of sync after file writes.

Fires after Write/Edit operations on INDEX.json, routing-tables.md, or agents/*.md
files. Runs the docs-sync-checker scanner when available, or falls back to a simple
file-count comparison between agents/INDEX.json and the agents/ directory on disk.

Event: PostToolUse (Write, Edit)
Filters: INDEX.json, routing-tables.md, agents/*.md, skills/INDEX.json, agents/INDEX.json
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Files that trigger a drift check when modified
_TRIGGER_NAMES = frozenset({"INDEX.json", "routing-tables.md"})

# Repo root — derived relative to this hook's location (hooks/ → repo root)
_REPO_ROOT = Path(__file__).parent.parent


def _is_watched_file(file_path: str) -> bool:
    """Return True if the modified file should trigger a drift check.

    Matches:
    - Any file named INDEX.json
    - Any file named routing-tables.md
    - Any *.md file inside an agents/ directory segment
    - skills/INDEX.json
    - agents/INDEX.json
    """
    path = Path(file_path)
    name = path.name

    if name in _TRIGGER_NAMES:
        return True

    # agents/*.md (any depth, excludes INDEX.md and README.md)
    parts = path.parts
    if "agents" in parts and name.endswith(".md") and name not in {"INDEX.md", "README.md"}:
        return True

    return False


def _run_scan_tools() -> tuple[bool, str]:
    """Run docs-sync-checker/scripts/scan_tools.py if it exists.

    Returns:
        (drift_detected, message)
    """
    script = _REPO_ROOT / "skills" / "docs-sync-checker" / "scripts" / "scan_tools.py"
    if not script.exists():
        return False, ""

    try:
        result = subprocess.run(
            ["python3", str(script), "--repo-root", str(_REPO_ROOT)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return True, f"scan_tools.py exited {result.returncode}: {result.stderr[:300]}"
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""
    except FileNotFoundError:
        return False, ""


def _fallback_count_check() -> tuple[bool, str]:
    """Compare agent .md file count on disk vs entries in agents/INDEX.json.

    Returns:
        (drift_detected, message)
    """
    agents_dir = _REPO_ROOT / "agents"
    index_path = agents_dir / "INDEX.json"

    if not agents_dir.is_dir() or not index_path.exists():
        return False, ""

    # Count .md files in agents/, excluding INDEX.md and README.md
    disk_files = [
        f for f in agents_dir.iterdir() if f.is_file() and f.suffix == ".md" and f.name not in {"INDEX.md", "README.md"}
    ]
    disk_count = len(disk_files)

    try:
        with open(index_path, encoding="utf-8") as fh:
            index_data = json.load(fh)
        index_count = len(index_data.get("agents", {}))
    except (json.JSONDecodeError, OSError):
        return False, ""

    if disk_count != index_count:
        return True, (
            f"agents/INDEX.json lists {index_count} agent(s) but {disk_count} .md file(s) "
            f"found on disk — run `python3 scripts/generate-agent-index.py` to regenerate"
        )

    return False, ""


def _check_drift() -> tuple[bool, str]:
    """Run drift detection: prefer scan_tools.py, fall back to count check."""
    drift, msg = _run_scan_tools()
    if drift:
        return drift, msg
    if not msg:
        # scan_tools.py either passed or was absent — run fallback regardless
        return _fallback_count_check()
    return False, ""


def main() -> None:
    """Main hook entry point."""
    hook_input: dict | None = None

    # Read from stdin with timeout protection
    if not sys.stdin.isatty():
        raw = read_stdin(timeout=2)
        if raw:
            try:
                hook_input = json.loads(raw)
            except json.JSONDecodeError:
                pass

    # Fall back to temp file (shared stdin cache used by hook chain)
    if not hook_input:
        try:
            with open("/tmp/claude_hook_stdin.json", encoding="utf-8") as fh:
                hook_input = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return

    if not hook_input:
        return

    # Extract file_path from tool_input
    tool_input_data = hook_input.get("tool_input", {})
    if isinstance(tool_input_data, str):
        try:
            tool_input_data = json.loads(tool_input_data)
        except (json.JSONDecodeError, TypeError):
            return

    file_path = tool_input_data.get("file_path", "") if isinstance(tool_input_data, dict) else ""

    if not file_path or not _is_watched_file(file_path):
        return

    drift_detected, message = _check_drift()

    if drift_detected and message:
        print(f"[docs-drift] WARNING: {message}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[docs-drift] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
