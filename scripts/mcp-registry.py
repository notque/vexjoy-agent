#!/usr/bin/env python3
"""
mcp-registry.py -- Single source of truth for MCP server metadata.

Used by /install, /do router, and install-doctor.py to discover,
configure, and validate MCP servers in the Claude Code Toolkit.

Usage:
    python3 scripts/mcp-registry.py list              # Table of all MCPs
    python3 scripts/mcp-registry.py list --json        # JSON array
    python3 scripts/mcp-registry.py get chrome-devtools        # Details for one MCP
    python3 scripts/mcp-registry.py get chrome-devtools --json # JSON for one MCP
    python3 scripts/mcp-registry.py check              # Check which MCPs are configured

Exit codes:
    0 -- Success
    1 -- MCP not found (get) or no MCPs configured (check)
    2 -- Usage error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REGISTRY: dict[str, dict[str, Any]] = {
    "chrome-devtools": {
        "name": "Chrome DevTools MCP",
        "description": "Live browser debugging, performance profiling, network inspection",
        "install_command": "claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest",
        "docs_url": "https://developer.chrome.com/blog/chrome-devtools-mcp",
        "tool_prefix": "mcp__chrome-devtools__",
        "paired_skills": ["wordpress-live-validation"],
        "use_cases": [
            "inspect page",
            "lighthouse",
            "console errors",
            "network requests",
            "performance profile",
            "debug in browser",
            "check my site",
        ],
        "category": "browser",
        "requires": "Chrome browser with DevTools MCP enabled",
    },
    "playwright": {
        "name": "Playwright MCP",
        "description": "Automated browser testing, validation workflows, screenshot comparison",
        "install_command": "claude mcp add playwright -- npx @anthropic-ai/mcp-playwright@latest",
        "docs_url": "https://github.com/anthropics/mcp-playwright",
        "tool_prefix": "mcp__plugin_playwright_playwright__",
        "paired_skills": ["wordpress-live-validation"],
        "use_cases": [
            "validate page",
            "test layout",
            "automated check",
            "screenshot test",
            "responsive check",
            "browser test",
        ],
        "category": "browser",
        "requires": "Node.js 20+",
    },
    "gopls": {
        "name": "gopls MCP",
        "description": "Go workspace intelligence: symbols, diagnostics, references, vulncheck",
        "install_command": "claude mcp add gopls -- gopls mcp",
        "docs_url": "https://pkg.go.dev/golang.org/x/tools/gopls",
        "tool_prefix": "mcp__gopls__",
        "paired_skills": ["go-code-review", "go-testing", "go-concurrency"],
        "use_cases": ["Go workspace", ".go files", "go.mod", "Go symbols", "Go diagnostics"],
        "category": "language",
        "requires": "gopls installed (go install golang.org/x/tools/gopls@latest)",
    },
    "context7": {
        "name": "Context7 MCP",
        "description": "Library documentation lookups and API reference",
        "install_command": "claude mcp add context7 -- npx @anthropic-ai/mcp-context7@latest",
        "docs_url": "https://context7.com",
        "tool_prefix": "mcp__plugin_context7_context7__",
        "paired_skills": [],
        "use_cases": ["library docs", "API reference", "how do I use X", "unfamiliar library"],
        "category": "documentation",
        "requires": "Node.js 20+",
    },
}

# Settings files where MCP servers may be configured
SETTINGS_PATHS = [
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.local.json",
    Path.home() / ".claude.json",
]


def _load_configured_servers() -> set[str]:
    """Parse all known settings files and return configured mcpServers keys."""
    configured: set[str] = set()
    for path in SETTINGS_PATHS:
        try:
            data = json.loads(path.read_text())
            for key in data.get("mcpServers", {}):
                configured.add(key)
        except (json.JSONDecodeError, OSError):
            continue
    return configured


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_list(*, use_json: bool) -> int:
    """List all registered MCP servers."""
    if use_json:
        print(json.dumps([{**v, "key": k} for k, v in REGISTRY.items()], indent=2))
        return 0

    # Table header
    print()
    print(f"  {'Name':<24} {'Category':<16} {'Description'}")
    print(f"  {'----':<24} {'--------':<16} {'-----------'}")
    for key, entry in REGISTRY.items():
        print(f"  {key:<24} {entry['category']:<16} {entry['description']}")
    print()
    return 0


def cmd_get(name: str, *, use_json: bool) -> int:
    """Get details for a single MCP server."""
    entry = REGISTRY.get(name)
    if entry is None:
        print(f"Unknown MCP server: {name}", file=sys.stderr)
        print(f"Available: {', '.join(REGISTRY)}", file=sys.stderr)
        return 1

    if use_json:
        print(json.dumps(entry, indent=2))
        return 0

    print()
    print(f"  {entry['name']}")
    print(f"  {'-' * len(entry['name'])}")
    print(f"  Description:  {entry['description']}")
    print(f"  Category:     {entry['category']}")
    print(f"  Requires:     {entry['requires']}")
    print(f"  Docs:         {entry['docs_url']}")
    print(f"  Tool prefix:  {entry['tool_prefix']}")
    print(f"  Install:      {entry['install_command']}")
    if entry["paired_skills"]:
        print(f"  Skills:       {', '.join(entry['paired_skills'])}")
    print(f"  Use cases:    {', '.join(entry['use_cases'])}")
    print()
    return 0


def cmd_check(*, use_json: bool) -> int:
    """Check which MCP servers appear configured in settings files."""
    configured_servers = _load_configured_servers()
    results: list[dict[str, Any]] = []

    for key, entry in REGISTRY.items():
        configured = key in configured_servers
        results.append({**entry, "key": key, "configured": configured})

    if use_json:
        print(json.dumps(results, indent=2))
    else:
        print()
        print(f"  {'Name':<24} {'Category':<16} {'Configured'}")
        print(f"  {'----':<24} {'--------':<16} {'----------'}")
        for r in results:
            status = "yes" if r["configured"] else "no"
            print(f"  {r['key']:<24} {r['category']:<16} {status}")
        print()

        configured_count = sum(1 for r in results if r["configured"])
        print(f"  {configured_count}/{len(results)} MCP servers configured")
        print()

    any_configured = any(r["configured"] for r in results)
    return 0 if any_configured else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="mcp-registry.py",
        description="MCP server registry for the Claude Code Toolkit.",
    )
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List all registered MCP servers")
    list_p.add_argument("--json", action="store_true", help="Output as JSON")

    get_p = sub.add_parser("get", help="Get details for one MCP server")
    get_p.add_argument("name", help="MCP server key (e.g. chrome-devtools)")
    get_p.add_argument("--json", action="store_true", help="Output as JSON")

    check_p = sub.add_parser("check", help="Check which MCPs are configured")
    check_p.add_argument("--json", action="store_true", help="Output as JSON")

    return parser


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "list":
        return cmd_list(use_json=args.json)
    elif args.command == "get":
        return cmd_get(args.name, use_json=args.json)
    elif args.command == "check":
        return cmd_check(use_json=args.json)

    parser.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
