#!/usr/bin/env python3
"""
Merge toolkit hooks into ~/.gemini/settings.json from a curated allowlist file.

The allowlist format is one entry per line: EVENT:filename [matcher]
Comments (lines starting with #) and blank lines are ignored.

Unlike the Codex hooks generator (which writes a standalone hooks.json),
this script merges into an existing settings.json, only modifying the
"hooks" key while preserving all other user configuration.

Gemini CLI hook events:
  SessionStart, SessionEnd, BeforeTool, AfterTool,
  BeforeAgent, AfterAgent, BeforeModel, AfterModel,
  Notification, PreCompress, BeforeToolSelection

Usage:
    python3 scripts/generate-gemini-settings-hooks.py --allowlist scripts/gemini-hooks-allowlist.txt
    python3 scripts/generate-gemini-settings-hooks.py --allowlist scripts/gemini-hooks-allowlist.txt --dry-run
    python3 scripts/generate-gemini-settings-hooks.py --allowlist scripts/gemini-hooks-allowlist.txt --output /tmp/settings.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Events that require a matcher (tool name to filter on).
EVENTS_REQUIRING_MATCHER = {"BeforeTool", "AfterTool"}

# Events where matcher field is omitted entirely.
EVENTS_WITHOUT_MATCHER = {"SessionStart", "SessionEnd", "Notification", "PreCompress", "BeforeToolSelection"}

# Events where matcher should default to a value when omitted.
EVENTS_WITH_DEFAULT_MATCHER: dict[str, str] = {}

# All known Gemini CLI events, in canonical output order.
EVENT_ORDER = [
    "SessionStart",
    "SessionEnd",
    "BeforeTool",
    "AfterTool",
    "BeforeAgent",
    "AfterAgent",
    "BeforeModel",
    "AfterModel",
    "Notification",
    "PreCompress",
    "BeforeToolSelection",
]

ALL_KNOWN_EVENTS = set(EVENT_ORDER)


def parse_allowlist(text: str) -> list[dict]:
    """Parse allowlist text into a list of entry dicts.

    Args:
        text: Contents of the allowlist file (not a path; the raw text).

    Returns:
        List of dicts with keys: event, filename, matcher (str or None).

    Raises:
        ValueError: On malformed lines (includes line number in message).
    """
    entries: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            raise ValueError(f"Line {lineno}: missing ':' separator in {raw!r}. Expected EVENT:filename [matcher].")

        event_part, rest = line.split(":", 1)
        event = event_part.strip()
        rest_parts = rest.strip().split()

        if not rest_parts:
            raise ValueError(f"Line {lineno}: missing filename after ':' in {raw!r}.")

        filename = rest_parts[0]
        matcher: str | None = rest_parts[1] if len(rest_parts) > 1 else None

        if event not in ALL_KNOWN_EVENTS:
            known = ", ".join(sorted(ALL_KNOWN_EVENTS))
            raise ValueError(f"Line {lineno}: unknown event {event!r}. Known events: {known}.")

        if event in EVENTS_REQUIRING_MATCHER and matcher is None:
            raise ValueError(
                f"Line {lineno}: {event} requires a matcher (e.g. 'run_shell_command') because Gemini "
                f"only fires {event} for named tools. Add a tool name after the filename: "
                f"'{event}:{filename} run_shell_command'."
            )

        entries.append({"event": event, "filename": filename, "matcher": matcher})

    return entries


def build_hooks_json(entries: list[dict], gemini_hooks_dir: str | None = None) -> dict:
    """Build the Gemini hooks structure from parsed allowlist entries.

    Args:
        entries: List of entry dicts from parse_allowlist().
        gemini_hooks_dir: Directory where hooks will reside. Defaults to $HOME/.gemini/hooks.

    Returns:
        Dict representing the hooks structure (the value for the "hooks" key).
    """
    if gemini_hooks_dir is None:
        gemini_hooks_dir = os.path.join(os.environ.get("HOME", "~"), ".gemini", "hooks")

    # Group by (event, effective_matcher) so shared matchers collapse into one block.
    groups: dict[tuple[str, str | None], list[str]] = {}

    for entry in entries:
        event = entry["event"]
        raw_matcher = entry["matcher"]
        filename = entry["filename"]

        # Determine the effective matcher for grouping and output.
        if event in EVENTS_WITH_DEFAULT_MATCHER and raw_matcher is None:
            effective_matcher: str | None = EVENTS_WITH_DEFAULT_MATCHER[event]
        elif event in EVENTS_WITHOUT_MATCHER:
            effective_matcher = None
        else:
            effective_matcher = raw_matcher

        key = (event, effective_matcher)
        groups.setdefault(key, [])
        groups[key].append(filename)

    if not groups:
        return {}

    # Build output dict with events in canonical order.
    hooks_by_event: dict[str, list[dict]] = {}

    for event in EVENT_ORDER:
        event_groups = {k: v for k, v in groups.items() if k[0] == event}
        if not event_groups:
            continue

        sorted_keys = sorted(event_groups.keys(), key=lambda k: (k[1] is None, k[1] or ""))
        event_blocks: list[dict] = []

        for key in sorted_keys:
            _, matcher = key
            filenames = event_groups[key]

            hook_entries = [
                {
                    "type": "command",
                    "command": f'python3 "{gemini_hooks_dir}/{fname}"',
                    "timeout": 600,
                }
                for fname in filenames
            ]

            block: dict = {}
            if matcher is not None:
                block["matcher"] = matcher
            block["hooks"] = hook_entries

            event_blocks.append(block)

        hooks_by_event[event] = event_blocks

    return hooks_by_event


def merge_settings(existing: dict, hooks_data: dict) -> dict:
    """Merge hooks into existing settings, preserving all other keys.

    Args:
        existing: Current settings.json content as a dict.
        hooks_data: Hooks structure to set (value for the "hooks" key).

    Returns:
        Updated settings dict with only the "hooks" key modified.
    """
    result = dict(existing)
    result["hooks"] = hooks_data
    return result


def main() -> None:
    """Parse CLI arguments, read the allowlist, and merge hooks into settings.json.

    Exits with code 0 on success, 1 on any error.
    """
    parser = argparse.ArgumentParser(
        description="Merge toolkit hooks into ~/.gemini/settings.json from a curated allowlist file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--allowlist", required=True, help="Path to the allowlist file.")
    parser.add_argument(
        "--output",
        default=os.path.join(os.environ.get("HOME", "~"), ".gemini", "settings.json"),
        help="Path to settings.json (default: ~/.gemini/settings.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print merged JSON to stdout instead of writing to disk.",
    )
    parser.add_argument(
        "--gemini-hooks-dir",
        default=None,
        help="Directory where hooks will live (default: $HOME/.gemini/hooks).",
    )

    args = parser.parse_args()

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.exists():
        print(f"Error: allowlist file not found: {allowlist_path}", file=sys.stderr)
        sys.exit(1)

    try:
        text = allowlist_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading allowlist: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        entries = parse_allowlist(text)
    except ValueError as exc:
        print(f"Error parsing allowlist: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        hooks_data = build_hooks_json(entries, gemini_hooks_dir=args.gemini_hooks_dir)
    except Exception as exc:
        print(f"Error building hooks: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)

    # Load existing settings.json if it exists.
    existing: dict = {}
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: could not read existing {output_path}: {exc}", file=sys.stderr)

    merged = merge_settings(existing, hooks_data)
    output_json = json.dumps(merged, indent=2)

    if args.dry_run:
        print(output_json)
        return

    # Back up existing file before overwriting.
    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = output_path.with_suffix(f".bak.{timestamp}")
        try:
            backup_path.write_bytes(output_path.read_bytes())
        except OSError as exc:
            print(f"Warning: could not create backup {backup_path}: {exc}", file=sys.stderr)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Error writing {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
