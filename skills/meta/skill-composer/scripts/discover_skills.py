#!/usr/bin/env python3
"""
Skill discovery script for skill-composer.
Scans available skills and builds metadata index.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


class SkillDiscoveryError(Exception):
    """Skill discovery related errors."""

    pass


def extract_yaml_frontmatter(skill_md_path: Path) -> Dict[str, str]:
    """Extract YAML frontmatter from SKILL.md file."""
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for YAML frontmatter
    if not content.startswith("---"):
        raise SkillDiscoveryError(f"No YAML frontmatter in {skill_md_path}")

    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise SkillDiscoveryError(f"Malformed YAML frontmatter in {skill_md_path}")

    frontmatter = parts[1].strip()
    _ = parts[2].strip()  # Body content not used in discovery

    # Parse YAML manually (simple key: value parsing)
    yaml_data = {}
    current_key = None
    current_value = []

    for line in frontmatter.split("\n"):
        # Check if this is a key: value line
        if ":" in line and not line.startswith(" "):
            # Save previous key if exists
            if current_key:
                yaml_data[current_key] = "\n".join(current_value).strip()

            # Parse new key
            key, value = line.split(":", 1)
            current_key = key.strip()
            current_value = [value.strip()] if value.strip() else []
        elif current_key and line.strip():
            # Multi-line value continuation
            current_value.append(line.strip())

    # Save last key
    if current_key:
        yaml_data[current_key] = "\n".join(current_value).strip()

    return yaml_data


def extract_skill_metadata(skill_md_path: Path) -> Dict[str, Any]:
    """Extract comprehensive metadata from SKILL.md."""
    yaml_data = extract_yaml_frontmatter(skill_md_path)

    # Read full content for additional analysis
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract operator context if present
    operator_context = extract_operator_context(content)

    # Infer input/output types from content
    inputs, outputs = infer_io_types(content)

    # Detect dependencies on other skills
    dependencies = detect_skill_dependencies(content)

    metadata = {
        "name": yaml_data.get("name", ""),
        "description": yaml_data.get("description", ""),
        "version": yaml_data.get("version", "1.0.0"),
        "file_path": str(skill_md_path),
        "inputs": inputs,
        "outputs": outputs,
        "dependencies": dependencies,
        "operator_context": operator_context,
        "has_scripts": (skill_md_path.parent / "scripts").exists(),
        "has_references": (skill_md_path.parent / "references").exists(),
    }

    return metadata


def extract_operator_context(content: str) -> Dict[str, List[str]]:
    """Extract operator context behaviors from content."""
    context = {"hardcoded": [], "default_on": [], "optional": []}

    # Find operator context section
    operator_match = re.search(r"## Operator Context.*?(?=\n## |\Z)", content, re.DOTALL)

    if not operator_match:
        return context

    operator_section = operator_match.group(0)

    # Extract hardcoded behaviors
    hardcoded_match = re.search(r"### Hardcoded Behaviors.*?(?=\n### |\Z)", operator_section, re.DOTALL)
    if hardcoded_match:
        context["hardcoded"] = extract_bullet_points(hardcoded_match.group(0))

    # Extract default behaviors
    default_match = re.search(r"### Default Behaviors.*?(?=\n### |\Z)", operator_section, re.DOTALL)
    if default_match:
        context["default_on"] = extract_bullet_points(default_match.group(0))

    # Extract optional behaviors
    optional_match = re.search(r"### Optional Behaviors.*?(?=\n### |\Z)", operator_section, re.DOTALL)
    if optional_match:
        context["optional"] = extract_bullet_points(optional_match.group(0))

    return context


def extract_bullet_points(text: str) -> List[str]:
    """Extract bullet points from text."""
    bullets = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- **"):
            # Extract the bold part as the key point
            match = re.match(r"- \*\*([^*]+)\*\*", line)
            if match:
                bullets.append(match.group(1))
    return bullets


def infer_io_types(content: str) -> tuple[List[str], List[str]]:
    """Infer input and output types from skill content."""
    inputs = []
    outputs = []

    # Look for common input patterns
    if "file_path" in content.lower() or "--input" in content:
        inputs.append("file_path")
    if "directory" in content.lower() or "--dir" in content:
        inputs.append("directory")
    if "config" in content.lower() or "--config" in content:
        inputs.append("configuration")
    if "repository" in content.lower() or "repo" in content:
        inputs.append("repository")

    # Look for common output patterns
    if "report" in content.lower() or "generate report" in content:
        outputs.append("report")
    if "json" in content.lower() or ".json" in content:
        outputs.append("json_data")
    if "markdown" in content.lower() or ".md" in content:
        outputs.append("markdown")
    if "validation" in content.lower() or "validate" in content:
        outputs.append("validation_result")
    if "test" in content.lower() or "tests" in content:
        outputs.append("test_results")

    return inputs, outputs


def detect_skill_dependencies(content: str) -> List[str]:
    """Detect references to other skills in content."""
    dependencies = []

    # Common skill reference patterns
    skill_patterns = [
        r"skill:\s*([a-z-]+)",
        r"invoke.*?([a-z-]+)\s+skill",
        r"use.*?([a-z-]+)\s+skill",
        r"after.*?([a-z-]+)\s+skill",
    ]

    for pattern in skill_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        dependencies.extend(matches)

    # Remove duplicates and self-references
    dependencies = list(set(dependencies))

    # Filter out common false positives
    false_positives = ["the", "a", "this", "that", "other", "new", "main"]
    dependencies = [d for d in dependencies if d not in false_positives]

    return dependencies


def discover_skills(skills_dir: Path) -> List[Dict[str, Any]]:
    """Discover all skills in directory."""
    skills = []
    errors = []

    # Find all SKILL.md files
    skill_files = list(skills_dir.glob("*/SKILL.md"))

    print(f"Discovering skills in {skills_dir}...", file=sys.stderr)
    print(f"Found {len(skill_files)} potential skills", file=sys.stderr)

    for skill_file in skill_files:
        try:
            metadata = extract_skill_metadata(skill_file)
            skills.append(metadata)
            print(f"  ✓ {metadata['name']}", file=sys.stderr)
        except Exception as e:
            error_msg = f"  ✗ {skill_file.parent.name}: {e}"
            errors.append(error_msg)
            print(error_msg, file=sys.stderr)

    print(f"\nDiscovered {len(skills)} skills successfully", file=sys.stderr)
    if errors:
        print(f"Encountered {len(errors)} errors", file=sys.stderr)

    return skills


def build_skill_index(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build comprehensive skill index."""
    index = {
        "total_skills": len(skills),
        "skills": skills,
        "skill_map": {skill["name"]: skill for skill in skills},
        "categories": categorize_skills(skills),
        "dependency_graph": build_dependency_graph(skills),
    }

    return index


