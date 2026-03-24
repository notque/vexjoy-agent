#!/usr/bin/env python3
"""
Unified INDEX.json generator for agents, skills, and pipelines.

Reads component directories, extracts YAML frontmatter, and generates
INDEX.json files matching the format of the existing per-type generators.

Usage:
    python3 scripts/generate-index.py [--type agents|skills|pipelines|all] [--check]
    python3 scripts/generate-index.py --coverage [--routing-tables PATH]

Options:
    --type TYPE             Component type to generate (default: all)
    --check                 Compare generated output vs current files, exit 1 if different
    --coverage              Compare INDEX.json components against routing tables, report gaps
    --routing-tables PATH   Path to routing-tables.md (default: ~/.claude/skills/do/references/routing-tables.md)

Exit codes:
    0 - Success (or --check with no differences, or --coverage with full coverage)
    1 - Error or --check found differences, or --coverage found gaps
    2 - Trigger collisions detected among force-routed entries
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

PHASE_HEADER_RE = re.compile(r"^### Phase [\d]+[a-z.]?[\d]*:\s*(.+?)(?:\s*\(|\s*--|\s*\u2014|$)")


def extract_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content.

    Tries PyYAML first, falls back to regex for malformed frontmatter
    (common in agent descriptions with unquoted colons).
    """
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    yaml_content = match.group(1)

    try:
        result = yaml.safe_load(yaml_content)
        if isinstance(result, dict):
            return result
    except yaml.YAMLError:
        pass

    # Fallback: regex extraction for key fields
    fm: dict = {}

    name_m = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
    if name_m:
        fm["name"] = name_m.group(1).strip()

    # Description: handle block scalars (>, |) and simple values
    desc_m = re.search(
        r"^description:\s*(?:[>|][\-+]?\s*\n\s+)?(.+?)(?=\n[a-z_-]+:|$)",
        yaml_content,
        re.MULTILINE | re.DOTALL,
    )
    if desc_m:
        fm["description"] = re.sub(r"\s+", " ", desc_m.group(1).strip())

    version_m = re.search(r"^version:\s*(.+)$", yaml_content, re.MULTILINE)
    if version_m:
        fm["version"] = version_m.group(1).strip()

    ui_m = re.search(r"^user-invocable:\s*(.+)$", yaml_content, re.MULTILINE)
    if ui_m:
        fm["user-invocable"] = ui_m.group(1).strip().lower() == "true"

    agent_m = re.search(r"^agent:\s*(.+)$", yaml_content, re.MULTILINE)
    if agent_m:
        fm["agent"] = agent_m.group(1).strip()

    model_m = re.search(r"^model:\s*(.+)$", yaml_content, re.MULTILINE)
    if model_m:
        fm["model"] = model_m.group(1).strip()

    color_m = re.search(r"^color:\s*(.+)$", yaml_content, re.MULTILINE)
    if color_m:
        fm["color"] = color_m.group(1).strip()

    # Routing section
    routing_m = re.search(r"^routing:\s*\n((?:\s+.+\n?)+)", yaml_content, re.MULTILINE)
    if routing_m:
        rc = routing_m.group(1)
        routing: dict = {}

        t_m = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", rc)
        if t_m:
            routing["triggers"] = [t.strip() for t in re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', t_m.group(1))]

        cat_m = re.search(r"category:\s*(.+)$", rc, re.MULTILINE)
        if cat_m:
            routing["category"] = cat_m.group(1).strip()

        fr_m = re.search(r"force_route:\s*(.+)$", rc, re.MULTILINE)
        if fr_m:
            routing["force_route"] = fr_m.group(1).strip().lower() == "true"

        pw_m = re.search(r"pairs_with:\s*\n((?:\s+-\s+.+\n?)+)", rc)
        if pw_m:
            routing["pairs_with"] = [p.strip() for p in re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', pw_m.group(1))]

        pw_empty = re.search(r"pairs_with:\s*\[\]", rc)
        if pw_empty and "pairs_with" not in routing:
            routing["pairs_with"] = []

        cx_m = re.search(r"complexity:\s*(.+)$", rc, re.MULTILINE)
        if cx_m:
            routing["complexity"] = cx_m.group(1).strip()

        if routing:
            fm["routing"] = routing

    return fm if fm else None


def short_description_skill(description: str) -> str:
    """First sentence of a skill description, max 200 chars."""
    if not description:
        return ""
    desc = re.sub(r"\s+", " ", description.replace("\\n", " ").strip())
    m = re.match(r"((?:[^.!?]|\.(?=[a-zA-Z0-9_]))+[.!?])", desc)
    if m and len(m.group(1)) <= 200:
        return m.group(1).strip()
    return desc[:147] + "..." if len(desc) > 150 else desc


def short_description_agent(description: str) -> str:
    """Extract a short description for an agent entry."""
    if not description:
        return ""
    desc = description.replace("\\n", " ")
    m = re.search(r"Use this agent when you need[^.]+", desc)
    if m:
        return m.group(0)
    sentences = desc.split(".")
    if sentences:
        return sentences[0].strip()
    return description[:100]


# ---------------------------------------------------------------------------
# Agent index generation (matches generate-agent-index.py output format)
# ---------------------------------------------------------------------------


def generate_agents_index(agents_dir: Path) -> dict:
    """Generate agents/INDEX.json in the v1.0 format."""
    index: dict = {
        "version": "1.0",
        "generated_by": "scripts/generate-agent-index.py",
        "agents": {},
    }

    for agent_file in sorted(agents_dir.glob("*.md")):
        content = agent_file.read_text(encoding="utf-8")
        fm = extract_frontmatter(content)
        if not fm:
            continue

        name = fm.get("name", agent_file.stem)
        entry: dict = {
            "file": agent_file.name,
            "short_description": short_description_agent(fm.get("description", "")),
        }

        if "routing" in fm:
            routing = fm["routing"]
            if "triggers" in routing:
                entry["triggers"] = routing["triggers"]
            if "pairs_with" in routing:
                entry["pairs_with"] = routing["pairs_with"]
            if "complexity" in routing:
                entry["complexity"] = routing["complexity"]
            if "category" in routing:
                entry["category"] = routing["category"]
        else:
            name_parts = name.replace("-", " ").split()
            entry["triggers"] = [p for p in name_parts if p not in ("general", "engineer", "compact")]

        index["agents"][name] = entry

    # Include private agents if they exist
    private_dir = agents_dir.parent / "private-agents"
    if private_dir.exists() and any(private_dir.iterdir()):
        for agent_file in sorted(private_dir.glob("*.md")):
            content = agent_file.read_text(encoding="utf-8")
            fm = extract_frontmatter(content)
            if not fm:
                continue
            name = fm.get("name", agent_file.stem)
            entry = {
                "file": agent_file.name,
                "short_description": short_description_agent(fm.get("description", "")),
            }
            if "routing" in fm:
                routing = fm["routing"]
                if "triggers" in routing:
                    entry["triggers"] = routing["triggers"]
                if "pairs_with" in routing:
                    entry["pairs_with"] = routing["pairs_with"]
                if "complexity" in routing:
                    entry["complexity"] = routing["complexity"]
                if "category" in routing:
                    entry["category"] = routing["category"]
            index["agents"][name] = entry

    return index


# ---------------------------------------------------------------------------
# Skill / Pipeline index generation (matches generate-skill-index.py format)
# ---------------------------------------------------------------------------


def extract_phases(content: str) -> list[str]:
    """Extract phase names from ### Phase N: NAME headers."""
    phases = []
    for line in content.splitlines():
        m = PHASE_HEADER_RE.match(line)
        if m:
            phase_name = m.group(1).strip().upper()
            if phase_name:
                phases.append(phase_name)
    return phases


def generate_skill_or_pipeline_index(
    source_dir: Path,
    dir_prefix: str,
    collection_key: str,
    is_pipeline: bool = False,
) -> dict:
    """Generate skills/INDEX.json or pipelines/INDEX.json in v2.0 format."""
    index: dict = {
        "version": "2.0",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/generate-skill-index.py",
        collection_key: {},
    }

    for skill_dir in sorted(source_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        content = skill_file.read_text(encoding="utf-8")
        fm = extract_frontmatter(content)
        if not fm:
            print(f"  Warning: no frontmatter in {skill_file}", file=sys.stderr)
            continue

        name = fm.get("name", skill_dir.name)
        entry: dict = {
            "file": f"{dir_prefix}/{skill_dir.name}/SKILL.md",
            "description": short_description_skill(fm.get("description", "")),
        }

        # Triggers
        routing = fm.get("routing", {})
        if isinstance(routing, dict) and "triggers" in routing:
            entry["triggers"] = routing["triggers"]
        else:
            name_parts = name.replace("-", " ").split()
            stop_words = {"skill", "pipeline", "the", "and", "for", "with"}
            triggers = [p for p in name_parts if len(p) > 2 and p.lower() not in stop_words]
            entry["triggers"] = [name] + triggers

        if isinstance(routing, dict) and "category" in routing:
            entry["category"] = routing["category"]

        if isinstance(routing, dict) and routing.get("force_route") is True:
            entry["force_route"] = True

        entry["user_invocable"] = bool(fm.get("user-invocable", False))

        if "version" in fm:
            entry["version"] = fm["version"]

        if is_pipeline and content:
            phases = extract_phases(content)
            if phases:
                entry["phases"] = phases

        if isinstance(routing, dict) and "pairs_with" in routing:
            entry["pairs_with"] = routing["pairs_with"]

        if "agent" in fm:
            entry["agent"] = fm["agent"]

        if "model" in fm:
            entry["model"] = fm["model"]

        index[collection_key][name] = entry

    return index


# ---------------------------------------------------------------------------
# Check mode: compare generated vs existing
# ---------------------------------------------------------------------------


def normalize_for_comparison(index: dict) -> dict:
    """Remove volatile fields (generated timestamp) for comparison."""
    cleaned = dict(index)
    cleaned.pop("generated", None)
    return cleaned


def check_index(generated: dict, existing_path: Path, label: str) -> bool:
    """Compare generated index against existing file. Returns True if match."""
    if not existing_path.exists():
        print(f"  {label}: {existing_path} does not exist (would be created)")
        return False

    existing = json.loads(existing_path.read_text(encoding="utf-8"))
    gen_clean = normalize_for_comparison(generated)
    ext_clean = normalize_for_comparison(existing)

    if gen_clean == ext_clean:
        print(f"  {label}: OK (matches)")
        return True

    # Find specific differences
    gen_keys = set(gen_clean.get(label.lower(), {}).keys()) if label.lower() in gen_clean else set()
    ext_keys = set(ext_clean.get(label.lower(), {}).keys()) if label.lower() in ext_clean else set()

    added = gen_keys - ext_keys
    removed = ext_keys - gen_keys
    if added:
        print(f"  {label}: new entries: {', '.join(sorted(added))}")
    if removed:
        print(f"  {label}: missing entries: {', '.join(sorted(removed))}")
    if not added and not removed:
        print(f"  {label}: entry content differs (same keys)")

    return False


# ---------------------------------------------------------------------------
# Coverage mode: compare INDEX.json entries against routing tables
# ---------------------------------------------------------------------------

# Matches the bold name in the first column of a markdown table row, e.g.:
#   | **golang-general-engineer** | ... |
#   | **fast (FORCE)** | ... |
#   | **/pr-review command** | ... |
ROUTING_TABLE_NAME_RE = re.compile(
    r"^\|\s*\*\*"  # row start, bold open
    r"(/?"  # optional leading slash (e.g. /pr-review)
    r"[\w][\w-]*)"  # the component name
    r"(?:\s*\(.*?\))?"  # optional parenthetical like (FORCE) or (pipeline-orchestrator-engineer)
    r"\*\*"  # bold close
    r".*\|",  # rest of the row
)


def parse_routing_table_names(routing_tables_path: Path) -> dict[str, set[str]]:
    """Parse routing-tables.md and extract component names by type.

    Returns a dict with keys 'agents', 'skills', 'pipelines' mapping to
    sets of component names found in the routing table entries.
    """
    content = routing_tables_path.read_text(encoding="utf-8")

    agents: set[str] = set()
    skills: set[str] = set()
    pipelines: set[str] = set()

    current_section = ""
    in_subsection = False

    for line in content.splitlines():
        # Track which section we're in via ## headers
        if line.startswith("## "):
            header = line.lstrip("# ").strip().lower()
            if "agent" in header:
                current_section = "agents"
            elif "pipeline" in header:
                current_section = "pipelines"
            else:
                current_section = "skills"
            in_subsection = False
            continue

        # Skip ### subsections (companion maps, infrastructure refs, policies)
        if line.startswith("### "):
            in_subsection = True
            continue

        if in_subsection:
            continue

        m = ROUTING_TABLE_NAME_RE.match(line)
        if not m:
            continue

        name = m.group(1).lstrip("/")

        if current_section == "agents":
            agents.add(name)
        elif current_section == "pipelines":
            pipelines.add(name)
        else:
            skills.add(name)

    return {"agents": agents, "skills": skills, "pipelines": pipelines}


def run_coverage_report(indexes: dict[str, tuple[dict, Path]], routing_tables_path: Path) -> int:
    """Compare INDEX.json components against routing tables and report gaps.

    Returns 0 if full coverage, 1 if gaps found.
    """
    if not routing_tables_path.exists():
        print(f"Error: routing tables not found at {routing_tables_path}", file=sys.stderr)
        return 1

    routed = parse_routing_table_names(routing_tables_path)

    has_gaps = False
    missing_from_routing: dict[str, list[str]] = {}
    stale_in_routing: dict[str, list[str]] = {}

    print("Routing Coverage Report:")

    for label, (idx, _path) in indexes.items():
        collection_key = label.lower()
        indexed_names = set(idx.get(collection_key, {}).keys())
        routed_names = routed.get(collection_key, set())

        missing = sorted(indexed_names - routed_names)
        stale = sorted(routed_names - indexed_names)

        in_routing_count = len(indexed_names & routed_names)
        print(f"  {label}: {len(indexed_names)} indexed, {in_routing_count} in routing tables, {len(missing)} missing")

        if missing:
            missing_from_routing[collection_key] = missing
            has_gaps = True
        if stale:
            stale_in_routing[collection_key] = stale
            has_gaps = True

    # Detail sections
    if missing_from_routing:
        print("\n  Missing from routing tables:")
        for component_type, names in sorted(missing_from_routing.items()):
            print(f"    {component_type}: {', '.join(names)}")

    if stale_in_routing:
        print("\n  Stale routing entries (not in INDEX):")
        for component_type, names in sorted(stale_in_routing.items()):
            print(f"    {component_type}: {', '.join(names)}")

    if not missing_from_routing and not stale_in_routing:
        print("\n  Full coverage — all components are routable.")

    return 1 if has_gaps else 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate INDEX.json files for agents, skills, and pipelines.")
    parser.add_argument(
        "--type",
        choices=["agents", "skills", "pipelines", "all"],
        default="all",
        help="Component type to generate (default: all)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated output vs current files, exit 1 if different",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Compare INDEX.json components against routing tables, report gaps",
    )
    parser.add_argument(
        "--routing-tables",
        type=Path,
        default=Path.home() / ".claude" / "skills" / "do" / "references" / "routing-tables.md",
        help="Path to routing-tables.md (default: ~/.claude/skills/do/references/routing-tables.md)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    agents_dir = repo_root / "agents"
    skills_dir = repo_root / "skills"
    pipelines_dir = repo_root / "pipelines"

    types = [args.type] if args.type != "all" else ["agents", "skills", "pipelines"]

    indexes: dict[str, tuple[dict, Path]] = {}

    if "agents" in types:
        if not agents_dir.exists():
            print(f"Error: agents directory not found at {agents_dir}", file=sys.stderr)
            return 1
        idx = generate_agents_index(agents_dir)
        indexes["Agents"] = (idx, agents_dir / "INDEX.json")

    if "skills" in types:
        if not skills_dir.exists():
            print(f"Error: skills directory not found at {skills_dir}", file=sys.stderr)
            return 1
        idx = generate_skill_or_pipeline_index(skills_dir, "skills", "skills")
        indexes["Skills"] = (idx, skills_dir / "INDEX.json")

    if "pipelines" in types:
        if pipelines_dir.exists():
            idx = generate_skill_or_pipeline_index(pipelines_dir, "pipelines", "pipelines", is_pipeline=True)
            indexes["Pipelines"] = (idx, pipelines_dir / "INDEX.json")

    if args.coverage:
        return run_coverage_report(indexes, args.routing_tables)

    if args.check:
        print("Checking INDEX.json files...")
        all_match = True
        for label, (idx, path) in indexes.items():
            if not check_index(idx, path, label):
                all_match = False
        if all_match:
            print("All INDEX.json files are up to date.")
            return 0
        else:
            print("INDEX.json files are out of date. Run without --check to regenerate.")
            return 1

    # Write mode
    for label, (idx, path) in indexes.items():
        path.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")

    # Summary
    parts = []
    for label, (idx, path) in indexes.items():
        collection_key = label.lower()
        count = len(idx.get(collection_key, {}))
        parts.append(f"{path} ({count} {collection_key})")
    print(f"Generated {', '.join(parts)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
