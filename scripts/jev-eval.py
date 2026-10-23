#!/usr/bin/env python3
"""Eval driver: run scripts/routing-ab-corpus.json (274 cases) through the /d
route, live, and write scripts/routing-ab-results/<out-dir>/.

One case runs the production path: `jev-route.py` prepare (safety force route
and attachment evidence), a session-model pick (`scripts/d_route_model.py`,
`claude -p` reading /d's SKILL.md, /do's rule text, and the routing manifest),
then `jev-route.py` finalize.

Standing rules this eval follows (docs/router-ab-runbook.md): append-only
corpus, SAFETY_BUCKETS, deterministic exact-pair + `acceptable`-alternate
scoring. Scoring reuses routing-ab-test.py's own `route_correct()` rather
than inventing new matching semantics -- imported by file path since that
script has a hyphenated filename (not import-able by name).

A pick of `general-purpose` or no agent is tracked separately as
`gp_or_null`: it is the Agent-greediness gate's last resort, a different
failure mode from a confidently wrong pick.

Any SAFETY_BUCKETS case that is wrong OR whose `source` is not
"pre-route-force" is a CRITICAL finding: it means the deterministic guard in
pre-route.py failed to catch a case it exists to catch -- a real coverage
gap, not a pick-quality issue.

This is a real, reusable tool (not scratch) but a throwaway-shaped driver:
run it, read the VERDICT.md it writes, done. Give a new run its own
--out-dir; never overwrite a completed run.

Usage:
    python3 scripts/jev-eval.py --out-dir scripts/routing-ab-results/d-router-v3-2026-10-15
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = REPO_ROOT / "scripts" / "routing-ab-corpus.json"
# Historical context only -- NOT re-measured in this run (see VERDICT.md).
SELF_ROUTE_BASELINE_NOTE = (
    "57.6% (57/99, corpus v1.1, 2026-06-10, deterministic exact-pair gate, "
    "see scripts/routing-ab-results/self-route-v1/VERDICT.md)"
)

# Each case is one Jev evaluation plus one model call. Four workers keep a run
# well under the per-second Jev token limit and avoid 429/503 retries that skew
# latency. Price a bigger run first: python3 scripts/jev-budget-check.py --eval-cases N.
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = 6.5


def _load_ab_module():
    """Import routing-ab-test.py by file path (hyphenated filename)."""
    spec = importlib.util.spec_from_file_location("routing_ab_test", REPO_ROOT / "scripts" / "routing-ab-test.py")
    if spec is None or spec.loader is None:
        raise ImportError("could not load routing-ab-test.py by path")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AB = _load_ab_module()
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import d_route_model

JEV_ROUTE = d_route_model._load_jev_route()


def load_corpus() -> list[dict]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return data["test_cases"]


def load_corpus_version() -> str:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return str(data.get("version", "unknown"))


def case_split(case: dict) -> str:
    """Stable dev/test assignment from the request text: 60% dev, 40% test."""
    digest = hashlib.sha256(case["request"].encode("utf-8")).digest()
    return "dev" if digest[0] % 5 < 3 else "test"


def case_workload(case: dict) -> str | None:
    return (case.get("provenance") or {}).get("workload")


def run_d_route(case: dict, project: dict | None, timeout: float, model: str, scratch: Path) -> dict:
    """prepare -> session-model pick -> finalize for one case. Never raises: a failure
    becomes a harness-error row with no agent or skill."""
    try:
        return d_route_model.pick_route(case["request"], project, model, scratch)
    except Exception as exc:
        return {
            "source": "harness-error",
            "agent": None,
            "skill": None,
            "pipeline": None,
            "agents": [],
            "attach": [],
            "problems": [f"harness: {type(exc).__name__}: {str(exc)[:200]}"],
            "prepared": {},
            "cost_usd": 0.0,
        }


def is_correct_for_accuracy(case: dict, result: dict) -> bool:
    route = {"agent": result.get("agent"), "skill": result.get("skill"), "pipeline": result.get("pipeline")}
    return bool(AB.route_correct(case, route))


def is_gp_or_null(result: dict) -> bool:
    return result.get("agent") in (None, "general-purpose")


def run_eval(
    out_dir: Path,
    workers: int,
    timeout: float,
    model: str,
    limit: int | None = None,
    split: str | None = None,
    workload_dirs: dict[str, str] | None = None,
    only_workloads: bool = False,
) -> list[dict]:
    corpus = load_corpus()
    workload_dirs = workload_dirs or {}
    if split:
        corpus = [c for c in corpus if case_split(c) == split]
    if only_workloads:
        corpus = [c for c in corpus if case_workload(c) in workload_dirs]
    if limit:
        corpus = corpus[:limit]  # smoke run: price and wiring check before the full corpus
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.gettempdir()) / "d-route-eval"
    scratch.mkdir(parents=True, exist_ok=True)

    raw_rows: list[dict | None] = [None] * len(corpus)

    def _work(i: int, case: dict) -> tuple[int, dict]:
        cwd = workload_dirs.get(case_workload(case))
        project = JEV_ROUTE.detect_project_context(cwd) if cwd else None
        return i, run_d_route(case, project, timeout, model, scratch)

    def _record(i: int, result: dict) -> None:
        case = corpus[i]
        raw_rows[i] = {
            "case": case,
            "route": result,
            "correct": is_correct_for_accuracy(case, result),
            "bucket": case.get("bucket"),
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        done = 0
        if corpus:
            # The first case runs alone: it writes the shared prompt cache the others read.
            _record(*_work(0, corpus[0]))
            done = 1
        futures = [pool.submit(_work, i, case) for i, case in enumerate(corpus) if i > 0]
        for future in as_completed(futures):
            _record(*future.result())
            done += 1
            if done % 25 == 0 or done == len(corpus):
                print(f"[jev-eval] {done}/{len(corpus)} cases done", file=sys.stderr)

    rows = [r for r in raw_rows if r is not None]
    (out_dir / "raw.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[jev-eval] wrote {out_dir / 'raw.json'}", file=sys.stderr)
    return rows


def _pctl(data: list[float], p: float) -> float | None:
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(1 for r in rows if r["correct"])
    gp_rows = [r for r in rows if is_gp_or_null(r["route"])]

    buckets = sorted({r["bucket"] for r in rows})
    per_bucket = {}
    for bucket in buckets:
        bucket_rows = [r for r in rows if r["bucket"] == bucket]
        per_bucket[bucket] = {
            "n": len(bucket_rows),
            "correct": sum(1 for r in bucket_rows if r["correct"]),
            "gp_or_null": sum(1 for r in bucket_rows if is_gp_or_null(r["route"])),
        }

    # SAFETY_BUCKETS is not uniform: benchmark-force_route/paraphrase-git/
    # paraphrase-security are REQUIRED to force-route (pre-route.py exists to
    # catch them); false-positive-guard is FORBIDDEN from force-routing (its
    # cases are idiom traps that must fall through). routing-ab-test.py
    # already encodes this split as FAST_PATH_REQUIRED_BUCKETS /
    # FAST_PATH_FORBIDDEN_BUCKETS -- reuse it rather than treating all four
    # buckets as "must come from pre-route-force," which would flag a
    # correctly-resisted guard case as a false CRITICAL finding.
    forbidden_buckets = AB.FAST_PATH_FORBIDDEN_BUCKETS
    safety_rows = [r for r in rows if r["bucket"] in AB.SAFETY_BUCKETS]
    critical_findings = []
    for r in safety_rows:
        source = r["route"].get("source")
        bucket = r["bucket"]
        if bucket in forbidden_buckets:
            # The only guard-coverage failure here is force-routing to the
            # trap at all; a non-force-routed wrong pick is a pick-accuracy
            # issue, already counted in the per-bucket accuracy stats, not a
            # deterministic-guard coverage gap.
            is_critical = source == "pre-route-force"
        else:
            is_critical = (not r["correct"]) or (source != "pre-route-force")
        if is_critical:
            critical_findings.append(
                {
                    "request": r["case"]["request"],
                    "bucket": bucket,
                    "source": source,
                    "correct": r["correct"],
                    "agent": r["route"].get("agent"),
                    "skill": r["route"].get("skill"),
                }
            )
    safety_pass = len(critical_findings) == 0

    force_route_rows = [r for r in rows if r["route"].get("source") == "pre-route-force"]
    prepared = [r["route"].get("prepared") or {} for r in rows]
    jev_latencies = [float(p["latency_ms"]) for p in prepared if isinstance(p.get("latency_ms"), (int, float))]
    latency_stats = {
        "n": len(jev_latencies),
        "p50": _pctl(jev_latencies, 0.50),
        "p95": _pctl(jev_latencies, 0.95),
        "mean": statistics.mean(jev_latencies) if jev_latencies else None,
    }
    usages = [p["usage"] for p in prepared if isinstance(p.get("usage"), dict)]
    input_tokens = [u["input_tokens"] for u in usages]
    output_tokens = [u["output_tokens"] for u in usages]
    usage_stats = {
        "n_with_usage": len(usages),
        "mean_input_tokens": statistics.mean(input_tokens) if input_tokens else None,
        "mean_output_tokens": statistics.mean(output_tokens) if output_tokens else None,
    }
    costs = [float(r["route"].get("cost_usd") or 0.0) for r in rows]

    source_counts: dict[str, int] = {}
    for r in rows:
        src = str(r["route"].get("source"))
        source_counts[src] = source_counts.get(src, 0) + 1
    error_rate = source_counts.get("harness-error", 0) / n if n else 0.0

    return {
        "n": n,
        "correct": correct,
        "accuracy_pct": round(100.0 * correct / n, 1) if n else 0.0,
        "gp_or_null_count": len(gp_rows),
        "per_bucket": per_bucket,
        "safety_pass": safety_pass,
        "critical_findings": critical_findings,
        "force_route_count": len(force_route_rows),
        "source_counts": source_counts,
        "error_rate_pct": round(100.0 * error_rate, 1),
        "latency": latency_stats,
        "usage": usage_stats,
        "model_cost_usd_total": round(sum(costs), 4),
        "model_cost_usd_mean": round(statistics.mean(costs), 4) if costs else None,
    }


def write_verdict(out_dir: Path, summary: dict, corpus_version: str, model: str) -> None:
    buckets = sorted(summary["per_bucket"])
    lines = []
    lines.append(f"# /d Router Eval -- VERDICT (run: {out_dir.name})")
    lines.append("")
    lines.append(
        f"Live run of scripts/jev-eval.py against scripts/routing-ab-corpus.json "
        f"(v{corpus_version}, {summary['n']} cases). Each case ran `jev-route.py` prepare (pre-route.py's "
        "safety force route and one Jev evaluation of the attachment questions), a session-model pick "
        f"(`claude -p --model {model}` reading /d's SKILL.md, /do's rule text, and the routing manifest), "
        "and `jev-route.py --finalize`."
    )
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"- Accuracy: {summary['correct']}/{summary['n']} ({summary['accuracy_pct']}%)")
    lines.append(f"- General-purpose or no agent: {summary['gp_or_null_count']}/{summary['n']}")
    lines.append(
        f"- Source split: pre-route-force={summary['force_route_count']}, other={json.dumps(summary['source_counts'])}"
    )
    lines.append(f"- Harness error rate: {summary['error_rate_pct']}%")
    lines.append("")
    lines.append("## Per-bucket (correct/total, general-purpose or null count)")
    lines.append("")
    lines.append("| Bucket | n | correct | gp or null |")
    lines.append("|---|---|---|---|")
    for bucket in buckets:
        b = summary["per_bucket"][bucket]
        marker = " `*`" if bucket in AB.SAFETY_BUCKETS else ""
        lines.append(f"| {bucket}{marker} | {b['n']} | {b['correct']} | {b['gp_or_null']} |")
    lines.append("")
    lines.append("`*` = gate-protected safety bucket (SAFETY_BUCKETS).")
    lines.append("")
    lines.append("## SAFETY_BUCKETS critical callout (hard gate)")
    lines.append("")
    lines.append(
        "SAFETY_BUCKETS is not uniform. `benchmark-force_route`, `paraphrase-git`, `paraphrase-security` are "
        "REQUIRED to force-route (pre-route.py exists to catch them; CRITICAL = wrong OR "
        '`source != "pre-route-force"`). `false-positive-guard` is FORBIDDEN from force-routing -- its cases '
        'are idiom traps that must fall through (CRITICAL = `source == "pre-route-force"` only; a '
        "non-force-routed wrong pick there is a pick-accuracy issue, already in the per-bucket accuracy stats "
        "above, not a deterministic-guard coverage gap). This mirrors routing-ab-test.py's own "
        "FAST_PATH_REQUIRED_BUCKETS / FAST_PATH_FORBIDDEN_BUCKETS split."
    )
    lines.append("")
    if summary["safety_pass"]:
        lines.append(
            "**PASS.** Every REQUIRED safety-bucket case was correct and came from "
            '`source="pre-route-force"`, and no FORBIDDEN-bucket case force-routed to its trap -- the '
            "deterministic guard behaved correctly on every safety-critical case."
        )
    else:
        lines.append(
            f"**FAIL.** {len(summary['critical_findings'])} safety-bucket case(s) violated the rule above -- a "
            "real coverage gap in pre-route.py's deterministic guard, not a pick-quality issue:"
        )
        lines.append("")
        for finding in summary["critical_findings"]:
            lines.append(
                f"- [{finding['bucket']}] {finding['request']!r} -- source={finding['source']!r}, "
                f"correct={finding['correct']}, agent={finding['agent']!r}, skill={finding['skill']!r}"
            )
    lines.append("")
    lines.append("## Jev attachment call")
    lines.append("")
    lat = summary["latency"]
    lines.append(f"- Latency (n={lat['n']}): p50={lat['p50']} ms, p95={lat['p95']} ms, mean={lat['mean']} ms")
    usage = summary["usage"]
    lines.append(
        f"- Cases with usage reported: {usage['n_with_usage']}; mean input_tokens={usage['mean_input_tokens']}, "
        f"mean output_tokens={usage['mean_output_tokens']}"
    )
    lines.append("")
    lines.append("## Session-model pick cost")
    lines.append("")
    lines.append(
        f"- Total ${summary['model_cost_usd_total']}, mean ${summary['model_cost_usd_mean']} per case "
        "(`claude -p` total_cost_usd, prompt cache warm)"
    )
    lines.append("")
    lines.append("## Comparison to prior router work")
    lines.append("")
    lines.append(
        f"This run's accuracy ({summary['correct']}/{summary['n']}, corpus v{corpus_version}) is **not** a "
        "paired same-corpus comparison against self-route. The only documented self-route baseline is "
        f"{SELF_ROUTE_BASELINE_NOTE} -- cite it as historical context only, do not present it as re-measured "
        "in this run."
    )
    lines.append("")
    lines.append(
        "This VERDICT states measured facts only. Whether to ship `/d` is a decision for whoever writes the "
        "final comparison report; this document does not make that call."
    )
    lines.append("")
    (out_dir / "VERDICT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[jev-eval] wrote {out_dir / 'VERDICT.md'}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live eval: routing-ab-corpus.json through the /d route.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for raw.json and VERDICT.md (never reuse a completed run's directory).",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="ThreadPoolExecutor worker count.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-call Jev timeout (seconds).")
    parser.add_argument("--model", default=d_route_model.DEFAULT_MODEL, help="Model that plays the /d session.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases (smoke run).")
    parser.add_argument(
        "--split", choices=("dev", "test"), default=None, help="Run one split: tune on dev, report test."
    )
    parser.add_argument(
        "--workload-dir",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Repository directory for cases whose provenance.workload is NAME; its project facts go to the pick.",
    )
    parser.add_argument(
        "--only-workloads", action="store_true", help="Run only cases whose workload has a --workload-dir."
    )
    args = parser.parse_args()

    workload_dirs = dict(item.split("=", 1) for item in args.workload_dir if "=" in item)
    rows = run_eval(
        args.out_dir,
        args.workers,
        args.timeout,
        args.model,
        args.limit,
        args.split,
        workload_dirs,
        args.only_workloads,
    )
    summary = summarize(rows)
    write_verdict(args.out_dir, summary, load_corpus_version(), args.model)

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
