#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Proactive Learning Injection

Injects relevant error patterns from learning.db BEFORE Bash/Edit tools run,
using the additionalContext return mechanism. This is proactive rather than
reactive — we warn about known pitfalls before the tool hits them.

Complements error-learner.py (PostToolUse) which learns AFTER errors happen.

Design Principles:
- Early-exit for non-target tools (Read, Glob, Grep, etc.)
- Sub-50ms execution (fires on EVERY tool use)
- Non-blocking (always exits 0)
- Lightweight output (max 500 chars to avoid context bloat)
- Only injects for high-confidence patterns (>= 0.7)
"""

import json
import os
import re
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output
from stdin_timeout import read_stdin

EVENT_NAME = "PreToolUse"

# Max characters in the injected context to stay lightweight
MAX_CONTEXT_CHARS = 500

# Max DB results to fetch
MAX_RESULTS = 3

# Minimum confidence for injection
MIN_CONFIDENCE = 0.7

# Keywords extracted from commands that map to learnable domains.
# These are intentionally broad — the DB query narrows via tag matching.
COMMAND_KEYWORD_PATTERNS = [
    # Build/test tools
    (re.compile(r"\b(go\s+(?:test|build|run|vet|mod))\b"), ["go", "golang"]),
    (re.compile(r"\b(cargo\s+(?:test|build|run|check))\b"), ["rust", "cargo"]),
    (re.compile(r"\b(npm\s+(?:test|run|install|build))\b"), ["npm", "javascript", "typescript"]),
    (re.compile(r"\b(pytest|python3?\s+-m\s+pytest)\b"), ["python", "pytest"]),
    (re.compile(r"\b(make|cmake)\b"), ["make", "build"]),
    # Package managers
    (re.compile(r"\b(pip\s+install|pip3\s+install)\b"), ["python", "pip", "import_error"]),
    (re.compile(r"\b(yarn|pnpm)\b"), ["javascript", "typescript"]),
    # Docker/K8s
    (re.compile(r"\b(docker|podman)\b"), ["docker", "container"]),
    (re.compile(r"\b(kubectl|helm)\b"), ["kubernetes", "k8s"]),
    # Common error-prone operations
    (re.compile(r"\b(chmod|chown|sudo)\b"), ["permissions"]),
    (re.compile(r"\b(curl|wget|fetch)\b"), ["connection", "timeout"]),
    (re.compile(r"\b(git\s+(?:push|pull|rebase|merge|checkout))\b"), ["git"]),
]

# For Edit tool: extract keywords from the file path
EDIT_FILE_PATTERNS = [
    (re.compile(r"\.go$"), ["go", "golang"]),
    (re.compile(r"\.py$"), ["python"]),
    (re.compile(r"\.ts$"), ["typescript"]),
    (re.compile(r"\.tsx$"), ["typescript", "react"]),
    (re.compile(r"\.js$"), ["javascript"]),
    (re.compile(r"\.rs$"), ["rust"]),
    (re.compile(r"Dockerfile"), ["docker"]),
    (re.compile(r"\.ya?ml$"), ["yaml", "kubernetes"]),
]


def extract_bash_tags(command: str) -> list[str]:
    """Extract relevant tags from a Bash command string."""
    tags = set()
    for pattern, keywords in COMMAND_KEYWORD_PATTERNS:
        if pattern.search(command):
            tags.update(keywords)

    # If no pattern matched, try to extract the base command
    if not tags:
        # Get first word (the command itself)
        parts = command.strip().split()
        if parts:
            base_cmd = parts[0].split("/")[-1]  # strip path prefix
            if len(base_cmd) > 1:
                tags.add(base_cmd)

    return list(tags)[:10]  # Cap at 10 tags


def extract_edit_tags(tool_input: dict) -> list[str]:
    """Extract relevant tags from an Edit tool input."""
    tags = set()
    file_path = tool_input.get("file_path", "")

    for pattern, keywords in EDIT_FILE_PATTERNS:
        if pattern.search(file_path):
            tags.update(keywords)

    # Check if old_string or new_string hints at error-prone patterns
    old_string = tool_input.get("old_string", "")
    if old_string:
        # The Edit tool's multiple_matches error is common
        tags.add("multiple_matches")

    return list(tags)[:10]


def format_hints(results: list[dict]) -> str:
    """Format DB results as a compact hint string.

    Stays within MAX_CONTEXT_CHARS budget.
    """
    lines = ["[learning-hint] Known patterns for this operation:"]
    chars = len(lines[0])

    for r in results:
        # Build a one-line summary from the value field
        value = r.get("value", "")
        first_line = value.split("\n")[0]

        # If value has " -> " separator (error -> solution format), use the solution part
        if " -> " in first_line:
            summary = first_line.split(" -> ", 1)[1][:120]
        else:
            summary = first_line[:120]

        category = r.get("category", "")
        error_type = r.get("error_type", "")
        label = error_type or category or r.get("topic", "hint")

        line = f"- [{label}]: {summary}"
        if chars + len(line) + 1 > MAX_CONTEXT_CHARS:
            break
        lines.append(line)
        chars += len(line) + 1

    # Only return if we have actual hints (more than just the header)
    if len(lines) <= 1:
        return ""

    return "\n".join(lines)


def main():
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            empty_output(EVENT_NAME).print_and_exit()

        event = json.loads(event_data)

        # tool_name filter removed — matcher "Bash|Edit" in settings.json prevents
        # this hook from spawning for non-matching tools.
        tool_name = event.get("tool_name", "")
        tool_input = event.get("tool_input", {})

        # Extract tags based on tool type
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if not command:
                empty_output(EVENT_NAME).print_and_exit()
            tags = extract_bash_tags(command)
        elif tool_name == "Edit":
            tags = extract_edit_tags(tool_input)
        else:
            empty_output(EVENT_NAME).print_and_exit()

        if not tags:
            empty_output(EVENT_NAME).print_and_exit()

        # Query learning.db for matching patterns via FTS5 full-text search
        # Lazy import to avoid paying cost when early-exiting
        from learning_db_v2 import search_learnings

        query_str = " OR ".join(tags)
        results = search_learnings(
            query_str,
            min_confidence=MIN_CONFIDENCE,
            exclude_graduated=True,
            limit=MAX_RESULTS,
        )

        if not results:
            if debug:
                print(f"[pretool] No patterns for tags={tags}", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Format and inject
        hint_text = format_hints(results)
        if not hint_text:
            empty_output(EVENT_NAME).print_and_exit()

        if debug:
            print(
                f"[pretool] Injecting {len(results)} hints for {tool_name} tags={tags}",
                file=sys.stderr,
            )

        context_output(EVENT_NAME, hint_text).print_and_exit()

    except json.JSONDecodeError:
        if debug:
            print("[pretool] Invalid JSON input", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
    except Exception as e:
        if debug:
            print(f"[pretool] Error: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
