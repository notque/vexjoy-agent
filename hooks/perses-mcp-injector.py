#!/usr/bin/env python3
"""Perses MCP Injector Hook.

Detects perses-related prompts and injects MCP tool discovery
instructions + percli availability checks.

Event: UserPromptSubmit
"""

import json
import sys

PERSES_KEYWORDS = [
    "perses",
    "percli",
    "dashboard-as-code",
    "perses dashboard",
    "perses project",
    "perses datasource",
    "perses variable",
    "perses plugin",
    "perses deploy",
    "perses migrate",
    "perses operator",
    "perses lint",
    "perses onboard",
    "perses mcp",
    "perses cue",
]

MCP_DISCOVERY_BLOCK = """
[perses-mcp] Perses context detected.

MCP TOOL DISCOVERY:
- Use ToolSearch("perses") to discover Perses MCP tools (perses_list_projects,
  perses_get_dashboard_by_name, perses_create_dashboard, etc.). If found:
  use MCP tools for direct Perses API interaction instead of percli CLI.
- If ToolSearch returns no results, fall back to percli CLI commands.

Available percli commands: login, project, get, describe, apply, delete,
lint, migrate, dac setup, dac build, plugin generate, plugin build,
plugin start, plugin test-schemas, config, whoami, refresh.
""".strip()


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError, ValueError):
        # Injector is non-critical — fail open (exit 0), but log
        print("[perses-mcp] WARNING: could not parse hook event", file=sys.stderr)
        sys.exit(0)

    prompt = event.get("prompt", "").lower()

    # Check if any perses keyword is in the prompt
    if any(kw in prompt for kw in PERSES_KEYWORDS):
        print(MCP_DISCOVERY_BLOCK)

    sys.exit(0)


if __name__ == "__main__":
    main()
