#!/usr/bin/env python3
"""
Documentation parser script for docs-sync-checker skill.
Parses README files to extract documented tools and detect sync issues.
"""

__version__ = "1.0.0"

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


class DocumentationParser:
    """Parse documentation files to extract tool references."""

    def __init__(self, repo_root: Path, debug: bool = False):
        self.repo_root = Path(repo_root).resolve()
        self.debug = debug
        self.errors: List[str] = []

    def log(self, message: str) -> None:
        """Log debug message."""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def parse_markdown_table(self, content: str, start_marker: str = None) -> List[Dict[str, str]]:
        """
        Parse markdown table from content.

        Args:
            content: Markdown file content
            start_marker: Optional header line to start parsing after

        Returns:
            List of row dicts with column names as keys
        """
        rows = []
        lines = content.split("\n")

        # Find start position
        start_idx = 0
        if start_marker:
            for i, line in enumerate(lines):
                if start_marker.lower() in line.lower():
                    start_idx = i
                    break

        # Find table header
        header_idx = None
        for i in range(start_idx, len(lines)):
            if "|" in lines[i]:
                header_idx = i
                break

        if header_idx is None:
            self.log("No markdown table found")
            return rows

        # Parse header
        header_line = lines[header_idx].strip()
        headers = [h.strip() for h in header_line.split("|") if h.strip()]

        # Skip separator line
        data_start = header_idx + 2

        # Parse data rows
        for line in lines[data_start:]:
            line = line.strip()

            # Stop at empty line or non-table line
            if not line or "|" not in line:
                break

            # Skip separator lines
            if re.match(r"^[\|\-\s:]+$", line):
                continue

            # Parse row
            cells = [c.strip() for c in line.split("|") if c.strip()]

            if len(cells) >= len(headers):
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(cells):
                        row_dict[header.lower()] = cells[i]
                rows.append(row_dict)

        return rows

    def parse_markdown_list(self, content: str, start_marker: str = None) -> List[str]:
        """
        Parse markdown list items.

        Returns:
            List of list item strings
        """
        items = []
        lines = content.split("\n")

        # Find start position
        start_idx = 0
        if start_marker:
            for i, line in enumerate(lines):
                if start_marker.lower() in line.lower():
                    start_idx = i
                    break

        # Parse list items (- or *)
        in_list = False
        for i in range(start_idx, len(lines)):
            line = lines[i].strip()

            # Start of list
            if line.startswith("-") or line.startswith("*"):
                in_list = True
                item = line.lstrip("-*").strip()
                items.append(item)
            # Continue list
            elif in_list and (line.startswith(" ") or line.startswith("\t")):
                # Indented continuation of previous item
                continue
            # End of list
            elif in_list and line and not line.startswith("-") and not line.startswith("*"):
                break

        return items

    def parse_skills_readme(self) -> List[Dict[str, str]]:
        """
        Parse skills/README.md table.

        Expected format:
        | Name | Description | Command | Hook |
        """
        readme_path = self.repo_root / "skills" / "README.md"

        if not readme_path.exists():
            self.log(f"Skills README not found: {readme_path}")
            return []

        self.log(f"Parsing {readme_path}")

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        rows = self.parse_markdown_table(content)

        # Normalize to standard format
        skills = []
        for row in rows:
            # Try common column names
            name = row.get("name") or row.get("skill") or row.get("skill name")
            description = row.get("description") or row.get("desc")
            command = row.get("command") or row.get("usage")

            if name:
                skills.append(
                    {
                        "name": name,
                        "description": description or "",
                        "command": command or "",
                        "source": "skills/README.md",
                    }
                )

        self.log(f"Found {len(skills)} skills in README")
        return skills

    def parse_agents_readme(self) -> List[Dict[str, str]]:
        """
        Parse agents/README.md table or list.

        Expected format can vary (table or list).
        """
        readme_path = self.repo_root / "agents" / "README.md"

        if not readme_path.exists():
            self.log(f"Agents README not found: {readme_path}")
            return []

        self.log(f"Parsing {readme_path}")

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try table format first
        rows = self.parse_markdown_table(content)
        if rows:
            agents = []
            for row in rows:
                name = row.get("name") or row.get("agent") or row.get("agent name")
                description = row.get("description") or row.get("desc")

                if name:
                    agents.append({"name": name, "description": description or "", "source": "agents/README.md"})
            self.log(f"Found {len(agents)} agents in README (table format)")
            return agents

        # Try list format
        items = self.parse_markdown_list(content)
        agents = []
        for item in items:
            # Parse "agent-name - Description" or "agent-name: Description"
            match = re.match(r"^([a-z0-9\-]+)[\s\-:]+(.+)$", item)
            if match:
                name, description = match.groups()
                agents.append({"name": name.strip(), "description": description.strip(), "source": "agents/README.md"})

        self.log(f"Found {len(agents)} agents in README (list format)")
        return agents

    def parse_commands_readme(self) -> List[Dict[str, str]]:
        """
        Parse commands/README.md list.

        Expected format: list of commands with descriptions.
        """
        readme_path = self.repo_root / "commands" / "README.md"

        if not readme_path.exists():
            self.log(f"Commands README not found: {readme_path}")
            return []

        self.log(f"Parsing {readme_path}")

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try table format
        rows = self.parse_markdown_table(content)
        if rows:
            commands = []
            for row in rows:
                name = row.get("command") or row.get("name")
                description = row.get("description") or row.get("desc")

                if name:
                    # Strip leading / if present
                    name = name.lstrip("/")
                    commands.append({"name": name, "description": description or "", "source": "commands/README.md"})
            self.log(f"Found {len(commands)} commands (table format)")
            return commands

        # Try list format
        items = self.parse_markdown_list(content)
        commands = []
        for item in items:
            # Parse "/command - Description" or "command: Description"
            match = re.match(r"^/?([a-z0-9/\-]+)[\s\-:]+(.+)$", item, re.IGNORECASE)
            if match:
                name, description = match.groups()
                commands.append(
                    {"name": name.strip(), "description": description.strip(), "source": "commands/README.md"}
                )

        self.log(f"Found {len(commands)} commands (list format)")
        return commands

    def parse_root_readme(self) -> List[Dict[str, str]]:
        """
        Parse root README.md for tool references.

        This file typically has high-level overview, not comprehensive list.
        """
        readme_path = self.repo_root / "README.md"

        if not readme_path.exists():
            self.log(f"Root README not found: {readme_path}")
            return []

        self.log(f"Parsing {readme_path}")

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract tool references (simple pattern matching)
        tools = []

        # Look for skill references: `skill: skill-name`
        skill_pattern = r"`skill:\s*([a-z0-9\-]+)`"
        for match in re.finditer(skill_pattern, content):
            tools.append({"type": "skill", "name": match.group(1), "source": "README.md"})

        # Look for agent references in text
        agent_pattern = r"`([a-z0-9\-]+(?:engineer|agent))`"
        for match in re.finditer(agent_pattern, content):
            tools.append({"type": "agent", "name": match.group(1), "source": "README.md"})

        # Look for command references: `/command`
        command_pattern = r"`/([a-z0-9/\-]+)`"
        for match in re.finditer(command_pattern, content):
            tools.append({"type": "command", "name": match.group(1), "source": "README.md"})

        self.log(f"Found {len(tools)} tool references in root README")
        return tools

    def parse_reference_doc(self) -> List[Dict[str, str]]:
        """
        Parse docs/REFERENCE.md for comprehensive tool documentation.
        """
        ref_path = self.repo_root / "docs" / "REFERENCE.md"

        if not ref_path.exists():
            self.log(f"Reference doc not found: {ref_path}")
            return []

        self.log(f"Parsing {ref_path}")

        with open(ref_path, "r", encoding="utf-8") as f:
            content = f.read()

        tools = []

        # Look for skill sections (### skill-name)
        skill_pattern = r"###\s+([a-z0-9\-]+)"
        for match in re.finditer(skill_pattern, content):
            skill_name = match.group(1)
            # Try to extract description (next line after header)
            pos = match.end()
            next_lines = content[pos : pos + 500].split("\n")
            description = ""
            for line in next_lines[1:]:  # Skip empty line after header
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line
                    break

            tools.append(
                {"type": "skill", "name": skill_name, "description": description, "source": "docs/REFERENCE.md"}
            )

        self.log(f"Found {len(tools)} tools in REFERENCE.md")
        return tools

    def detect_issues(
        self, scan_results: Dict[str, Any], documented: Dict[str, List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """
        Detect sync issues by comparing scan results with documented tools.

        Returns:
            Dict with issues categorized by type
        """
        issues = {"missing_entries": [], "stale_entries": [], "version_mismatches": [], "incomplete_entries": []}

        # Build sets of discovered tool names
        discovered_skills = {s["name"] for s in scan_results.get("skills", [])}
        discovered_agents = {a["name"] for a in scan_results.get("agents", [])}
        discovered_commands = {c["name"] for c in scan_results.get("commands", [])}

        # Build lookup for versions
        skill_versions = {s["name"]: s["version"] for s in scan_results.get("skills", [])}
        agent_versions = {a["name"]: a["version"] for a in scan_results.get("agents", [])}

        # Check skills README
        skills_readme = documented.get("skills/README.md", [])
        documented_skills = {s["name"] for s in skills_readme}

        # Missing skills
        for skill in discovered_skills - documented_skills:
            skill_info = next((s for s in scan_results["skills"] if s["name"] == skill), None)
            if skill_info:
                issues["missing_entries"].append(
                    {
                        "tool_type": "skill",
                        "tool_name": skill,
                        "tool_path": skill_info["path"],
                        "missing_from": ["skills/README.md"],
                        "severity": "high",
                        "yaml_description": skill_info["description"],
                    }
                )

        # Stale skills
        for skill in documented_skills - discovered_skills:
            issues["stale_entries"].append(
                {"tool_type": "skill", "tool_name": skill, "documented_in": ["skills/README.md"], "severity": "medium"}
            )

        # Version mismatches for skills
        for skill in skills_readme:
            skill_name = skill["name"]
            if skill_name in skill_versions:
                # Try to extract version from command or description
                # This is heuristic - version may not always be in README
                pass  # Version comparison would need version column in README

        # Check agents README
        agents_readme = documented.get("agents/README.md", [])
        documented_agents = {a["name"] for a in agents_readme}

        # Missing agents
        for agent in discovered_agents - documented_agents:
            agent_info = next((a for a in scan_results["agents"] if a["name"] == agent), None)
            if agent_info:
                issues["missing_entries"].append(
                    {
                        "tool_type": "agent",
                        "tool_name": agent,
                        "tool_path": agent_info["path"],
                        "missing_from": ["agents/README.md"],
                        "severity": "high",
                        "yaml_description": agent_info["description"],
                    }
                )

        # Stale agents
        for agent in documented_agents - discovered_agents:
            issues["stale_entries"].append(
                {"tool_type": "agent", "tool_name": agent, "documented_in": ["agents/README.md"], "severity": "medium"}
            )

        # Check commands README
        commands_readme = documented.get("commands/README.md", [])
        documented_commands = {c["name"] for c in commands_readme}

        # Missing commands
        for command in discovered_commands - documented_commands:
            command_info = next((c for c in scan_results["commands"] if c["name"] == command), None)
            if command_info:
                issues["missing_entries"].append(
                    {
                        "tool_type": "command",
                        "tool_name": command,
                        "tool_path": command_info["path"],
                        "missing_from": ["commands/README.md"],
                        "severity": "high",
                        "yaml_description": command_info.get("description", ""),
                    }
                )

        # Stale commands
        for command in documented_commands - discovered_commands:
            issues["stale_entries"].append(
                {
                    "tool_type": "command",
                    "tool_name": command,
                    "documented_in": ["commands/README.md"],
                    "severity": "medium",
                }
            )

        return issues


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parse documentation files and detect sync issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo-root", type=Path, required=True, help="Repository root directory")
    parser.add_argument("--scan-results", type=Path, help="Path to scan results JSON from scan_tools.py")
    parser.add_argument("--output", type=Path, help="Output JSON file (default: stdout)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    try:
        # Parse documentation
        parser_obj = DocumentationParser(args.repo_root, debug=args.debug)

        documented = {
            "skills/README.md": parser_obj.parse_skills_readme(),
            "agents/README.md": parser_obj.parse_agents_readme(),
            "commands/README.md": parser_obj.parse_commands_readme(),
            "README.md": parser_obj.parse_root_readme(),
            "docs/REFERENCE.md": parser_obj.parse_reference_doc(),
        }

        results = {
            "documented": documented,
            "parse_timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "files_parsed": len(documented),
        }

        # Load scan results if provided
        scan_results = None
        if args.scan_results:
            with open(args.scan_results, "r", encoding="utf-8") as f:
                scan_results = json.load(f)

            # Detect issues
            issues = parser_obj.detect_issues(scan_results, documented)
            results["issues"] = issues

            # Summary
            results["summary"] = {
                "missing_entries": len(issues["missing_entries"]),
                "stale_entries": len(issues["stale_entries"]),
                "version_mismatches": len(issues["version_mismatches"]),
                "total_issues": len(issues["missing_entries"])
                + len(issues["stale_entries"])
                + len(issues["version_mismatches"]),
            }

        # Output results
        output_json = json.dumps(results, indent=2, ensure_ascii=False)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"Parse results written to: {args.output}", file=sys.stderr)
        else:
            print(output_json)

        # Exit with error if issues found
        if results.get("summary", {}).get("total_issues", 0) > 0:
            print(f"\nWarning: {results['summary']['total_issues']} sync issues found", file=sys.stderr)
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
