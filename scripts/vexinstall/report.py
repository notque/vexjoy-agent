"""Run reports (``reports/<ts>.json``, keep 50) and the one-line summary."""

from __future__ import annotations

from pathlib import Path

from .common import REPORTS_KEEP
from .fsops import Guard, atomic_write_json
from .ledger import Ledger
from .plan import Plan

_BUCKETS = {
    "add": "added",
    "replace": "replaced",
    "remove": "removed",
    "container": "removed",
    "skip": "skipped",
    "blocked": "blocked",
    "collision": "collisions",
    "stale": "stale",
    "forget": "forgotten",
}


def plan_diff(plan: Plan) -> dict:
    """Group plan actions into report buckets per target."""
    out: dict = {}
    for t, tp in plan.targets.items():
        buckets: dict[str, list] = {v: [] for v in dict.fromkeys(_BUCKETS.values())}
        buckets["adopted"] = []
        buckets["taken_over"] = []
        for a in tp.actions:
            if a.adopt:
                buckets["adopted"].append(a.dest)
            if a.takeover:
                buckets["taken_over"].append(a.dest)
            key = _BUCKETS.get(a.op)
            if key:
                buckets[key].append({"dest": a.dest, "reason": a.reason} if a.reason else a.dest)
        out[t] = buckets
    return out


def write_report(reports_dir: Path, ts: str, data: dict, guard: Guard) -> Path:
    """Write one report and prune to the newest 50."""
    path = reports_dir / f"{ts}.json"
    atomic_write_json(path, data, guard)
    olds = sorted(reports_dir.glob("*.json"))
    for old in olds[:-REPORTS_KEEP]:
        old.unlink()
    return path


def summary_line(label: str, plan: Plan, ledger: Ledger, applied: set[str] | None = None) -> str:
    """``[sync] claude: +2 ~1 -0, 71 skills, 0 collisions; codex: ...`` (skill counts from the ledger)."""
    parts = []
    for t, tp in plan.targets.items():
        if applied is not None and t not in applied:
            continue
        skills = sum(1 for e in ledger.for_target(t).values() if e.kind == "skill")
        parts.append(
            f"{t}: +{tp.count('add')} ~{tp.count('replace')} -{tp.removals}, "
            f"{skills} skills, {len(tp.collisions)} collisions"
        )
    return f"[{label}] " + "; ".join(parts)
