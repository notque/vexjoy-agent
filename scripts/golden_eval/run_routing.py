#!/usr/bin/env python3
"""Routing-level golden eval: /do vs /d on scripts/golden_eval/tasks.json.

Each task runs `--runs` times per router with the machinery the routers use:

  d   jev-route.py prepare (one Jev call) -> a `claude -p` session holding /d's
      SKILL.md, /do's rule text, and the manifest picks the route and the
      execution plan -> jev-route.py --finalize -> d_gate checks the plan.
  do  pre-route.py -> a `claude -p` session holding /do's SKILL.md and the
      manifest picks the route and the execution plan.

Both arms use the same `--model`. No task is executed; only the routing reply
is scored: skill, pipeline, required skill groups, forbidden skills, and for /d
whether the execution plan stays in the main loop except for allowed reasons.
Every row records start and end timestamps for replay. Results go to a fresh
`--out-dir`; `--score DIR` rescores saved rows.

Usage:
  nice -n 10 python3 scripts/golden_eval/run_routing.py --out-dir scripts/routing-ab-results/<new> --runs 2
  python3 scripts/golden_eval/run_routing.py --score scripts/routing-ab-results/<dir>
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "router_attachment"))

import d_gate
import d_route_model
import run_eval

TASKS = HERE / "tasks.json"
ROUTERS = ("d", "do")
JEV_TOKEN_BUDGET = 45_000  # stop new Jev calls past this (run cap ~50k)

_PLAN_KEYS = """"execution": [{"part": "<primary, or a worker's scope>", "mode": "main|dispatch",
 "dispatch_reason": "<fan-out|worktree|haiku-gather|verifier, or null>"}]"""

D_PROMPT = (
    """You are executing the /d skill for the user request below. Its SKILL.md, /do's routing rules, and the routing
manifest are in your system prompt. Phase 1 step 1 already ran: JEV_RESULT is given. You cannot run tools and must not
execute the task. Apply Phase 1 step 2 exactly as SKILL.md instructs, and decide where each part runs per Phase 5. Output
ONLY one JSON object with these keys: {"skill": ..., "pipeline": ..., "stack": [...], "workers": [{"skill": ...,
"scope": ...}], "complexity": "trivial|simple|medium|complex", "confidence": ..., "reasoning": ..., """
    + _PLAN_KEYS
    + """}. No prose, no code fences.

User request:
<request>
%s
</request>

JEV_RESULT:
%s
"""
)

DO_PROMPT = (
    """You are executing the /do skill (its SKILL.md and the routing manifest are in your system prompt) for the
user request below. You cannot run tools: the manifest text is already provided, and PRE_ROUTE_RESULT is the output of
pre-route.py for this request. Do not execute the task. Apply Phases 1-4 exactly as SKILL.md instructs, then output ONLY
one JSON object with these keys: {"skill": ..., "pipeline": ..., "stack": [...], "workers": [...],
"complexity": "trivial|simple|medium|complex", """
    + _PLAN_KEYS
    + """}. No prose, no code fences.

User request:
<request>
%s
</request>

