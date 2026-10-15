#!/usr/bin/env python3
"""Plant small AST bugs in a hook or validator, run its tests, and list the mutants the tests miss.

Usage:
    python3 scripts/mutation-check.py --list
    python3 scripts/mutation-check.py --hook hooks/some-hook.py [--hook scripts/validate-x.py ...]
    python3 scripts/mutation-check.py --all [--workers 8] [--json]

On-demand only: a full sweep takes about 30 minutes and is not wired into CI. Mutants are written into throwaway
copies of the repo; the real files are never edited.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from mutation_check import report, runner, scope

REPO = HERE.parent


def select_targets(targets: list[scope.Target], hooks: list[str], run_all: bool) -> list[scope.Target]:
    """Return the targets matching *hooks* (file name or repo path), or every target when *run_all*."""
    if run_all:
        return targets
    picked: list[scope.Target] = []
    for raw in hooks:
        want = Path(raw)
        try:
            want = want.resolve().relative_to(REPO)
        except ValueError:
            pass
        match = [t for t in targets if t.name == want.name and (len(want.parts) == 1 or t.source == want.as_posix())]
        if not match:
            raise SystemExit(
                f"no mutation target for {raw}: file needs a registered hook or validate-*.py and a test file"
            )
        picked.extend(m for m in match if m not in picked)
    return picked


def cmd_list(targets: list[scope.Target], excluded: list[dict[str, str]]) -> int:
    """Print every target with its tests, then the files skipped for lack of tests."""
    for t in targets:
        print(f"{t.kind:9} {t.name:45} {' '.join(Path(x).name for x in t.tests)}")
    print("excluded:", ", ".join(f"{e['name']} ({e['reason']})" for e in excluded) or "none")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        "--hook", action="append", default=[], metavar="PATH", help="hook or validator to mutate (repeatable)"
    )
    ap.add_argument("--all", action="store_true", help="mutate every hook and validator that has a test file")
    ap.add_argument("--list", action="store_true", help="list the targets and exit")
    ap.add_argument("--json", action="store_true", help="print survivors and totals as JSON")
    ap.add_argument("--workers", type=int, default=8, help="parallel sandboxes (default 8)")
    ap.add_argument("--seed", type=int, default=0, help="sampling seed when a target has more mutants than its cap")
    ap.add_argument(
        "--cache", type=Path, default=None, help="keep and resume results in this directory (default: temp dir)"
    )
    args = ap.parse_args(argv)

    targets, excluded = scope.discover(REPO)
    if args.list:
        return cmd_list(targets, excluded)
    if not args.hook and not args.all:
        ap.error("one of --hook, --all, or --list is required")
    chosen = select_targets(targets, args.hook, args.all)

    cache = args.cache or Path(tempfile.mkdtemp(prefix="mutation-check-"))
    log = sys.stderr if args.json else sys.stdout
    before = runner.repo_fingerprint(REPO)
    run = runner.Runner(REPO, cache, workers=args.workers, seed=args.seed)
    try:
        run.start()
        bases = run.baselines(chosen)
        for name, rec in sorted(bases.items()):
            print(f"baseline {name}: usable={rec['usable']} {rec['reason']}", file=log)
        with contextlib.redirect_stdout(log):
            run.run_all(chosen, bases)
    finally:
        shutil.rmtree(run.root, ignore_errors=True)
    unchanged = before == runner.repo_fingerprint(REPO)

    names = {t.name for t in chosen}
    results = {n: d for n, d in runner.load_results(cache).items() if n in names}
    surv = report.survivors(results)
    if args.json:
        rows = report.per_target(results, {t.name: t.deny for t in chosen})
        print(json.dumps({"targets": rows, "survivors": surv, "repo_unchanged": unchanged}, indent=1))
    else:
        print()
        report.main(cache, {t.name: t.deny for t in chosen}, names)
        print()
        print(report.format_survivors(surv))
        print("\nreal repo unchanged by the run:", unchanged)
    if args.cache is None:
        shutil.rmtree(cache, ignore_errors=True)
    return 0 if unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
