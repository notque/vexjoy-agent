#!/usr/bin/env python3
"""Build Antigravity CLI and Python SDK subagent specifications from agent markdown definitions.

Extracts persona details from agents/<name>.md:
- YAML frontmatter (description, companion_skills, allowed-tools)
- Specialist category and tool permissions (Implementer, Reviewer, Scout, Coordinator)
- SystemPrompt combining agent body + agents/base-instructions.md
- Outputs JSON payload ready for define_subagent and types.SubagentConfig / LocalAgentConfig
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Resolve repo root relative to this script
REPO_ROOT = Path(__file__).resolve().parent.parent

# Try to use shared frontmatter parser from scripts.lib
try:
    from scripts.lib.frontmatter import parse_frontmatter
except ImportError:
    import re

    _FM_PATTERN = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

    def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:  # type: ignore[misc]
        m = _FM_PATTERN.match(text)
        if not m:
            return None, text
        import yaml

        body = text[m.end() :]
        if body.startswith("\n"):
            body = body[1:]
        try:
            return yaml.safe_load(m.group(1)), body
        except Exception:
            return None, body


COORDINATOR_AGENTS: frozenset[str] = frozenset(
    {
        "project-coordinator-engineer",
        "pipeline-orchestrator-engineer",
        "research-coordinator-engineer",
    }
)

SCOUT_AGENTS: frozenset[str] = frozenset(
    {
        "research-subagent-executor",
    }
)


def resolve_specialist_category(agent_name: str, frontmatter: dict[str, Any] | None = None) -> str:
    """Classify agent into one of: implementer, reviewer, scout, coordinator."""
    name_clean = agent_name.strip().lower()
    if name_clean in COORDINATOR_AGENTS or "coordinator" in name_clean or "orchestrat" in name_clean:
        return "coordinator"
    if name_clean in SCOUT_AGENTS or name_clean.startswith("research-subagent") or name_clean.endswith("-scout"):
        return "scout"
    if name_clean.startswith("reviewer-"):
        return "reviewer"
    if frontmatter:
        routing = frontmatter.get("routing") if isinstance(frontmatter.get("routing"), dict) else {}
        cat = str(routing.get("category") or frontmatter.get("category") or "").strip().lower()
        if cat == "review":
            return "reviewer"
        if cat == "research":
            return "scout"
        if cat == "meta" and ("coordinator" in name_clean or "orchestrat" in name_clean):
            return "coordinator"
    return "implementer"


def resolve_tool_permissions(category: str) -> tuple[bool, bool, bool]:
    """Return (EnableWriteTools, EnableMCPTools, EnableSubagentTools) based on specialist category.

    Matrix:
      Implementers / Builders: WriteOnly (True, False, False)
      Reviewers / Auditors: ReadOnly (False, False, False)
      Researchers / Scouts: MCPReadOnly (False, True, False)
      Coordinators / Planners: Full (True, True, True)
    """
    cat = category.strip().lower()
    if cat in ("implementer", "builder"):
        return True, False, False
    if cat in ("reviewer", "auditor"):
        return False, False, False
    if cat in ("scout", "researcher"):
        return False, True, False
    if cat in ("coordinator", "planner"):
        return True, True, True
    return True, False, False


def compile_system_prompt(agent_body: str, base_instructions: str) -> str:
    """Compile agent body and base instructions into a single SystemPrompt."""
    parts = []
    body_clean = agent_body.strip()
    if body_clean:
        parts.append(body_clean)
    base_clean = base_instructions.strip()
    if base_clean:
        parts.append(base_clean)
    return "\n\n---\n\n".join(parts)


def resolve_agent_path(agent: str, repo_root: Path) -> Path:
    """Resolve an agent name or path into an existing agent markdown file path."""
    candidate = Path(agent)
    if candidate.is_file():
        return candidate.resolve()

    agent_clean = agent.strip()
    if agent_clean.endswith(".md"):
        agent_clean = agent_clean[:-3]

    standard_path = repo_root / "agents" / f"{agent_clean}.md"
    if standard_path.is_file():
        return standard_path

    raise FileNotFoundError(f"Agent definition not found for '{agent}' (checked: {standard_path})")


def build_subagent_spec(
    agent: str,
    *,
    repo_root: Path | None = None,
    category_override: str | None = None,
    enable_write_override: bool | None = None,
    enable_mcp_override: bool | None = None,
    enable_subagent_override: bool | None = None,
) -> dict[str, Any]:
    """Build subagent specification dictionary from agent markdown file and base instructions."""
    root = repo_root.resolve() if repo_root else REPO_ROOT
    agent_path = resolve_agent_path(agent, root)
    agent_name = agent_path.stem

    text = agent_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if fm is None:
        fm = {}

    name = str(fm.get("name") or agent_name).strip()
    description = str(fm.get("description") or "").strip()
    # Normalize multiline description
    description = " ".join(description.split())

    routing = fm.get("routing") if isinstance(fm.get("routing"), dict) else {}
    companion_skills = fm.get("companion_skills") or routing.get("pairs_with") or []
    if isinstance(companion_skills, str):
        companion_skills = [companion_skills]
    allowed_tools = fm.get("allowed-tools") or []

    category = category_override or resolve_specialist_category(name, fm)
    write_tools, mcp_tools, subagent_tools = resolve_tool_permissions(category)

    if enable_write_override is not None:
        write_tools = enable_write_override
    if enable_mcp_override is not None:
        mcp_tools = enable_mcp_override
    if enable_subagent_override is not None:
        subagent_tools = enable_subagent_override

    base_instructions_path = root / "agents" / "base-instructions.md"
    base_instructions = ""
    if base_instructions_path.is_file():
        base_instructions = base_instructions_path.read_text(encoding="utf-8")

    system_prompt = compile_system_prompt(body, base_instructions)

    define_subagent_payload = {
        "Name": name,
        "Description": description,
        "SystemPrompt": system_prompt,
        "EnableWriteTools": write_tools,
        "EnableMCPTools": mcp_tools,
        "EnableSubagentTools": subagent_tools,
    }

    sdk_config_payload = {
        "name": name,
        "description": description,
        "system_instruction": system_prompt,
        "capabilities": {
            "enable_write_tools": write_tools,
            "enable_mcp_tools": mcp_tools,
            "enable_subagents": subagent_tools,
        },
    }

    return {
        "Name": name,
        "Description": description,
        "SystemPrompt": system_prompt,
        "EnableWriteTools": write_tools,
        "EnableMCPTools": mcp_tools,
        "EnableSubagentTools": subagent_tools,
        "category": category,
        "companion_skills": companion_skills,
        "allowed_tools": allowed_tools,
        "define_subagent": define_subagent_payload,
        "sdk_config": sdk_config_payload,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, help="Agent name or path to agents/<name>.md")
    parser.add_argument(
        "--format",
        choices=("json", "define_subagent", "sdk"),
        default="json",
        help="Output format (default: json with all fields)",
    )
    parser.add_argument(
        "--category",
        choices=("implementer", "reviewer", "scout", "coordinator"),
        default=None,
        help="Explicitly override specialist category",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Root path of the repository (default: auto-detected)",
    )
    parser.add_argument("--enable-write-tools", type=lambda s: s.lower() in ("1", "true", "yes"), default=None)
    parser.add_argument("--enable-mcp-tools", type=lambda s: s.lower() in ("1", "true", "yes"), default=None)
    parser.add_argument("--enable-subagent-tools", type=lambda s: s.lower() in ("1", "true", "yes"), default=None)

    args = parser.parse_args(argv)

    try:
        spec = build_subagent_spec(
            args.agent,
            repo_root=args.repo_root,
            category_override=args.category,
            enable_write_override=args.enable_write_tools,
            enable_mcp_override=args.enable_mcp_tools,
            enable_subagent_override=args.enable_subagent_tools,
        )
    except Exception as exc:
        print(f"build-subagent-spec: error: {exc}", file=sys.stderr)
        return 2

    if args.format == "define_subagent":
        out = spec["define_subagent"]
    elif args.format == "sdk":
        out = spec["sdk_config"]
    else:
        out = spec

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
