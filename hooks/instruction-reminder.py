#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit hook to periodically re-inject instruction files.

Combats context drift in long-running sessions by re-surfacing project instructions.
Supports: CLAUDE.md, AGENTS.md, RULES.md

Inspired by the claude-md-reminder.sh pattern.
Uses shared hook utilities for consistent output formatting.
"""

import fcntl
import os
import sys
from pathlib import Path

# Add lib to path for hook_utils import
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import (
    EXCLUDE_DIRS,
    context_output,
    empty_output,
    get_project_dir,
    get_state_file,
)

# Configuration
THROTTLE_INTERVAL = 3  # Re-inject every N prompts
INSTRUCTION_FILES = ["CLAUDE.md", "AGENTS.md", "RULES.md"]


def get_prompt_count() -> int:
    """Get and increment the prompt count with file locking for concurrent safety."""
    state_file = get_state_file("instruction-reminder")
    count = 0

    try:
        # Open or create the file
        with open(state_file, "a+") as f:
            # Acquire exclusive lock for concurrent safety
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                # Read current count
                f.seek(0)
                content = f.read().strip()
                if content:
                    count = int(content)

                # Increment and write back
                count += 1
                f.seek(0)
                f.truncate()
                f.write(str(count))
            finally:
                # Release lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (ValueError, OSError):
        count = 1  # Default to 1 on error

    return count


def discover_instruction_files(project_dir: Path) -> list[Path]:
    """Discover all instruction files in project and global locations."""
    found_files = []

    for file_name in INSTRUCTION_FILES:
        # 1. Global file (~/.claude/CLAUDE.md, etc.)
        global_file = Path.home() / ".claude" / file_name
        if global_file.exists():
            found_files.append(global_file)

        # 2. Project root file
        project_file = project_dir / file_name
        if project_file.exists():
            found_files.append(project_file)

        # 3. Subdirectory files (recursive, with exclusions)
        try:
            for child in project_dir.rglob(file_name):
                # Skip excluded directories
                if any(part in EXCLUDE_DIRS for part in child.parts):
                    continue
                # Skip symlinks for security (prevent traversal attacks)
                if child.is_symlink():
                    continue
                if child not in found_files:
                    found_files.append(child)
        except OSError:
            # Best-effort discovery: if we hit a filesystem error while walking
            # the project tree (e.g., permission issues), skip recursive
            # discovery for this pattern rather than failing the hook.
            pass

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in found_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    return unique_files


def get_display_path(file_path: Path, project_dir: Path) -> str:
    """Get a display-friendly path for the file."""
    home = Path.home()

    if str(file_path).startswith(str(home / ".claude")):
        return f"~/.claude/{file_path.name} (global)"

    try:
        rel_path = file_path.relative_to(project_dir)
        return str(rel_path)
    except ValueError:
        return file_path.name


def get_file_emoji(file_name: str) -> str:
    """Get emoji for file type."""
    emojis = {
        "CLAUDE.md": "📋",
        "AGENTS.md": "🤖",
        "RULES.md": "📜",
    }
    return emojis.get(file_name, "📄")


def build_reminder_content(files: list[Path], project_dir: Path, prompt_count: int) -> str:
    """Build the reminder content with all instruction files."""
    sections = []

    sections.append("<instruction-files-reminder>")
    sections.append(f"Re-reading instruction files to combat context drift (prompt {prompt_count}):\n")

    for file_path in files:
        display_path = get_display_path(file_path, project_dir)
        emoji = get_file_emoji(file_path.name)

        sections.append("━" * 50)
        sections.append(f"{emoji} {display_path}")
        sections.append("━" * 50)
        sections.append("")

        try:
            content = file_path.read_text(encoding="utf-8")
            sections.append(content)
            sections.append("")
        except OSError as e:
            sections.append(f"[Error reading file: {e}]")
            sections.append("")

    sections.append("</instruction-files-reminder>")

    # Add agent usage reminder
    agent_reminder = """
<agent-usage-reminder>
CONTEXT CHECK: Before using Glob/Grep/Read chains, consider agents:

| Task | Agent |
|------|-------|
| Explore codebase | Explore |
| Multi-file search | Explore |
| Complex research | general-purpose |
| Code review | parallel-code-review skill (3 reviewers) |
| Go implementation | golang-general-engineer |
| Python implementation | python-general-engineer |

**3-File Rule:** If reading >3 files, use an agent instead. 15x more context-efficient.
</agent-usage-reminder>
"""
    sections.append(agent_reminder)

    # Add duplication prevention reminder
    duplication_guard = """
<duplication-prevention-guard>
**BEFORE ADDING CONTENT** to any file:
1. SEARCH FIRST: `grep -r 'keyword' --include='*.md'`
2. If exists -> REFERENCE it, don't copy
3. Canonical sources: CLAUDE.md (rules), docs/*.md (details)
4. NEVER duplicate - always link to single source of truth
</duplication-prevention-guard>
"""
    sections.append(duplication_guard)

    return "\n".join(sections)


def main():
    """Main entry point for the hook."""
    event_name = "UserPromptSubmit"

    # Get prompt count and check if we should inject
    prompt_count = get_prompt_count()

    if prompt_count % THROTTLE_INTERVAL != 0:
        # Not time to inject yet
        empty_output(event_name).print_and_exit()

    # Time to inject! Discover instruction files
    project_dir = get_project_dir()
    files = discover_instruction_files(project_dir)

    if not files:
        # No instruction files found
        empty_output(event_name).print_and_exit()

    # Build reminder content
    reminder = build_reminder_content(files, project_dir, prompt_count)

    # Output hook response with injected context
    context_output(event_name, reminder).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[instruction-reminder] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
