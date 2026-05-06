#!/usr/bin/env python3
"""
Tool discovery script for docs-sync-checker skill.
Scans repository for skills, agents, and commands.
"""

__version__ = "1.0.0"

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class ToolScanner:
    """Discover all tools in repository."""

    def __init__(self, repo_root: Path, debug: bool = False):
        self.repo_root = Path(repo_root).resolve()
        self.debug = debug
        self.errors: List[str] = []

    def log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def parse_yaml_frontmatter(self, file_path: Path) -> Optional[Dict[str, str]]:
        """
        Extract YAML frontmatter from markdown file.

        Returns dict with name, description, version or None if invalid.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for YAML frontmatter
            if not content.startswith("---"):
                self.log(f"No YAML frontmatter in {file_path}")
                return None

            # Extract frontmatter
            parts = content.split("---", 2)
            if len(parts) < 3:
                self.log(f"Malformed YAML frontmatter in {file_path}")
                return None

            frontmatter = parts[1].strip()

            # Parse YAML fields (simple regex-based parsing)
            yaml_data = {}
            for line in frontmatter.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Match "key: value" pattern
                match = re.match(r"^(\w+):\s*(.+)$", line)
                if match:
                    key, value = match.groups()
                    yaml_data[key] = value.strip()

            # Validate required fields
            required_fields = ["name", "description", "version"]
            for field in required_fields:
                if field not in yaml_data:
                    error = f"Missing required field '{field}' in {file_path}"
                    self.log(error)
                    self.errors.append(error)
                    return None

            return yaml_data

        except Exception as e:
            error = f"Error parsing {file_path}: {e}"
            self.log(error)
            self.errors.append(error)
            return None

    def scan_skills(self) -> List[Dict[str, Any]]:
        """
        Scan skills/ directory for SKILL.md files.

        Returns list of skill metadata dicts.
        """
        skills = []
        skills_dir = self.repo_root / "skills"

        if not skills_dir.exists():
            self.log(f"Skills directory not found: {skills_dir}")
            return skills

        self.log(f"Scanning skills directory: {skills_dir}")

        # Find all SKILL.md files in skills/*/SKILL.md
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                self.log(f"No SKILL.md in {skill_dir.name}")
                continue

            yaml_data = self.parse_yaml_frontmatter(skill_file)
            if yaml_data:
                skills.append(
                    {
                        "name": yaml_data["name"],
                        "description": yaml_data["description"],
                        "version": yaml_data.get("version", "unknown"),
                        "path": str(skill_file.relative_to(self.repo_root)),
                        "directory": skill_dir.name,
                    }
                )
                self.log(f"Found skill: {yaml_data['name']} at {skill_file}")

        return skills

    def scan_agents(self) -> List[Dict[str, Any]]:
        """
        Scan agents/ directory for *.md files with YAML frontmatter.

        Returns list of agent metadata dicts.
        """
        agents = []
        agents_dir = self.repo_root / "agents"

        if not agents_dir.exists():
            self.log(f"Agents directory not found: {agents_dir}")
            return agents

        self.log(f"Scanning agents directory: {agents_dir}")

        # Find all .md files in agents/*.md (not subdirectories)
        for agent_file in agents_dir.glob("*.md"):
            if not agent_file.is_file():
                continue

            yaml_data = self.parse_yaml_frontmatter(agent_file)
            if yaml_data:
                agents.append(
                    {
                        "name": yaml_data["name"],
                        "description": yaml_data["description"],
                        "version": yaml_data.get("version", "unknown"),
                        "path": str(agent_file.relative_to(self.repo_root)),
                    }
                )
                self.log(f"Found agent: {yaml_data['name']} at {agent_file}")

        return agents

    def scan_commands(self) -> List[Dict[str, Any]]:
        """
        Scan commands/ directory for *.md files.

        Returns list of command metadata dicts.
        Handles namespaced commands (commands/code/cleanup.md → code/cleanup)
        """
        commands = []
        commands_dir = self.repo_root / "commands"

        if not commands_dir.exists():
            self.log(f"Commands directory not found: {commands_dir}")
            return commands

        self.log(f"Scanning commands directory: {commands_dir}")

        # Find all .md files in commands/**/*.md (recursive)
        for command_file in commands_dir.rglob("*.md"):
            if not command_file.is_file():
                continue

            # Determine namespace and command name
            rel_path = command_file.relative_to(commands_dir)
            parts = rel_path.parts

            if len(parts) == 1:
                # Top-level command: commands/do.md → do
                namespace = None
                command_name = parts[0].replace(".md", "")
            else:
                # Namespaced command: commands/code/cleanup.md → code/cleanup
                namespace = parts[0]
                command_name = "/".join(parts[:-1]) + "/" + parts[-1].replace(".md", "")

            # Try to extract description from file (optional)
            description = self._extract_command_description(command_file)

            commands.append(
                {
                    "name": command_name,
                    "namespace": namespace,
                    "path": str(command_file.relative_to(self.repo_root)),
                    "description": description,
                }
            )
            self.log(f"Found command: {command_name} at {command_file}")

        return commands

    def _extract_command_description(self, file_path: Path) -> str:
        """
        Extract description from command file.

        Tries to find first paragraph or header after title.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Look for first paragraph after title (# Title)
            found_title = False
            for line in lines:
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Skip title line
                if line.startswith("#") and not found_title:
                    found_title = True
                    continue

                # First non-empty, non-header line after title
                if found_title and not line.startswith("#"):
                    return line[:200]  # Max 200 chars

            return "Command description not available"

        except Exception as e:
            self.log(f"Could not extract description from {file_path}: {e}")
            return "Command description not available"

    def scan_all(self, types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Scan all tool types.

        Args:
            types: List of types to scan ('skills', 'agents', 'commands')
                   If None, scan all types.

        Returns:
            Dict with scan results and metadata.
        """
        from datetime import datetime

        if types is None:
            types = ["skills", "agents", "commands"]

        results = {
            "scan_timestamp": datetime.utcnow().isoformat() + "Z",
            "repo_root": str(self.repo_root),
            "scan_version": __version__,
        }

        if "skills" in types:
            results["skills"] = self.scan_skills()
            self.log(f"Found {len(results['skills'])} skills")

        if "agents" in types:
            results["agents"] = self.scan_agents()
            self.log(f"Found {len(results['agents'])} agents")

        if "commands" in types:
            results["commands"] = self.scan_commands()
            self.log(f"Found {len(results['commands'])} commands")

        # Add error summary
        if self.errors:
            results["errors"] = self.errors
            results["error_count"] = len(self.errors)

        return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scan repository for skills, agents, and commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo-root", type=Path, required=True, help="Repository root directory")
    parser.add_argument("--types", type=str, help="Comma-separated list of types to scan (skills,agents,commands)")
    parser.add_argument("--output", type=Path, help="Output JSON file (default: stdout)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Parse types
    types = None
    if args.types:
        types = [t.strip() for t in args.types.split(",")]

    # Validate repo root
    if not args.repo_root.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": "RepositoryNotFound",
                    "message": f"Repository root not found: {args.repo_root}",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Scan repository
        scanner = ToolScanner(args.repo_root, debug=args.debug)
        results = scanner.scan_all(types=types)

        # Add summary
        total_tools = sum(
            [len(results.get("skills", [])), len(results.get("agents", [])), len(results.get("commands", []))]
        )

        results["summary"] = {
            "total_tools": total_tools,
            "skills_count": len(results.get("skills", [])),
            "agents_count": len(results.get("agents", [])),
            "commands_count": len(results.get("commands", [])),
        }

        # Output results
        output_json = json.dumps(results, indent=2, ensure_ascii=False)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"Scan results written to: {args.output}", file=sys.stderr)
        else:
            print(output_json)

        # Exit with error if scan had errors
        if results.get("errors"):
            print(f"\nWarning: {len(results['errors'])} errors during scan", file=sys.stderr)
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
