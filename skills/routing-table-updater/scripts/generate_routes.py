#!/usr/bin/env python3
"""
Generate routing table entries from extracted metadata.
Detects conflicts and applies priority rules.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


class GenerationError(Exception):
    """Custom exception for generation errors."""

    pass


def format_trigger_patterns(patterns: List[str]) -> str:
    """
    Format trigger patterns as quoted comma-separated list.

    Example: ["lint", "format"] → '"lint", "format"'
    """
    if not patterns:
        return '""'

    quoted_patterns = [f'"{p}"' for p in patterns]
    return ", ".join(quoted_patterns)


def generate_intent_detection_entry(capability: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Intent Detection Patterns table entry.

    Table format:
    | User Says | Route To | Complexity | [AUTO-GENERATED] |
    """
    patterns = capability.get("trigger_patterns", [])
    if not patterns:
        raise GenerationError(
            f"No trigger patterns for skill {capability['name']}\n"
            f"Update description to include explicit trigger phrases"
        )

    name = capability["name"]
    complexity = capability["complexity"]

    # Determine route target format
    if "skill" in capability["type"]:
        route_to = f"{name} skill"
    else:
        route_to = f"{name} agent"

    entry = {
        "user_says": format_trigger_patterns(patterns),
        "route_to": route_to,
        "complexity": complexity,
        "auto_generated": True,
        "source_file": capability["file_path"],
        "pattern_list": patterns,  # For conflict detection
    }

    return entry


