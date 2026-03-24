#!/usr/bin/env python3
"""Safe hook registration: deploy file THEN register in settings.json.

Enforces the correct order: file must exist at ~/.claude/hooks/ BEFORE
it gets registered in settings.json. Prevents the deadlock scenario
where a missing hook file causes Python exit code 2, which Claude Code
interprets as an intentional BLOCK on every tool call.

Usage:
    # Register a hook (copies to ~/.claude/hooks/ first, then registers)
    python3 scripts/register-hook.py add \
        --file hooks/pretool-synthesis-gate.py \
        --event PreToolUse \
        --description "Consultation synthesis gate" \
        --timeout 3000

    # Unregister a hook (removes from settings.json first, then optionally deletes file)
    python3 scripts/register-hook.py remove \
        --name pretool-synthesis-gate.py \
        --event PreToolUse

    # List all registered hooks
    python3 scripts/register-hook.py list

    # Validate all registered hooks have backing files
    python3 scripts/register-hook.py validate

Exit codes:
    0 - Success
    1 - Error (file not found, invalid JSON, etc.)
    2 - Validation failure (registered hook has no backing file)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HOOKS_DIR = Path.home() / ".claude" / "hooks"


def load_settings() -> dict:
    """Load settings.json."""
    if not SETTINGS_PATH.exists():
        print(f"ERROR: {SETTINGS_PATH} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def save_settings(data: dict) -> None:
    """Save settings.json with trailing newline."""
    SETTINGS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_hooks_list(settings: dict, event: str) -> list[dict]:
    """Get the hooks list for a given event type."""
    hooks = settings.get("hooks", {})
    event_groups = hooks.get(event, [])
    if not event_groups:
        return []
    # Settings uses array of groups, each with a "hooks" array
    if isinstance(event_groups, list) and event_groups:
        first = event_groups[0]
        if isinstance(first, dict) and "hooks" in first:
            return first["hooks"]
    return []


def cmd_add(args: argparse.Namespace) -> None:
    """Add a hook: deploy file first, then register."""
    source = Path(args.file)
    if not source.exists():
        print(f"ERROR: Source file not found: {source}", file=sys.stderr)
        sys.exit(1)

    target = HOOKS_DIR / source.name
    hook_command = f'python3 "$HOME/.claude/hooks/{source.name}"'

    # Step 1: DEPLOY file to ~/.claude/hooks/ FIRST
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[1/3] Deployed: {source} -> {target}")

    # Step 2: VERIFY the deployed file is importable
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", f"import py_compile; py_compile.compile('{target}', doraise=True)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Roll back deployment
        target.unlink(missing_ok=True)
        print(f"ERROR: File has syntax errors, rolled back deployment:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"[2/3] Verified: {target} compiles cleanly")

    # Step 3: REGISTER in settings.json (only after file is deployed and verified)
    settings = load_settings()
    hooks_list = get_hooks_list(settings, args.event)

    # Check for duplicates
    for h in hooks_list:
        if source.name in h.get("command", ""):
            print(f"Already registered: {source.name} in {args.event}")
            return

    new_hook = {
        "type": "command",
        "command": hook_command,
        "description": args.description,
        "timeout": args.timeout,
    }

    # Insert after first hook (unified gate stays first)
    insert_pos = min(1, len(hooks_list))
    hooks_list.insert(insert_pos, new_hook)
    save_settings(settings)
    print(f"[3/3] Registered: {source.name} in {args.event} at position {insert_pos}")
    print(f"\nDone. Hook is live.")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a hook: unregister first, then optionally delete file."""
    settings = load_settings()
    hooks_list = get_hooks_list(settings, args.event)

    # Step 1: UNREGISTER from settings.json FIRST
    original_len = len(hooks_list)
    hooks_list[:] = [h for h in hooks_list if args.name not in h.get("command", "")]

    if len(hooks_list) == original_len:
        print(f"Not found: {args.name} in {args.event}")
    else:
        save_settings(settings)
        print(f"[1/2] Unregistered: {args.name} from {args.event}")

    # Step 2: Optionally delete the file
    target = HOOKS_DIR / args.name
    if target.exists() and args.delete_file:
        target.unlink()
        print(f"[2/2] Deleted: {target}")
    elif target.exists():
        print(f"[2/2] Kept file: {target} (use --delete-file to remove)")


def cmd_list(args: argparse.Namespace) -> None:
    """List all registered hooks."""
    settings = load_settings()
    hooks = settings.get("hooks", {})
    for event, groups in hooks.items():
        if not groups:
            continue
        print(f"\n{event}:")
        for group in groups:
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                desc = h.get("description", "")
                timeout = h.get("timeout", "?")
                # Extract filename from command
                name = cmd.split("/")[-1].rstrip('"') if "/" in cmd else cmd
                print(f"  {name:45s} timeout={timeout}ms")
                if desc:
                    print(f"    {desc}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate all registered hooks have backing files."""
    settings = load_settings()
    hooks = settings.get("hooks", {})
    issues = []

    for event, groups in hooks.items():
        if not groups:
            continue
        for group in groups:
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                if "$HOME/.claude/hooks/" not in cmd:
                    continue
                # Extract filename
                name = cmd.split("$HOME/.claude/hooks/")[-1].rstrip('"')
                target = HOOKS_DIR / name
                if not target.exists():
                    issues.append((event, name, "FILE MISSING"))
                    print(f"  FAIL: {event} -> {name} — file does not exist at {target}")
                else:
                    print(f"  OK:   {event} -> {name}")

    if issues:
        print(f"\n{len(issues)} hook(s) registered without backing files!")
        print("This WILL deadlock Claude Code (Python exit 2 = BLOCK).")
        print("Fix: create the missing files or unregister the hooks.")
        sys.exit(2)
    else:
        print("\nAll registered hooks have backing files.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe hook registration (deploy-before-register)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Deploy and register a hook")
    p_add.add_argument("--file", required=True, help="Path to hook .py file in repo")
    p_add.add_argument("--event", required=True, help="Hook event type (PreToolUse, PostToolUse, etc.)")
    p_add.add_argument("--description", required=True, help="Hook description for settings.json")
    p_add.add_argument("--timeout", type=int, default=3000, help="Timeout in ms (default: 3000)")

    # remove
    p_rm = sub.add_parser("remove", help="Unregister (and optionally delete) a hook")
    p_rm.add_argument("--name", required=True, help="Hook filename (e.g., pretool-synthesis-gate.py)")
    p_rm.add_argument("--event", required=True, help="Hook event type")
    p_rm.add_argument("--delete-file", action="store_true", help="Also delete the file from ~/.claude/hooks/")

    # list
    sub.add_parser("list", help="List all registered hooks")

    # validate
    sub.add_parser("validate", help="Validate all hooks have backing files")

    args = parser.parse_args()
    {"add": cmd_add, "remove": cmd_remove, "list": cmd_list, "validate": cmd_validate}[args.command](args)


if __name__ == "__main__":
    main()
