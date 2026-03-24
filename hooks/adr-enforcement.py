#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: ADR Compliance Enforcement

After every Write or Edit tool call on a pipeline component file, automatically
run adr-compliance.py and inject violations as feedback into the next context.

Design Principles:
- Non-blocking (always exits 0)
- Silent on non-pipeline files (no noise)
- Graceful degradation when adr-compliance.py not yet deployed
- Skips when no active ADR session (.adr-session.json absent)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, log_warning
from stdin_timeout import read_stdin

__EVENT_NAME = "PostToolUse"

# Pipeline component files that trigger enforcement (matched against repo-relative paths)
_PIPELINE_COMPONENT_PATTERNS = [
    r"^skills/[^/]+/SKILL\.md$",
    r"^agents/[^/]+\.md$",
    r"^scripts/[^/]+\.py$",
    r"^hooks/[^/]+\.py$",
]

# Repo-relative paths to exclude even if they match a component pattern
_EXCLUDE_PATTERNS = [
    r"^agents/INDEX\.json",
    r"^hooks/lib/",
    r"^hooks/adr-enforcement\.py$",
    r"^scripts/tests/",
    r"^scripts/__pycache__/",
]

# Reference files used by adr-compliance.py
__STEP_MENU = "~/.claude/skills/pipeline-scaffolder/references/step-menu.md"
__SPEC_FORMAT = "~/.claude/skills/pipeline-scaffolder/references/pipeline-spec-format.md"


def is_pipeline_component(file_path: str) -> bool:
    """Check if the file is a pipeline component that should be compliance-checked.

    Normalizes the path to be relative to the repo root before matching, so
    patterns like agents/ only match the top-level agents/ directory and not
    arbitrary path components.
    """
    try:
        repo_root = Path(__file__).parent.parent.resolve()
        abs_path = Path(file_path).resolve()
        rel_path = abs_path.relative_to(repo_root)
        rel_str = str(rel_path)
    except (ValueError, Exception):
        return False

    for exclude in _EXCLUDE_PATTERNS:
        if re.search(exclude, rel_str):
            return False

    return any(re.match(pattern, rel_str) for pattern in _PIPELINE_COMPONENT_PATTERNS)


def load_session(cwd: str) -> dict | None:
    """Load .adr-session.json from cwd. Returns None if absent or invalid."""
    session_path = Path(cwd) / ".adr-session.json"
    if not session_path.exists():
        return None
    try:
        with open(session_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def run_compliance_check(
    compliance_script: Path,
    file_path: str,
    cwd: str,
) -> dict | None:
    """
    Run adr-compliance.py check on the file.

    Returns parsed JSON output dict, or None on subprocess failure.
    """
    cmd = [
        sys.executable,
        str(compliance_script),
        "check",
        "--file",
        file_path,
        "--step-menu",
        _STEP_MENU,
        "--spec-format",
        _SPEC_FORMAT,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)
    except subprocess.TimeoutExpired:
        log_warning("adr-compliance.py timed out after 10s")
        return None
    except (json.JSONDecodeError, OSError):
        return None


def format_violations(file_path: str, check_result: dict) -> str:
    """Format violation output for context injection."""
    violations = check_result.get("violations", [])
    lines = []

    # Use a relative display path when possible
    display_path = file_path
    _chk = "COMPLIANCE CHECK"
    lines.append(f"[adr-enforcement] {_chk}: {display_path}")

    count = len(violations)
    _vf = "VIOLATIONS FOUND"
    lines.append(f"[adr-enforcement] {_vf} ({count}):")

    for v in violations:
        line_num = v.get("line", "?")
        v_type = v.get("type", "unknown")
        value = v.get("value", "")
        suggestion = v.get("suggestion", "")
        entry = f'  Line {line_num}: {v_type} "{value}"'
        if suggestion:
            entry += f" — {suggestion}"
        lines.append(f"[adr-enforcement] {entry}")

    lines.append("[adr-enforcement] FIX REQUIRED before proceeding:")
    lines.append(f"[adr-enforcement]   python3 ~/.claude/scripts/adr-compliance.py check --file {display_path} \\")
    lines.append(f"[adr-enforcement]     --step-menu {_STEP_MENU} \\")
    lines.append(f"[adr-enforcement]     --spec-format {_SPEC_FORMAT}")

    return "\n".join(lines)


def format_pass(file_path: str, check_result: dict) -> str:
    """Format PASS output for context injection."""
    display_path = file_path
    # Include grounding counts if available in result metadata
    meta = check_result.get("stats", {})
    step_count = meta.get("step_names_checked", 0)
    schema_count = meta.get("schema_types_checked", 0)

    if step_count or schema_count:
        detail = f"({step_count} step names, {schema_count} schema types grounded)"
        return f"[adr-enforcement] COMPLIANCE CHECK: {display_path} — PASS {detail}"
    return f"[adr-enforcement] COMPLIANCE CHECK: {display_path} — PASS"


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        event = json.loads(raw)

        # Only process PostToolUse events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != _EVENT_NAME:
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Only act on Write or Edit tool calls
        tool_name = event.get("tool_name", "")
        if tool_name not in ("Write", "Edit"):
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Extract file path from tool input
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Check scope — only pipeline component files
        if not is_pipeline_component(file_path):
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Determine cwd
        cwd = event.get("cwd", str(Path.cwd()))

        # Check for active ADR session
        session = load_session(cwd)
        if session is None:
            # No active session — skip silently
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Locate adr-compliance.py
        compliance_script = Path(cwd) / "scripts" / "adr-compliance.py"
        if not compliance_script.exists():
            log_warning(
                f"adr-compliance.py not found at {compliance_script} — "
                "ADR enforcement inactive (system not yet deployed)"
            )
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Run compliance check
        check_result = run_compliance_check(compliance_script, file_path, cwd)
        if check_result is None:
            # Subprocess failed or returned no JSON — skip silently
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        verdict = check_result.get("verdict", "unknown")

        if verdict == "FAIL":
            context = format_violations(file_path, check_result)
        else:
            context = format_pass(file_path, check_result)

        context_output(_EVENT_NAME, context).print_and_exit(0)

    except (json.JSONDecodeError, KeyError, TypeError):
        empty_output(_EVENT_NAME).print_and_exit(0)
    except Exception:
        empty_output(_EVENT_NAME).print_and_exit(0)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
