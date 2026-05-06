#!/usr/bin/env python3
"""
Extract metadata from skills and agents for routing table generation.
Parses YAML frontmatter and extracts trigger patterns.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


class ExtractionError(Exception):
    """Custom exception for extraction errors."""

    pass


def extract_yaml_frontmatter(content: str) -> Dict[str, str]:
    """
    Extract YAML frontmatter from markdown content.

    Returns dict with frontmatter fields.
    """
    # Check for frontmatter delimiter
    if not content.startswith("---"):
        raise ExtractionError("No YAML frontmatter found (missing opening ---)")

    # Split by --- to extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ExtractionError("No YAML frontmatter found (missing closing ---)")

    frontmatter_text = parts[1].strip()

    # Parse YAML fields (simple key: value parsing)
    frontmatter = {}
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        frontmatter[key] = value

    return frontmatter


def extract_trigger_patterns(description: str) -> List[str]:
    """
    Extract trigger patterns from description.

    Uses multiple extraction strategies:
    1. Quoted phrases: "pattern1", "pattern2"
    2. "Use when" clauses
    3. Action verbs + domain nouns
    """
    patterns = []

    # Strategy 1: Quoted phrases
    quoted_pattern = r'"([^"]+)"'
    quoted_matches = re.findall(quoted_pattern, description)
    patterns.extend(quoted_matches)

    # Strategy 2: "Use when" clauses
    use_when_pattern = r"(?:Use when|Trigger on|Invoke for)\s+(.+?)(?:\.|$)"
    use_when_match = re.search(use_when_pattern, description, re.IGNORECASE)
    if use_when_match:
        clause = use_when_match.group(1)
        # Extract quoted phrases from clause
        clause_patterns = re.findall(quoted_pattern, clause)
        patterns.extend(clause_patterns)

    # Strategy 3: Common keywords
    keyword_map = {
        "lint": ["lint", "format", "style check"],
        "test": ["test", "TDD", "testing"],
        "review": ["review", "audit", "check quality"],
        "debug": ["debug", "fix bug", "troubleshoot"],
        "refactor": ["refactor", "restructure", "rename"],
        "generate": ["generate", "create", "scaffold"],
    }

    desc_lower = description.lower()
    for keyword, expansions in keyword_map.items():
        if keyword in desc_lower:
            patterns.extend(expansions)

    # Deduplicate and return
    unique_patterns = list(dict.fromkeys(patterns))  # Preserve order
    return unique_patterns


def infer_complexity(description: str) -> str:
    """
    Infer complexity level from description keywords.

    Returns: Trivial, Simple, Medium, Complex, or Medium-Complex
    """
    desc_lower = description.lower()

    # Complex indicators
    complex_keywords = [
        "orchestrate",
        "coordinate",
        "multi-step",
        "complex",
        "research",
        "investigate",
        "comprehensive",
        "systematic",
    ]
    if any(kw in desc_lower for kw in complex_keywords):
        return "Complex"

    # Simple indicators
    simple_keywords = ["quick", "simple", "check", "run", "format", "lint"]
    if any(kw in desc_lower for kw in simple_keywords):
        return "Simple"

    # Trivial indicators
    trivial_keywords = ["status", "lookup", "show", "display"]
    if any(kw in desc_lower for kw in trivial_keywords):
        return "Trivial"

    # Default to Medium
    return "Medium"


def determine_routing_table(capability_type: str, trigger_patterns: List[str], domain_keywords: List[str]) -> str:
    """
    Determine which routing table this capability belongs to.

    Returns: Intent Detection Patterns, Task Type, Domain-Specific, or Combination
    """
    if capability_type == "agent":
        # Agents typically go to Domain-Specific or Task Type
        if domain_keywords:
            return "Domain-Specific Routing"
        else:
            return "Task Type Routing"

    else:  # skill
        # Skills with combinations go to Combination table
        if any("+" in pattern for pattern in trigger_patterns):
            return "Combination Routing"
        # Otherwise Intent Detection
        else:
            return "Intent Detection Patterns"


def extract_domain_keywords(description: str, name: str) -> List[str]:
    """
    Extract domain/technology keywords from agent description.

    Returns list of technology names.
    """
    keywords = []

    # Common technology patterns
    tech_pattern = r"\b(Go|Golang|Python|TypeScript|React|Next\.js|Node\.js|Kubernetes|K8s|Docker|PostgreSQL|MongoDB|Redis|GraphQL|REST|API|SQLite|Peewee|Prometheus|Grafana|RabbitMQ|Ansible|Helm|OpenStack|Elasticsearch|OpenSearch)\b"
    tech_matches = re.findall(tech_pattern, description, re.IGNORECASE)
    keywords.extend(tech_matches)

    # Extract from name (e.g., "golang-general-engineer" → "Golang")
    name_lower = name.lower()
    if "golang" in name_lower or "go-" in name_lower:
        keywords.append("Go")
        keywords.append("Golang")
    if "python" in name_lower:
        keywords.append("Python")
    if "typescript" in name_lower:
        keywords.append("TypeScript")
    if "kubernetes" in name_lower or "k8s" in name_lower:
        keywords.append("Kubernetes")
        keywords.append("K8s")

    # Deduplicate
    unique_keywords = list(dict.fromkeys(keywords))
    return unique_keywords


def extract_capability_metadata(file_path: Path, capability_type: str, repo_path: Path) -> Dict[str, Any]:
    """
    Extract metadata from a single skill or agent file.

    Returns dict with extracted metadata.
    """
    if not file_path.exists():
        raise ExtractionError(f"File not found: {file_path}")

    # Read file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract YAML frontmatter
    try:
        frontmatter = extract_yaml_frontmatter(content)
    except ExtractionError as e:
        raise ExtractionError(f"Error parsing {file_path}: {e}")

    # Validate required fields
    required_fields = ["name", "description"]
    for field in required_fields:
        if field not in frontmatter:
            raise ExtractionError(
                f"Missing required field '{field}' in {file_path}\n"
                f"YAML frontmatter must include: {', '.join(required_fields)}"
            )

    name = frontmatter["name"]
    description = frontmatter["description"]

    # Extract patterns based on type
    if capability_type == "skill":
        trigger_patterns = extract_trigger_patterns(description)
        domain_keywords = []
    else:  # agent
        trigger_patterns = []
        domain_keywords = extract_domain_keywords(description, name)

    # Infer complexity
    complexity = infer_complexity(description)

    # Determine routing table
    routing_table = determine_routing_table(capability_type, trigger_patterns, domain_keywords)

    # Build metadata dict
    metadata = {
        "type": capability_type,
        "name": name,
        "description": description,
        "file_path": str(file_path.relative_to(repo_path)),
        "complexity": complexity,
        "routing_table": routing_table,
    }

    if capability_type == "skill":
        metadata["trigger_patterns"] = trigger_patterns
    else:  # agent
        metadata["domain_keywords"] = domain_keywords

    return metadata


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Extract metadata from skills and agents for routing")
    parser.add_argument("--input", type=Path, required=True, help="Input JSON from scan.py (contains file lists)")
    parser.add_argument("--output", type=Path, help="Output JSON file path (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output to stderr")

    args = parser.parse_args()

    try:
        # Load scan results
        if not args.input.exists():
            raise ExtractionError(f"Input file not found: {args.input}")

        with open(args.input, "r", encoding="utf-8") as f:
            scan_data = json.load(f)

        if scan_data.get("status") != "success":
            raise ExtractionError(f"Input scan data has error status: {scan_data.get('status')}")

        repo_path = Path(scan_data["repository"])
        skills = scan_data["skills"]
        agents = scan_data["agents"]

        if args.verbose:
            print(f"Extracting metadata from {len(skills)} skills and {len(agents)} agents", file=sys.stderr)

        capabilities = []

        # Extract from skills
        for skill_rel_path in skills:
            skill_path = repo_path / skill_rel_path

            if args.verbose:
                print(f"Extracting: {skill_rel_path}", file=sys.stderr)

            try:
                metadata = extract_capability_metadata(skill_path, "skill", repo_path)
                capabilities.append(metadata)
            except ExtractionError as e:
                print(f"WARNING: {e}", file=sys.stderr)
                continue

        # Extract from agents
        for agent_rel_path in agents:
            agent_path = repo_path / agent_rel_path

            if args.verbose:
                print(f"Extracting: {agent_rel_path}", file=sys.stderr)

            try:
                metadata = extract_capability_metadata(agent_path, "agent", repo_path)
                capabilities.append(metadata)
            except ExtractionError as e:
                print(f"WARNING: {e}", file=sys.stderr)
                continue

        # Build result
        result = {"status": "success", "extracted": len(capabilities), "capabilities": capabilities}

        if args.verbose:
            print(f"Extracted metadata from {len(capabilities)} capabilities", file=sys.stderr)

        # Output result
        output_json = json.dumps(result, indent=2, ensure_ascii=False)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)

            if args.verbose:
                print(f"Metadata written to: {args.output}", file=sys.stderr)
        else:
            print(output_json)

    except ExtractionError as e:
        print(
            json.dumps({"status": "error", "error_type": "ExtractionError", "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(1)

    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
