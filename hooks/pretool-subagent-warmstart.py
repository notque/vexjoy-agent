#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Subagent Warm Start

Enriches subagent (Agent tool) prompts with parent session context.
Injects a <parent-context> block containing files seen, task plan
status, ADR session info, key decisions, and discovery briefs.

This gives subagents immediate awareness of the parent session's
state without needing to re-discover context from scratch.

Design Principles:
- Non-blocking (always exits 0)
- Sub-50ms execution (file reads only, no subprocess)
- Graceful degradation on missing files
- Caps output at ~8000 chars (~2000 tokens)
"""

import json
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output
from stdin_timeout import read_stdin

EVENT_NAME = "PreToolUse"

SESSION_READS_FILE = ".claude/session-reads.txt"
TASK_PLAN_FILE = "task_plan.md"
ADR_SESSION_FILE = ".adr-session.json"
DISCOVERIES_DIR = ".planning/discoveries"

MAX_OUTPUT_CHARS = 8000
MAX_FILES_SHOWN = 20


def load_recent_reads(reads_path: Path, max_count: int = MAX_FILES_SHOWN) -> list[str]:
    """Load up to max_count most recent file paths from session-reads.txt.

    Args:
        reads_path: Path to the session-reads.txt file.
        max_count: Maximum number of paths to return.

    Returns:
        List of file path strings, most recent last (tail of file).
    """
    if not reads_path.is_file():
        return []

    try:
        content = reads_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        # Return the most recent entries (tail of file)
        return lines[-max_count:]
    except OSError:
        return []


def extract_task_plan(plan_path: Path) -> dict[str, str]:
    """Extract Goal and Status lines from task_plan.md.

    Args:
        plan_path: Path to task_plan.md.

    Returns:
        Dict with 'goal' and 'status' keys (empty strings if not found).
    """
    result = {"goal": "", "status": ""}

    if not plan_path.is_file():
        return result

    try:
        content = plan_path.read_text(encoding="utf-8")
    except OSError:
        return result

    lines = content.splitlines()
    in_goal_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Goal":
            in_goal_section = True
            continue
        if in_goal_section:
            if stripped.startswith("## "):
                # Hit next section heading, goal section is over
                in_goal_section = False
            elif stripped:
                result["goal"] = stripped[:200]
                in_goal_section = False
        if stripped.startswith("**Currently in Phase") or stripped.startswith("**Status"):
            result["status"] = stripped[:200]

    return result


def extract_decisions(plan_path: Path) -> list[str]:
    """Extract decisions from the 'Decisions Made' section of task_plan.md.

    Args:
        plan_path: Path to task_plan.md.

    Returns:
        List of decision strings.
    """
    if not plan_path.is_file():
        return []

    try:
        content = plan_path.read_text(encoding="utf-8")
    except OSError:
        return []

    decisions: list[str] = []
    in_decisions = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Decisions Made":
            in_decisions = True
            continue
        if in_decisions:
            if stripped.startswith("## "):
                break  # Next section
            if stripped.startswith("- "):
                decisions.append(stripped[2:].strip()[:200])

    return decisions


def load_adr_session(session_path: Path) -> dict[str, str]:
    """Load ADR session metadata from .adr-session.json.

    Args:
        session_path: Path to .adr-session.json.

    Returns:
        Dict with 'adr_path' and 'domain' keys (empty strings if not found).
    """
    result = {"adr_path": "", "domain": ""}

    if not session_path.is_file():
        return result

    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
        result["adr_path"] = data.get("adr_path", "")
        result["domain"] = data.get("domain", "")
    except (OSError, json.JSONDecodeError):
        pass

    return result


def list_discoveries(discoveries_dir: Path) -> list[str]:
    """List discovery brief filenames from .planning/discoveries/.

    Args:
        discoveries_dir: Path to the discoveries directory.

    Returns:
        List of filenames (not full paths).
    """
    if not discoveries_dir.is_dir():
        return []

    try:
        return sorted(f.name for f in discoveries_dir.iterdir() if f.is_file())
    except OSError:
        return []


def build_context_block(
    files: list[str],
    task_plan: dict[str, str],
    decisions: list[str],
    adr_session: dict[str, str],
    discoveries: list[str],
) -> str:
    """Build the parent-context block for subagent injection.

    Args:
        files: List of file paths seen in the session.
        task_plan: Dict with 'goal' and 'status' from task_plan.md.
        decisions: List of decisions from task_plan.md.
        adr_session: Dict with 'adr_path' and 'domain'.
        discoveries: List of discovery brief filenames.

    Returns:
        Formatted context block string, capped at MAX_OUTPUT_CHARS.
    """
    parts: list[str] = []

    # Files seen
    if files:
        file_list = ", ".join(files)
        parts.append(f"[warmstart] Files seen ({len(files)}): {file_list}")
    else:
        parts.append("[warmstart] Files seen (0): none")

    # Task plan
    if task_plan["goal"]:
        parts.append(f"[warmstart] Task: {task_plan['goal']}")
    if task_plan["status"]:
        parts.append(f"[warmstart] Status: {task_plan['status']}")

    # ADR session
    if adr_session["adr_path"]:
        parts.append(f"[warmstart] ADR session: {adr_session['adr_path']} (domain: {adr_session['domain']})")

    # Decisions
    if decisions:
        decision_text = "; ".join(decisions)
        parts.append(f"[warmstart] Decisions: {decision_text}")

    # Discoveries
    if discoveries:
        disc_text = ", ".join(discoveries)
        parts.append(f"[warmstart] Discovery briefs: {disc_text}")

    header = "[warmstart] Parent session context for subagent:"
    body = "\n".join(parts)
    full_output = f"{header}\n{body}"

    # Cap at MAX_OUTPUT_CHARS
    if len(full_output) > MAX_OUTPUT_CHARS:
        full_output = full_output[: MAX_OUTPUT_CHARS - 3] + "..."

    return full_output


def main() -> None:
    """Process PreToolUse events for Agent tool warm start injection.

    Flow:
    1. Read stdin JSON, check tool_name == "Agent"
    2. Gather parent session context from various files
    3. Build <parent-context> block
    4. Inject via context_output
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # tool_name filter removed — matcher "Agent" in settings.json prevents
        # this hook from spawning for non-Agent tools.

        # Gather context from various sources
        files = load_recent_reads(Path(SESSION_READS_FILE))
        task_plan = extract_task_plan(Path(TASK_PLAN_FILE))
        decisions = extract_decisions(Path(TASK_PLAN_FILE))
        adr_session = load_adr_session(Path(ADR_SESSION_FILE))
        discoveries = list_discoveries(Path(DISCOVERIES_DIR))

        # Build context block
        context_block = build_context_block(
            files=files,
            task_plan=task_plan,
            decisions=decisions,
            adr_session=adr_session,
            discoveries=discoveries,
        )

        # Inject context
        context_output(EVENT_NAME, context_block).print_and_exit()

    except Exception as e:
        print(f"[warmstart] error: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[warmstart] Fatal: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
