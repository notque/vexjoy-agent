#!/usr/bin/env python3
"""Read .local/profile.yaml and emit one disabled item per line.

Used by install.sh to drive per-component filtering. Missing or malformed
profile files are treated as empty (no items disabled), so the installer
behaves identically to a fresh checkout when the profile is absent.

Usage:
    python3 scripts/load-profile.py --list skills
    python3 scripts/load-profile.py --list agents
    python3 scripts/load-profile.py --list hooks

Exit codes:
    0 — success (output may be empty)
    2 — bad arguments
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = REPO_ROOT / ".local" / "profile.yaml"
CATEGORIES = ("skills", "agents", "hooks")


def load(profile_path: Path) -> dict[str, list[str]]:
    if not profile_path.is_file():
        return {cat: [] for cat in CATEGORIES}
    try:
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"warning: {profile_path} is not valid YAML ({exc}); treating as empty", file=sys.stderr)
        return {cat: [] for cat in CATEGORIES}
    disabled = data.get("disabled") if isinstance(data, dict) else None
    if not isinstance(disabled, dict):
        return {cat: [] for cat in CATEGORIES}
    out: dict[str, list[str]] = {}
    for cat in CATEGORIES:
        items = disabled.get(cat) or []
        if not isinstance(items, list):
            print(f"warning: disabled.{cat} in {profile_path} is not a list; ignoring", file=sys.stderr)
            items = []
        out[cat] = [str(x).strip() for x in items if str(x).strip()]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", choices=CATEGORIES, required=True, help="Category to print.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Path to profile.yaml.")
    args = parser.parse_args()

    items = load(args.profile)[args.list]
    for name in items:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
