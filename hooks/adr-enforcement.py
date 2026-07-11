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
import os
import re
import subprocess
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error, log_warning
from stdin_timeout import read_stdin

_EVENT_NAME = "PostToolUse"
_TRUSTED_ROOT = Path(__file__).resolve().parent.parent

# Pipeline component files that trigger enforcement (matched against repo-relative paths)
_PIPELINE_COMPONENT_PATTERNS = [
    r"^skills/(?:[^/]+/)?[^/]+/SKILL\.md$",
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
_STEP_MENU = "skills/workflow/references/pipeline-scaffolder/references/step-menu.md"
_SPEC_FORMAT = "skills/workflow/references/pipeline-scaffolder/references/pipeline-spec-format.md"


def _project_root(event: dict) -> Path:
    """Resolve the repository the hook event is operating on."""
    candidate = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()
    return Path(candidate).resolve()


def _project_relative_path(file_path: str, project_root: Path) -> Path | None:
    """Return ``file_path`` relative to the event project, or None if outside it."""
    try:
        path = Path(file_path)
        absolute = path.resolve() if path.is_absolute() else (project_root / path).resolve()
        return absolute.relative_to(project_root)
    except (OSError, ValueError):
        return None


def is_pipeline_component(file_path: str, project_root: Path | None = None) -> bool:
    """Check if the file is a pipeline component that should be compliance-checked.

    Normalizes the path to be relative to the repo root before matching, so
    patterns like agents/ only match the top-level agents/ directory and not
    arbitrary path components.
    """
    root = project_root or Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())).resolve()
    rel_path = _project_relative_path(file_path, root)
    if rel_path is None:
        return False
    rel_str = rel_path.as_posix()

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
    project_root: Path,
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
        str(project_root / file_path),
        "--step-menu",
        str(project_root / _STEP_MENU),
        "--spec-format",
        str(project_root / _SPEC_FORMAT),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(_TRUSTED_ROOT),
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
    lines.append(f"[adr-enforcement]   python3 scripts/adr-compliance.py check --file {display_path} \\")
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

        # tool_name/event_type filters removed — matcher "Write|Edit" in settings.json
        # prevents this hook from spawning for non-matching tools.

        # Extract file path from tool input
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        project_root = _project_root(event)
        relative_path = _project_relative_path(file_path, project_root)

        # Check scope — only pipeline component files in the event project.
        if relative_path is None or not is_pipeline_component(file_path, project_root):
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        cwd = str(project_root)
        display_path = relative_path.as_posix()

        # Check for active ADR session
        session = load_session(cwd)
        if session is None:
            # No active session — skip silently
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Locate adr-compliance.py
        compliance_script = _TRUSTED_ROOT / "scripts" / "adr-compliance.py"
        if not compliance_script.exists():
            log_warning(
                f"adr-compliance.py not found at {compliance_script} — "
                "ADR enforcement inactive (system not yet deployed)"
            )
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        # Run compliance check
        check_result = run_compliance_check(compliance_script, display_path, project_root)
        if check_result is None:
            # Subprocess failed or returned no JSON — skip silently
            empty_output(_EVENT_NAME).print_and_exit(0)
            return

        verdict = check_result.get("verdict", "unknown")

        if verdict == "FAIL":
            context = format_violations(display_path, check_result)
        else:
            context = format_pass(display_path, check_result)

        context_output(_EVENT_NAME, context).print_and_exit(0)

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        hook_error("adr-enforcement", e)
        empty_output(_EVENT_NAME).print_and_exit(0)
    except Exception as e:
        hook_error("adr-enforcement", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
