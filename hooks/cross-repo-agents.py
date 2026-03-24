#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Cross-Repo Agent Discovery

Discovers custom agents in the current working directory's .claude/agents/
folder and injects them into context so they can be used via /do router.

Design Principles:
- SILENT when no local agents found
- Discovers agents from cwd's .claude/agents/ directory
- Injects concise agent summaries for routing
- Fast execution (<50ms target)
- Non-blocking (always exits 0)
"""

import os
import re
import sys
from pathlib import Path


def extract_agent_info(agent_path: Path) -> dict | None:
    """Extract agent metadata from markdown file.

    Returns dict with name, description, triggers or None if invalid.
    """
    try:
        content = agent_path.read_text()

        # Look for YAML frontmatter
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            # Try to extract from content directly
            name = agent_path.stem
            # Look for first heading as description
            heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            description = heading_match.group(1) if heading_match else name
            return {
                "name": name,
                "file": str(agent_path),
                "description": description[:100],
                "triggers": [name.replace("-", " ")],
            }

        yaml_content = match.group(1)
        info = {"file": str(agent_path)}

        # Parse name
        name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
        info["name"] = name_match.group(1).strip() if name_match else agent_path.stem

        # Parse description
        desc_match = re.search(r"^description:\s*(.+?)(?:\n[a-z]|$)", yaml_content, re.MULTILINE | re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip().replace("\\n", " ")
            # Extract "Use this agent when..." part
            use_match = re.search(r"Use this agent when (.+?)(?:\.|$)", desc)
            if use_match:
                info["description"] = f"Use when {use_match.group(1).strip()}"
            else:
                info["description"] = desc[:100]
        else:
            info["description"] = info["name"]

        # Parse triggers from routing section
        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", yaml_content)
        if triggers_match:
            triggers_text = triggers_match.group(1)
            triggers = re.findall(r"-\s+[\"']?([^\"'\n]+)[\"']?", triggers_text)
            info["triggers"] = [t.strip() for t in triggers]
        else:
            # Generate triggers from name
            info["triggers"] = [info["name"].replace("-", " ")]

        return info

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[cross-repo] Failed to parse {agent_path}: {e}", file=sys.stderr)
        return None


def discover_local_agents(cwd: str) -> list[dict]:
    """Discover agents in cwd/.claude/agents/ directory."""
    agents = []
    agents_dir = Path(cwd) / ".claude" / "agents"

    if not agents_dir.exists():
        return agents

    for agent_path in agents_dir.glob("*.md"):
        info = extract_agent_info(agent_path)
        if info:
            agents.append(info)

    return sorted(agents, key=lambda x: x["name"])


def main():
    """Discover and inject local agents at session start."""
    try:
        cwd = os.getcwd()

        # Discover local agents
        agents = discover_local_agents(cwd)

        if not agents:
            return  # Silent when no local agents

        # Print discovery information
        print(f"[cross-repo] Found {len(agents)} local agent(s) in .claude/agents/")

        # Print agent summaries for routing
        print("[cross-repo] Available local agents:")
        for agent in agents:
            triggers = ", ".join(agent["triggers"][:3])
            print(f"  - {agent['name']}: {agent['description']}")
            print(f"    Triggers: {triggers}")
            print(f"    File: {agent['file']}")

        # Print routing instruction
        print("\n[cross-repo] To use local agents, read the agent file and follow its instructions.")
        print("[cross-repo] The /do router can invoke these via: Task tool with prompt referencing agent file")

    except Exception as e:
        # Log to stderr if debug enabled, but never fail
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[cross-repo] Error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
