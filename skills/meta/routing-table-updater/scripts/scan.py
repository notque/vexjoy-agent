#!/usr/bin/env python3
"""
Scan script for routing-table-updater skill.
Discovers all skills and agents in the repository.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List


class ScanError(Exception):
    """Custom exception for scan errors."""

    pass


def scan_skills(repo_path: Path) -> List[str]:
    """
    Scan for all skill SKILL.md files.

    Returns list of relative paths from repo root.
    """
    skills_dir = repo_path / "skills"

    if not skills_dir.exists():
        raise ScanError(f"Skills directory not found: {skills_dir}")

    if not skills_dir.is_dir():
        raise ScanError(f"Skills path is not a directory: {skills_dir}")

    skill_files = []

    # Each skill should be in skills/{skill-name}/SKILL.md
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists() and skill_md.is_file():
            # Store relative path from repo root
            rel_path = skill_md.relative_to(repo_path)
            skill_files.append(str(rel_path))

    return sorted(skill_files)


def scan_agents(repo_path: Path) -> List[str]:
    """
    Scan for all agent markdown files.

    Returns list of relative paths from repo root.
    """
    agents_dir = repo_path / "agents"

    if not agents_dir.exists():
        raise ScanError(f"Agents directory not found: {agents_dir}")

    if not agents_dir.is_dir():
        raise ScanError(f"Agents path is not a directory: {agents_dir}")

    agent_files = []

    # Agents are directly in agents/*.md
    for agent_file in agents_dir.glob("*.md"):
        if agent_file.is_file():
            # Skip README.md
            if agent_file.name.lower() == "readme.md":
                continue

            # Store relative path from repo root
            rel_path = agent_file.relative_to(repo_path)
            agent_files.append(str(rel_path))

    return sorted(agent_files)


def validate_repository(repo_path: Path) -> None:
    """Validate repository structure."""
    if not repo_path.exists():
        raise ScanError(f"Repository path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ScanError(f"Repository path is not a directory: {repo_path}")

    # Check for commands/do.md (target file)
    do_md = repo_path / "commands" / "do.md"
    if not do_md.exists():
        raise ScanError(f"Target routing file not found: {do_md}\nThis skill requires commands/do.md to exist")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scan repository for skills and agents", formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--repo", type=Path, required=True, help="Repository root path (contains skills/ and agents/ directories)"
    )
    parser.add_argument("--output", type=Path, help="Output JSON file path (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output to stderr")

    args = parser.parse_args()

    try:
        if args.verbose:
            print(f"Scanning repository: {args.repo}", file=sys.stderr)

        # Validate repository structure
        validate_repository(args.repo)

        # Scan for skills
        if args.verbose:
            print("Scanning for skills...", file=sys.stderr)
        skills = scan_skills(args.repo)

        # Scan for agents
        if args.verbose:
            print("Scanning for agents...", file=sys.stderr)
        agents = scan_agents(args.repo)

        # Build result
        result = {
            "status": "success",
            "repository": str(args.repo.resolve()),
            "skills_found": len(skills),
            "agents_found": len(agents),
            "skills": skills,
            "agents": agents,
        }

        if args.verbose:
            print(f"Found {len(skills)} skills and {len(agents)} agents", file=sys.stderr)

        # Output result
        output_json = json.dumps(result, indent=2, ensure_ascii=False)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)

            if args.verbose:
                print(f"Results written to: {args.output}", file=sys.stderr)
        else:
            print(output_json)

    except ScanError as e:
        print(json.dumps({"status": "error", "error_type": "ScanError", "message": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
