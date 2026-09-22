#!/usr/bin/env python3
"""Fail when a tracked repo file carries a private overlay name or overlay content.

Reads overlay names and sources from the installed vexinstall ledger (plus the
configured overlays.json), then scans ``git ls-files``. Prints only the tracked
path and the matched overlay name. Never prints file contents.

Usage:
    python3 scripts/check-private-leak.py [--repo PATH] [--home PATH] [--json]

Exit codes: 0 clean (or no overlay data on this host), 1 leak found, 2 bad config.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vexinstall import ledger as ledger_mod
from vexinstall.common import OverlayConfigError
from vexinstall.context import state_dir
from vexinstall.leak import find_leaks
from vexinstall.ledger import Ledger
from vexinstall.sources import default_overlays_path, load_overlays, load_public


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--home", type=Path, default=Path.home())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    led, _ = ledger_mod.load(ledger_mod.ledger_path(state_dir(args.home)))
    try:
        cfg = load_overlays(default_overlays_path(args.home), repo, args.home)
    except OverlayConfigError as exc:
        print(f"check-private-leak: {exc}", file=sys.stderr)
        return 2
    leaks = find_leaks(repo, led or Ledger(), cfg, load_public(repo))
    if args.json:
        print(json.dumps([{"path": x.path, "name": x.name, "how": x.how} for x in leaks], indent=2))
    else:
        for x in leaks:
            print(f"LEAK {x.path}: {x.how} '{x.name}'")
        print(f"check-private-leak: {len(leaks)} finding(s)")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