def generate_domain_specific_entry(capability: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Domain-Specific Routing table entry.

    Table format:
    | Domain Mentioned | Agent | Typical Complexity | [AUTO-GENERATED] |
    """
    keywords = capability.get("domain_keywords", [])
    if not keywords:
        raise GenerationError(
            f"No domain keywords for agent {capability['name']}\nAgent description must include technology names"
        )

    name = capability["name"]
    complexity = capability["complexity"]

    entry = {
        "domain_mentioned": ", ".join(keywords),
        "agent": name,
        "typical_complexity": complexity,
        "auto_generated": True,
        "source_file": capability["file_path"],
        "keyword_list": keywords,  # For conflict detection
    }

    return entry


def generate_task_type_entry(capability: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Task Type Routing table entry.

    Table format:
    | Task Type | Route To Agent | Complexity | [AUTO-GENERATED] |
    """
    # For agents without domain keywords
    name = capability["name"]
    complexity = capability["complexity"]

    # Extract task type from description
    description = capability["description"]

    # Use first sentence or clause as task type
    task_type = description.split(".")[0].strip()
    if len(task_type) > 100:
        task_type = task_type[:97] + "..."

    entry = {
        "task_type": f'"{task_type}"',
        "route_to": f"{name} agent",
        "complexity": complexity,
        "auto_generated": True,
        "source_file": capability["file_path"],
    }

    return entry


def detect_conflicts(entries: List[Dict[str, Any]], table_name: str) -> List[Dict[str, Any]]:
    """
    Detect routing conflicts within a table.

    Returns list of conflict descriptions.
    """
    conflicts = []

    if table_name == "Intent Detection Patterns":
        # Check for pattern overlaps
        pattern_map: Dict[str, List[str]] = {}

        for entry in entries:
            patterns = entry.get("pattern_list", [])
            route = entry["route_to"]

            for pattern in patterns:
                pattern_lower = pattern.lower()
                if pattern_lower not in pattern_map:
                    pattern_map[pattern_lower] = []
                pattern_map[pattern_lower].append(route)

        # Find patterns with multiple routes
        for pattern, routes in pattern_map.items():
            if len(routes) > 1 and len(set(routes)) > 1:  # Multiple different routes
                # Determine severity
                severity = "low"  # Default

                # High severity if routes are incompatible
                if "deploy" in pattern.lower():
                    severity = "high"
                elif any(word in pattern.lower() for word in ["create", "build", "setup"]):
                    severity = "medium"

                conflicts.append(
                    {
                        "pattern": pattern,
                        "routes": list(set(routes)),
                        "severity": severity,
                        "resolution": "More specific pattern takes precedence",
                    }
                )

    elif table_name == "Domain-Specific Routing":
        # Check for domain keyword overlaps
        keyword_map: Dict[str, List[str]] = {}

        for entry in entries:
            keywords = entry.get("keyword_list", [])
            agent = entry["agent"]

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in keyword_map:
                    keyword_map[keyword_lower] = []
                keyword_map[keyword_lower].append(agent)

        # Find keywords with multiple agents
        for keyword, agents in keyword_map.items():
            if len(agents) > 1 and len(set(agents)) > 1:
                conflicts.append(
                    {
                        "keyword": keyword,
                        "agents": list(set(agents)),
                        "severity": "medium",
                        "resolution": "More specific domain context takes precedence",
                    }
                )

    return conflicts


def generate_routing_entries(capabilities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate all routing table entries from capabilities.

    Returns dict organized by routing table.
    """
    routing_entries = {
        "Intent Detection Patterns": [],
        "Task Type Routing": [],
        "Domain-Specific Routing": [],
        "Combination Routing": [],
    }

    all_conflicts = []

    for capability in capabilities:
        routing_table = capability["routing_table"]

        try:
            if routing_table == "Intent Detection Patterns":
                entry = generate_intent_detection_entry(capability)
                routing_entries[routing_table].append(entry)

            elif routing_table == "Domain-Specific Routing":
                entry = generate_domain_specific_entry(capability)
                routing_entries[routing_table].append(entry)

            elif routing_table == "Task Type Routing":
                entry = generate_task_type_entry(capability)
                routing_entries[routing_table].append(entry)

            # Combination routing handled separately (manual only for now)

        except GenerationError as e:
            print(f"WARNING: {e}", file=sys.stderr)
            continue

    # Detect conflicts in each table
    for table_name, entries in routing_entries.items():
        if entries:
            conflicts = detect_conflicts(entries, table_name)
            all_conflicts.extend(conflicts)

    # Sort entries alphabetically within each table
    for table_name in routing_entries:
        if table_name == "Intent Detection Patterns":
            # Sort by first pattern
            routing_entries[table_name].sort(key=lambda e: e.get("pattern_list", [""])[0].lower())
        elif table_name == "Domain-Specific Routing":
            # Sort by first keyword
            routing_entries[table_name].sort(key=lambda e: e.get("keyword_list", [""])[0].lower())
        elif table_name == "Task Type Routing":
            # Sort by task type
            routing_entries[table_name].sort(key=lambda e: e.get("task_type", "").lower())

    return routing_entries, all_conflicts


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate routing table entries from metadata")
    parser.add_argument("--input", type=Path, required=True, help="Input JSON from extract_metadata.py")
    parser.add_argument("--output", type=Path, help="Output JSON file path (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output to stderr")

    args = parser.parse_args()

    try:
        # Load metadata
        if not args.input.exists():
            raise GenerationError(f"Input file not found: {args.input}")

        with open(args.input, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        if metadata.get("status") != "success":
            raise GenerationError(f"Input metadata has error status: {metadata.get('status')}")

        capabilities = metadata["capabilities"]

        if args.verbose:
            print(f"Generating routing entries for {len(capabilities)} capabilities", file=sys.stderr)

        # Generate routing entries
        routing_entries, conflicts = generate_routing_entries(capabilities)

        # Count total entries
        total_entries = sum(len(entries) for entries in routing_entries.values())

        # Build result
        result = {
            "status": "success",
            "entries_generated": total_entries,
            "conflicts_detected": len(conflicts),
            "routing_entries": routing_entries,
            "conflicts": conflicts,
        }

        if args.verbose:
            print(f"Generated {total_entries} routing entries", file=sys.stderr)
            if conflicts:
                print(f"Detected {len(conflicts)} routing conflicts", file=sys.stderr)

        # Output result
        output_json = json.dumps(result, indent=2, ensure_ascii=False)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)

            if args.verbose:
                print(f"Routing entries written to: {args.output}", file=sys.stderr)
        else:
            print(output_json)

    except GenerationError as e:
        print(
            json.dumps({"status": "error", "error_type": "GenerationError", "message": str(e)}, indent=2),
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
