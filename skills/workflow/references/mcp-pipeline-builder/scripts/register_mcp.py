#!/usr/bin/env python3
"""
register_mcp.py — Append-only MCP server registration for Claude Code.

Reads the existing Claude Code MCP config, appends a new server entry, and
writes atomically. Never overwrites existing entries. Supports dry-run mode.

Usage:
    python3 register_mcp.py \\
        --name server-name \\
        --command node \\
        --args /path/to/dist/index.js \\
        [--args --additional-arg] \\
        [--env KEY=VALUE] \\
        [--dry-run] \\
        [--project]

Examples:
    # Register a TypeScript MCP server globally
    python3 register_mcp.py \\
        --name github-mcp-server \\
        --command node \\
        --args /home/user/github-mcp-server/dist/index.js \\
        --env GITHUB_TOKEN=ghp_xxx

    # Register a Python MCP server at project scope (dry-run first)
    python3 register_mcp.py \\
        --name myservice-mcp-server \\
        --command python3 \\
        --args /home/user/myservice-mcp-server/src/main.py \\
        --env SERVICE_API_KEY=sk-xxx \\
        --dry-run \\
        --project
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append-only MCP server registration for Claude Code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--name",
        required=True,
        help="MCP server name (used as the key in mcpServers config).",
    )
    parser.add_argument(
        "--command",
        required=True,
        help="Command to run the server (e.g., 'node', 'python3').",
    )
    parser.add_argument(
        "--args",
        action="append",
        metavar="ARG",
        default=[],
        help="Argument to pass to the command. Repeat for multiple args.",
    )
    parser.add_argument(
        "--env",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        help="Environment variable as KEY=VALUE. Repeat for multiple vars.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the config snippet without writing to disk.",
    )
    parser.add_argument(
        "--project",
        action="store_true",
        help="Write to .claude/settings.json in CWD instead of ~/.claude.json.",
    )
    return parser.parse_args()


def resolve_config_path(use_project: bool) -> Path:
    """Determine the target config file path."""
    if use_project:
        project_config = Path.cwd() / ".claude" / "settings.json"
        return project_config
    return Path.home() / ".claude.json"


def read_config(config_path: Path) -> dict:
    """Read and parse the config file. Returns empty dict if file doesn't exist."""
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError as e:
        print(
            f"ERROR: Config file {config_path} contains invalid JSON: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_env_vars(env_list: list[str]) -> dict[str, str]:
    """Parse KEY=VALUE strings into a dict. Exits on malformed input."""
    result = {}
    for item in env_list:
        if "=" not in item:
            print(
                f"ERROR: --env value must be KEY=VALUE format, got: {item!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        key, _, value = item.partition("=")
        if not key:
            print(
                f"ERROR: --env key cannot be empty, got: {item!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        result[key] = value
    return result


def build_server_entry(
    command: str,
    args: list[str],
    env: dict[str, str],
) -> dict:
    """Build the mcpServers entry dict."""
    entry: dict = {
        "command": command,
        "args": args,
    }
    if env:
        entry["env"] = env
    return entry


def write_config_atomic(config_path: Path, config: dict) -> None:
    """Write config to a temp file, then rename atomically."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory for atomic rename
    fd, tmp_path = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=".register_mcp_tmp_",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")  # Trailing newline
        os.rename(tmp_path, config_path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def format_snippet(name: str, entry: dict) -> str:
    """Format a printable snippet showing the new entry in context."""
    snippet = {"mcpServers": {name: entry}}
    return json.dumps(snippet, indent=2)


def main() -> None:
    args = parse_args()

    # Parse and validate env vars
    env_vars = parse_env_vars(args.env)

    # Build the entry
    server_entry = build_server_entry(args.command, args.args, env_vars)
    snippet = format_snippet(args.name, server_entry)

    if args.dry_run:
        print("DRY RUN — config snippet (not written):")
        print()
        print(snippet)
        print()
        config_path = resolve_config_path(args.project)
        print(f"Would write to: {config_path}")
        return

    # Resolve config location
    config_path = resolve_config_path(args.project)

    # Read existing config (read-before-write)
    config = read_config(config_path)

    # Ensure mcpServers key exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Check for existing entry — never overwrite
    if args.name in config["mcpServers"]:
        print(
            f"WARNING: Server '{args.name}' already exists in {config_path}.",
            file=sys.stderr,
        )
        print(
            "Existing entry was NOT modified. To update it, edit the config manually.",
            file=sys.stderr,
        )
        print("\nExisting entry:", file=sys.stderr)
        print(
            json.dumps({args.name: config["mcpServers"][args.name]}, indent=2),
            file=sys.stderr,
        )
        print(
            f"\nTo use a different name, re-run with: --name {args.name}-v2",
            file=sys.stderr,
        )
        sys.exit(1)

    # Append the new entry
    config["mcpServers"][args.name] = server_entry

    # Write atomically
    write_config_atomic(config_path, config)

    # Confirm
    print(f"MCP server registered: {args.name}")
    print(f"Config location: {config_path}")
    print()
    print("Config snippet written:")
    print(snippet)
    print()
    print("Restart Claude Code to activate the new MCP server.")


if __name__ == "__main__":
    main()
