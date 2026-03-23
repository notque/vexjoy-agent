#!/usr/bin/env python3
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
    re.compile(r"/pipelines/[^/]+/SKILL\.md$"),
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
# INJECTION PATTERNS — compiled at module level for performance
# ═══════════════════════════════════════════════════════════════

# Each entry: (compiled_regex, category, risk_description)
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # 1. Instruction override
    (
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        "instruction-override",
        "Attempts to override prior instructions",
    ),
    (
        re.compile(r"disregard\s+(all\s+)?(previous|above|prior)", re.IGNORECASE),
        "instruction-override",
        "Attempts to disregard prior context",
    ),
    (
        re.compile(r"forget\s+(all\s+)?your\s+instructions", re.IGNORECASE),
        "instruction-override",
        "Attempts to clear agent instructions",
    ),
    (
        re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
        "instruction-override",
        "Attempts to inject new instructions",
    ),
    (
        re.compile(r"override\s+(all\s+)?(system|safety|security)\s+(prompt|instructions|rules)", re.IGNORECASE),
        "instruction-override",
        "Attempts to override system safety rules",
    ),
    # 2. Role hijacking
    (
        re.compile(r"you\s+are\s+now\s+a\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to reassign agent identity",
    ),
    (
        re.compile(r"pretend\s+you'?re\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to make agent assume false identity",
    ),
    (
        re.compile(
            r"from\s+now\s+on\s+you\s+(are|will|should|must)\b", re.IGNORECASE
        ),
        "role-hijacking",
        "Attempts to permanently alter agent behavior",
    ),
    (
        re.compile(r"\b(admin|developer|jailbreak)\s+mode\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts to activate privileged mode",
    ),
    (
        re.compile(r"\bact\s+as\s+(root|admin|sudo)\b", re.IGNORECASE),
        "role-hijacking",
        "Attempts authority escalation",
    ),
    # 3. Prompt extraction
    (
        re.compile(
            r"(print|output|reveal|show|repeat|display)\s+(your\s+)?(system\s+prompt|instructions|rules|system\s+message)",
            re.IGNORECASE,
        ),
        "prompt-extraction",
        "Attempts to extract system prompt or instructions",
    ),
    (
        re.compile(r"what\s+are\s+your\s+(rules|instructions|constraints)", re.IGNORECASE),
        "prompt-extraction",
        "Probes for agent configuration details",
    ),
    # 4. Fake message boundaries
    (
        re.compile(r"</?system>", re.IGNORECASE),
        "fake-boundary",
        "Fake <system> tag — attempts message boundary injection",
    ),
    (
        re.compile(r"</?assistant>", re.IGNORECASE),
        "fake-boundary",
        "Fake <assistant> tag — attempts message boundary injection",
    ),
    (
        re.compile(r"</?user>", re.IGNORECASE),
        "fake-boundary",
        "Fake <user> tag — attempts message boundary injection",
    ),
    (
        re.compile(r"\[SYSTEM\]"),
        "fake-boundary",
        "Fake [SYSTEM] marker — attempts boundary injection",
    ),
    (
        re.compile(r"\[INST\]"),
        "fake-boundary",
        "Fake [INST] marker — attempts Llama-style boundary injection",
    ),
    (
        re.compile(r"<<SYS>>"),
        "fake-boundary",
        "Fake <<SYS>> marker — attempts Llama-style system injection",
    ),
]

# 5. Invisible Unicode — checked separately (character-level scan)
_INVISIBLE_CODEPOINTS: dict[int, str] = {
    0x200B: "zero-width space",
    0x200C: "zero-width non-joiner",
    0x200D: "zero-width joiner",
    0x200E: "left-to-right mark",
    0x200F: "right-to-left mark",
    0x00AD: "soft hyphen",
    0x202A: "left-to-right embedding",
    0x202B: "right-to-left embedding",
    0x202C: "pop directional formatting",
    0x202D: "left-to-right override",
    0x202E: "right-to-left override",
    0xFEFF: "byte order mark (mid-text)",
    0x2060: "word joiner",
    0x2061: "function application",
    0x2062: "invisible times",
    0x2063: "invisible separator",
    0x2064: "invisible plus",
}


# ═══════════════════════════════════════════════════════════════
# SCANNING
# ═══════════════════════════════════════════════════════════════


def _scan_content(content: str, file_path: str) -> list[str]:
    """Scan content for injection patterns. Returns list of warning strings."""
    warnings = []

    # Split into lines for line-number reporting
    lines = content.split("\n")

    # Regex pattern scan
    for pattern, category, risk in _INJECTION_PATTERNS:
        for line_num, line in enumerate(lines, 1):
            if pattern.search(line):
                matched = line.strip()[:80]
                warnings.append(
                    f"[INJECTION-WARN] Potential prompt injection in {file_path}:{line_num}\n"
                    f"  Category: {category}\n"
                    f"  Pattern: {matched}\n"
                    f"  Risk: {risk}\n"
                    f"  Action: Review this content before it enters agent context"
                )
                break  # One warning per pattern per file is enough

    # Invisible Unicode scan — only if no massive content (performance guard)
    if len(content) < 500_000:
        invisible_found: dict[str, list[int]] = {}
        for line_num, line in enumerate(lines, 1):
            for char in line:
                cp = ord(char)
                if cp in _INVISIBLE_CODEPOINTS:
                    name = _INVISIBLE_CODEPOINTS[cp]
                    if name not in invisible_found:
                        invisible_found[name] = []
                    if len(invisible_found[name]) < 3:  # Cap locations
                        invisible_found[name].append(line_num)

        for name, line_nums in invisible_found.items():
            locations = ", ".join(f"line {n}" for n in line_nums)
            warnings.append(
                f"[INJECTION-WARN] Invisible Unicode in {file_path}\n"
                f"  Category: invisible-unicode\n"
                f"  Pattern: {name} (U+{_get_codepoint(name):04X}) at {locations}\n"
                f"  Risk: Hidden characters can conceal malicious content\n"
                f"  Action: Review this content before it enters agent context"
            )

    return warnings


def _get_codepoint(name: str) -> int:
    """Reverse lookup codepoint from name."""
    for cp, n in _INVISIBLE_CODEPOINTS.items():
        if n == name:
            return cp
    return 0


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

    # Field name compatibility: try new names first, fall back to old
    tool = event.get("tool_name") or event.get("tool", "")
    if tool not in ("Write", "Edit"):
        empty_output(EVENT_NAME).print_and_exit()

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
            print(
                f"[injection-scanner] Clean: {file_path}", file=sys.stderr
            )
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