def categorize_skills(skills: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Categorize skills by domain."""
    categories = {
        "testing": [],
        "quality": [],
        "documentation": [],
        "workflow": [],
        "code-analysis": [],
        "debugging": [],
        "other": [],
    }

    for skill in skills:
        name = skill["name"]
        desc = skill["description"].lower()

        if any(word in desc for word in ["test", "tdd", "red-green-refactor"]):
            categories["testing"].append(name)
        elif any(word in desc for word in ["quality", "lint", "style", "validation"]):
            categories["quality"].append(name)
        elif any(word in desc for word in ["comment", "documentation", "doc"]):
            categories["documentation"].append(name)
        elif any(word in desc for word in ["workflow", "orchestrat", "task"]):
            categories["workflow"].append(name)
        elif any(word in desc for word in ["analyz", "pattern", "extract", "mine"]):
            categories["code-analysis"].append(name)
        elif any(word in desc for word in ["debug", "fix", "diagnos"]):
            categories["debugging"].append(name)
        else:
            categories["other"].append(name)

    return categories


def build_dependency_graph(skills: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Build dependency graph from skill dependencies."""
    graph = {}

    for skill in skills:
        skill_name = skill["name"]
        dependencies = skill.get("dependencies", [])

        # Only include dependencies that reference known skills
        valid_deps = [dep for dep in dependencies if any(s["name"] == dep for s in skills)]

        if valid_deps:
            graph[skill_name] = valid_deps

    return graph


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Discover skills and build metadata index")
    parser.add_argument("--skills-dir", type=Path, required=True, help="Directory containing skills")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON file path")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    try:
        # Validate skills directory
        if not args.skills_dir.exists():
            raise SkillDiscoveryError(f"Skills directory not found: {args.skills_dir}")

        if not args.skills_dir.is_dir():
            raise SkillDiscoveryError(f"Not a directory: {args.skills_dir}")

        # Discover skills
        skills = discover_skills(args.skills_dir)

        if not skills:
            raise SkillDiscoveryError("No skills found")

        # Build index
        print("\nBuilding skill index...", file=sys.stderr)
        index = build_skill_index(skills)

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        print(f"Index written to: {args.output}", file=sys.stderr)

        # Print summary
        print("\n" + "=" * 60, file=sys.stderr)
        print("SKILL INDEX SUMMARY", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Total skills: {index['total_skills']}", file=sys.stderr)
        print("\nCategories:", file=sys.stderr)
        for category, skill_list in index["categories"].items():
            if skill_list:
                print(f"  {category}: {len(skill_list)}", file=sys.stderr)
        print(
            f"\nSkills with dependencies: {len(index['dependency_graph'])}",
            file=sys.stderr,
        )
        print("=" * 60, file=sys.stderr)

        # Output success to stdout
        print(
            json.dumps(
                {
                    "status": "success",
                    "total_skills": index["total_skills"],
                    "output_file": str(args.output),
                },
                indent=2,
            )
        )

    except SkillDiscoveryError as e:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": "SkillDiscoveryError",
                    "message": str(e),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            json.dumps(
                {"status": "error", "error_type": type(e).__name__, "message": str(e)},
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
