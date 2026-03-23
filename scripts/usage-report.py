#!/usr/bin/env python3
"""
Usage Report CLI - Display skill and agent usage statistics.

Reports which skills and agents are actively used vs. dormant.
Cross-references invocation data against discovered skills/agents on disk.

Usage:
    python3 scripts/usage-report.py                    # Summary report
    python3 scripts/usage-report.py --days 7           # Last 7 days
    python3 scripts/usage-report.py --dormant          # Show dormant skills/agents
    python3 scripts/usage-report.py --json             # JSON output
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve repo root relative to this script (scripts/ -> repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent

# Add hooks/lib to path for usage_db imports
sys.path.insert(0, str(REPO_ROOT / "hooks" / "lib"))


def discover_skills() -> list[str]:
    """Discover all skill names by globbing skills/*/SKILL.md and pipelines/*/SKILL.md."""
    names = []
    for dirname in ("skills", "pipelines"):
        d = REPO_ROOT / dirname
        if d.is_dir():
            for skill_md in d.glob("*/SKILL.md"):
                names.append(skill_md.parent.name)
    return sorted(names)


def discover_agents() -> list[str]:
    """Discover all agent names by globbing agents/*.md."""
    agents_dir = REPO_ROOT / "agents"
    if not agents_dir.is_dir():
        return []

    names = []
    for agent_md in agents_dir.glob("*.md"):
        # Strip .md extension to get agent name
        names.append(agent_md.stem)
    return sorted(names)


def format_time_ago(iso_timestamp: str) -> str:
    """Format an ISO timestamp as a human-readable relative time."""
    try:
        # Parse ISO timestamp — handle both aware and naive
        ts = iso_timestamp.replace("Z", "+00:00")
        if "+" not in ts and ts.count("-") <= 2:
            # Naive timestamp, assume UTC
            dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(ts)

        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"
    except (ValueError, TypeError):
        return "unknown"


def print_text_report(days: int, show_dormant: bool) -> None:
    """Print human-readable usage report."""
    from usage_db import get_agent_usage, get_dormant_agents, get_dormant_skills, get_skill_usage

    skill_usage = get_skill_usage(days=days)
    agent_usage = get_agent_usage(days=days)

    all_skills = discover_skills()
    all_agents = discover_agents()

    print(f"USAGE REPORT (last {days} days)")
    print("=" * 30)
    print()

    # Skills section
    if skill_usage:
        print("Skills (by frequency):")
        for i, s in enumerate(skill_usage, 1):
            name = s["name"]
            count = s["count"]
            last = format_time_ago(s["last_used"])
            print(f"  {i:>3}. {name:<30} {count:>4} calls  (last: {last})")
        print()
    else:
        print("Skills: No invocations recorded.")
        print()

    # Agents section
    if agent_usage:
        print("Agents (by frequency):")
        for i, a in enumerate(agent_usage, 1):
            atype = a["type"]
            count = a["count"]
            last = format_time_ago(a["last_used"])
            print(f"  {i:>3}. {atype:<30} {count:>4} calls  (last: {last})")
        print()
    else:
        print("Agents: No invocations recorded.")
        print()

    # Dormant section (always shown in summary, detailed in --dormant mode)
    dormant_skills = get_dormant_skills(days=days, known_skills=all_skills)
    dormant_agents = get_dormant_agents(days=days, known_agents=all_agents)

    print(f"Dormant (0 calls in {days} days):")
    print(f"  Skills: {len(dormant_skills)} of {len(all_skills)}")
    print(f"  Agents: {len(dormant_agents)} of {len(all_agents)}")

    if show_dormant:
        print()
        if dormant_skills:
            print("Dormant Skills:")
            for name in dormant_skills:
                print(f"  - {name}")
        if dormant_agents:
            print()
            print("Dormant Agents:")
            for name in dormant_agents:
                print(f"  - {name}")


def print_json_report(days: int, show_dormant: bool) -> None:
    """Print JSON usage report."""
    from usage_db import get_agent_usage, get_dormant_agents, get_dormant_skills, get_skill_usage

    all_skills = discover_skills()
    all_agents = discover_agents()

    report = {
        "period_days": days,
        "skills": {
            "usage": get_skill_usage(days=days),
            "total_known": len(all_skills),
        },
        "agents": {
            "usage": get_agent_usage(days=days),
            "total_known": len(all_agents),
        },
    }

    if show_dormant:
        report["skills"]["dormant"] = get_dormant_skills(days=days, known_skills=all_skills)
        report["agents"]["dormant"] = get_dormant_agents(days=days, known_agents=all_agents)
    else:
        dormant_skills = get_dormant_skills(days=days, known_skills=all_skills)
        dormant_agents = get_dormant_agents(days=days, known_agents=all_agents)
        report["skills"]["dormant_count"] = len(dormant_skills)
        report["agents"]["dormant_count"] = len(dormant_agents)

    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Usage report for Claude Code skills and agents")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to report on (default: 30)",
    )
    parser.add_argument(
        "--dormant",
        action="store_true",
        help="Show detailed list of dormant skills and agents",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output in JSON format",
    )

    args = parser.parse_args()

    if args.json_output:
        print_json_report(days=args.days, show_dormant=args.dormant)
    else:
        print_text_report(days=args.days, show_dormant=args.dormant)


if __name__ == "__main__":
    main()
