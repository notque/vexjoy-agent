#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Plan Gate

Blocks implementation when task_plan.md doesn't exist at the project root.
Forces agents to create a plan before writing implementation code.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Write/Edit tool.

Detection logic:
- Tool is Write or Edit
- Target path is under agents/ or skills/ — gated regardless of file extension,
  because SKILL.md and agent .md files are behavioral specs (implementation, not docs)
- task_plan.md does not exist at the project root

Project root resolution (Defect 1 fix): the plan is anchored to a stable
project root, not the session pwd (which is often a deep subdirectory).
Order: CLAUDE_PROJECT_DIR env → nearest ancestor of cwd containing .git → cwd.

Allow-through conditions:
- Target file is NOT under agents/ or skills/
- The target file is itself named task_plan.md (never gate the plan file)
- task_plan.md exists at the project root
- PLAN_GATE_BYPASS=1 env var (for use by the plans skill itself)
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "PLAN_GATE_BYPASS"

# Paths that ARE gated — all files under these get gated regardless of extension,
# because SKILL.md and agent .md files are behavioral specs (implementation, not docs).
_GATED_PREFIXES = (
    "/agents/",
    "/skills/",
)


def _is_gated(file_path: str) -> bool:
    """Return True if this file is in an implementation directory that requires a plan."""
    normalised = file_path.replace("\\", "/")
    return any(prefix in normalised for prefix in _GATED_PREFIXES)


def _find_project_root(event_cwd: str) -> Path:
    """Resolve a stable project root to anchor task_plan.md.

    Order: CLAUDE_PROJECT_DIR env → nearest ancestor of cwd containing .git → cwd.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    cur = Path(event_cwd or ".").resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Write|Edit" in settings.json prevents
    # this hook from spawning for non-matching tools.

    # Bypass env var — set by the plans skill itself.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[plan-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Never gate the plan file itself — it is the unblocker (Defect 2).
    if Path(file_path).name == "task_plan.md":
        if debug:
            print("[plan-gate] Target is task_plan.md — allowing through", file=sys.stderr)
        sys.exit(0)

    # Gate all files under agents/ or skills/ regardless of extension, because
    # SKILL.md and agent .md files are behavioral specs. Everything else allows.
    if not _is_gated(file_path):
        if debug:
            print(f"[plan-gate] Not a gated path, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # Resolve a stable project root to anchor the plan (Defect 1):
    # CLAUDE_PROJECT_DIR → nearest ancestor with .git → cwd.
    base_dir = _find_project_root(event.get("cwd", "."))

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
    deny_tool_use(
        "PreToolUse",
        "Create task_plan.md before modifying implementation code in agents/ or skills/. "
        "Use the planning skill to create one.",
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-plan-gate", e)
    finally:
        sys.exit(0)