PRE_ROUTE_RESULT:
%s
"""
)


def load_tasks(path: Path = TASKS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["tasks"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jev_tokens(usage: object) -> int:
    """Input plus output tokens from a Jev usage dict, whatever the key names."""
    if not isinstance(usage, dict):
        return 0
    if isinstance(usage.get("total_tokens"), (int, float)):
        return int(usage["total_tokens"])
    total = 0
    for key in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            total += int(value)
    return total


# ---------------------------------------------------------------- scoring (pure)


def plan_parts(decision: dict | None) -> list[dict]:
    raw = (decision or {}).get("execution")
    parts = [p for p in raw if isinstance(p, dict)] if isinstance(raw, list) else []
    out = []
    for p in parts:
        mode = str(p.get("mode") or "").strip().lower()
        reason = p.get("dispatch_reason")
        reason = str(reason).strip().lower() if reason not in (None, "", "null") else None
        out.append({"mode": mode if mode in ("main", "dispatch") else "invalid", "reason": reason})
    return out


def score_row(task: dict, router: str, decision: dict | None, final: dict | None, patterns: frozenset[str]) -> dict:
    """Score one routing reply. `final` is the /d finalized route (None for /do)."""
    decision = decision or {}
    route = run_eval.d_model_decision(final) if final is not None else decision
    attached = run_eval.attached_skills(route, patterns)
    skill = (route.get("skill") or None) if isinstance(route.get("skill"), str) else None
    pipeline = route.get("pipeline") if isinstance(route.get("pipeline"), str) and route.get("pipeline") else None
    complexity = str(decision.get("complexity") or "").strip().lower()
    if task.get("expect_trivial"):
        skill_ok = complexity == "trivial"
        pipeline_ok = complexity == "trivial" or pipeline in task["pipeline"]
    else:
        skill_ok = skill in task["skill"]
        pipeline_ok = pipeline in task["pipeline"]
    groups_ok = all(any(s in attached for s in group) for group in task["required"])
    forbidden = [s for s in attached if s in task["forbid"]]
    parts = plan_parts(decision)
    dispatches = [p for p in parts if p["mode"] == "dispatch"]
    rules = task["d_exec"]
    # /d plan validity is the d_gate enum; /do has no reason field by design.
    plan_valid = bool(parts) and all(
        p["mode"] == "main" or (p["mode"] == "dispatch" and p["reason"] in d_gate.DISPATCH_REASONS) for p in parts
    )
    exec_ok = (
        plan_valid
        and (not rules["main"] or any(p["mode"] == "main" for p in parts))
        and all(p["reason"] in rules["reasons"] for p in dispatches)
        and (not rules["expect_dispatch"] or bool(dispatches))
    )
    return {
        "id": task["id"],
        "router": router,
        "skill": skill,
        "pipeline": pipeline,
        "complexity": complexity,
        "attached": attached,
        "skill_ok": skill_ok,
        "pipeline_ok": pipeline_ok,
        "groups_ok": groups_ok,
        "forbidden": forbidden,
        "route_ok": skill_ok and pipeline_ok and groups_ok and not forbidden,
        "parts": parts,
        "main_parts": sum(p["mode"] == "main" for p in parts),
        "dispatch_parts": len(dispatches),
        "dispatch_reasons": [p["reason"] or "unstated" for p in dispatches],
        "plan_valid_d": plan_valid,
        "exec_ok_d": exec_ok,
    }


def aggregate(scores: list[dict], runs: int) -> dict:
    """Per-router numbers: per run, and rows right in every run."""
    out: dict[str, dict] = {}
    for router in ROUTERS:
        rows = [s for s in scores if s["router"] == router]
        if not rows:
            continue
        by_run: dict[int, list[dict]] = {}
        for s in rows:
            by_run.setdefault(s["run"], []).append(s)
        ids = sorted({s["id"] for s in rows})
        all_runs_ok = sum(1 for i in ids if all(s["route_ok"] for s in rows if s["id"] == i))
        parts = sum(s["main_parts"] + s["dispatch_parts"] for s in rows)
        reasons: dict[str, int] = {}
        for s in rows:
            for r in s["dispatch_reasons"]:
                reasons[r] = reasons.get(r, 0) + 1
        out[router] = {
            "tasks": len(ids),
            "runs": runs,
            "route_ok_per_run": {str(k): sum(s["route_ok"] for s in v) for k, v in sorted(by_run.items())},
            "route_ok_all_runs": all_runs_ok,
            "skill_ok_per_run": {str(k): sum(s["skill_ok"] for s in v) for k, v in sorted(by_run.items())},
            "pipeline_ok_per_run": {str(k): sum(s["pipeline_ok"] for s in v) for k, v in sorted(by_run.items())},
            "groups_ok_per_run": {str(k): sum(s["groups_ok"] for s in v) for k, v in sorted(by_run.items())},
            "forbidden_hits": sum(len(s["forbidden"]) for s in rows),
            "pipeline_picked_rate": round(sum(1 for s in rows if s["pipeline"]) / len(rows), 3),
            "main_part_share": round(sum(s["main_parts"] for s in rows) / parts, 3) if parts else None,
            "dispatch_reasons": reasons,
            "exec_ok_d_per_run": {str(k): sum(s["exec_ok_d"] for s in v) for k, v in sorted(by_run.items())},
            "changed_between_runs": sorted(
                i for i in ids if len({(s["skill"], s["pipeline"]) for s in rows if s["id"] == i}) > 1
            ),
        }
    return out


# ---------------------------------------------------------------- runners (live)


class Budget:
    def __init__(self, cap: int) -> None:
        self.cap, self.used, self.lock = cap, 0, threading.Lock()

    def take(self) -> bool:
        with self.lock:
            return self.used < self.cap

    def add(self, tokens: int) -> None:
        with self.lock:
            self.used += tokens


def run_one(task: dict, router: str, run: int, model: str, scratch: Path, budget: Budget) -> dict:
    started = _now()
    t0 = time.monotonic()
    request = task["request"]
    row: dict = {"id": task["id"], "router": router, "run": run, "started": started}
    if router == "d":
        if not budget.take():
            row.update(error="jev token budget reached", decision=None, final=None, ended=_now())
            return row
        prepared = d_route_model.prepare(request)
        budget.add(jev_tokens(prepared.get("usage")))
        decision, cost, text, usage = d_route_model.call_model(
            d_route_model.system_file(request, scratch), D_PROMPT % (request, json.dumps(prepared)), model, scratch
        )
        final = d_route_model.finalize(prepared, decision)
        row.update(prepared=prepared, jev_tokens=jev_tokens(prepared.get("usage")), final=final)
    else:
        pre = run_eval.run_pre_route(request)
        decision, cost, text, usage = d_route_model.call_model(
            run_eval.build_do_system_file(scratch, task), DO_PROMPT % (request, json.dumps(pre)), model, scratch
        )
        row.update(pre_route=pre, jev_tokens=0, final=None)
    row.update(
        decision=decision,
        cost_usd=cost,
        usage_model=usage,
        text=text[:2000] if decision is None else "",
        seconds=round(time.monotonic() - t0, 2),
        ended=_now(),
    )
    return row


def score_dir(out_dir: Path, tasks: list[dict], patterns: frozenset[str]) -> dict:
    by_id = {t["id"]: t for t in tasks}
    rows = [json.loads(line) for line in (out_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line]
    scores = []
    for r in rows:
        if r["id"] not in by_id:
            continue
        s = score_row(by_id[r["id"]], r["router"], r.get("decision"), r.get("final"), patterns)
        s["run"] = r["run"]
        scores.append(s)
    runs = max((r["run"] for r in rows), default=0)
    summary = {
        "tasks": len(tasks),
        "runs": runs,
        "model": rows[0].get("model") if rows else None,
        "started": min((r["started"] for r in rows), default=None),
        "ended": max((r.get("ended") or "" for r in rows), default=None),
        "model_cost_usd": {
            rt: round(sum(r.get("cost_usd") or 0 for r in rows if r["router"] == rt), 4) for rt in ROUTERS
        },
        "jev_tokens": sum(r.get("jev_tokens") or 0 for r in rows),
        "jev_calls": sum(1 for r in rows if r["router"] == "d" and r.get("prepared") is not None),
        # The Jev client caches answers: a repeat request returns in milliseconds with no usage.
        "jev_cache_hits": sum(
            1
            for r in rows
            if r["router"] == "d"
            and isinstance(r.get("prepared"), dict)
            and r["prepared"].get("usage") is None
            and not r["prepared"].get("error")
        ),
        "routers": aggregate(scores, runs),
        "rows": scores,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    notes_path = out_dir / "NOTES.md"
    notes = "\n" + notes_path.read_text(encoding="utf-8") if notes_path.is_file() else ""
    (out_dir / "VERDICT.md").write_text(render_verdict(summary, notes), encoding="utf-8")
    return summary


def _per_run(value: dict) -> str:
    return " / ".join(str(v) for _k, v in sorted(value.items()))


def render_verdict(summary: dict, notes: str = "") -> str:
    """Numbers only: the owner judges which router is better. `notes` is NOTES.md from the run dir."""
    routers = summary["routers"]
    names = [r for r in ROUTERS if r in routers]
    n = summary["tasks"]
    head = "| Metric | " + " | ".join(f"/{r}" for r in names) + " |\n|---|" + "---|" * len(names) + "\n"

    def row(label: str, fn) -> str:
        return f"| {label} | " + " | ".join(fn(routers[r]) for r in names) + " |\n"

    table = head + "".join(
        [
            row(f"Route correct per run (of {n})", lambda m: _per_run(m["route_ok_per_run"])),
            row(f"Route correct in every run (of {n})", lambda m: str(m["route_ok_all_runs"])),
            row("Skill correct per run", lambda m: _per_run(m["skill_ok_per_run"])),
            row("Pipeline correct per run", lambda m: _per_run(m["pipeline_ok_per_run"])),
            row("Required skill groups hit per run", lambda m: _per_run(m["groups_ok_per_run"])),
            row("Forbidden skill picks", lambda m: str(m["forbidden_hits"])),
            row("Pipeline picked (share of rows)", lambda m: str(m["pipeline_picked_rate"])),
            row("Main-loop share of planned parts", lambda m: str(m["main_part_share"])),
            row(
                "Dispatch reasons",
                lambda m: ", ".join(f"{k} {v}" for k, v in sorted(m["dispatch_reasons"].items())) or "none",
            ),
            row("Plan within /d's dispatch rules per run", lambda m: _per_run(m["exec_ok_d_per_run"])),
            row("Tasks whose pick changed between runs", lambda m: ", ".join(m["changed_between_runs"]) or "none"),
        ]
    )
    misses = "".join(
        f"| {s['id']} | /{s['router']} | {s['run']} | {s['skill']} | {s['pipeline']} | "
        f"{'' if s['skill_ok'] else 'skill '}{'' if s['pipeline_ok'] else 'pipeline '}"
        f"{'' if s['groups_ok'] else 'groups '}{'forbidden ' if s['forbidden'] else ''}|\n"
        for s in summary["rows"]
        if not s["route_ok"]
    )
    cost = ", ".join(f"/{r} ${v}" for r, v in summary["model_cost_usd"].items())
    return (
        "# d-single-loop-v1: /do vs /d routing on the golden set\n\n"
        f"Tasks: {n} (`scripts/golden_eval/tasks.json`), runs per router: {summary['runs']}, "
        f"model (both arms): `{summary['model']}`. Window: {summary['started']} to {summary['ended']}.\n"
        f"Model cost: {cost}. Jev: {summary['jev_calls']} calls, {summary.get('jev_cache_hits', 0)} of them "
        f"served from the Jev cache, {summary['jev_tokens']} tokens (/d prepare only).\n\n"
        "Routing level only: no task was executed. /do's plan follows /do's rules (Medium and Complex dispatch), "
        "so the /d dispatch-rule row is a /d check, shown for /do for reference only.\n\n"
        + table
        + "\n## Rows not route-correct\n\n| Task | Router | Run | Skill | Pipeline | Missed |\n|---|---|---|---|---|---|\n"
        + (misses or "| none | | | | | |\n")
        + (notes or "")
        + "\nRescore: `python3 scripts/golden_eval/run_routing.py --score <this dir>`. Per-row detail: `summary.json`, "
        "raw replies with timestamps: `rows.jsonl`.\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, help="fresh results directory")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--model", default="opus", help="same model for both arms")
    ap.add_argument("--workers", type=int, default=4, help="parallel calls (max 4)")
    ap.add_argument("--only", default="", help="comma-separated task ids")
    ap.add_argument("--routers", default="d,do")
    ap.add_argument("--score", type=Path, help="rescore an existing results directory and exit")
    args = ap.parse_args(argv)

    tasks = load_tasks()
    if args.only:
        wanted = set(args.only.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
    patterns = frozenset(p.stem for p in (REPO / "skills" / "shared-patterns").glob("*.md"))
    if args.score:
        print(json.dumps(score_dir(args.score, tasks, patterns)["routers"], indent=1))
        return 0
    if not args.out_dir:
        ap.error("--out-dir is required unless --score is given")
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        ap.error(f"{args.out_dir} is not empty; give each run a fresh directory")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.gettempdir()) / "golden-routing-eval"
    scratch.mkdir(parents=True, exist_ok=True)
    budget = Budget(JEV_TOKEN_BUDGET)
    jobs = [(t, r, n) for n in range(1, args.runs + 1) for t in tasks for r in args.routers.split(",")]
    lock = threading.Lock()
    rows_path = args.out_dir / "rows.jsonl"

    def job(item: tuple[dict, str, int]) -> None:
        task, router, run = item
        row = run_one(task, router, run, args.model, scratch, budget)
        row["model"] = args.model
        with lock, rows_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    # One call per router first warms each prompt cache.
    warm = [j for j in jobs if j[0] is tasks[0] and j[2] == 1]
    for item in warm:
        job(item)
    with ThreadPoolExecutor(max_workers=max(1, min(4, args.workers))) as pool:
        list(pool.map(job, [j for j in jobs if j not in warm]))
    summary = score_dir(args.out_dir, tasks, patterns)
    print(json.dumps({k: summary[k] for k in ("model_cost_usd", "jev_tokens", "jev_calls", "routers")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
