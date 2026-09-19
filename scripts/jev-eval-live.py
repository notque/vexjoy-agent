#!/usr/bin/env python3
"""Evaluate /d routing accuracy against the live manifest's own trigger phrases.

Every skill's `routing.triggers` list defines what requests should route to it.
This script treats each trigger as a test case: send it to the router, check
whether the router picks the skill that owns the trigger.

Includes private skills, agents, and anything else in the live manifest.

Usage:
    python3 scripts/jev-eval-live.py                    # full run
    python3 scripts/jev-eval-live.py --limit 10         # smoke run
    python3 scripts/jev-eval-live.py --skill security   # one skill
    python3 scripts/jev-eval-live.py --summary          # just the numbers
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JEV_ROUTE = REPO_ROOT / "scripts" / "jev-route.py"
DEFAULT_TIMEOUT = 8.0
DEFAULT_WORKERS = 4


def load_cases(skill_filter: str | None = None) -> list[dict]:
    """Build test cases from the live manifest."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import importlib.util

    sp = importlib.util.spec_from_file_location("rm", str(REPO_ROOT / "scripts" / "routing-manifest.py"))
    rm = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(rm)
    entries = rm.load_entries()

    cases = []
    # d and do are slash commands, not routing targets
    skip_skills = {"d", "do"}
    for e in entries:
        if e.get("type") != "skill":
            continue
        name = e["name"]
        if name in skip_skills:
            continue
        if skill_filter and name != skill_filter:
            continue
        triggers = e.get("triggers", [])
        force = e.get("force_route", False)
        for trigger in triggers:
            cases.append(
                {
                    "request": trigger,
                    "expected_skill": name,
                    "force_route": force,
                    "bucket": "force-route" if force else "jev",
                }
            )
    return cases


def case_split(case: dict) -> str:
    """Stable dev/test split: 60% dev, 40% test."""
    digest = hashlib.sha256(case["request"].encode("utf-8")).digest()
    return "dev" if digest[0] % 5 < 3 else "test"


def route_one(request: str, timeout: float) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, str(JEV_ROUTE), "--request", request, "--json-compact"],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            check=False,
            cwd=str(REPO_ROOT),
        )
        return json.loads(proc.stdout)
    except Exception as exc:
        return {"fallback": True, "skill": None, "source": f"error: {exc}"}


def is_correct(case: dict, result: dict) -> bool:
    if result.get("fallback"):
        return False
    return result.get("skill") == case["expected_skill"]


def run(cases: list[dict], workers: int, timeout: float) -> list[dict]:
    rows = [None] * len(cases)

    def _work(i, case):
        return i, route_one(case["request"], timeout)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_work, i, c) for i, c in enumerate(cases)]
        for done, future in enumerate(as_completed(futures), 1):
            i, result = future.result()
            rows[i] = {
                "case": cases[i],
                "result": result,
                "correct": is_correct(cases[i], result),
                "split": case_split(cases[i]),
            }
            if done % 50 == 0 or done == len(cases):
                correct_so_far = sum(r["correct"] for r in rows if r)
                print(f"  {done}/{len(cases)} ({100 * correct_so_far / done:.0f}%)", file=sys.stderr)
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(r["correct"] for r in rows)
    by_skill = {}
    for r in rows:
        skill = r["case"]["expected_skill"]
        if skill not in by_skill:
            by_skill[skill] = {"n": 0, "correct": 0, "wrong_picks": []}
        by_skill[skill]["n"] += 1
        by_skill[skill]["correct"] += r["correct"]
        if not r["correct"]:
            by_skill[skill]["wrong_picks"].append(r["result"].get("skill"))

    return {
        "n": n,
        "correct": correct,
        "accuracy_pct": round(100 * correct / n, 1) if n else 0,
        "fallbacks": sum(bool(r["result"].get("fallback")) for r in rows),
        "by_skill": by_skill,
    }


def main():
    parser = argparse.ArgumentParser(description="Eval /d routing against live manifest triggers.")
    parser.add_argument("--limit", type=int, help="Run only first N cases.")
    parser.add_argument("--skill", help="Test only this skill's triggers.")
    parser.add_argument("--split", choices=("dev", "test"), help="Run one split only.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--summary", action="store_true", help="Print only the summary line.")
    parser.add_argument("--out", help="Save raw results to this JSON file.")
    args = parser.parse_args()

    cases = load_cases(args.skill)
    if args.split:
        cases = [c for c in cases if case_split(c) == args.split]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} cases ({args.split or 'all'} split)...", file=sys.stderr)
    rows = run(cases, args.workers, args.timeout)
    s = summarize(rows)

    if args.summary:
        print(f"{s['accuracy_pct']}% ({s['correct']}/{s['n']})")
    else:
        print(f"\n{'Skill':<30} {'Correct':>8} {'Total':>6} {'Pct':>6}  Wrong picks")
        print("-" * 85)
        for skill in sorted(s["by_skill"], key=lambda k: s["by_skill"][k]["correct"] / max(s["by_skill"][k]["n"], 1)):
            d = s["by_skill"][skill]
            pct = 100 * d["correct"] / d["n"] if d["n"] else 0
            wrongs = ", ".join(set(str(w) for w in d["wrong_picks"][:5]))
            print(f"  {skill:<28} {d['correct']:>8}/{d['n']:<6} {pct:>5.0f}%  {wrongs}")
        print(f"\nTotal: {s['correct']}/{s['n']} = {s['accuracy_pct']}%  (fallbacks: {s['fallbacks']})")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"summary": s, "rows": rows}, fh, indent=2)
        print(f"Saved to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
