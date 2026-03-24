#!/usr/bin/env python3
"""
Capabilities Catalog CLI — Discover agents, skills, and pipelines at runtime.

Usage:
    python3 scripts/list-capabilities.py summary [--json]
    python3 scripts/list-capabilities.py skills [--category CAT] [--brief] [--json] [--markdown]
    python3 scripts/list-capabilities.py agents [--category CAT] [--brief] [--json] [--markdown]
    python3 scripts/list-capabilities.py pipelines [--json] [--markdown]
    python3 scripts/list-capabilities.py show <name> [--json]
    python3 scripts/list-capabilities.py search <query> [--json]
    python3 scripts/list-capabilities.py route <prompt>
    python3 scripts/list-capabilities.py catalog [--json]
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Resolve repo root relative to this script (scripts/ -> repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS_INDEX = REPO_ROOT / "skills" / "INDEX.json"
PIPELINES_INDEX = REPO_ROOT / "pipelines" / "INDEX.json"
AGENTS_INDEX = REPO_ROOT / "agents" / "INDEX.json"
ROUTING_CONFIG = REPO_ROOT / "scripts" / "routing-config.json"

DESC_TRUNCATE = 55
STALE_EXIT_CODE = 2


# ---------------------------------------------------------------------------
# Index loading + staleness check
# ---------------------------------------------------------------------------


def load_skills_index() -> tuple[dict, str | None]:
    """Load skills/INDEX.json and return the skills dict keyed by name."""
    if not SKILLS_INDEX.exists():
        print(f"ERROR: {SKILLS_INDEX} not found", file=sys.stderr)
        sys.exit(1)
    data = json.loads(SKILLS_INDEX.read_text())
    return data.get("skills", {}), data.get("generated")


def load_pipelines_index() -> tuple[dict, str | None]:
    """Load pipelines/INDEX.json and return the pipelines dict keyed by name."""
    if not PIPELINES_INDEX.exists():
        return {}, None
    data = json.loads(PIPELINES_INDEX.read_text())
    return data.get("pipelines", {}), data.get("generated")


def load_agents_index() -> dict:
    """Load agents/INDEX.json and return the agents dict keyed by name."""
    if not AGENTS_INDEX.exists():
        print(f"ERROR: {AGENTS_INDEX} not found", file=sys.stderr)
        sys.exit(1)
    data = json.loads(AGENTS_INDEX.read_text())
    return data.get("agents", {}), data.get("generated")


def _newest_mtime(glob_pattern: str, base: Path) -> float | None:
    """Return the mtime of the newest file matching the glob, or None."""
    mtimes = [p.stat().st_mtime for p in base.glob(glob_pattern) if p.is_file()]
    return max(mtimes) if mtimes else None


def check_staleness(index_path: Path, generated: str | None, glob_pattern: str, base: Path, label: str) -> bool:
    """Emit a stderr warning if source files are newer than the index timestamp.

    Returns True if stale.
    """
    if generated is None:
        return False

    try:
        ts = generated.replace("Z", "+00:00")
        index_dt = datetime.fromisoformat(ts)
        index_mtime = index_dt.timestamp()
    except (ValueError, TypeError):
        return False

    newest = _newest_mtime(glob_pattern, base)
    if newest is None:
        return False

    # Count files newer than the index
    newer_count = sum(1 for p in base.glob(glob_pattern) if p.is_file() and p.stat().st_mtime > index_mtime)
    if newer_count > 0:
        if "agent" in label.lower():
            regen_script = "scripts/generate-agent-index.py"
        else:
            regen_script = "scripts/generate-skill-index.py"
        print(
            f"⚠ {index_path.relative_to(REPO_ROOT)} may be stale ({newer_count} files newer). "
            f"Run: python3 {regen_script}",
            file=sys.stderr,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _trunc(text: str, width: int = DESC_TRUNCATE) -> str:
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def _triggers_str(triggers: list[str], width: int = 22) -> str:
    joined = ",".join(triggers)
    if len(joined) <= width:
        return joined
    return joined[: width - 3] + "..."


def _table_header(cols: list[tuple[str, int]]) -> str:
    parts = [f"{name:<{w}}" for name, w in cols]
    return "  ".join(parts)


def _table_row(values: list[tuple[str, int]]) -> str:
    parts = [f"{val:<{w}}" for val, w in values]
    return "  ".join(parts)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Subcommand: summary
# ---------------------------------------------------------------------------


def cmd_summary(args) -> int:
    skills_dict, skills_gen = load_skills_index()
    pipelines_dict, pipelines_gen = load_pipelines_index()
    agents_dict, agents_gen = load_agents_index()

    stale = False
    stale |= check_staleness(SKILLS_INDEX, skills_gen, "*/SKILL.md", REPO_ROOT / "skills", "skills")
    if pipelines_gen:
        stale |= check_staleness(PIPELINES_INDEX, pipelines_gen, "*/SKILL.md", REPO_ROOT / "pipelines", "pipelines")
    stale |= check_staleness(AGENTS_INDEX, agents_gen, "*.md", REPO_ROOT / "agents", "agents")

    total_skills = len(skills_dict)
    total_pipelines = len(pipelines_dict)
    total_agents = len(agents_dict)

    if args.json_output:
        print(
            json.dumps(
                {
                    "skills": {"total": total_skills},
                    "pipelines": {"total": total_pipelines},
                    "agents": {"total": total_agents},
                },
                indent=2,
            )
        )
    else:
        print(f"Skills:    {total_skills:>4}")
        print(f"Pipelines: {total_pipelines:>4}")
        print(f"Agents:    {total_agents:>4}")
        print()
        print("Run: python3 scripts/list-capabilities.py skills --category <cat>")

    return STALE_EXIT_CODE if stale else 0


# ---------------------------------------------------------------------------
# Subcommand: skills
# ---------------------------------------------------------------------------


def _filter_skills_by_category(skills: list[dict], category: str) -> list[dict]:
    cat = category.lower()
    result = []
    for s in skills:
        name = s.get("name", "").lower()
        desc = s.get("description", "").lower()
        if name.startswith(cat) or cat in name or cat in desc:
            result.append(s)
    return result


def cmd_skills(args) -> int:
    skills_dict, skills_gen = load_skills_index()
    stale = check_staleness(SKILLS_INDEX, skills_gen, "*/SKILL.md", REPO_ROOT / "skills", "skills")

    skills = _dict_as_list(skills_dict)

    if args.category:
        skills = _filter_skills_by_category(skills, args.category)

    if args.brief:
        print(f"{len(skills)} skills")
        return STALE_EXIT_CODE if stale else 0

    if args.json_output:
        print(json.dumps(skills, indent=2))
        return STALE_EXIT_CODE if stale else 0

    cols = [("NAME", 24), ("TRIGGERS", 22), ("DESCRIPTION", 55)]

    if args.markdown:
        rows = [[s.get("name", ""), ",".join(s.get("triggers", [])), s.get("description", "")] for s in skills]
        print(_markdown_table(["NAME", "TRIGGERS", "DESCRIPTION"], rows))
    else:
        print(_table_header(cols))
        for s in skills:
            row = [
                (s.get("name", ""), 24),
                (_triggers_str(s.get("triggers", [])), 22),
                (_trunc(s.get("description", "")), 55),
            ]
            print(_table_row(row))

    return STALE_EXIT_CODE if stale else 0


# ---------------------------------------------------------------------------
# Subcommand: agents
# ---------------------------------------------------------------------------


def _dict_as_list(d: dict) -> list[dict]:
    """Convert a dict-keyed index to a list with 'name' field."""
    return [{"name": name, **info} for name, info in d.items()]


def _filter_agents_by_category(agents: list[dict], category: str) -> list[dict]:
    cat = category.lower()
    return [a for a in agents if a.get("category", "").lower() == cat]


def cmd_agents(args) -> int:
    agents_dict, agents_gen = load_agents_index()
    stale = check_staleness(AGENTS_INDEX, agents_gen, "*.md", REPO_ROOT / "agents", "agents")

    agents = _dict_as_list(agents_dict)

    if args.category:
        agents = _filter_agents_by_category(agents, args.category)

    if args.brief:
        print(f"{len(agents)} agents")
        return STALE_EXIT_CODE if stale else 0

    if args.json_output:
        print(json.dumps(agents, indent=2))
        return STALE_EXIT_CODE if stale else 0

    cols = [("NAME", 30), ("TRIGGERS", 22), ("DESCRIPTION", 55)]

    if args.markdown:
        rows = [[a.get("name", ""), ",".join(a.get("triggers", [])), a.get("short_description", "")] for a in agents]
        print(_markdown_table(["NAME", "TRIGGERS", "DESCRIPTION"], rows))
    else:
        print(_table_header(cols))
        for a in agents:
            row = [
                (a.get("name", ""), 30),
                (_triggers_str(a.get("triggers", [])), 22),
                (_trunc(a.get("short_description", "")), 55),
            ]
            print(_table_row(row))

    return STALE_EXIT_CODE if stale else 0


# ---------------------------------------------------------------------------
# Subcommand: pipelines
# ---------------------------------------------------------------------------


def cmd_pipelines(args) -> int:
    pipelines_dict, pipelines_gen = load_pipelines_index()
    stale = False
    if pipelines_gen:
        stale = check_staleness(PIPELINES_INDEX, pipelines_gen, "*/SKILL.md", REPO_ROOT / "pipelines", "pipelines")

    pipelines = _dict_as_list(pipelines_dict)

    if args.json_output:
        print(json.dumps(pipelines, indent=2))
        return STALE_EXIT_CODE if stale else 0

    cols = [("NAME", 26), ("PHASES", 7), ("DESCRIPTION", 55)]

    if args.markdown:
        rows = [[p.get("name", ""), str(len(p.get("phases", []))), p.get("description", "")] for p in pipelines]
        print(_markdown_table(["NAME", "PHASES", "DESCRIPTION"], rows))
    else:
        print(_table_header(cols))
        for p in pipelines:
            phase_count = str(len(p.get("phases", [])))
            row = [
                (p.get("name", ""), 26),
                (phase_count, 7),
                (_trunc(p.get("description", "")), 55),
            ]
            print(_table_row(row))

    return STALE_EXIT_CODE if stale else 0


# ---------------------------------------------------------------------------
# Subcommand: show
# ---------------------------------------------------------------------------


def cmd_show(args) -> int:
    skills_dict, _ = load_skills_index()
    pipelines_dict, _ = load_pipelines_index()
    agents_dict, _ = load_agents_index()

    name = args.name

    # Search skills first (O(1) lookup)
    skill = skills_dict.get(name)
    if skill:
        if args.json_output:
            print(json.dumps({"type": "skill", "name": name, **skill}, indent=2))
        else:
            print("Type:           skill")
            print(f"Name:           {name}")
            print(f"Description:    {skill.get('description', '')}")
            print(f"Triggers:       {', '.join(skill.get('triggers', []))}")
            print(f"Version:        {skill.get('version', 'unknown')}")
            print(f"User-invocable: {skill.get('user_invocable', True)}")
            print(f"Category:       {skill.get('category', 'unknown')}")
            print(f"File:           {skill.get('file', '')}")
        return 0

    # Search pipelines
    pipeline = pipelines_dict.get(name)
    if pipeline:
        if args.json_output:
            print(json.dumps({"type": "pipeline", "name": name, **pipeline}, indent=2))
        else:
            print("Type:           pipeline")
            print(f"Name:           {name}")
            print(f"Description:    {pipeline.get('description', '')}")
            print(f"Triggers:       {', '.join(pipeline.get('triggers', []))}")
            phases = pipeline.get("phases", [])
            print(f"Phases:         {' -> '.join(phases)}")
            print(f"Version:        {pipeline.get('version', 'unknown')}")
            print(f"File:           {pipeline.get('file', '')}")
        return 0

    # Search agents
    agent_info = agents_dict.get(name)
    if agent_info:
        if args.json_output:
            print(json.dumps({"type": "agent", "name": name, **agent_info}, indent=2))
        else:
            print("Type:           agent")
            print(f"Name:           {name}")
            print(f"Description:    {agent_info.get('short_description', '')}")
            print(f"Triggers:       {', '.join(agent_info.get('triggers', []))}")
            print(f"Complexity:     {agent_info.get('complexity', 'unknown')}")
            print(f"Category:       {agent_info.get('category', 'unknown')}")
            pairs = agent_info.get("pairs_with", [])
            if pairs:
                print(f"Pairs with:     {', '.join(pairs)}")
            print(f"File:           agents/{agent_info.get('file', '')}")
        return 0

    print(f"ERROR: '{name}' not found in skills, pipelines, or agents index", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Subcommand: search
# ---------------------------------------------------------------------------


def cmd_search(args) -> int:
    skills_dict, _ = load_skills_index()
    pipelines_dict, _ = load_pipelines_index()
    agents_dict, _ = load_agents_index()

    query = args.query.lower()
    results: list[dict] = []

    def _search_dict(d: dict, entry_type: str) -> None:
        for name, info in d.items():
            desc = info.get("description", "") or info.get("short_description", "")
            triggers = info.get("triggers", [])

            if query in name.lower():
                match_field = "name"
            elif any(query in t.lower() for t in triggers):
                match_field = "trigger"
            elif query in desc.lower():
                match_field = "description"
            else:
                continue

            results.append(
                {
                    "match": match_field,
                    "type": entry_type,
                    "name": name,
                    "description": desc,
                }
            )

    _search_dict(skills_dict, "skill")
    _search_dict(pipelines_dict, "pipeline")
    _search_dict(agents_dict, "agent")

    # Sort: name > trigger > description
    _order = {"name": 0, "trigger": 1, "description": 2}
    results.sort(key=lambda r: _order.get(r["match"], 3))

    if args.json_output:
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print(f"No results for '{args.query}'")
        return 0

    cols = [("MATCH", 13), ("TYPE", 7), ("NAME", 30), ("DESCRIPTION", 55)]
    print(_table_header(cols))
    for r in results:
        row = [
            (f"[{r['match']}]", 13),
            (r["type"], 7),
            (r["name"], 30),
            (_trunc(r["description"]), 55),
        ]
        print(_table_row(row))

    return 0


# ---------------------------------------------------------------------------
# Subcommand: route
# ---------------------------------------------------------------------------


def _load_routing_config() -> dict:
    """Load scripts/routing-config.json."""
    if not ROUTING_CONFIG.exists():
        print(f"ERROR: {ROUTING_CONFIG} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(ROUTING_CONFIG.read_text())


def _word_boundary_match(trigger: str, text: str) -> bool:
    """Return True if trigger appears at a word boundary in text."""
    pattern = r"(?<!\w)" + re.escape(trigger) + r"(?!\w)"
    return bool(re.search(pattern, text))


def _route_prompt(prompt_text: str) -> dict:
    """Deterministically route a free-text prompt to an agent+skill.

    Priority order:
      1. Force routes (confidence 1.0, no agent)
      2. Domain agents (confidence 0.9 / 0.7)
      3. Task-type agents (confidence 0.9 / 0.7)
      4. Voice agents (confidence 0.9 / 0.7)
      5. No match (confidence 0.0)
    """
    config = _load_routing_config()
    prompt_lower = prompt_text.lower()

    # --- Step 1: Force routes ---
    for entry in config.get("force_routes", []):
        skill = entry["skill"]
        for trigger in entry.get("triggers", []):
            # Special case: *_test.go → look for _test.go substring
            check = trigger[1:] if trigger.startswith("*") else trigger
            if check in prompt_lower:
                return {
                    "agent": None,
                    "skill": skill,
                    "force_route": True,
                    "triggers_matched": [trigger],
                    "confidence": 1.0,
                    "reason": f"Force-route: {skill} (trigger match: {check})",
                    "alternatives": [],
                }

    # --- Step 2: Skill overrides (verb scan, applied later) ---
    override_skill: str | None = None
    for override in config.get("skill_overrides", []):
        for verb in override.get("verbs", []):
            if verb in prompt_lower:
                override_skill = override["skill"]
                break
        if override_skill:
            break

    # --- Steps 3-5: Collect all agent matches ---
    candidates: list[dict] = []

    def _score_entry(entry: dict, agent_key: str, skill_key: str) -> None:
        agent = entry.get(agent_key)
        base_skill = entry.get(skill_key) or entry.get("default_skill")
        effective_skill = override_skill if override_skill else base_skill
        matched: list[str] = []
        best_conf = 0.0
        for trigger in entry.get("triggers", []):
            if trigger in prompt_lower:
                conf = 0.9 if _word_boundary_match(trigger, prompt_lower) else 0.7
                if conf > best_conf:
                    best_conf = conf
                matched.append(trigger)
        if matched:
            candidates.append(
                {
                    "agent": agent,
                    "skill": effective_skill,
                    "confidence": best_conf,
                    "triggers_matched": matched,
                }
            )

    for entry in config.get("domain_agents", []):
        _score_entry(entry, "agent", "default_skill")

    for entry in config.get("task_type_agents", []):
        _score_entry(entry, "agent", "skill")

    for entry in config.get("voice_agents", []):
        _score_entry(entry, "agent", "default_skill")

    if not candidates:
        return {
            "agent": None,
            "skill": None,
            "force_route": False,
            "triggers_matched": [],
            "confidence": 0.0,
            "reason": "no match",
            "alternatives": [],
        }

    # Sort descending by confidence, then by trigger count as tiebreaker
    candidates.sort(key=lambda c: (c["confidence"], len(c["triggers_matched"])), reverse=True)

    winner = candidates[0]
    alts = []
    for c in candidates[1:]:
        if len(alts) >= 2:
            break
        if c["agent"] != winner["agent"] or c["skill"] != winner["skill"]:
            alts.append({"agent": c["agent"], "skill": c["skill"], "confidence": c["confidence"]})

    trigger_display = winner["triggers_matched"][0] if winner["triggers_matched"] else ""
    reason = f"Domain/task match: {winner['agent']} + {winner['skill']} (trigger: {trigger_display})"

    return {
        "agent": winner["agent"],
        "skill": winner["skill"],
        "force_route": False,
        "triggers_matched": winner["triggers_matched"],
        "confidence": winner["confidence"],
        "reason": reason,
        "alternatives": alts,
    }


def cmd_route(args) -> int:
    """Route a free-text prompt and print the decision as JSON."""
    result = _route_prompt(args.prompt)
    print(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: catalog (compact output for LLM context injection)
# ---------------------------------------------------------------------------


def cmd_catalog(args) -> int:
    """Output a compact capability catalog suitable for LLM context injection.

    Produces a JSON object with skills and agents, each containing only
    name, description (first sentence), and triggers.  Designed to be
    injected as <available-capabilities> context for routing decisions.
    """
    skills_dict, _ = load_skills_index()
    pipelines_dict, _ = load_pipelines_index()
    agents_dict, _ = load_agents_index()

    def _first_sentence(text: str, max_len: int = 80) -> str:
        """Extract first sentence, truncated to max_len."""
        for sep in [". ", ".\n", ".\t"]:
            idx = text.find(sep)
            if idx != -1:
                text = text[: idx + 1]
                break
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text

    def _catalog_entries(d: dict, desc_key: str = "description") -> list[dict]:
        entries = []
        for name, info in d.items():
            entry = {"name": name}
            desc = info.get(desc_key, "")
            entry["description"] = _first_sentence(desc)
            triggers = info.get("triggers", [])
            if triggers:
                entry["triggers"] = triggers
            pairs = info.get("pairs_with", [])
            if pairs:
                entry["pairs_with"] = pairs
            entries.append(entry)
        return entries

    catalog_skills = _catalog_entries(skills_dict)
    catalog_pipelines = _catalog_entries(pipelines_dict)
    catalog_agents = _catalog_entries(agents_dict, "short_description")

    catalog = {
        "skills": catalog_skills,
        "pipelines": catalog_pipelines,
        "agents": catalog_agents,
        "total_skills": len(catalog_skills),
        "total_pipelines": len(catalog_pipelines),
        "total_agents": len(catalog_agents),
    }

    print(json.dumps(catalog, indent=2 if not args.compact else None))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List and search the agent/skill/pipeline catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # summary
    p_summary = subparsers.add_parser("summary", help="Show counts of skills, agents, and pipelines")
    p_summary.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    p_summary.set_defaults(func=cmd_summary)

    # skills
    p_skills = subparsers.add_parser("skills", help="List skills")
    p_skills.add_argument("--category", help="Filter by category prefix or keyword")
    p_skills.add_argument("--brief", action="store_true", help="Show count only")
    p_skills.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    p_skills.add_argument("--markdown", action="store_true", help="Output markdown table")
    p_skills.set_defaults(func=cmd_skills)

    # agents
    p_agents = subparsers.add_parser("agents", help="List agents")
    p_agents.add_argument("--category", help="Filter by category field")
    p_agents.add_argument("--brief", action="store_true", help="Show count only")
    p_agents.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    p_agents.add_argument("--markdown", action="store_true", help="Output markdown table")
    p_agents.set_defaults(func=cmd_agents)

    # pipelines
    p_pipelines = subparsers.add_parser("pipelines", help="List pipeline skills")
    p_pipelines.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    p_pipelines.add_argument("--markdown", action="store_true", help="Output markdown table")
    p_pipelines.set_defaults(func=cmd_pipelines)

    # show
    p_show = subparsers.add_parser("show", help="Show detail for a named skill or agent")
    p_show.add_argument("name", help="Skill or agent name")
    p_show.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    p_show.set_defaults(func=cmd_show)

    # search
    p_search = subparsers.add_parser("search", help="Search skills and agents by keyword")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    p_search.set_defaults(func=cmd_search)

    # route
    p_route = subparsers.add_parser("route", help="Route a free-text prompt to agent+skill (always outputs JSON)")
    p_route.add_argument("prompt", help="Free-text prompt to route")
    p_route.set_defaults(func=cmd_route)

    # catalog
    p_catalog = subparsers.add_parser("catalog", help="Compact capability catalog for LLM context injection")
    p_catalog.add_argument("--compact", action="store_true", help="Single-line JSON (no indentation)")
    p_catalog.set_defaults(func=cmd_catalog)

    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
