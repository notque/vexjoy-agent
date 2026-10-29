#!/usr/bin/env python3
# hook-version: 1.0.2
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

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "USAGE_TRACKER_BYPASS"


def main():
    """Process PostToolUse events, recording Skill and Agent invocations."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[usage-tracker] Bypassed via USAGE_TRACKER_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # tool_name/event_type filters removed — matcher "Skill|Agent" in settings.json
        # prevents this hook from spawning for non-matching tools.
        tool_name = event.get("tool_name", "")

        # Lazy import — only loaded when we actually need to record
        from hook_utils import get_project_dir, get_session_id
        from usage_db import record_agent, record_skill

        session_id = get_session_id()
        project_path = str(get_project_dir())
        # PostToolUse events carry input under "tool_input" or "input"
        # depending on harness version; try both so the skill name is never
        # lost (the "unknown" gap that hid 17% of skill invocations).
        tool_input = event.get("tool_input") or event.get("input") or {}

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
            try:
                from learning_db_v2 import record_evidence_event

                record_evidence_event(
                    event_type="skill_invocation",
                    source="hook:usage-tracker",
                    session_id=session_id,
                    project_path=project_path,
                    skill=skill_name,
                    tool_name="Skill",
                    action="invoke",
                    target=args_summary,
                )
            except Exception:
                pass

        elif tool_name == "Agent":
            # Try subagent_type first (Agent tool), then agentType (Workflow's agent()),
            # then fall back to a labelled sentinel so "unknown" rows are visibly a
            # telemetry gap, not a legit agent name.
            agent_type = tool_input.get("subagent_type") or tool_input.get("agentType") or "unattributed-dispatch"
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
            try:
                from learning_db_v2 import record_evidence_event

                record_evidence_event(
                    event_type="agent_invocation",
                    source="hook:usage-tracker",
                    session_id=session_id,
                    project_path=project_path,
                    agent=agent_type,
                    tool_name="Agent",
                    action="invoke",
                    target=description or None,
                    metadata={"isolation": isolation},
                )
            except Exception:
                pass

    except Exception as e:
        hook_error("usage-tracker", e)
    finally:
        sys.exit(0)  # ALWAYS exit 0


if __name__ == "__main__":
    main()
