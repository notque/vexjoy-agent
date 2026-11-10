#!/usr/bin/env python3
"""Audit allowed-tools declarations in agent frontmatter.

ADR-063 (local-only): Tool Restriction Enforcement. The list is advisory:
Claude Code reads ``tools:`` for subagents and ignores ``allowed-tools:``, so
the declaration documents intended tool use and restricts nothing.

The audit passes every agent that declares ``allowed-tools``. It reports an
agent without one. ``AGENT_ROLES`` only supplies the list ``--fix`` adds, so
an agent missing from that table still passes when it declares its own list.
Files in ``agents/`` without a frontmatter ``name`` are not agents and are
skipped.

Usage:
  python3 scripts/audit-tool-restrictions.py --audit     # Report only
  python3 scripts/audit-tool-restrictions.py --fix        # Add missing allowed-tools
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib.frontmatter import parse_frontmatter as _parse_frontmatter

# Role classifications and their allowed tools. Every role lists Skill: an
# agent loads its paired skills through the Skill tool.
ROLE_TOOLS = {
    "reviewer-readonly": [
        "Read",
        "Glob",
        "Grep",
        "Agent",
        "WebFetch",
        "WebSearch",
        "Skill",
    ],
    "reviewer-with-fix": [
        "Read",
        "Edit",
        "Write",
        "Glob",
        "Grep",
        "Bash",
        "Agent",
        "Skill",
    ],
    "research": [
        "Read",
        "Glob",
        "Grep",
        "WebFetch",
        "WebSearch",
        "Agent",
        "Skill",
    ],
    "orchestrator": [
        "Read",
        "Glob",
        "Grep",
        "Agent",
        "Bash",
        "Skill",
    ],
    "code-modifier": [
        "Read",
        "Edit",
        "Write",
        "Bash",
        "Glob",
        "Grep",
        "Agent",
        "Skill",
    ],
    "documentation": [
        "Read",
        "Write",
        "Glob",
        "Grep",
        "WebFetch",
        "WebSearch",
        "Skill",
    ],
}

# Explicit agent-to-role mappings
AGENT_ROLES = {
    # Consolidated reviewers - read-only by default
    "reviewer-code": "reviewer-readonly",
    "reviewer-domain": "reviewer-readonly",
    "reviewer-perspectives": "reviewer-readonly",
    "reviewer-system": "reviewer-readonly",
    # Research/orchestration - no code modification
    "research-coordinator-engineer": "research",
    "research-subagent-executor": "research",
    "project-coordinator-engineer": "orchestrator",
    "pipeline-orchestrator-engineer": "orchestrator",
    "system-upgrade-engineer": "orchestrator",
    # Documentation - write docs but no bash
    "technical-documentation-engineer": "documentation",
    "technical-journalist-writer": "documentation",
    # Code modifiers - full access (their job is to write code)
    "ansible-automation-engineer": "code-modifier",
    "combat-effects-upgrade": "code-modifier",
    "data-engineer": "code-modifier",
    "database-engineer": "code-modifier",
    "github-profile-rules-engineer": "research",
    "golang-general-engineer": "code-modifier",
    "hook-development-engineer": "code-modifier",
    "kotlin-general-engineer": "code-modifier",
    "kubernetes-helm-engineer": "code-modifier",
    "mcp-local-docs-engineer": "code-modifier",
    "nextjs-ecommerce-engineer": "code-modifier",
    "nodejs-api-engineer": "code-modifier",
    "opensearch-elasticsearch-engineer": "code-modifier",
    "performance-optimization-engineer": "code-modifier",
    "perses-engineer": "code-modifier",
    "php-general-engineer": "code-modifier",
    "pixijs-combat-renderer": "code-modifier",
    "prometheus-grafana-engineer": "code-modifier",
    "python-general-engineer": "code-modifier",
    "python-openstack-engineer": "code-modifier",
    "rabbitmq-messaging-engineer": "code-modifier",
    "react-native-engineer": "code-modifier",
    "react-portfolio-engineer": "code-modifier",
    "rive-skeletal-animator": "code-modifier",
    "rust-general-engineer": "code-modifier",
    "sqlite-peewee-engineer": "code-modifier",
    "swift-general-engineer": "code-modifier",
    "testing-automation-engineer": "code-modifier",
    "toolkit-governance-engineer": "code-modifier",
    "typescript-debugging-engineer": "code-modifier",
    "typescript-frontend-engineer": "code-modifier",
    "ui-design-engineer": "code-modifier",
}


def parse_frontmatter(content: str) -> tuple[dict, str, str]:
    """Parse YAML frontmatter from markdown content.
    Returns (frontmatter_dict, frontmatter_text, body_text).
    """
    fm, body = _parse_frontmatter(content)
    if fm is None:
        return {}, "", content
    fm_text = content[3 : content.find("---", 3)].strip()
    return fm, fm_text, body


def has_allowed_tools(content: str) -> bool:
    """Check if frontmatter contains allowed-tools."""
    return "allowed-tools:" in content.split("---")[1] if content.count("---") >= 2 else False


def add_allowed_tools(content: str, tools: list[str]) -> str:
    """Add allowed-tools to frontmatter."""
    if content.count("---") < 2:
        return content

    parts = content.split("---", 2)
    fm = parts[1]

    # Build tools YAML
    tools_yaml = "allowed-tools:\n" + "\n".join(f"  - {t}" for t in tools)

    # Insert before the closing ---
    fm = fm.rstrip() + "\n" + tools_yaml + "\n"

    return "---" + fm + "---" + parts[2]


def audit(agents_dir: Path, fix: bool = False) -> int:
    """Audit all agents for an allowed-tools declaration.

    Returns the number of agents still missing one, or with ``fix`` the number
    of agents the run added one to.
    """
    issues = 0
    fixed = 0

    for agent_file in sorted(agents_dir.glob("*.md")):
        name = agent_file.stem
        content = agent_file.read_text()

        frontmatter, _, _ = parse_frontmatter(content)
        if not frontmatter.get("name"):
            print(f"  SKIP: {name} — no frontmatter name, not an agent")
            continue

        if has_allowed_tools(content):
            print(f"  OK: {name} — has allowed-tools")
            continue

        role = AGENT_ROLES.get(name)
        if role is None:
            print(f"  MISSING: {name} — no allowed-tools and no role in AGENT_ROLES; add a role or declare the list")
            issues += 1
        elif fix:
            expected_tools = ROLE_TOOLS[role]
            agent_file.write_text(add_allowed_tools(content, expected_tools))
            print(f"  FIXED: {name} — added {role} tools ({len(expected_tools)} tools)")
            fixed += 1
        else:
            print(f"  MISSING: {name} — needs {role} tools")
            issues += 1

    return issues if not fix else fixed


def main():
    parser = argparse.ArgumentParser(description="Audit agent tool restrictions (ADR-063)")
    parser.add_argument("--audit", action="store_true", help="Report missing allowed-tools")
    parser.add_argument("--fix", action="store_true", help="Add missing allowed-tools to agents")
    args = parser.parse_args()

    if not args.audit and not args.fix:
        args.audit = True

    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    if not agents_dir.exists():
        print(f"Error: agents directory not found at {agents_dir}")
        sys.exit(1)

    print(f"Auditing {len(list(agents_dir.glob('*.md')))} agents in {agents_dir}")
    print(f"Mode: {'FIX' if args.fix else 'AUDIT'}")
    print()

    result = audit(agents_dir, fix=args.fix)

    if args.fix:
        print(f"\nFixed {result} agents")
    else:
        if result > 0:
            print(f"\n{result} agents need allowed-tools declarations")
            print("Run with --fix to add them")
            sys.exit(1)
        else:
            print("\nAll agents have allowed-tools declarations")


if __name__ == "__main__":
    main()
