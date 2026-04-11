#!/usr/bin/env python3
"""Generate a compact routing manifest for the Haiku routing agent.

Reads skills/INDEX.json, agents/INDEX.json, and pipeline-index.json,
then outputs a compact text manifest that an LLM can parse efficiently.

Usage:
    python3 scripts/routing-manifest.py
    python3 scripts/routing-manifest.py --json

Exit codes:
    0 — Always (advisory)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_index(tracked: Path, local_name: str) -> Path:
    """Return the local override path when it exists, otherwise the tracked path.

    Local override files (INDEX.local.json) are gitignored and may contain
    entries for symlinked directories. They are produced by running the
    generator with --include-private --output <local-path>.
    """
    local = tracked.parent / local_name
    return local if local.exists() else tracked


INDEX_PATHS = {
    "skills": _resolve_index(REPO_ROOT / "skills" / "INDEX.json", "INDEX.local.json"),
    "agents": _resolve_index(REPO_ROOT / "agents" / "INDEX.json", "INDEX.local.json"),
    "pipelines": REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json",
}


def load_entries() -> list[dict]:
    """Load all INDEX entries into a flat list."""
    entries = []

    for index_type, path in INDEX_PATHS.items():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

        items = raw.get(index_type, {})
        if not isinstance(items, dict):
            continue

        for name, data in items.items():
            if not isinstance(data, dict):
                continue
            entries.append(
                {
                    "name": name,
                    "type": "skill" if index_type == "skills" else index_type.rstrip("s"),
                    "description": data.get("description") or data.get("short_description", ""),
                    "triggers": data.get("triggers", []),
                    "category": data.get("category", ""),
                    "agent": data.get("agent"),
                    "model": data.get("model"),
                    "pairs_with": data.get("pairs_with", []),
                    "force_route": bool(data.get("force_route", False)),
                }
            )

    return entries


def format_compact(entries: list[dict]) -> str:
    """Format entries as a compact text manifest for LLM consumption.

    Two sections: agents (with paired skills) and skills (with triggers).
    Optimized for token efficiency — one line per entry.
    """
    agents = []
    skills = []
    pipelines = []

    for e in entries:
        name = e["name"]
        desc = e["description"]
        pairs = ", ".join(e["pairs_with"][:3]) if e["pairs_with"] else ""

        if e["type"] == "agent":
            pairs_str = f" [{pairs}]" if pairs else ""
            agents.append(f"  {name}{pairs_str} — {desc}")
        elif e["type"] == "pipeline":
            pipelines.append(f"  {name} — {desc}")
        else:
            force_str = " FORCE" if e.get("force_route") else ""
            agent_str = f" agent={e['agent']}" if e.get("agent") else ""
            cat_str = f" ({e['category']})" if e.get("category") else ""
            skills.append(f"  {name}{force_str}{agent_str}{cat_str} — {desc}")

    sections = []
    if agents:
        sections.append("AGENTS:\n" + "\n".join(sorted(agents)))
    if skills:
        sections.append("SKILLS:\n" + "\n".join(sorted(skills)))
    if pipelines:
        sections.append("PIPELINES:\n" + "\n".join(sorted(pipelines)))

    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate routing manifest for Haiku agent.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    entries = load_entries()

    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        print(format_compact(entries))

    return 0


if __name__ == "__main__":
    sys.exit(main())
