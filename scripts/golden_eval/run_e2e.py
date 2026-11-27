#!/usr/bin/env python3
"""End-to-end golden eval: full `/do` and `/d` sessions on the e2e tasks.

Built, not launched by default. Each e2e task in tasks.json runs `--runs`
times per router as a real `claude -p "/<router> <request>"` session in a
disposable copy of fixture/ (its own git repo, no remote), with its own
CLAUDE_LEARNING_DIR and receipt dir so the owner's telemetry is untouched.

Per session it records, with wall-clock timestamps per stream event for replay:
- Skill tool calls (did the session load the routed skill: the article's
  skill-load metric), Agent tool calls and their subagent types (main vs dispatch)
- the final reply, cost, and duration
- acceptance checks from tasks.json (commands in the run dir, reply regexes)
- a rubric grade of the final reply by `claude -p --model <grader>` (pass per criterion)

The sessions load the INSTALLED skills (~/.claude/skills/d, ~/.claude/scripts).
The runner refuses unless the installed /d SKILL.md and d_gate.py match this
checkout (install this branch first), and refuses without `--launch`.

Usage:
  nice -n 10 python3 scripts/golden_eval/run_e2e.py --out-dir <fresh dir> --runs 2 --launch
  python3 scripts/golden_eval/run_e2e.py --estimate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FIXTURE = HERE / "fixture"
TASKS = HERE / "tasks.json"
ROUTERS = ("d", "do")
SESSION_TIMEOUT_S = 1800
# Tools a session may use. No push, no gh, no web: the fixture has no remote
# and the tasks need none.
ALLOWED_TOOLS = (
    "Read Edit Write Glob Grep Skill Agent "
    "Bash(python3:*) Bash(bash:*) Bash(git status:*) Bash(git diff:*) Bash(git log:*) Bash(git add:*) "
    "Bash(git commit:*) Bash(git show:*) Bash(mktemp:*) Bash(printf:*) Bash(cat:*) Bash(rm -f:*) Bash(ls:*)"
)
DISALLOWED_TOOLS = "Bash(git push:*) Bash(gh:*) WebFetch WebSearch"
# Planning numbers for --estimate, from the routing-level run (opus, cache warm)
# and Jev prepare usage. Session cost is a guess per complexity, not a measure.
EST_SESSION_USD = {"low": 0.8, "high": 3.0}
EST_GRADE_USD = 0.06
EST_JEV_TOKENS_PER_D_SESSION = 3_000  # prepare ~1k + intent alignment ~2k


def load_tasks() -> list[dict]:
    return [t for t in json.loads(TASKS.read_text(encoding="utf-8"))["tasks"] if t.get("e2e")]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def install_matches() -> list[str]:
    """Files whose installed copy differs from this checkout (empty = sessions test this branch)."""
    home = Path.home() / ".claude"
    pairs = [
        (REPO / "skills" / "meta" / "d" / "SKILL.md", home / "skills" / "d" / "SKILL.md"),
        (REPO / "scripts" / "d_gate.py", home / "scripts" / "d_gate.py"),
        (REPO / "scripts" / "build-dispatch.py", home / "scripts" / "build-dispatch.py"),
    ]
    return [str(installed) for ours, installed in pairs if _sha(ours) != _sha(installed)]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_workdir(task: dict, base: Path) -> Path:
    work = base / "repo"
    shutil.copytree(FIXTURE, work)
    _git(work, "init", "-q", "-b", "main")
    _git(work, "-c", "user.email=eval@localhost", "-c", "user.name=eval", "add", "-A")
    _git(work, "-c", "user.email=eval@localhost", "-c", "user.name=eval", "commit", "-q", "-m", "fixture")
    setup = task.get("setup")
    if setup:
        _git(work, "checkout", "-q", "-b", setup["branch"])
        for rel, text in setup["write"].items():
            (work / rel).write_text(text, encoding="utf-8")
        _git(work, "-c", "user.email=eval@localhost", "-c", "user.name=eval", "add", "-A")
        _git(work, "-c", "user.email=eval@localhost", "-c", "user.name=eval", "commit", "-q", "-m", setup["message"])
    return work


def run_session(router: str, request: str, work: Path, env: dict, model: str) -> dict:
    cmd = [
        "claude",
        "-p",
        f"/{router} {request}",
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--disallowedTools",
        DISALLOWED_TOOLS,
    ]
    events: list[dict] = []
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    def _kill_on_timeout() -> None:
        try:
            if proc.poll() is None:
                proc.kill()
        except OSError:
            pass

    timer = threading.Timer(SESSION_TIMEOUT_S, _kill_on_timeout)
    timer.daemon = True
    timer.start()
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                events.append({"t": _now(), "e": json.loads(line)})
            except ValueError:
                continue
            if time.monotonic() - started > SESSION_TIMEOUT_S:
                proc.kill()
                break
        proc.wait(timeout=60)
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
    return {"events": events, "seconds": round(time.monotonic() - started, 1), "exit": proc.returncode}


def tool_uses(events: list[dict]) -> list[dict]:
    """Every tool_use block in assistant messages, in order, with its event time."""
    out = []
    for item in events:
        msg = item["e"].get("message") if item["e"].get("type") == "assistant" else None
        for block in (msg or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                out.append({"t": item["t"], "name": block.get("name"), "input": block.get("input") or {}})
    return out


def final_result(events: list[dict]) -> dict:
    for item in reversed(events):
        if item["e"].get("type") == "result":
            return item["e"]
    return {}


def check_acceptance(task: dict, work: Path, reply: str) -> list[dict]:
    results = []
    for check in task.get("acceptance") or []:
        if "reply_regex" in check:
            ok = re.search(check["reply_regex"], reply or "") is not None
            results.append({"check": check, "ok": ok})
            continue
        # Commands come from the checked-in tasks.json, never from session output.
        proc = subprocess.run(
            ["bash", "-c", check["cmd"]], cwd=work, capture_output=True, text=True, timeout=300, check=False
        )
        ok = True
        if "expect_exit" in check:
            ok = proc.returncode == check["expect_exit"]
        if ok and "expect_regex" in check:
            ok = re.search(check["expect_regex"], proc.stdout.strip(), re.M) is not None
        results.append({"check": check, "ok": ok, "exit": proc.returncode, "stdout": proc.stdout[-400:]})
    return results


GRADE_PROMPT = """Grade the final answer of an AI coding session against each rubric criterion.
Return ONLY a JSON object {"criteria": [{"criterion": "...", "pass": true|false, "why": "<one short sentence>"}]}.

