#!/usr/bin/env python3
"""Router-attachment eval: does /d or /do attach the right agent and skills?

Routers under test:
  d-prepare  jev-route.py prepare output only (safety force route and attachment
             evidence). Writes the JEV_RESULT that d-model replays.
  d-model    a model plays the /d session: it reads /d's SKILL.md, /do's routing
             rules, and the routing manifest, picks the agent, skill, and
             pipeline, and `jev-route.py --finalize` adds the attachments
             (scripts/d_route_model.py).
  do-model   a model applies /do's SKILL.md to the routing manifest plus the
             pre-route.py result and emits the build-dispatch decision.

Model runs use `claude -p --model <model> --tools ""` and ask only for the
routing JSON. Every run writes a fresh JSON file; scoring is pure and shared
with scripts/tests/test_router_attachment_eval.py.

Usage:
  python3 scripts/router_attachment/run_eval.py --router d-prepare --out /tmp/x/d-prepare.json
  python3 scripts/router_attachment/run_eval.py --router d-model --jev-results /tmp/x/d-prepare.json --out ...
  python3 scripts/router_attachment/run_eval.py --score /tmp/x/d-model.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import d_route_model

CASES = HERE / "cases.json"
DEFAULT_MODEL = "claude-opus-4-6"


# ---------------------------------------------------------------- catalog


def load_cases(split: str = "all") -> list[dict]:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if split == "all" or c["split"] == split]


def load_catalog() -> dict[str, set[str]]:
    """Live manifest names plus shared-pattern stems (stack-only prompt injections)."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "routing-manifest.py"), "--json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(REPO),
    )
    entries = json.loads(proc.stdout)
    patterns = {p.stem for p in (REPO / "skills" / "shared-patterns").glob("*.md")}
    return {
        "agents": {e["name"] for e in entries if e["type"] == "agent"} | {"general-purpose"},
        "skills": {e["name"] for e in entries if e["type"] == "skill"},
        "pipelines": {e["name"] for e in entries if e["type"] == "pipeline"},
        "patterns": patterns,
    }


# ---------------------------------------------------------------- scoring


