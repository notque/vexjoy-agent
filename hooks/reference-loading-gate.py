#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Reference Loading Gate (Advisory V1)

Fires on Write and Edit tool calls. Checks whether the target file belongs
to an agent or skill component that has a references/ subdirectory, and if
so emits a reminder to load the relevant reference file before making changes.

This is ADVISORY (exit 0 always) — V1 design. See TODO below for V2 enforcing design.

Detection logic:
- Tool is Write or Edit
- Target file_path is inside an agents/ or skills/ component directory
- That component has a references/ subdirectory
- Target file is NOT itself inside references/ (editing reference files is fine)

Allow-through conditions (silent):
- Target file is not in an agents/ or skills/ subtree
- Component has no references/ subdirectory
- Target file is inside a references/ directory
- REF_GATE_BYPASS=1 env var

Advisory output:
- Emits [auto-fix] reminder to stderr when a references/ directory is found
- Always exits 0 — never blocks in V1

TODO (V2 Enforcing Design):
  A companion PostToolUse hook (posttool-ref-tracker.py) would record every
  Read call whose path matches */references/*.md to a session state file at
  /tmp/claude-ref-gate-{session_id}.state.
  This hook would then consult that state file, and BLOCK (exit 2 or deny JSON)
  if no reference has been loaded for the relevant component.

  Context marker for umbrella dispatch (ADR-170 Phase 2):
  The /do router would set UMBRELLA_COMPONENT=<name> when dispatching with an
  umbrella skill/agent, allowing the gate to restrict enforcement to umbrella
  tasks only rather than firing for every edit in agents/ or skills/.

ADR-170: Reference Loading Verification Hook
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "REF_GATE_BYPASS"

# Normalised path fragments that indicate a component root worth checking.
# Both agents/ (flat .md files) and skills/<name>/ (subdirectory components).
_COMPONENT_PREFIXES = ("/agents/", "/skills/")


def _resolve_component_root(file_path: str, base_dir: Path) -> Path | None:
    """Return the component root directory if the path is inside an agent or skill.

    For agents: the component root is the agents/ directory itself (agents are
    flat .md files, not subdirectories).
    For skills: the component root is the immediate subdirectory, e.g.
    skills/go-patterns/ for skills/go-patterns/SKILL.md.

    Returns None if the path is not inside a component directory or if the
    path is itself inside a references/ subdirectory (editing references is fine).

    Args:
        file_path: The file path from tool_input (may be absolute or relative).
        base_dir: Project root used for relative path resolution.

    Returns:
        Path of the component root directory, or None if not applicable.
    """
    normalised = file_path.replace("\\", "/")

    # If the target is inside a references/ subdirectory, pass through silently.
    if "/references/" in normalised:
        return None

    # Agents: flat files directly under agents/.
    # Component root is the agents/ directory itself.
    if "/agents/" in normalised:
        # Resolve to get an absolute Path so we can test for references/.
        try:
            resolved = Path(file_path) if Path(file_path).is_absolute() else (base_dir / file_path)
            agents_dir = resolved.parent
            # agents/ should be a single level: agents/<file>.md
            if agents_dir.name == "agents":
                return agents_dir
        except (OSError, ValueError):
            pass
        return None

    # Skills: subdirectory components under skills/<name>/.
    if "/skills/" in normalised:
        try:
            resolved = Path(file_path) if Path(file_path).is_absolute() else (base_dir / file_path)
            # Walk up until we find a directory whose parent is named "skills".
            candidate = resolved if resolved.is_dir() else resolved.parent
            for _ in range(5):  # Limit depth to avoid runaway traversal
                if candidate.parent.name == "skills":
                    return candidate
                if candidate.parent == candidate:
                    break
                candidate = candidate.parent
        except (OSError, ValueError):
            pass
        return None

    return None


def _has_references_dir(component_root: Path) -> bool:
    """Return True if the component root has a non-empty references/ subdirectory.

    Args:
        component_root: Path to the component directory to inspect.

    Returns:
        True if references/ exists and contains at least one .md file.
    """
    references_dir = component_root / "references"
    if not references_dir.is_dir():
        return False
    # Only fire if there are actually reference files to load.
    try:
        return any(references_dir.glob("*.md"))
    except OSError:
        return False


def main() -> None:
    """Run the reference loading gate advisory check."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Bypass env var.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[ref-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    # Edit tool uses file_path; Write uses file_path too — same field name.
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    if debug:
        print(f"[ref-gate] Checking file_path={file_path!r} base_dir={base_dir}", file=sys.stderr)

    component_root = _resolve_component_root(file_path, base_dir)
    if component_root is None:
        if debug:
            print(f"[ref-gate] Not a component path or inside references/ — allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    if not _has_references_dir(component_root):
        if debug:
            print(
                f"[ref-gate] Component has no references/ directory — allowing: {component_root}",
                file=sys.stderr,
            )
        sys.exit(0)

    # Component has reference files — emit advisory reminder.
    references_dir = component_root / "references"
    print(
        f"[ref-gate] Component at {component_root.name}/ has reference files in references/. "
        "Load the relevant reference file before making changes.",
        file=sys.stderr,
    )
    print(
        f"[auto-fix] action=load-reference | Load the relevant reference file from "
        f"{references_dir} before making changes.",
        file=sys.stderr,
    )

    # V1: advisory only — always exit 0.
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[ref-gate] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never block tools.
    finally:
        sys.exit(0)
