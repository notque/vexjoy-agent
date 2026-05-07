#!/usr/bin/env python3
"""
vexjoy-adr — Create and manage ADRs in the centralized ~/.vexjoy-agent/ directory.

Keeps governance artifacts out of individual repositories by writing ADRs to
~/.vexjoy-agent/{repo_name}/adrs/{component_name}.md

Usage:
    python3 scripts/vexjoy-adr.py create <component-name> [--repo <name>]
    python3 scripts/vexjoy-adr.py list [--repo <name>]
    python3 scripts/vexjoy-adr.py show <component-name> [--repo <name>]

If --repo is omitted, the repo name is derived from the git remote origin URL
of the current directory, or the directory basename as fallback.

Exit codes:
    0 = success
    1 = error (file exists, missing args, etc.)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

_VEXJOY_STATE_DIR = Path.home() / ".vexjoy-agent"

_ADR_TEMPLATE = """\
# ADR: {component_name}

## Status
Proposed

## Date
{date}

## Context
<!-- Why is this component needed? What problem does it solve? -->

## Decision
<!-- What is the approach? Key design choices. -->

## Consequences
<!-- What trade-offs does this introduce? What becomes easier/harder? -->

## Components
- Type: {component_type}
- Name: `{component_name}`

## References
<!-- Links to related ADRs, skills, or documentation -->
"""


def _derive_repo_name(cwd: Path) -> str:
    """Derive repo name from git remote or directory basename."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=3,
            cwd=str(cwd),
        )
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            name = url.rstrip("/").rsplit("/", 1)[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return name
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return cwd.name


def _guess_component_type(name: str) -> str:
    """Guess component type from naming conventions."""
    if name.endswith("-engineer") or name.endswith("-agent"):
        return "agent"
    if name.startswith("voice-"):
        return "skill (voice)"
    return "skill/agent"


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new ADR file at the centralized location."""
    repo_name = args.repo or _derive_repo_name(Path.cwd())
    component_name = args.component_name

    adr_dir = _VEXJOY_STATE_DIR / repo_name / "adrs"
    adr_path = adr_dir / f"{component_name}.md"

    if adr_path.exists():
        print(f"ADR already exists: {adr_path}", file=sys.stderr)
        return 1

    adr_dir.mkdir(parents=True, exist_ok=True)

    content = _ADR_TEMPLATE.format(
        component_name=component_name,
        date=date.today().isoformat(),
        component_type=_guess_component_type(component_name),
    )
    adr_path.write_text(content)
    print(f"Created: {adr_path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List ADRs for a repo."""
    repo_name = args.repo or _derive_repo_name(Path.cwd())
    adr_dir = _VEXJOY_STATE_DIR / repo_name / "adrs"

    if not adr_dir.is_dir():
        print(f"No ADRs found for repo '{repo_name}' (dir: {adr_dir})")
        return 0

    adrs = sorted(adr_dir.glob("*.md"))
    if not adrs:
        print(f"No ADRs found for repo '{repo_name}'")
        return 0

    print(f"ADRs for {repo_name} ({len(adrs)}):")
    for adr in adrs:
        print(f"  - {adr.stem}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show contents of a specific ADR."""
    repo_name = args.repo or _derive_repo_name(Path.cwd())
    adr_path = _VEXJOY_STATE_DIR / repo_name / "adrs" / f"{args.component_name}.md"

    if not adr_path.is_file():
        print(f"ADR not found: {adr_path}", file=sys.stderr)
        return 1

    print(adr_path.read_text())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage centralized ADRs in ~/.vexjoy-agent/",
        prog="vexjoy-adr",
    )
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Create a new ADR")
    p_create.add_argument("component_name", help="Component name (e.g., sapcc-dns)")
    p_create.add_argument("--repo", help="Override repo name (default: auto-detect)")

    # list
    p_list = sub.add_parser("list", help="List ADRs for a repo")
    p_list.add_argument("--repo", help="Override repo name (default: auto-detect)")

    # show
    p_show = sub.add_parser("show", help="Show an ADR's contents")
    p_show.add_argument("component_name", help="Component name to show")
    p_show.add_argument("--repo", help="Override repo name (default: auto-detect)")

    args = parser.parse_args()

    if args.command == "create":
        return cmd_create(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "show":
        return cmd_show(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
