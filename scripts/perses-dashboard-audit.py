#!/usr/bin/env python3
"""Perses Dashboard Audit.

Audit Perses dashboard definitions for quality metrics:
panel count, query complexity, variable chains, datasource references.

Usage:
    python3 scripts/perses-dashboard-audit.py <file> [--format json|text]
"""

import argparse
import json
import sys
from pathlib import Path


def load_dashboard(path):
    """Load a dashboard definition from JSON or YAML file."""
    filepath = Path(path)
    if not filepath.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        content = filepath.read_text(encoding="utf-8")
    except (PermissionError, OSError) as e:
        print(f"ERROR: cannot read {path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Try JSON first
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Fall back to YAML
        try:
            import yaml
        except ImportError:
            print("ERROR: YAML support requires PyYAML. Install with: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            print(f"ERROR: invalid YAML in {path}: {e}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(data, dict):
        print(
            f"ERROR: {path} does not contain a valid Perses resource (expected object, got {type(data).__name__})",
            file=sys.stderr,
        )
        sys.exit(1)

    return data


def audit_dashboard(dashboard):
    """Audit a dashboard definition and return findings."""
    findings = []
    spec = dashboard.get("spec", {})
    metadata = dashboard.get("metadata", {})

    # Basic info
    name = metadata.get("name", "unknown")
    project = metadata.get("project", "unknown")

    # Panel count
    panels = spec.get("panels", {})
    panel_count = len(panels)

    # Variable analysis
    variables = spec.get("variables", [])
    variable_count = len(variables)
    variable_names = []
    for var in variables:
        var_spec = var.get("spec", {})
        variable_names.append(var_spec.get("name", "unnamed"))

    # Layout analysis
    layouts = spec.get("layouts", [])
    layout_count = len(layouts)
    referenced_panels = set()
    for layout in layouts:
        items = layout.get("spec", {}).get("items", [])
        for item in items:
            ref = item.get("content", {}).get("$ref", "")
            if ref.startswith("#/spec/panels/"):
                referenced_panels.add(ref.split("/")[-1])

    # Unreferenced panels
    unreferenced = set(panels.keys()) - referenced_panels
    if unreferenced:
        findings.append(
            {
                "severity": "warning",
                "message": f"Unreferenced panels: {', '.join(unreferenced)}",
                "suggestion": "Add these panels to a layout or remove them",
            }
        )

    # Datasource analysis
    datasources = spec.get("datasources", {})
    datasource_count = len(datasources)

    # Query complexity (count queries across all panels)
    total_queries = 0
    for panel_id, panel in panels.items():
        panel_spec = panel.get("spec", {})
        queries = panel_spec.get("queries", [])
        total_queries += len(queries)

        # Check for missing display name
        display = panel_spec.get("display", {})
        if not display.get("name"):
            findings.append(
                {
                    "severity": "info",
                    "message": f"Panel '{panel_id}' has no display name",
                    "suggestion": "Add a descriptive name for clarity",
                }
            )

    # Check for missing description
    display = spec.get("display", {})
    if not display.get("description"):
        findings.append(
            {
                "severity": "info",
                "message": "Dashboard has no description",
                "suggestion": "Add a description for documentation",
            }
        )

    return {
        "dashboard": name,
        "project": project,
        "metrics": {
            "panels": panel_count,
            "variables": variable_count,
            "layouts": layout_count,
            "datasources": datasource_count,
            "total_queries": total_queries,
            "unreferenced_panels": len(unreferenced),
        },
        "variables": variable_names,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit Perses dashboard definitions")
    parser.add_argument("file", help="Dashboard definition file (JSON or YAML)")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    args = parser.parse_args()

    dashboard = load_dashboard(args.file)
    result = audit_dashboard(dashboard)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        m = result["metrics"]
        print(f"Dashboard: {result['dashboard']} (project: {result['project']})")
        print(f"  Panels: {m['panels']}, Variables: {m['variables']}, Layouts: {m['layouts']}")
        print(f"  Datasources: {m['datasources']}, Total queries: {m['total_queries']}")
        if m["unreferenced_panels"] > 0:
            print(f"  WARNING: {m['unreferenced_panels']} unreferenced panel(s)")
        if result["findings"]:
            print(f"\nFindings ({len(result['findings'])}):")
            for f in result["findings"]:
                print(f"  [{f['severity']}] {f['message']}")
                print(f"    \u2192 {f['suggestion']}")

    # Exit 1 if warnings found (useful for CI gating)
    has_warnings = any(f["severity"] == "warning" for f in result["findings"])
    sys.exit(1 if has_warnings else 0)


if __name__ == "__main__":
    main()
