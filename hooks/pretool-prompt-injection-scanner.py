#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Prompt Injection Scanner (self-filters to Write and Edit)

Scans content written to agent context files for LLM-level prompt injection
patterns: instruction overrides, role hijacking, prompt extraction, fake
message boundaries, and invisible Unicode characters.

ADVISORY ONLY — outputs warnings via additionalContext, never blocks (exit 0).
Files that legitimately discuss injection (security docs, this ADR, test
fixtures) would be blocked by a hard gate. The goal is awareness, not prevention.

Scope: Only fires on files targeting agent context paths — skills, agents,
hooks, task plans, handoff files, ADRs, and CLAUDE.md files.

Performance target: <50ms. Compiled regex patterns loaded at module level.

ADR: adr/070-prompt-injection-defense-layer.md
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output
from injection_patterns import scan_content as _scan_patterns
from stdin_timeout import read_stdin

EVENT_NAME = "PreToolUse"

# ═══════════════════════════════════════════════════════════════
# CONTEXT PATH PATTERNS — only scan files that enter agent context
# ═══════════════════════════════════════════════════════════════

_CONTEXT_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"/agents/[^/]+\.md$"),
    re.compile(r"/skills/[^/]+/SKILL\.md$"),
    re.compile(r"/hooks/[^/]+\.py$"),
    re.compile(r"/commands/[^/]+/SKILL\.md$"),
    re.compile(r"/adr/[^/]+\.md$"),
    re.compile(r"CLAUDE\.md$"),
    re.compile(r"task_plan\.md$"),
    re.compile(r"HANDOFF\.json$"),
    re.compile(r"\.continue-here\.md$"),
]


_SELF_EXCLUDE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"pretool-prompt-injection-scanner\.py$"),
    re.compile(r"/adr/070-prompt-injection-defense-layer\.md$"),
]


def _is_context_file(file_path: str) -> bool:
    """Check if the file path targets an agent context file (excluding self)."""
    if any(p.search(file_path) for p in _SELF_EXCLUDE_PATTERNS):
        return False
    return any(p.search(file_path) for p in _CONTEXT_PATH_PATTERNS)


# ═══════════════════════════════════════════════════════════════
# SCANNING
# ═══════════════════════════════════════════════════════════════


def _scan_content(content: str, file_path: str) -> list[str]:
    """Scan content for injection patterns. Returns list of warning strings."""
    findings = _scan_patterns(content, source_label=file_path)
    warnings = []
    for f in findings:
        if f["category"] == "invisible-unicode":
            warnings.append(
                f"[INJECTION-WARN] Invisible Unicode in {f['location']}\n"
                f"  Category: {f['category']}\n"
                f"  Pattern: {f['snippet']}\n"
                f"  Risk: {f['risk']}\n"
                f"  Action: Review this content before it enters agent context"
            )
        else:
            warnings.append(
                f"[INJECTION-WARN] Potential prompt injection in {f['location']}\n"
                f"  Category: {f['category']}\n"
                f"  Pattern: {f['snippet']}\n"
                f"  Risk: {f['risk']}\n"
                f"  Action: Review this content before it enters agent context"
            )
    return warnings


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)  # Must be under settings.json 3s external timeout
    if not raw:
        empty_output(EVENT_NAME).print_and_exit()

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[injection-scanner] JSON parse failed: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    # tool_name filter removed — matcher "Write|Edit" in settings.json prevents
    # this hook from spawning for non-matching tools.
    tool = event.get("tool_name") or event.get("tool", "")
    tool_input = event.get("tool_input", event.get("input", {}))
    file_path = tool_input.get("file_path", "")
    if not file_path:
        empty_output(EVENT_NAME).print_and_exit()

    # Only scan agent context files
    if not _is_context_file(file_path):
        empty_output(EVENT_NAME).print_and_exit()

    # Extract content to scan
    content = ""
    if tool == "Write":
        content = tool_input.get("content", "")
    elif tool == "Edit":
        # Scan new_string — the content being written into the file
        content = tool_input.get("new_string", "")

    if not content:
        empty_output(EVENT_NAME).print_and_exit()

    # Scan for injection patterns
    warnings = _scan_content(content, file_path)

    if not warnings:
        if debug:
            print(f"[injection-scanner] Clean: {file_path}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    # Format advisory output
    header = f"[injection-scanner] {len(warnings)} potential injection pattern(s) detected:"
    full_output = header + "\n\n" + "\n\n".join(warnings)

    if debug:
        print(
            f"[injection-scanner] {len(warnings)} warnings for {file_path}",
            file=sys.stderr,
        )

    context_output(EVENT_NAME, full_output).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Fail OPEN — advisory hook must never crash the session
        # But ALWAYS log so we know the scanner is broken
        print(f"[injection-scanner] FATAL: hook crashed: {e}", file=sys.stderr)
        sys.exit(0)
