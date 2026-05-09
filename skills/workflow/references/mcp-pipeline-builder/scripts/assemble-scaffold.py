#!/usr/bin/env python3
"""Assemble a TypeScript MCP server scaffold from templates.

Reads template files from the co-located templates/ directory and substitutes
{{variables}} from command-line arguments. Outputs individual files or a
complete project directory.

Usage:
    python3 assemble-scaffold.py --list
    python3 assemble-scaffold.py --service github --entity issue --output-dir ./github-mcp-server
    python3 assemble-scaffold.py --service github --entity issue --file package.json
"""

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"

TEMPLATE_FILES = {
    "package.json": "package.json.tmpl",
    "tsconfig.json": "tsconfig.json.tmpl",
    "src/index.ts": "index.ts.tmpl",
    "src/tools/{tool_group}.ts": "tools.ts.tmpl",
    "src/services/client.ts": "client-http.ts.tmpl",
    "src/services/client-cli.ts": "client-cli.ts.tmpl",
    "README.md": "readme.md.tmpl",
}


def pascal_case(name: str) -> str:
    return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))


def substitute(template: str, variables: dict) -> str:
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


def list_templates():
    print("Available MCP scaffold templates:")
    print()
    print(f"  Templates directory: {TEMPLATES_DIR}")
    print()
    for output_path, tmpl_file in sorted(TEMPLATE_FILES.items()):
        path = TEMPLATES_DIR / tmpl_file
        exists = "OK" if path.exists() else "MISSING"
        print(f"  {output_path:<40} <- {tmpl_file:<25} [{exists}]")
    print()
    print("Key patterns:")
    print("  - Tool annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint")
    print("  - Error handling: always return text content, never throw from tool handler")
    print("  - Auth: read from env vars, throw at startup if missing")
    print("  - Logging: use console.error() (not console.log) with stdio transport")


def assemble_file(template_name: str, variables: dict) -> str:
    template = load_template(template_name)
    return substitute(template, variables)


def build_variables(args) -> dict:
    service = args.service
    entity = args.entity or "item"
    tool_group = args.tool_group or f"{entity}s"
    env_prefix = args.env_prefix or service.upper().replace("-", "_")

    return {
        "service": service,
        "service_name": args.service_name or pascal_case(service),
        "entity": entity,
        "entity_pascal": pascal_case(entity),
        "tool_group": tool_group,
        "tool_group_pascal": pascal_case(tool_group),
        "env_var_prefix": env_prefix,
        "purpose": args.purpose or f"interact with {pascal_case(service)}",
    }


def assemble_single(args, variables: dict):
    """Output a single template file."""
    # Find the template for the requested file
    for output_path, tmpl_file in TEMPLATE_FILES.items():
        resolved = output_path.replace("{tool_group}", variables["tool_group"])
        if args.file in (output_path, resolved, tmpl_file, Path(tmpl_file).stem):
            content = assemble_file(tmpl_file, variables)
            print(content)
            return

    print(f"Error: unknown file '{args.file}'. Use --list to see options.", file=sys.stderr)
    sys.exit(1)


def assemble_project(args, variables: dict):
    """Create a complete project directory."""
    output_dir = Path(args.output_dir)

    for output_path, tmpl_file in TEMPLATE_FILES.items():
        resolved_path = output_path.replace("{tool_group}", variables["tool_group"])
        full_path = output_dir / resolved_path

        full_path.parent.mkdir(parents=True, exist_ok=True)
        content = assemble_file(tmpl_file, variables)
        full_path.write_text(content)
        print(f"  Created: {full_path}", file=sys.stderr)

    print(f"\nProject scaffolded at: {output_dir}", file=sys.stderr)
    print(f"Next steps:", file=sys.stderr)
    print(f"  cd {output_dir}", file=sys.stderr)
    print(f"  npm install", file=sys.stderr)
    print(f"  npm run build", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble a TypeScript MCP server scaffold from templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --service github --entity issue --file package.json
  %(prog)s --service github --entity issue --output-dir ./github-mcp-server
        """,
    )
    parser.add_argument("--list", action="store_true", help="List available templates")
    parser.add_argument("--service", help="Service name (kebab-case, e.g., 'github')")
    parser.add_argument(
        "--service-name", dest="service_name", help="Display name (e.g., 'GitHub'). Default: PascalCase of --service"
    )
    parser.add_argument("--entity", help="Primary entity name (e.g., 'issue')")
    parser.add_argument("--tool-group", dest="tool_group", help="Tool group name (default: {entity}s)")
    parser.add_argument("--env-prefix", dest="env_prefix", help="Environment variable prefix (default: SERVICE upper)")
    parser.add_argument("--purpose", help="One-line purpose for README")
    parser.add_argument("--file", help="Output a single template file")
    parser.add_argument("--output-dir", dest="output_dir", help="Create complete project in this directory")

    args = parser.parse_args()

    if args.list:
        list_templates()
        return

    if not args.service:
        parser.error("--service is required (use --list to see templates)")

    variables = build_variables(args)

    if args.file:
        assemble_single(args, variables)
    elif args.output_dir:
        assemble_project(args, variables)
    else:
        # Default: list what would be generated
        print("Files that would be generated:")
        for output_path in TEMPLATE_FILES:
            resolved = output_path.replace("{tool_group}", variables["tool_group"])
            print(f"  {resolved}")
        print()
        print("Use --file <name> for a single file, or --output-dir <path> for complete project.")


if __name__ == "__main__":
    main()
