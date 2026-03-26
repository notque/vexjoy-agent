#!/usr/bin/env python3
"""
Deny-List Generator — Phase 2 of the security-threat-model skill.

Produces a ready-to-merge deny-list config for ~/.claude/settings.json
from the surface scan findings produced by scan-threat-surface.py.

Static baseline rules are always included. Additional rules are derived
from surface scan findings:
- Hook uses curl/wget -> Bash(curl *) / Bash(wget *)
- Hook uses ssh/scp   -> Bash(ssh *) / Bash(scp *)
- Skill has unscoped allowed-tools -> path-scoped deny entries for sensitive dirs
- ANTHROPIC_BASE_URL found anywhere -> Bash(* ANTHROPIC_BASE_URL=*)

Output: security/deny-list.json

Usage:
    python3 scripts/generate-deny-list.py --surface security/surface-report.json --output security/deny-list.json
    python3 scripts/generate-deny-list.py --help
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ─── Static Baseline ───────────────────────────────────────────

_BASELINE_DENY: list[str] = [
    "Read(~/.ssh/**)",
    "Read(~/.aws/**)",
    "Read(**/.env*)",
    "Write(~/.ssh/**)",
    "Write(~/.aws/**)",
    "Bash(curl * | bash)",
    "Bash(ssh *)",
    "Bash(scp *)",
    "Bash(nc *)",
    "Bash(* ANTHROPIC_BASE_URL=*)",
]

# Rules added when unscoped tools are found
_UNSCOPED_TOOL_DENY: list[str] = [
    "Read(~/.ssh/**)",
    "Read(~/.aws/**)",
    "Read(**/.env*)",
    "Write(~/.ssh/**)",
    "Write(~/.aws/**)",
]


# ─── Derivation Logic ──────────────────────────────────────────


def _derive_rules_from_surface(surface: dict) -> list[str]:
    """Derive additional deny rules from surface scan findings."""
    extra: list[str] = []
    seen: set[str] = set()

    def add(rule: str) -> None:
        if rule not in seen:
            extra.append(rule)
            seen.add(rule)

    # Check hook commands for outbound patterns
    for hook in surface.get("hooks", []):
        cmd = hook.get("command", "").lower()
        if "curl" in cmd or "wget" in cmd:
            add("Bash(curl *)")
            add("Bash(wget *)")
        if "ssh" in cmd or "scp" in cmd:
            add("Bash(ssh *)")
            add("Bash(scp *)")
        if " nc " in cmd or cmd.startswith("nc ") or cmd.endswith(" nc"):
            add("Bash(nc *)")

    # Unscoped tools in skills -> sensitive path deny entries
    for skill in surface.get("skills", []):
        if skill.get("has_unscoped_tools"):
            for rule in _UNSCOPED_TOOL_DENY:
                add(rule)
            break  # one skill with unscoped tools is enough to add all rules

    # ANTHROPIC_BASE_URL found -> deny env override
    if surface.get("base_url_findings"):
        add("Bash(* ANTHROPIC_BASE_URL=*)")

    return extra


def build_deny_list(surface: dict) -> dict:
    """Build the full deny-list config from baseline + derived rules."""
    deny: list[str] = list(_BASELINE_DENY)
    seen: set[str] = set(_BASELINE_DENY)

    for rule in _derive_rules_from_surface(surface):
        if rule not in seen:
            deny.append(rule)
            seen.add(rule)

    return {
        "run_id": surface.get("run_id", "unknown"),
        "scanned_at": surface.get("scanned_at", ""),
        "derived_from": "surface-report.json",
        "permissions": {"deny": deny},
        "metadata": {
            "baseline_count": len(_BASELINE_DENY),
            "derived_count": len(deny) - len(_BASELINE_DENY),
            "total_count": len(deny),
        },
    }


# ─── Main ──────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deny-list config from surface scan findings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--surface",
        default="security/surface-report.json",
        help="Path to surface-report.json (default: security/surface-report.json)",
    )
    parser.add_argument(
        "--output",
        default="security/deny-list.json",
        help="Output path for deny-list.json (default: security/deny-list.json)",
    )
    args = parser.parse_args()

    surface_path = Path(args.surface)
    if not surface_path.exists():
        print(f"[deny-list] ERROR: surface report not found: {surface_path}", file=sys.stderr)
        print("[deny-list] Run scan-threat-surface.py first.", file=sys.stderr)
        sys.exit(1)

    try:
        surface = json.loads(surface_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[deny-list] ERROR: invalid JSON in {surface_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate required keys
    for key in ("hooks", "skills", "mcp_servers"):
        if key not in surface:
            print(f"[deny-list] ERROR: surface report missing key '{key}'", file=sys.stderr)
            sys.exit(1)

    result = build_deny_list(surface)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    meta = result["metadata"]
    print(
        f"[deny-list] baseline={meta['baseline_count']} derived={meta['derived_count']} "
        f"total={meta['total_count']} run_id={result['run_id']}",
        file=sys.stderr,
    )
    print(f"[deny-list] Written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"[deny-list] FATAL: {e}", file=sys.stderr)
        sys.exit(1)
