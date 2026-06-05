#!/usr/bin/env python3
"""Rank stale skill/agent scaffolding as pruning candidates. Report-only.

ADR: skill-scaffold-pruning. The toolkit creates skills and agents but never
retires them. Three staleness signals are already computable today with no new
capture:

  1. git mtime — last-touched epoch per component file.
  2. routing frequency — `topic="routing"` rows in learning.db, aggregated by
     the skill/agent segment of `key="agent:skill"`.
  3. orphaned INDEX entry — an INDEX `file` that no longer exists on disk.

This script joins all three, scores each component, and prints the top N
candidates with the reason for each. It never edits, deletes, or blocks; exit is
always 0. The script proposes; the human prunes (record in
docs/deprecation-template.md).

Quarterly run (documented, human-initiated — no cron created here):
    python3 scripts/stale-skill-scan.py --top 20

Usage:
    python3 scripts/stale-skill-scan.py [--top N] [--kind skills|agents|all]
        [--min-age-days 180] [--json] [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# Insert repo hooks/lib so learning_db_v2 imports (sibling pattern,
# learning-db.py:42-51).
_HOME_LIB = Path.home() / ".claude" / "hooks" / "lib"
if _HOME_LIB.is_dir():
    sys.path.insert(0, str(_HOME_LIB))
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "hooks" / "lib"))

from learning_db_v2 import query_learnings

DAY = 86400


def git_mtime(path: str) -> int | None:
    """Last git-commit epoch for `path`, or None when untracked/unknown.

    `git log -1 --format=%ct -- <path>`. Empty output (new/untracked file) ->
    None; the caller treats that as "now" (age 0, never a candidate).
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = result.stdout.strip()
    if not out:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def _route_counts() -> tuple[dict[str, int], dict[str, int]]:
    """Aggregate routing observation_count by skill segment and agent segment.

    key="agent:skill". Skill counts keyed by the last segment; agent counts by
    the first. Returns (skill_counts, agent_counts).
    """
    rows = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )
    skill_counts: dict[str, int] = {}
    agent_counts: dict[str, int] = {}
    for r in rows:
        key = r.get("key", "")
        if ":" not in key:
            continue
        agent, _, skill = key.partition(":")
        n = int(r.get("observation_count", 1) or 1)
        agent = agent.strip()
        skill = skill.strip()
        if agent:
            agent_counts[agent] = agent_counts.get(agent, 0) + n
        if skill and skill != "-":
            skill_counts[skill] = skill_counts.get(skill, 0) + n
    return skill_counts, agent_counts


def _load_index(repo_root: Path, kind: str) -> dict[str, dict]:
    """Load skills or agents INDEX.json entries dict ({} when absent/bad)."""
    fname = "skills" if kind == "skill" else "agents"
    inner = "skills" if kind == "skill" else "agents"
    path = repo_root / fname / "INDEX.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = data.get(inner, {})
    return {n: e for n, e in entries.items() if isinstance(e, dict)}


def _score_component(
    *,
    kind: str,
    name: str,
    file_field: str,
    repo_root: Path,
    routes: int,
    min_age_days: int,
    now_epoch: int,
    mtime_fn,
) -> dict | None:
    """Score one component. Returns a result row, or None when healthy (score 0).

    Scoring (deterministic, per ADR):
      orphaned (INDEX file missing) -> +100
      age >= min_age_days           -> +min(age_months, 24), +1 per stale month
      routes == 0                   -> +20  (never routed)
      routes <= 2                   -> +10  (rarely routed)
    """
    # Normalize mixed separators (skills/business\\csuite/SKILL.md on Windows).
    norm = file_field.replace("\\", "/") if file_field else ""
    abs_path = (repo_root / norm) if norm else None
    orphaned = not (abs_path and abs_path.is_file())

    mtime = None if orphaned or abs_path is None else mtime_fn(str(abs_path))
    if mtime is None:
        # Orphan has no file mtime; untracked file treated as now (age 0).
        age_days = 0
    else:
        age_days = max(0, (now_epoch - mtime) // DAY)

    score = 0
    reasons: list[str] = []

    if orphaned:
        score += 100
        reasons.append("orphaned: INDEX file missing on disk")

    if age_days >= min_age_days:
        age_points = min(age_days // 30, 24)
        score += int(age_points)
        reasons.append(f"untouched {int(age_days)}d")

    if routes == 0:
        score += 20
        reasons.append("never routed")
    elif routes <= 2:
        score += 10
        reasons.append(f"rarely routed ({routes})")

    if score == 0:
        return None

    return {
        "kind": kind,
        "name": name,
        "file": norm,
        "age_days": int(age_days),
        "routes": routes,
        "orphaned": orphaned,
        "score": int(score),
        "reasons": reasons,
    }


def scan(
    *,
    repo_root: Path,
    top: int = 15,
    kind: str = "all",
    min_age_days: int = 180,
    now_epoch: int | None = None,
    mtime_fn=git_mtime,
) -> list[dict]:
    """Rank pruning candidates. Pure read; never edits or blocks.

    now_epoch and mtime_fn are injectable for deterministic tests.
    Returns result rows sorted by score desc, truncated to `top`.
    """
    now_epoch = now_epoch if now_epoch is not None else int(time.time())
    skill_counts, agent_counts = _route_counts()

    kinds = []
    if kind in ("skills", "all"):
        kinds.append("skill")
    if kind in ("agents", "all"):
        kinds.append("agent")

    results: list[dict] = []
    for component_kind in kinds:
        index = _load_index(repo_root, component_kind)
        counts = skill_counts if component_kind == "skill" else agent_counts
        for name, entry in index.items():
            row = _score_component(
                kind=component_kind,
                name=name,
                file_field=entry.get("file", ""),
                repo_root=repo_root,
                routes=counts.get(name, 0),
                min_age_days=min_age_days,
                now_epoch=now_epoch,
                mtime_fn=mtime_fn,
            )
            if row is not None:
                results.append(row)

    # Sort by score desc, then name for stable order.
    results.sort(key=lambda r: (-r["score"], r["name"]))
    return results[:top]


def _print_human(results: list[dict], top: int) -> None:
    """Print the ranked candidate table."""
    import datetime

    today = datetime.date.today().isoformat()
    print(f"Stale-skill scan — {len(results)} candidates (top {top}), {today}")
    print("-" * 60)
    print(f"{'SCORE':>5}  {'KIND':<6} {'NAME':<28} {'AGE':>6}  {'ROUTES':>6}  REASONS")
    for r in results:
        print(
            f"{r['score']:>5}  {r['kind']:<6} {r['name']:<28} "
            f"{r['age_days']:>5}d  {r['routes']:>6}  {'; '.join(r['reasons'])}"
        )
    print("-" * 60)
    print("These are candidates, not deletions. Review each before deprecating.")
    print("Next step: docs/deprecation-template.md, then remove the component or mark it redundant.")


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Always returns 0 — report-only never fails a pipeline."""
    parser = argparse.ArgumentParser(description="Rank stale skill/agent scaffolding. Report-only.")
    parser.add_argument("--top", type=int, default=15, help="Cap candidates printed (default 15).")
    parser.add_argument("--kind", choices=["skills", "agents", "all"], default="all", help="Scope (default all).")
    parser.add_argument("--min-age-days", type=int, default=180, help="Below this git-mtime age, never a candidate.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    parser.add_argument("--repo-root", default=None, help="Override repo root (tests point at a fixture tree).")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _REPO_ROOT

    results = scan(
        repo_root=repo_root,
        top=args.top,
        kind=args.kind,
        min_age_days=args.min_age_days,
    )

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        _print_human(results, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
