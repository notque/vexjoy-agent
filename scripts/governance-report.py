#!/usr/bin/env python3
"""
Governance Event Report CLI — query and resolve governance events.

Usage:
    # Show last 7 days of events
    python3 governance-report.py --days 7

    # Filter by event type
    python3 governance-report.py --days 7 --type approval_requested

    # Show only unresolved events
    python3 governance-report.py --days 30 --unresolved

    # Filter by severity
    python3 governance-report.py --severity critical --unresolved

    # Mark an event resolved
    python3 governance-report.py --resolve gov-1234567890-abc --resolution false_positive

    # Export as JSON
    python3 governance-report.py --days 7 --export json

Exit codes:
    0 — success
    1 — resolution failed (event not found, invalid resolution state)
    2 — bad arguments
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from the scripts/ directory or from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOKS_LIB = _REPO_ROOT / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

try:
    from learning_db_v2 import (
        VALID_EVENT_TYPES,
        VALID_RESOLUTIONS,
        VALID_SEVERITIES,
        query_governance_events,
        resolve_governance_event,
    )
except ImportError as exc:
    print(f"error: cannot import learning_db_v2: {exc}", file=sys.stderr)
    sys.exit(2)

# ─── Severity ordering for display ────────────────────────────────────────────

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "warning": 3}

_SEVERITY_LABELS = {
    "critical": "CRIT ",
    "high": "HIGH ",
    "medium": "MED  ",
    "warning": "WARN ",
    None: "     ",
}


# ─── Formatters ───────────────────────────────────────────────────────────────


def _format_table(events: list[dict]) -> str:
    """Render events as a compact aligned table."""
    if not events:
        return "No governance events found."

    lines: list[str] = []
    lines.append(f"{'ID':<28}  {'SEV':<6}{'TYPE':<22}{'TOOL':<10}{'PHASE':<6}{'BLK':<5}{'RESOLVED':<12}  CREATED")
    lines.append("-" * 110)

    for ev in events:
        sev_label = _SEVERITY_LABELS.get(ev.get("severity"), "     ")
        resolved = ev.get("resolution") or ("-" if ev.get("resolved_at") is None else "yes")
        created = (ev.get("created_at") or "")[:19]
        blocked = "Y" if ev.get("blocked") else "N"
        tool = (ev.get("tool_name") or "")[:9]
        phase = (ev.get("hook_phase") or "")[:5]
        etype = (ev.get("event_type") or "")[:21]
        eid = (ev.get("id") or "")[:27]

        lines.append(f"{eid:<28}  {sev_label:<6}{etype:<22}{tool:<10}{phase:<6}{blocked:<5}{resolved:<12}  {created}")

    unresolved = sum(1 for e in events if e.get("resolved_at") is None)
    blocked = sum(1 for e in events if e.get("blocked"))
    lines.append("")
    lines.append(f"Total: {len(events)}  Unresolved: {unresolved}  Blocked: {blocked}")
    return "\n".join(lines)


def _format_json(events: list[dict]) -> str:
    return json.dumps(events, indent=2, default=str)


# ─── Command handlers ─────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    events = query_governance_events(
        days=args.days,
        event_type=args.type,
        severity=args.severity,
        unresolved_only=args.unresolved,
        limit=args.limit,
    )

    # Sort by severity then created_at descending
    events.sort(
        key=lambda e: (
            _SEVERITY_ORDER.get(e.get("severity") or "", 99),
            -(hash(e.get("created_at") or "")),
        )
    )

    if args.export == "json":
        print(_format_json(events))
    else:
        print(_format_table(events))

    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    resolution = args.resolution
    if resolution not in VALID_RESOLUTIONS:
        print(
            f"error: invalid resolution '{resolution}'. Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}",
            file=sys.stderr,
        )
        return 2

    ok = resolve_governance_event(args.resolve, resolution)
    if not ok:
        print(
            f"error: event '{args.resolve}' not found or already resolved.",
            file=sys.stderr,
        )
        return 1

    print(f"Resolved {args.resolve} as '{resolution}'.")
    return 0


# ─── Argument parsing ─────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="governance-report",
        description="Query and resolve governance events from learning.db",
    )

    # Listing filters
    p.add_argument(
        "--days",
        type=int,
        metavar="N",
        default=None,
        help="Show events from the last N days (default: all time)",
    )
    p.add_argument(
        "--type",
        metavar="EVENT_TYPE",
        choices=sorted(VALID_EVENT_TYPES),
        default=None,
        help=f"Filter by event type: {', '.join(sorted(VALID_EVENT_TYPES))}",
    )
    p.add_argument(
        "--severity",
        metavar="LEVEL",
        choices=sorted(VALID_SEVERITIES),
        default=None,
        help=f"Filter by severity: {', '.join(sorted(VALID_SEVERITIES))}",
    )
    p.add_argument(
        "--unresolved",
        action="store_true",
        default=False,
        help="Show only unresolved events",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=200,
        metavar="N",
        help="Maximum number of events to return (default: 200)",
    )
    p.add_argument(
        "--export",
        choices=["json"],
        default=None,
        help="Export format (json)",
    )

    # Resolution
    p.add_argument(
        "--resolve",
        metavar="EVENT_ID",
        default=None,
        help="Mark an event as resolved by its id",
    )
    p.add_argument(
        "--resolution",
        metavar="STATE",
        choices=sorted(VALID_RESOLUTIONS),
        default=None,
        help=f"Resolution state (required with --resolve): {', '.join(sorted(VALID_RESOLUTIONS))}",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve path takes priority
    if args.resolve:
        if not args.resolution:
            parser.error("--resolve requires --resolution (dismissed|false_positive|remediated)")
        return cmd_resolve(args)

    return cmd_list(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(0)  # fail open — governance report failure must never block
