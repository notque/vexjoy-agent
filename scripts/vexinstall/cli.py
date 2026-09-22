"""Argument parsing and dispatch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .apply import (
    run_apply,
    run_plan,
    run_prune,
    run_restore_settings,
    run_restore_trash,
    run_uninstall,
)
from .common import MODES, TARGET_NAMES, ExitCode
from .context import Options, Result
from .doctor import run_doctor
from .migrate import run_migrate_overlays
from .repair import run_repair

COMMANDS = (
    "plan",
    "apply",
    "sync",
    "doctor",
    "uninstall",
    "repair-repo",
    "prune",
    "restore-trash",
    "restore-settings",
    "migrate-overlays",
)


def build_parser() -> argparse.ArgumentParser:
    """CLI parser."""
    p = argparse.ArgumentParser(prog="vexinstall", description="vexjoy installer engine")
    p.add_argument("command", choices=COMMANDS)
    p.add_argument("ts", nargs="?", help="timestamp for restore-trash / restore-settings")
    p.add_argument("--target", default="all", choices=(*TARGET_NAMES, "all"))
    p.add_argument("--dry-run", action="store_true", help="plan only; write nothing")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--home", type=Path, default=None, help="override HOME root (tests)")
    p.add_argument("--source-root", type=Path, default=None, help="public repo checkout")
    p.add_argument("--mode", choices=MODES, default=None)
    p.add_argument("--allow-mass-remove", action="store_true", help="apply only; sync never honors it")
    p.add_argument("--adopt-source", action="store_true", help="accept a new source_root, worktree, or tmp path")
    p.add_argument("--index-only", action="store_true", help="sync/apply: regenerate installed indexes only")
    p.add_argument("--confirm", action="store_true", help="repair-repo / prune: actually act")
    p.add_argument("--unowned", action="store_true", help="prune: target unowned dangling/category entries")
    p.add_argument("--overlays-file", type=Path, default=None, help="alternate overlays.json (read-only use)")
    p.add_argument("--show-diff", action="store_true", help="repair-repo: print full diffs instead of --stat")
    p.add_argument(
        "--takeover",
        action="store_true",
        help="plan/apply: trash and replace unowned entries at desired dests (never honored by sync)",
    )
    return p


def to_options(ns: argparse.Namespace) -> Options:
    """Namespace -> Options."""
    return Options(
        command=ns.command,
        target=ns.target,
        dry_run=ns.dry_run,
        json=ns.json,
        home=(ns.home or Path.home()).absolute(),
        source_root=ns.source_root,
        mode=ns.mode,
        allow_mass_remove=ns.allow_mass_remove and ns.command != "sync",
        adopt_source=ns.adopt_source,
        index_only=ns.index_only,
        confirm=ns.confirm,
        unowned=ns.unowned,
        overlays_file=ns.overlays_file,
        show_diff=ns.show_diff,
        takeover=ns.takeover and ns.command in ("plan", "apply"),
        ts=ns.ts,
    )


def dispatch(opts: Options) -> Result:
    """Run one command."""
    cmd = opts.command
    if cmd == "plan":
        return run_plan(opts)
    if cmd == "apply":
        return run_apply(opts, sync=False)
    if cmd == "sync":
        return run_apply(opts, sync=True)
    if cmd == "doctor":
        return run_doctor(opts)
    if cmd == "uninstall":
        return run_uninstall(opts)
    if cmd == "repair-repo":
        return run_repair(opts)
    if cmd == "prune":
        return run_prune(opts)
    if cmd == "restore-trash":
        return run_restore_trash(opts)
    if cmd == "restore-settings":
        return run_restore_settings(opts)
    if cmd == "migrate-overlays":
        return run_migrate_overlays(opts)
    return Result(code=int(ExitCode.USAGE), err=[f"unknown command {cmd}"])


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the exit code."""
    ns = build_parser().parse_args(argv)
    opts = to_options(ns)
    res = dispatch(opts)
    if opts.json:
        payload = {"exit": res.code, "out": res.out, "err": res.err, "data": res.data}
        print(json.dumps(payload, indent=2, default=str))
    else:
        for line in res.out:
            print(line)
        for line in res.err:
            print(line, file=sys.stderr)
    return res.code
