#!/usr/bin/env python3
"""Assemble a SKILL.md from the skill-template.md.tmpl and phase templates.

Reads templates from the co-located templates/ directory and substitutes
{{variables}} from command-line arguments or a JSON spec file.

Usage:
    python3 assemble-skill.py --name my-skill --domain prometheus --help
    python3 assemble-skill.py --spec pipeline-spec.json --subdomain metrics-authoring
    python3 assemble-skill.py --list
"""

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"
PHASES_DIR = TEMPLATES_DIR / "phases"

FAMILY_TEMPLATES = {
    "research-gathering": "research-gathering.md.tmpl",
    "structuring": "structuring.md.tmpl",
    "generation": "generation.md.tmpl",
    "validation": "validation.md.tmpl",
    "review": "review.md.tmpl",
    "safety-guarding": "safety-guarding.md.tmpl",
    "domain-extension": "domain-extension.md.tmpl",
    "synthesis-reporting": "synthesis-reporting.md.tmpl",
    "decision-planning": "decision-planning.md.tmpl",
    "observation": "observation.md.tmpl",
    "interaction": "interaction.md.tmpl",
    "git-release": "git-release.md.tmpl",
    "learning-retro": "learning-retro.md.tmpl",
}

COMPLEXITY_THRESHOLDS = {"Simple": 5, "Medium": 8}


def compute_complexity(chain_length: int) -> str:
    if chain_length <= COMPLEXITY_THRESHOLDS["Simple"]:
        return "Simple"
    if chain_length <= COMPLEXITY_THRESHOLDS["Medium"]:
        return "Medium"
    return "Complex"


def title_case(name: str) -> str:
    return name.replace("-", " ").title()


def substitute(template: str, variables: dict) -> str:
    """Simple {{variable}} substitution. Leaves unmatched placeholders intact."""
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        print(f"Error: template not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def load_phase_template(family: str) -> str:
    filename = FAMILY_TEMPLATES.get(family)
    if not filename:
        print(f"Warning: no phase template for family '{family}'", file=sys.stderr)
        return f"### Phase {{{{i}}}}: {{{{step.step}}}}\n\n(No template for family: {family})\n"
    path = PHASES_DIR / filename
    if not path.exists():
        print(f"Error: phase template not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def list_templates():
    print("Main template:")
    print(f"  {TEMPLATES_DIR / 'skill-template.md.tmpl'}")
    print()
    print("Phase family templates:")
    for family, filename in sorted(FAMILY_TEMPLATES.items()):
        path = PHASES_DIR / filename
        exists = "OK" if path.exists() else "MISSING"
        print(f"  {family:<25} {filename:<35} [{exists}]")


def assemble(args):
    """Assemble a SKILL.md from template + variables."""
    main_template = load_template("skill-template.md.tmpl")

    variables = {
        "skill_name": args.name,
        "domain": args.domain,
        "subdomain_name": args.subdomain,
        "task_type": args.task_type,
        "agent_name": args.agent,
        "operator_profile": args.profile,
        "description": args.description or f"{title_case(args.name)} pipeline",
        "skill_name_title": title_case(args.name),
        "subdomain_slug": args.subdomain.lower().replace(" ", "-"),
        "trigger_keywords": args.triggers or f'"{args.name}"',
        "max_refine_cycles": str(args.max_refine_cycles),
    }

    # Compute derived variables
    chain_length = args.phase_count or 6
    variables["phase_count"] = str(chain_length)
    variables["complexity"] = compute_complexity(chain_length)

    output = substitute(main_template, variables)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble a SKILL.md from templates and variables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --name prometheus-metrics --domain prometheus --subdomain metrics-authoring
  %(prog)s --name my-skill --domain my-domain --subdomain my-sub --task-type generation
        """,
    )
    parser.add_argument("--list", action="store_true", help="List available templates")
    parser.add_argument("--name", help="Skill name (kebab-case)")
    parser.add_argument("--domain", help="Domain name")
    parser.add_argument("--subdomain", help="Subdomain name")
    parser.add_argument("--task-type", dest="task_type", default="generation", help="Task type (default: generation)")
    parser.add_argument("--agent", default="general-engineer", help="Agent name to bind (default: general-engineer)")
    parser.add_argument(
        "--profile",
        default="personal",
        choices=["personal", "work", "ci", "production"],
        help="Operator profile (default: personal)",
    )
    parser.add_argument("--description", help="Skill description")
    parser.add_argument("--triggers", help="Comma-separated trigger keywords")
    parser.add_argument("--phase-count", dest="phase_count", type=int, help="Number of phases in the chain")
    parser.add_argument(
        "--max-refine-cycles", dest="max_refine_cycles", type=int, default=3, help="Max refine cycles (default: 3)"
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if args.list:
        list_templates()
        return

    if not args.name:
        parser.error("--name is required (use --list to see available templates)")

    if not args.domain:
        parser.error("--domain is required")

    if not args.subdomain:
        args.subdomain = args.name

    assemble(args)


if __name__ == "__main__":
    main()
