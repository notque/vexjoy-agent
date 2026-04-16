#!/usr/bin/env python3
"""
Migration script: Remove dead stub hooks and register useful unregistered hooks.

Reads ~/.claude/settings.json, removes 3 dead stub registrations, adds 3
useful hook registrations, and writes the updated file.

Dead stubs removed:
  - instruction-reminder.py (UserPromptSubmit) -- fires every prompt, does nothing
  - auto-plan-detector.py (UserPromptSubmit) -- fires every prompt, does nothing
  - retro-knowledge-injector.py (SessionStart) -- replaced by session-context.py

Hooks registered:
  - pretool-config-protection.py (PreToolUse, Write|Edit) -- blocks linter config weakening
  - posttool-docs-drift-alert.py (PostToolUse, Write|Edit) -- detects INDEX/routing drift
  - suggest-compact.py (PreToolUse, Write|Edit) -- advises /compact after N tool calls

Usage:
  python3 scripts/migrate-hooks-cleanup.py           # apply changes
  python3 scripts/migrate-hooks-cleanup.py --dry-run  # preview changes without writing

ADR: adr/dead-hook-cleanup.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# Hook commands to remove (matched by substring in the command field).
_DEAD_HOOKS = [
    "instruction-reminder.py",
    "auto-plan-detector.py",
    "retro-knowledge-injector.py",
]

# Hook registrations to add.
_NEW_HOOKS: list[dict] = [
    {
        "event": "PreToolUse",
        "matcher": "Write|Edit",
        "hook": {
            "type": "command",
            "command": 'python3 "$HOME/.claude/hooks/pretool-config-protection.py"',
            "description": "Config protection: blocks linter/formatter config weakening (ADR-115)",
            "timeout": 3000,
        },
    },
    {
        "event": "PostToolUse",
        "matcher": "Write|Edit",
        "hook": {
            "type": "command",
            "command": 'python3 "$HOME/.claude/hooks/posttool-docs-drift-alert.py"',
            "description": "Docs drift alert: warns when INDEX.json or routing tables diverge from disk",
            "timeout": 3000,
        },
    },
    {
        "event": "PreToolUse",
        "matcher": "Write|Edit",
        "hook": {
            "type": "command",
            "command": 'python3 "$HOME/.claude/hooks/suggest-compact.py"',
            "description": "Strategic compact advisor: suggests /compact after N tool calls (ADR-103)",
            "timeout": 3000,
        },
    },
]


def _remove_dead_hooks(settings: dict) -> list[str]:
    """Remove dead stub hook entries from settings. Returns list of removed hook names."""
    removed: list[str] = []
    hooks_section = settings.get("hooks", {})

    for event_name, event_groups in list(hooks_section.items()):
        if not isinstance(event_groups, list):
            continue

        for group in event_groups:
            if not isinstance(group, dict):
                continue
            hook_list = group.get("hooks", [])
            original_len = len(hook_list)

            # Filter out dead hooks
            surviving = []
            for hook in hook_list:
                cmd = hook.get("command", "")
                is_dead = any(dead_name in cmd for dead_name in _DEAD_HOOKS)
                if is_dead:
                    hook_name = cmd.split("/")[-1].rstrip('"')
                    removed.append(f"{event_name}: {hook_name}")
                else:
                    surviving.append(hook)

            if len(surviving) < original_len:
                group["hooks"] = surviving

        # Clean up empty groups (groups with no hooks left)
        hooks_section[event_name] = [g for g in event_groups if isinstance(g, dict) and g.get("hooks")]

        # Clean up empty event entries
        if not hooks_section[event_name]:
            del hooks_section[event_name]

    return removed


def _is_already_registered(settings: dict, command_substring: str) -> bool:
    """Check if a hook with the given command substring is already registered."""
    hooks_section = settings.get("hooks", {})
    for event_groups in hooks_section.values():
        if not isinstance(event_groups, list):
            continue
        for group in event_groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if command_substring in hook.get("command", ""):
                    return True
    return False


def _add_new_hooks(settings: dict) -> list[str]:
    """Add new hook registrations. Returns list of added hook descriptions."""
    added: list[str] = []
    hooks_section = settings.setdefault("hooks", {})

    for new_hook in _NEW_HOOKS:
        event = new_hook["event"]
        matcher = new_hook["matcher"]
        hook_entry = new_hook["hook"]
        cmd = hook_entry["command"]

        # Extract filename for duplicate check
        filename = cmd.split("/")[-1].rstrip('"')

        if _is_already_registered(settings, filename):
            continue

        # Find existing group with matching event + matcher, or create one
        event_groups = hooks_section.setdefault(event, [])
        target_group = None
        for group in event_groups:
            if isinstance(group, dict) and group.get("matcher") == matcher:
                target_group = group
                break

        if target_group is None:
            target_group = {"matcher": matcher, "hooks": []}
            event_groups.append(target_group)

        target_group["hooks"].append(hook_entry)
        added.append(f"{event} ({matcher}): {filename}")

    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove dead stub hooks and register useful unregistered hooks.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying settings.json",
    )
    args = parser.parse_args()

    if not _SETTINGS_PATH.exists():
        print(f"ERROR: {_SETTINGS_PATH} not found", file=sys.stderr)
        sys.exit(1)

    settings = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))

    # Step 1: Remove dead stubs
    removed = _remove_dead_hooks(settings)

    # Step 2: Add useful hooks
    added = _add_new_hooks(settings)

    # Report
    if not removed and not added:
        print("No changes needed -- hooks already clean.")
        return

    if removed:
        print(f"Removed {len(removed)} dead stub hook(s):")
        for r in removed:
            print(f"  - {r}")

    if added:
        print(f"Added {len(added)} hook registration(s):")
        for a in added:
            print(f"  + {a}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written to disk.")
        return

    # Write updated settings
    _SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nUpdated {_SETTINGS_PATH}")


if __name__ == "__main__":
    main()
