#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write Hook: ADR Creation Gate

Blocks creation of new agent/skill/pipeline component files when no ADR
exists for that component in the adr/ directory.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Write tool.

Detection logic:
- Tool is Write (edits to existing files pass through)
- Target path matches /agents/<name>.md, /skills/<name>/SKILL.md,
- The target file does not already exist on disk (new creation only)
- adr/{name}.md does not exist in the project root

Allow-through conditions:
- Tool is not Write
- Target file does not match a component path pattern
- Target file already exists on disk (update, not creation)
- Target path matches _ADR_PATH_ALLOWLIST (producer-allowlisted skills like create-voice)
- adr/{name}.md exists in the project root
- ADR_CREATION_GATE_BYPASS=1 env var
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "ADR_CREATION_GATE_BYPASS"

# Match agents/foo-bar.md → "foo-bar"
_AGENT_RE = re.compile(r"/agents/([^/]+)\.md$")
# Match skills/foo-bar/SKILL.md → "foo-bar"
_SKILL_RE = re.compile(r"/skills/([^/]+)/SKILL\.md$")
# Match pipelines/foo-bar/SKILL.md → "foo-bar"
_PIPELINE_RE = re.compile(r"/pipelines/([^/]+)/SKILL\.md$")

# Path-shape allowlist for components whose creation is governed by an upstream
# skill's own methodology, not by a per-component ADR. Mirrors the allowlist in
# pretool-unified-gate.py:_CREATION_PATH_ALLOWLIST. Keep these two in sync —
# anything that bypasses the creation-gate also bypasses the ADR gate, because
# the upstream skill's methodology *is* the architectural justification.
#
# Maintainer note: do NOT broaden these patterns. Each entry must point to a
# path shape produced by exactly one well-known upstream skill. If a new
# component type wants in, write the producer skill first, then add the entry.
_ADR_PATH_ALLOWLIST: list[tuple[re.Pattern[str], str]] = [
    # voice-* skills are produced by `create-voice` (skills/create-voice/
    # SKILL.md Step 5: GENERATE). The create-voice skill itself documents the
    # voice-creation methodology; a per-voice ADR would be redundant.
    (re.compile(r"/skills/voice-[^/]+/SKILL\.md$"), "create-voice"),
]


def _extract_component_name(file_path: str) -> str | None:
    """Return the component name if the path is a new agent/skill/pipeline file.

    Args:
        file_path: Absolute or relative path from the tool input.

    Returns:
        Component name string, or None if the path is not a component file.
    """
    normalised = file_path.replace("\\", "/")
    for pattern in (_AGENT_RE, _SKILL_RE, _PIPELINE_RE):
        match = pattern.search(normalised)
        if match:
            return match.group(1)
    return None


def main() -> None:
    """Run the ADR creation gate check."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Write" in settings.json prevents
    # this hook from spawning for non-Write tools.

    # Bypass env var.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[adr-creation-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check if the path matches a component pattern.
    component_name = _extract_component_name(file_path)
    if component_name is None:
        if debug:
            print(f"[adr-creation-gate] Not a component path, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # If the file already exists this is an update, not a creation — allow through.
    if Path(file_path).exists():
        if debug:
            print(f"[adr-creation-gate] File already exists (update), allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # Path-shape allowlist: skills produced by named upstream pipelines whose
    # own methodology is the architectural justification.
    normalised = file_path.replace("\\", "/")
    for allowed_pattern, producer in _ADR_PATH_ALLOWLIST:
        if allowed_pattern.search(normalised):
            if debug:
                print(
                    f"[adr-creation-gate] Producer-allowlisted ({producer}), allowing: {file_path}",
                    file=sys.stderr,
                )
            sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    adr_path = base_dir / "adr" / f"{component_name}.md"
    if adr_path.is_file():
        if debug:
            print(f"[adr-creation-gate] ADR found at {adr_path} — allowing through", file=sys.stderr)
        sys.exit(0)

    # ADR is missing — block.
    print(
        f"[adr-creation-gate] BLOCKED: Create adr/{component_name}.md before creating new component.",
        file=sys.stderr,
    )
    print("[fix-with-skill] plans", file=sys.stderr)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Create adr/{component_name}.md before creating this new component. "
                        "Use the plans skill to draft the ADR first."
                    ),
                }
            }
        )
    )
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
            print(f"[adr-creation-gate] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never block tools.
    finally:
        sys.exit(0)