def attached_skills(decision: dict, patterns: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Skill names a decision attaches: primary skill, then stack, de-duplicated.

    Shared-pattern stems (anti-rationalization-core, local-only) are prompt
    injections, not skills, so they are neither credited nor penalized.
    """
    names: list[str] = []
    raw = [decision.get("skill")] + list(decision.get("stack") or [])
    for item in raw:
        if not item or not isinstance(item, str):
            continue
        name = item.strip().lower().removeprefix("shared-patterns/").removesuffix(".md")
        if name in {"-", "null", "none"} or name in patterns or name in names:
            continue
        names.append(name)
    return names


def score_case(case: dict, decision: dict | None, patterns: set[str] | frozenset[str] = frozenset()) -> dict:
    """Score one decision against one labeled case. Pure function."""
    if not decision:
        decision = {}
    agent = (decision.get("agent") or "general-purpose").strip()
    agent_ok = ("*" in case["agents"] or agent in case["agents"]) and agent not in case.get("forbid_agents", [])
    attached = attached_skills(decision, patterns)
    allowed = {s for g in case["required"] for s in g} | set(case.get("acceptable", []))
    groups_hit = sum(1 for g in case["required"] if any(s in attached for s in g))
    correct = [s for s in attached if s in allowed]
    forbidden_hit = [s for s in attached if s in case.get("forbid_skills", [])]
    return {
        "id": case["id"],
        "split": case["split"],
        "domain": case["domain"],
        "agent": agent,
        "agent_ok": agent_ok,
        "attached": attached,
        "groups_total": len(case["required"]),
        "groups_hit": groups_hit,
        "attached_n": len(attached),
        "attached_correct": len(correct),
        "forbidden_hit": forbidden_hit,
        "full": agent_ok and groups_hit == len(case["required"]) and not forbidden_hit,
    }


def aggregate(scores: list[dict]) -> dict:
    n = len(scores)
    if n == 0:
        return {"n": 0}
    groups_total = sum(s["groups_total"] for s in scores)
    attached_n = sum(s["attached_n"] for s in scores)
    recall = sum(s["groups_hit"] for s in scores) / groups_total if groups_total else 1.0
    precision = sum(s["attached_correct"] for s in scores) / attached_n if attached_n else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "n": n,
        "agent_acc": round(sum(s["agent_ok"] for s in scores) / n, 3),
        "skill_recall": round(recall, 3),
        "skill_precision": round(precision, 3),
        "skill_f1": round(f1, 3),
        "full_attach": round(sum(s["full"] for s in scores) / n, 3),
        "forbidden_hits": sum(len(s["forbidden_hit"]) for s in scores),
        "general_purpose": sum(s["agent"] == "general-purpose" for s in scores),
    }


def report(rows: list[dict], cases: list[dict], patterns: set[str]) -> dict:
    by_id = {c["id"]: c for c in cases}
    scores = [score_case(by_id[r["id"]], r.get("decision"), patterns) for r in rows if r["id"] in by_id]
    out = {"all": aggregate(scores)}
    for split in ("dev", "ood"):
        out[split] = aggregate([s for s in scores if s["split"] == split])
    out["misses"] = [
        {k: s[k] for k in ("id", "agent", "agent_ok", "attached", "groups_hit", "groups_total", "forbidden_hit")}
        for s in scores
        if not s["full"]
    ]
    return out


# ---------------------------------------------------------------- runners


def run_pre_route(request: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(request)
        path = fh.name
    try:
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "pre-route.py"), "--request-file", path, "--json-compact"],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=60,
            check=False,
        )
        return json.loads(proc.stdout)
    finally:
        Path(path).unlink(missing_ok=True)


DO_PROMPT = """You are executing the /do skill (its SKILL.md and the routing manifest are in your system prompt) for the
user request below. You cannot run tools: the manifest text is already provided, and PRE_ROUTE_RESULT is the output of
pre-route.py for this request. Do not execute the task. Apply Phases 1-3 exactly as SKILL.md instructs, then output
ONLY the JSON decision object you would pass to build-dispatch.py in Phase 4, restricted to these keys:
{"agent": ..., "agents": [...], "skill": ..., "pipeline": ..., "stack": [...]}
No prose, no code fences.

User request:
<request>
%s
</request>

PRE_ROUTE_RESULT:
%s
"""


def build_do_system_file(scratch: Path, case: dict) -> Path:
    """System prompt file for do-model: /do reads the manifest per request.

    The manifest is built with the request, as `get-routing-manifest.sh
    --request-file` does, so private entries appear only when the request names
    their domain.
    """
    text = (
        (REPO / "skills" / "meta" / "do" / "SKILL.md").read_text(encoding="utf-8")
        + "\n\n# Routing manifest (output of get-routing-manifest.sh)\n\n"
        + d_route_model.manifest_for(case["request"])
    )
    # Name by content: requests whose gated manifest is identical share one
    # file, so they share the prompt-cache prefix.
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    path = scratch / f"do-model-system-{digest}.md"
    path.write_text(text, encoding="utf-8")
    return path


def d_model_decision(route: dict) -> dict:
    """What /d dispatches: the finalized route, with `attach` as the stack."""
    return {
        "agent": route.get("agent"),
        "skill": route.get("skill"),
        "pipeline": route.get("pipeline"),
        "stack": list(route.get("attach") or []) or list(route.get("stack") or []),
        "agents": route.get("agents") or [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--router", choices=["d-prepare", "d-model", "do-model"])
    ap.add_argument("--split", default="all", choices=["all", "dev", "ood"])
    ap.add_argument("--out", type=Path, help="fresh results JSON path")
    ap.add_argument("--jev-results", type=Path, help="d-prepare results to reuse as JEV_RESULT for d-model")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--score", type=Path, help="score an existing results file and exit")
    args = ap.parse_args()

    catalog = load_catalog()
    cases = load_cases(args.split)
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    if args.score:
        rows = json.loads(args.score.read_text(encoding="utf-8"))["rows"]
        print(json.dumps(report(rows, cases, catalog["patterns"]), indent=1))
        return 0
    if not args.router or not args.out:
        ap.error("--router and --out are required unless --score is given")
    if args.out.exists():
        ap.error(f"{args.out} exists; give each run a fresh path")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # A stable working directory and system file keep the prompt-cache prefix
    # identical across runs, so repeat runs pay cache reads, not cache writes.
    scratch = Path(tempfile.gettempdir()) / "router-attachment-eval"
    scratch.mkdir(parents=True, exist_ok=True)

    jev_cache: dict[str, dict] = {}
    if args.jev_results:
        for row in json.loads(args.jev_results.read_text(encoding="utf-8"))["rows"]:
            jev_cache[row["id"]] = row["raw"]

    def one(case: dict) -> dict:
        started = time.monotonic()
        if args.router == "d-prepare":
            raw = d_route_model.prepare(case["request"])
            return {"id": case["id"], "raw": raw, "decision": None, "cost_usd": 0.0, "s": time.monotonic() - started}
        if args.router == "d-model":
            route = d_route_model.pick_route(
                case["request"], model=args.model, scratch=scratch, prepared=jev_cache.get(case["id"])
            )
            return {
                "usage": route["usage_model"],
                "id": case["id"],
                "raw": route["prepared"],
                "decision": d_model_decision(route),
                "problems": route["problems"],
                "cost_usd": route["cost_usd"],
                "text": route["decision_text"],
                "s": time.monotonic() - started,
            }
        raw = run_pre_route(case["request"])
        decision, cost, text, usage = d_route_model.call_model(
            build_do_system_file(scratch, case), DO_PROMPT % (case["request"], json.dumps(raw)), args.model, scratch
        )
        return {
            "usage": usage,
            "id": case["id"],
            "raw": raw,
            "decision": decision,
            "cost_usd": cost,
            "text": text[:2000] if decision is None else "",
            "s": time.monotonic() - started,
        }

    # Warm the prompt cache with one call before fanning out.
    rows = [one(cases[0])] if cases else []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        rows += list(pool.map(one, cases[1:]))

    result = {
        "router": args.router,
        "model": args.model if args.router != "d-prepare" else None,
        "split": args.split,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "rows": rows,
    }
    result["report"] = report(rows, cases, catalog["patterns"])
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    summary = {k: result["report"][k] for k in ("all", "dev", "ood")}
    print(json.dumps({"router": args.router, "cost_usd": result["cost_usd"], **summary}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
