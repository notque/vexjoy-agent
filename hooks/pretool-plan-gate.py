#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Plan Gate

Blocks implementation when task_plan.md doesn't exist in the project root.
Forces agents to create a plan before writing implementation code.

This is a HARD GATE — exit 2 blocks the Write/Edit tool.

Detection logic:
- Tool is Write or Edit
- Target path is in agents/, skills/, or pipelines/
- task_plan.md does not exist in the project root

Allow-through conditions:
- Target file is NOT in agents/, skills/, or pipelines/
- task_plan.md exists in the project root
- PLAN_GATE_BYPASS=1 env var (for use by the plans skill itself)
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "PLAN_GATE_BYPASS"

# Paths that ARE implementation code — only these get gated.
# Everything else (docs, config, CI, plans, tests, scripts, hooks) passes through.
_GATED_PREFIXES = (
    "/agents/",
    "/skills/",
    "/pipelines/",
)


def _is_gated(file_path: str) -> bool:
    """Return True if this file is in an implementation directory that requires a plan."""
    normalised = file_path.replace("\\", "/")
    return any(prefix in normalised for prefix in _GATED_PREFIXES)


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    # Bypass env var — set by the plans skill itself.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[plan-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Only gate implementation code (agents/, skills/, pipelines/).
    # Everything else (docs, config, CI, plans, tests, scripts, hooks) passes through.
    if not _is_gated(file_path):
        if debug:
            print(f"[plan-gate] Not a gated path, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    plan_path = base_dir / "task_plan.md"
    if plan_path.is_file():
        if debug:
            print(f"[plan-gate] task_plan.md found at {plan_path} — allowing through", file=sys.stderr)
        sys.exit(0)

    # task_plan.md is missing — block.
    print(
        "[plan-gate] BLOCKED: Create task_plan.md before modifying implementation code.",
        file=sys.stderr,
    )
    print("[fix-with-skill] plans", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(2) propagate for blocks
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[plan-gate] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never exit 2 on unexpected errors.
        sys.exit(0)
