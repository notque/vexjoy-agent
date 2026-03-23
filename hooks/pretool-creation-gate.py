#!/usr/bin/env python3
"""
PreToolUse:Write Hook: Creation Gate

Blocks direct creation of new agent/skill files that bypass the
skill-creator-engineer pipeline. Forces the LLM to route through
proper creation workflows that produce full-depth components.

This is a HARD GATE — it physically prevents the Write tool from creating
new agent or skill files. The LLM receives a [fix-with-agent] directive
telling it to use skill-creator-engineer.

Detection logic:
- Tool is Write (not Edit — edits to existing files are allowed)
- Target path matches agents/*.md or skills/*/SKILL.md
- File does NOT already exist on disk (creation, not overwrite)

Allow-through conditions:
- File already exists (update, not creation)
- CREATION_GATE_BYPASS=1 env var is set (for the creator pipeline itself)
- Path is not in agents/ or skills/*/ (other files are fine)

Precedent: pretool-git-submission-gate.py — same hook type, same exit 2
block pattern, same [fix-with-skill/agent] directive.

Design Principles:
- Sub-5ms for non-matching paths (early exit)
- Blocks with exit 2 + stderr message
- Non-blocking for edits, non-agent/skill paths, and existing files
- Passthrough when CREATION_GATE_BYPASS=1 env var is set
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Env var that creator pipelines set to bypass this gate.
_BYPASS_ENV = "CREATION_GATE_BYPASS"

# Patterns for agent and skill file creation.
# Match agents/<name>.md, skills/<name>/SKILL.md, and pipelines/<name>/SKILL.md anywhere in the path.
_AGENT_PATTERN = re.compile(r"/agents/[^/]+\.md$")
_SKILL_PATTERN = re.compile(r"/(skills|pipelines)/[^/]+/SKILL\.md$")


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name != "Write":
        sys.exit(0)

    # Check bypass env var
    if os.environ.get(_BYPASS_ENV) == "1":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Only gate agent and skill files
    is_agent = bool(_AGENT_PATTERN.search(file_path))
    is_skill = bool(_SKILL_PATTERN.search(file_path))
    if not is_agent and not is_skill:
        sys.exit(0)

    # Allow overwrites of existing files (this is an update, not creation)
    if os.path.exists(file_path):
        sys.exit(0)

    # Block: new agent or skill file being created outside the creator pipeline
    component_type = "agent" if is_agent else "skill"
    print(
        f"[creation-gate] BLOCKED: New {component_type} must be created via skill-creator-engineer or skill-creation-pipeline.\n"
        f"[creation-gate] Path: {file_path}\n"
        f"[fix-with-agent] skill-creator-engineer",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A broken hook must fail OPEN (exit 0), not fail CLOSED (exit 2).
        # Python's default error exit code is 2, which Claude Code interprets
        # as "block this tool" — causing a deadlock if the hook crashes.
        sys.exit(0)
