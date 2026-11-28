#!/usr/bin/env python3
"""Build Antigravity CLI and Python SDK subagent specifications for a skill-carried worker.

The repo's specialist agents are retired (plans/009): the worker is a generic
persona and the skill carries the domain. This builds that persona:

- From a skill (`--skill <name>`, the normal path): name `<skill>-worker`, the
  skill's description, a short SystemPrompt that tells the worker to follow the
  skill's SKILL.md and its Reference Loading Table, plus
  `skills/shared-patterns/base-instructions.md`.
- From an agent file (`--agent <name|path>`): kept for private overlay agents
  (agents/<name>.md installed beside the repo) and explicit paths. SystemPrompt
  is the agent body plus the base instructions.

Specialist category (Implementer, Reviewer, Scout, Coordinator) sets tool
permissions. Outputs JSON ready for define_subagent and
types.SubagentConfig / LocalAgentConfig.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Resolve repo root relative to this script
REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_INSTRUCTIONS_REL = Path("skills") / "shared-patterns" / "base-instructions.md"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.frontmatter import parse_frontmatter

# Skills whose work is read-only review or external research. Category comes
# from the skill name first, then its routing category.
REVIEWER_SKILLS: frozenset[str] = frozenset({"review", "security", "code-quality"})
SCOUT_SKILLS: frozenset[str] = frozenset({"research"})
REVIEWER_CATEGORIES: frozenset[str] = frozenset({"review", "code-review", "security"})
SCOUT_CATEGORIES: frozenset[str] = frozenset({"research"})


def resolve_specialist_category(name: str, frontmatter: dict[str, Any] | None = None) -> str:
    """Classify a skill or agent into one of: implementer, reviewer, scout, coordinator."""
    name_clean = name.strip().lower()
    if "coordinator" in name_clean or "orchestrat" in name_clean:
        return "coordinator"
    if name_clean in SCOUT_SKILLS or name_clean.startswith("research-subagent") or name_clean.endswith("-scout"):
        return "scout"
    if name_clean in REVIEWER_SKILLS or name_clean.startswith("reviewer-"):
        return "reviewer"
    if frontmatter:
        routing = frontmatter.get("routing") if isinstance(frontmatter.get("routing"), dict) else {}
        cat = str(routing.get("category") or frontmatter.get("category") or "").strip().lower()
        if cat in REVIEWER_CATEGORIES:
            return "reviewer"
        if cat in SCOUT_CATEGORIES:
            return "scout"
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


def compile_system_prompt(persona_body: str, base_instructions: str) -> str:
    """Compile the persona body and base instructions into a single SystemPrompt."""
    parts = []
    body_clean = persona_body.strip()
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


def resolve_skill_path(skill: str, repo_root: Path) -> Path:
    """Resolve a skill name or path into its SKILL.md.

    Checks a direct path, the installed flat layout (skills/<name>/SKILL.md),
    then the repo's grouped layout (skills/<group>/<name>/SKILL.md).
    """
    candidate = Path(skill)
    if candidate.is_file():
        return candidate.resolve()
    if candidate.is_dir() and (candidate / "SKILL.md").is_file():
        return (candidate / "SKILL.md").resolve()

    name = skill.strip().lower()
    flat = repo_root / "skills" / name / "SKILL.md"
    if flat.is_file():
        return flat
    grouped = sorted((repo_root / "skills").glob(f"*/{name}/SKILL.md"))
    if grouped:
        return grouped[0]
    raise FileNotFoundError(f"Skill definition not found for '{skill}' (checked: {flat}, skills/*/{name}/SKILL.md)")


def _read_base_instructions(root: Path) -> str:
    path = root / BASE_INSTRUCTIONS_REL
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _skill_persona(skill_name: str, description: str) -> str:
    lines = [f"# {skill_name} worker", ""]
    if description:
        lines += [f"Domain: {description}", ""]
    lines.append(
        f"Load and follow the `{skill_name}` skill's SKILL.md before starting work, then read the references "
        "its Reference Loading Table names for this task. The skill carries the domain rules."
    )
    return "\n".join(lines)


def build_subagent_spec(
    agent: str | None = None,
    *,
    skill: str | None = None,
    repo_root: Path | None = None,
    category_override: str | None = None,
    enable_write_override: bool | None = None,
    enable_mcp_override: bool | None = None,
    enable_subagent_override: bool | None = None,
) -> dict[str, Any]:
    """Build a subagent specification from a skill (normal) or an agent file (private overlay)."""
    root = repo_root.resolve() if repo_root else REPO_ROOT
    if skill:
        path = resolve_skill_path(skill, root)
        fm, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
        fm = fm or {}
        skill_name = str(fm.get("name") or path.parent.name).strip()
        name = f"{skill_name}-worker"
        description = " ".join(str(fm.get("description") or "").split())
        persona = _skill_persona(skill_name, description)
        companion_skills = [skill_name]
        category_key = skill_name
    elif agent:
        path = resolve_agent_path(agent, root)
        fm, persona = parse_frontmatter(path.read_text(encoding="utf-8"))
        fm = fm or {}
        name = str(fm.get("name") or path.stem).strip()
        description = " ".join(str(fm.get("description") or "").split())
        routing = fm.get("routing") if isinstance(fm.get("routing"), dict) else {}
        companion_skills = fm.get("companion_skills") or routing.get("pairs_with") or []
        if isinstance(companion_skills, str):
            companion_skills = [companion_skills]
        category_key = name
    else:
        raise ValueError("build_subagent_spec needs a skill or an agent")

    allowed_tools = fm.get("allowed-tools") or []
    category = category_override or resolve_specialist_category(category_key, fm)
    write_tools, mcp_tools, subagent_tools = resolve_tool_permissions(category)

    if enable_write_override is not None:
        write_tools = enable_write_override
    if enable_mcp_override is not None:
        mcp_tools = enable_mcp_override
    if enable_subagent_override is not None:
        subagent_tools = enable_subagent_override

    system_prompt = compile_system_prompt(persona, _read_base_instructions(root))

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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--skill", help="Skill name or path to its SKILL.md (the normal worker persona)")
    source.add_argument("--agent", help="Private overlay agent name or path to agents/<name>.md")
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
            skill=args.skill,
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
