#!/usr/bin/env python3
"""
Classify Hooks — ADR-175 experiment infrastructure.

Reads ~/.claude/settings.json hook registrations and classifies each hook
into one of three tiers based on its filename:

  Tier 1 (safety):       branch-safety, injection-scanner, config-protection,
                         security-scan, bash-injection
  Tier 2 (productivity): error-learner, learning-injector, auto-plan, plan-gate,
                         lint-hint, adr-enforcement, synthesis-gate
  Tier 3 (informational): everything else

Usage:
    python3 scripts/classify-hooks.py
    python3 scripts/classify-hooks.py --json
    python3 scripts/classify-hooks.py --tier 1
    python3 scripts/classify-hooks.py --settings /path/to/settings.json

Exit codes:
    0 = success
    1 = settings.json not found or unreadable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"

TIER1_KEYWORDS = {"branch-safety", "injection-scanner", "config-protection", "security-scan", "bash-injection"}
TIER2_KEYWORDS = {
    "error-learner",
    "learning-injector",
    "auto-plan",
    "plan-gate",
    "lint-hint",
    "adr-enforcement",
    "synthesis-gate",
}

# All supported hook event types in settings.json
HOOK_EVENT_TYPES = ["PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit", "Stop"]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_hook(hook_name: str) -> tuple[int, str]:
    """Classify a hook name into tier 1, 2, or 3.

    Args:
        hook_name: The hook basename (without extension).

    Returns:
        Tuple of (tier_number, classification_reason).
    """
    for keyword in TIER1_KEYWORDS:
        if keyword in hook_name:
            return 1, f"safety keyword '{keyword}' found in name"

    for keyword in TIER2_KEYWORDS:
        if keyword in hook_name:
            return 2, f"productivity keyword '{keyword}' found in name"

    return 3, "no safety or productivity keywords matched"


def extract_hook_name(command: str) -> str:
    """Extract the hook basename (without extension) from a command string.

    Args:
        command: The full hook command, e.g. 'python3 /path/to/hook-name.py'.

    Returns:
        Basename without extension, e.g. 'hook-name'.
    """
    # Split on whitespace and take the last token that looks like a path
    parts = command.strip().split()
    for part in reversed(parts):
        if "/" in part or part.endswith(".py") or part.endswith(".sh"):
            return Path(part).stem
    # Fallback: last token
    return Path(parts[-1]).stem if parts else command


# ---------------------------------------------------------------------------
# Settings loading
# ---------------------------------------------------------------------------


def load_hook_records(settings_path: Path) -> list[dict]:
    """Parse settings.json and return a flat list of hook records.

    Each record has:
        hook_name, event_type, command, tier, classification_reason

    Args:
        settings_path: Path to settings.json.

    Returns:
        List of hook record dicts.
    """
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks_section = data.get("hooks", {})

    records: list[dict] = []

    for event_type, registrations in hooks_section.items():
        if not isinstance(registrations, list):
            continue
        for registration in registrations:
            if not isinstance(registration, dict):
                continue
            inner_hooks = registration.get("hooks", [])
            if not isinstance(inner_hooks, list):
                continue
            for hook_entry in inner_hooks:
                if not isinstance(hook_entry, dict):
                    continue
                command = hook_entry.get("command", "")
                hook_name = extract_hook_name(command)
                tier, reason = classify_hook(hook_name)
                records.append(
                    {
                        "hook_name": hook_name,
                        "event_type": event_type,
                        "command": command,
                        "tier": tier,
                        "classification_reason": reason,
                    }
                )

    return records


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_markdown(records: list[dict]) -> str:
    """Format hook records as a markdown table.

    Args:
        records: List of hook record dicts.

    Returns:
        Markdown table string.
    """
    if not records:
        return "_No hooks registered._\n"

    lines = [
        "| Hook Name | Event Type | Tier | Classification Reason |",
        "|-----------|------------|------|-----------------------|",
    ]
    for r in records:
        lines.append(f"| {r['hook_name']} | {r['event_type']} | Tier {r['tier']} | {r['classification_reason']} |")
    return "\n".join(lines) + "\n"


def format_json(records: list[dict]) -> str:
    """Format hook records as a JSON array.

    Args:
        records: List of hook record dicts.

    Returns:
        JSON string.
    """
    return json.dumps(records, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="classify-hooks.py",
        description="Classify registered hooks from settings.json into safety/productivity/informational tiers.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        default=False,
        help="Output as JSON instead of markdown table.",
    )
    parser.add_argument(
        "--tier",
        metavar="N",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help="Filter output to specific tier (1, 2, or 3).",
    )
    parser.add_argument(
        "--settings",
        metavar="PATH",
        default=None,
        help=f"Override default settings.json path (default: {DEFAULT_SETTINGS}).",
    )
    return parser


def main() -> int:
    """Entry point — parse args, classify hooks, and print report."""
    parser = _build_parser()
    args = parser.parse_args()

    settings_path = Path(args.settings) if args.settings else DEFAULT_SETTINGS

    if not settings_path.exists():
        print(f"error: settings.json not found at {settings_path}", file=sys.stderr)
        print("hint: specify an alternate path with --settings PATH", file=sys.stderr)
        return 1

    try:
        records = load_hook_records(settings_path)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {settings_path}: {exc}", file=sys.stderr)
        return 1

    if args.tier is not None:
        records = [r for r in records if r["tier"] == args.tier]

    if args.output_json:
        print(format_json(records))
    else:
        print(format_markdown(records))

    return 0


if __name__ == "__main__":
    sys.exit(main())