Task request:
%s

Rubric:
%s

Files changed (git diff --stat against the fixture commit):
%s

Final answer:
<answer>
%s
</answer>
"""


def grade(task: dict, reply: str, diffstat: str, model: str, cwd: Path) -> dict:
    rubric = "\n".join(f"- {c}" for c in task.get("rubric") or [])
    prompt = GRADE_PROMPT % (task["request"], rubric, diffstat or "(none)", (reply or "")[:20000])
    proc = subprocess.run(
        ["claude", "-p", "--model", model, "--tools", "", "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=600,
        check=False,
    )
    try:
        outer = json.loads(proc.stdout)
        text = outer.get("result") or ""
        parsed = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        crit = parsed.get("criteria") or []
        return {
            "criteria": crit,
            "passed": sum(1 for c in crit if c.get("pass") is True),
            "total": len(task.get("rubric") or []),
            "cost_usd": float(outer.get("total_cost_usd") or 0.0),
        }
    except (ValueError, AttributeError):
        return {"criteria": [], "passed": 0, "total": len(task.get("rubric") or []), "error": proc.stdout[-300:]}


def run_one(task: dict, router: str, run: int, out_dir: Path, model: str, grader: str) -> dict:
    base = Path(tempfile.mkdtemp(prefix=f"golden-e2e-{task['id']}-{router}-{run}-"))
    try:
        work = make_workdir(task, base)
        env = dict(os.environ)
        env.pop("CLAUDECODE", None)
        env["CLAUDE_LEARNING_DIR"] = str(base / "learning")
        env["VEXJOY_D_RECEIPT_DIR"] = str(base / "receipts")
        started = _now()
        session = run_session(router, task["request"], work, env, model)
        uses = tool_uses(session["events"])
        result = final_result(session["events"])
        reply = result.get("result") or ""
        diffstat = subprocess.run(
            ["git", "diff", "--stat", "HEAD"], cwd=work, capture_output=True, text=True, check=False
        ).stdout
        row = {
            "id": task["id"],
            "router": router,
            "run": run,
            "started": started,
            "ended": _now(),
            "seconds": session["seconds"],
            "exit": session["exit"],
            "cost_usd": result.get("total_cost_usd"),
            "num_turns": result.get("num_turns"),
            "skill_calls": [{"t": u["t"], "skill": u["input"].get("skill")} for u in uses if u["name"] == "Skill"],
            "agent_calls": [
                {"t": u["t"], "subagent_type": u["input"].get("subagent_type"), "model": u["input"].get("model")}
                for u in uses
                if u["name"] in ("Agent", "Task")
            ],
            "expected_skills": task.get("skill") or [],
            "acceptance": check_acceptance(task, work, reply),
            "grade": grade(task, reply, diffstat, grader, base),
            "reply": reply[:8000],
        }
        called = {str(c["skill"] or "").split(":")[-1] for c in row["skill_calls"]}
        row["skill_loaded"] = bool(called & set(task.get("skill") or [])) if task.get("skill") else None
        (out_dir / "events").mkdir(exist_ok=True)
        route_events = base / "learning" / "route-events.jsonl"
        if route_events.is_file():  # the session's own routing telemetry, kept for router-metrics.py
            shutil.copyfile(route_events, out_dir / "events" / f"{task['id']}-{router}-{run}.route-events.jsonl")
        (out_dir / "events" / f"{task['id']}-{router}-{run}.jsonl").write_text(
            "\n".join(json.dumps(e) for e in session["events"]), encoding="utf-8"
        )
        return row
    finally:
        shutil.rmtree(base, ignore_errors=True)


def summarize(rows: list[dict]) -> dict:
    out = {}
    for router in ROUTERS:
        rs = [r for r in rows if r["router"] == router]
        if not rs:
            continue
        # A worker's Skill calls are not in the parent stream, so a dispatching
        # session's skill load is a lower bound: report the two groups apart.
        main_only = [r["skill_loaded"] for r in rs if r["skill_loaded"] is not None and not r["agent_calls"]]
        dispatching = [r["skill_loaded"] for r in rs if r["skill_loaded"] is not None and r["agent_calls"]]
        out[router] = {
            "sessions": len(rs),
            "skill_loaded_main_only_sessions": f"{sum(main_only)}/{len(main_only)}",
            "skill_loaded_dispatching_sessions_lower_bound": f"{sum(dispatching)}/{len(dispatching)}",
            "acceptance_all_pass": sum(all(c["ok"] for c in r["acceptance"]) for r in rs),
            "rubric_passed": f"{sum(r['grade']['passed'] for r in rs)}/{sum(r['grade']['total'] for r in rs)}",
            "dispatching_sessions": sum(1 for r in rs if r["agent_calls"]),
            "agent_calls": sum(len(r["agent_calls"]) for r in rs),
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rs), 2),
            "median_seconds": sorted(r["seconds"] for r in rs)[len(rs) // 2],
        }
    return out


def estimate(runs: int) -> dict:
    sessions = len(load_tasks()) * len(ROUTERS) * runs
    d_sessions = len(load_tasks()) * runs
    return {
        "sessions": sessions,
        "session_usd_range": [
            round(sessions * EST_SESSION_USD["low"], 2),
            round(sessions * EST_SESSION_USD["high"], 2),
        ],
        "grading_usd": round(sessions * EST_GRADE_USD, 2),
        "jev_tokens": d_sessions * EST_JEV_TOKENS_PER_D_SESSION,
        "wall_clock_minutes_at_4_parallel": [round(sessions * 3 / 4), round(sessions * 10 / 4)],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--grader", default="opus")
    ap.add_argument("--workers", type=int, default=2, help="parallel sessions (max 4)")
    ap.add_argument("--only", default="")
    ap.add_argument("--launch", action="store_true", help="required: start real sessions")
    ap.add_argument("--allow-install-mismatch", action="store_true")
    ap.add_argument("--estimate", action="store_true", help="print the cost estimate and exit")
    args = ap.parse_args(argv)
    if args.estimate:
        print(json.dumps(estimate(args.runs), indent=1))
        return 0
    if not args.launch or not args.out_dir:
        ap.error("--out-dir and --launch are required to start sessions (see --estimate first)")
    mismatched = install_matches()
    if mismatched and not args.allow_install_mismatch:
        print("installed copies differ from this checkout; install this branch first:\n  " + "\n  ".join(mismatched))
        return 2
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        ap.error(f"{args.out_dir} is not empty; give each run a fresh directory")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    if args.only:
        tasks = [t for t in tasks if t["id"] in set(args.only.split(","))]
    jobs = [(t, r, n) for n in range(1, args.runs + 1) for t in tasks for r in ROUTERS]
    with ThreadPoolExecutor(max_workers=max(1, min(4, args.workers))) as pool:
        rows = list(pool.map(lambda j: run_one(j[0], j[1], j[2], args.out_dir, args.model, args.grader), jobs))
    (args.out_dir / "rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    summary = summarize(rows)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
