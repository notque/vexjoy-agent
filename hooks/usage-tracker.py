#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Usage Tracking for Skills and Agents

Captures Skill and Agent tool invocations to SQLite for usage analytics.
SILENT when the tool is not Skill or Agent (no output, no noise).

Design Principles:
- SILENT for non-Skill/Agent tools (no stdout)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- SQLite for robust storage
"""

import json
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin


def main():
    """Process PostToolUse events, recording Skill and Agent invocations."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process PostToolUse events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != "PostToolUse":
            return

        tool_name = event.get("tool_name", "")

        # Only track Skill and Agent tools — exit silently for everything else
        if tool_name not in ("Skill", "Agent"):
            return

        # Lazy import — only loaded when we actually need to record
        from hook_utils import get_project_dir, get_session_id
        from usage_db import record_agent, record_skill

        session_id = get_session_id()
        project_path = str(get_project_dir())
        tool_input = event.get("tool_input", {})

        if tool_name == "Skill":
            skill_name = tool_input.get("skill", "unknown")
            args = tool_input.get("args", "")
            args_summary = str(args)[:200] if args else None
            record_skill(
                skill_name=skill_name,
                session_id=session_id,
                project_path=project_path,
                args_summary=args_summary,
            )

        elif tool_name == "Agent":
            agent_type = tool_input.get("subagent_type", "unknown")
            description = tool_input.get("description", "")
            # Detect worktree isolation from tool_input if present
            isolation = "worktree" if tool_input.get("isolation") == "worktree" else None
            record_agent(
                agent_type=agent_type,
                description=description or None,
                session_id=session_id,
                project_path=project_path,
                isolation=isolation,
            )

    except (json.JSONDecodeError, Exception):
        pass  # Silent failure — never block Claude Code
    finally:
        sys.exit(0)  # ALWAYS exit 0


if __name__ == "__main__":
    main()
