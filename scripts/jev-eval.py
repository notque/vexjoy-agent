#!/usr/bin/env python3
"""Eval driver: run scripts/routing-ab-corpus.json (v1.4, 269 cases) through
scripts/jev-route.py, live, and write scripts/routing-ab-results/<out-dir>/.

Standing rules this eval follows (docs/router-ab-runbook.md): append-only
corpus, SAFETY_BUCKETS, deterministic exact-pair + `acceptable`-alternate
scoring. Scoring reuses routing-ab-test.py's own `route_correct()` rather
than inventing new matching semantics — imported by file path since that
script has a hyphenated filename (not import-able by name).

A `fallback: true` jev-route.py result scores as incorrect for accuracy
purposes but is tracked separately as `fallback_rate`: Jev saying "I don't
know" is a different failure mode from Jev being confidently wrong.

Any SAFETY_BUCKETS case that is wrong OR whose `source` is not
"pre-route-force" is a CRITICAL finding: it means the deterministic guard in
pre-route.py failed to catch a case it exists to catch — a real coverage
gap, not a Jev quality issue.

This is a real, reusable tool (not scratch) but a throwaway-shaped driver:
run it, read the VERDICT.md it writes, done. Give a new run its own
--out-dir; never overwrite a completed run.

Usage:
    python3 scripts/jev-eval.py --out-dir scripts/routing-ab-results/jev-router-v1-2026-09-16
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = REPO_ROOT / "scripts" / "routing-ab-corpus.json"
JEV_ROUTE = REPO_ROOT / "scripts" / "jev-route.py"

# Measured this session: `wc -c ~/.claude/cache/routing-manifest.txt` (bytes)
# and a chars/4 token estimate — the baseline /do pays on every dispatch.
MANIFEST_BASELINE_BYTES = 62844
MANIFEST_BASELINE_TOKENS_APPROX = 15711

# Historical context only — NOT re-measured in this run (see VERDICT.md).
SELF_ROUTE_BASELINE_NOTE = (
    "57.6% (57/99, corpus v1.1, 2026-06-10, deterministic exact-pair gate, "
    "see scripts/routing-ab-results/self-route-v1/VERDICT.md)"
)

DEFAULT_WORKERS = 10
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


def run_jev_route(
    request: str,
    timeout: float,
    confidence_floor: float,
    cwd: str | None = None,
    route_args: list[str] | None = None,
) -> dict:
    """One subprocess call to jev-route.py. Never raises: a bad subprocess
    result is turned into a harness-error fallback row instead."""
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(JEV_ROUTE),
                "--request",
                request,
                "--json-compact",
                "--timeout",
                str(timeout),
                "--confidence-floor",
                str(confidence_floor),
                *(["--cwd", cwd] if cwd else []),
                *(route_args or []),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=timeout + 15,
            check=False,
        )
        return json.loads(proc.stdout)
    except Exception as exc:
        return {
            "available": False,
            "jev_called": False,
            "matched": False,
            "fallback": True,
            "fallback_reason": f"harness: jev-route.py subprocess failed: {type(exc).__name__}: {str(exc)[:200]}",
            "agent": None,
            "skill": None,
            "pipeline": None,
            "complexity": None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": "eval harness: subprocess failed or returned invalid JSON",
            "stack": [],
            "signals": None,
            "signal_scores": None,
            "source": "harness-error",
            "latency_ms": None,
            "usage": None,
        }


def is_correct_for_accuracy(case: dict, result: dict) -> bool:
    """A fallback result never counts as correct, regardless of its raw pick."""
    if result.get("fallback"):
        return False
    route = {"agent": result.get("agent"), "skill": result.get("skill")}
    return bool(AB.route_correct(case, route))


def run_eval(
    out_dir: Path,
    workers: int,
    timeout: float,
    confidence_floor: float,
    limit: int | None = None,
    split: str | None = None,
    workload_dirs: dict[str, str] | None = None,
    only_workloads: bool = False,
    route_args: list[str] | None = None,
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

    raw_rows: list[dict | None] = [None] * len(corpus)

    def _work(i: int, case: dict) -> tuple[int, dict]:
        return i, run_jev_route(
            case["request"], timeout, confidence_floor, workload_dirs.get(case_workload(case)), route_args
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_work, i, case) for i, case in enumerate(corpus)]
        for done, future in enumerate(as_completed(futures), start=1):
            i, result = future.result()
            case = corpus[i]
            correct = is_correct_for_accuracy(case, result)
            raw_rows[i] = {
                "case": case,
                "jev_result": result,
                "correct": correct,
                "bucket": case.get("bucket"),
            }
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


def _latency_total_ms(latency_ms: object) -> float | None:
    """Normalize jev-route.py's `latency_ms` field across router versions.

    v1 reported a flat float (one HTTP call). v2's two-stage design reports
    `{"stage1_ms", "stage2_ms", "total_ms"}` -- the combined real latency of
    both round trips. Accept either shape so this eval driver keeps working
    unmodified against future latency-shape changes, as long as they add a
    `total_ms` key or stay a flat number.
    """
    if isinstance(latency_ms, dict):
        total = latency_ms.get("total_ms")
        return float(total) if isinstance(total, (int, float)) else None
    if isinstance(latency_ms, (int, float)):
        return float(latency_ms)
    return None


def _usage_totals(usage: object) -> tuple[int, int] | None:
    """Normalize jev-route.py's `usage` field across router versions.

    v1 reported one flat `{input_tokens, output_tokens}` dict (one HTTP
    call). v2 reports `{"stage1": {...} | None, "stage2": {...} | None}` --
    itemized per round trip, summed here for a single comparable total.
    """
    if not isinstance(usage, dict):
        return None
    if "input_tokens" in usage and "output_tokens" in usage:
        in_tok, out_tok = usage.get("input_tokens"), usage.get("output_tokens")
        if isinstance(in_tok, int) and isinstance(out_tok, int):
            return in_tok, out_tok
        return None
    legs = [v for v in (usage.get("stage1"), usage.get("stage2")) if isinstance(v, dict)]
    if not legs:
        return None
    in_tok = sum(int(leg.get("input_tokens", 0)) for leg in legs)
    out_tok = sum(int(leg.get("output_tokens", 0)) for leg in legs)
    return in_tok, out_tok


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(1 for r in rows if r["correct"])
    fallback_rows = [r for r in rows if r["jev_result"].get("fallback")]
    fallback_rate = len(fallback_rows) / n if n else 0.0

    buckets = sorted({r["bucket"] for r in rows})
    per_bucket = {}
    for bucket in buckets:
        bucket_rows = [r for r in rows if r["bucket"] == bucket]
        per_bucket[bucket] = {
            "n": len(bucket_rows),
            "correct": sum(1 for r in bucket_rows if r["correct"]),
            "fallback": sum(1 for r in bucket_rows if r["jev_result"].get("fallback")),
        }

    # SAFETY_BUCKETS is not uniform: benchmark-force_route/paraphrase-git/
    # paraphrase-security are REQUIRED to force-route (pre-route.py exists to
    # catch them); false-positive-guard is FORBIDDEN from force-routing (its
    # cases are idiom traps that must fall through). routing-ab-test.py
    # already encodes this split as FAST_PATH_REQUIRED_BUCKETS /
    # FAST_PATH_FORBIDDEN_BUCKETS — reuse it rather than treating all four
    # buckets as "must come from pre-route-force," which would flag a
    # correctly-resisted guard case as a false CRITICAL finding.
    required_buckets = AB.FAST_PATH_REQUIRED_BUCKETS
    forbidden_buckets = AB.FAST_PATH_FORBIDDEN_BUCKETS
    safety_rows = [r for r in rows if r["bucket"] in AB.SAFETY_BUCKETS]
    critical_findings = []
    for r in safety_rows:
        source = r["jev_result"].get("source")
        bucket = r["bucket"]
        if bucket in forbidden_buckets:
            # The only guard-coverage failure here is force-routing to the
            # trap at all; a non-force-routed wrong pick is a Jev accuracy
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
                    "agent": r["jev_result"].get("agent"),
                    "skill": r["jev_result"].get("skill"),
                }
            )
    safety_pass = len(critical_findings) == 0

    force_route_rows = [r for r in rows if r["jev_result"].get("source") == "pre-route-force"]
    jev_rows = [r for r in rows if r["jev_result"].get("source") == "jev"]
    jev_called_latencies = [
        v
        for r in rows
        if r["jev_result"].get("jev_called")
        for v in [_latency_total_ms(r["jev_result"].get("latency_ms"))]
        if v is not None
    ]
    latency_stats = {
        "n": len(jev_called_latencies),
        "p50": _pctl(jev_called_latencies, 0.50),
        "p95": _pctl(jev_called_latencies, 0.95),
        "mean": statistics.mean(jev_called_latencies) if jev_called_latencies else None,
    }

    input_tokens = []
    output_tokens = []
    for r in rows:
        totals = _usage_totals(r["jev_result"].get("usage"))
        if totals is None:
            continue
        input_tokens.append(totals[0])
        output_tokens.append(totals[1])
    usage_stats = {
        "n_with_usage": len(input_tokens),
        "mean_input_tokens": statistics.mean(input_tokens) if input_tokens else None,
        "mean_output_tokens": statistics.mean(output_tokens) if output_tokens else None,
    }

    sizes = [len(json.dumps(r["jev_result"], separators=(",", ":"))) for r in rows]
    median_size = statistics.median(sizes) if sizes else 0
    size_ratio = median_size / MANIFEST_BASELINE_BYTES if MANIFEST_BASELINE_BYTES else None

    source_counts: dict[str, int] = {}
    for r in rows:
        src = str(r["jev_result"].get("source"))
        source_counts[src] = source_counts.get(src, 0) + 1
    error_rate = (source_counts.get("error", 0) + source_counts.get("harness-error", 0)) / n if n else 0.0

    return {
        "n": n,
        "correct": correct,
        "accuracy_pct": round(100.0 * correct / n, 1) if n else 0.0,
        "fallback_count": len(fallback_rows),
        "fallback_rate_pct": round(100.0 * fallback_rate, 1),
        "per_bucket": per_bucket,
        "safety_pass": safety_pass,
        "critical_findings": critical_findings,
        "force_route_count": len(force_route_rows),
        "jev_source_count": len(jev_rows),
        "source_counts": source_counts,
        "error_rate_pct": round(100.0 * error_rate, 1),
        "latency": latency_stats,
        "usage": usage_stats,
        "median_decision_bytes": median_size,
        "manifest_baseline_bytes": MANIFEST_BASELINE_BYTES,
        "manifest_baseline_tokens_approx": MANIFEST_BASELINE_TOKENS_APPROX,
        "size_ratio_vs_manifest": size_ratio,
    }


def write_verdict(out_dir: Path, summary: dict, corpus_version: str) -> None:
    buckets = sorted(summary["per_bucket"])
    lines = []
    lines.append(f"# Jev Router Eval — VERDICT (run: {out_dir.name})")
    lines.append("")
    lines.append(
        f"Date: 2026-09-16. Live run of scripts/jev-eval.py against scripts/routing-ab-corpus.json "
        f"(v{corpus_version}, {summary['n']} cases) through scripts/jev-route.py: pre-route.py's deterministic "
        "force-route guard runs first (never overridden by Jev), then -- for non-force-routed, non-trivial "
        "requests -- TypeSafe's Jev classifier (`jev-latest`) answers the routing decision via jev-route.py's "
        "current call design (see its module docstring for the exact stage-by-stage shape and round-trip count "
        "this run used)."
    )
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"- Accuracy: {summary['correct']}/{summary['n']} ({summary['accuracy_pct']}%)")
    lines.append(f"- Fallback rate: {summary['fallback_count']}/{summary['n']} ({summary['fallback_rate_pct']}%)")
    lines.append(
        f"- Source split: pre-route-force={summary['force_route_count']}, jev={summary['jev_source_count']}, "
        f"other={json.dumps(summary['source_counts'])}"
    )
    lines.append(f"- Error rate (source=error or harness-error): {summary['error_rate_pct']}%")
    lines.append("")
    lines.append("## Per-bucket (correct/total, fallback count)")
    lines.append("")
    lines.append("| Bucket | n | correct | fallback |")
    lines.append("|---|---|---|---|")
    for bucket in buckets:
        b = summary["per_bucket"][bucket]
        marker = " `*`" if bucket in AB.SAFETY_BUCKETS else ""
        lines.append(f"| {bucket}{marker} | {b['n']} | {b['correct']} | {b['fallback']} |")
    lines.append("")
    lines.append("`*` = gate-protected safety bucket (SAFETY_BUCKETS).")
    lines.append("")
    lines.append("## SAFETY_BUCKETS critical callout (hard gate)")
    lines.append("")
    lines.append(
        "SAFETY_BUCKETS is not uniform. `benchmark-force_route`, `paraphrase-git`, `paraphrase-security` are "
        "REQUIRED to force-route (pre-route.py exists to catch them; CRITICAL = wrong OR "
        '`source != "pre-route-force"`). `false-positive-guard` is FORBIDDEN from force-routing — its cases '
        'are idiom traps that must fall through (CRITICAL = `source == "pre-route-force"` only; a '
        "non-force-routed wrong pick there is a Jev accuracy issue, already in the per-bucket accuracy stats "
        "above, not a deterministic-guard coverage gap). This mirrors routing-ab-test.py's own "
        "FAST_PATH_REQUIRED_BUCKETS / FAST_PATH_FORBIDDEN_BUCKETS split."
    )
    lines.append("")
    if summary["safety_pass"]:
        lines.append(
            "**PASS.** Every REQUIRED safety-bucket case was correct and came from "
            '`source="pre-route-force"`, and no FORBIDDEN-bucket case force-routed to its trap — the '
            "deterministic guard behaved correctly on every safety-critical case."
        )
    else:
        lines.append(
            f"**FAIL.** {len(summary['critical_findings'])} safety-bucket case(s) violated the rule above — a "
            "real coverage gap in pre-route.py's deterministic guard, not a Jev quality issue:"
        )
        lines.append("")
        for finding in summary["critical_findings"]:
            lines.append(
                f"- [{finding['bucket']}] {finding['request']!r} — source={finding['source']!r}, "
                f"correct={finding['correct']}, agent={finding['agent']!r}, skill={finding['skill']!r}"
            )
    lines.append("")
    lines.append("## Latency")
    lines.append("")
    lat = summary["latency"]
    lines.append(f"- Jev-called cases (n={lat['n']}): p50={lat['p50']} ms, p95={lat['p95']} ms, mean={lat['mean']} ms")
    lines.append(
        f"- Force-route-instant (zero latency, no Jev call): {summary['force_route_count']}/{summary['n']} cases"
    )
    lines.append(f"- Jev-called: {summary['jev_source_count']}/{summary['n']} cases")
    lines.append("")
    lines.append("## Token usage (Jev-reported, where present)")
    lines.append("")
    usage = summary["usage"]
    lines.append(
        f"- Cases with usage reported: {usage['n_with_usage']}; mean input_tokens={usage['mean_input_tokens']}, "
        f"mean output_tokens={usage['mean_output_tokens']}"
    )
    lines.append("")
    lines.append("## Decision size vs. the /do manifest baseline")
    lines.append("")
    lines.append(f"- Median jev-route.py decision JSON: {summary['median_decision_bytes']} bytes")
    lines.append(
        f"- Baseline /do routing manifest (measured this session): {summary['manifest_baseline_bytes']} bytes "
        f"(~{summary['manifest_baseline_tokens_approx']} tokens), read into the orchestrator's context on "
        "every dispatch"
    )
    ratio = summary["size_ratio_vs_manifest"]
    ratio_pct = round(100.0 * ratio, 2) if ratio is not None else None
    lines.append(
        f"- Ratio: the median decision is {ratio_pct}% of the manifest baseline's byte size "
        f"({'~1/' + str(round(1 / ratio)) if ratio else 'n/a'} the size)"
    )
    lines.append("")
    lines.append("## Comparison to prior router work")
    lines.append("")
    lines.append(
        f"This run's accuracy ({summary['correct']}/{summary['n']}, corpus v{corpus_version}) is **not** a "
        "paired same-corpus comparison against self-route. The only documented self-route baseline is "
        f"{SELF_ROUTE_BASELINE_NOTE} — cite it as historical context only, do not present it as re-measured "
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
    parser = argparse.ArgumentParser(description="Live eval: routing-ab-corpus.json through jev-route.py.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for raw.json and VERDICT.md (never reuse a completed run's directory).",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="ThreadPoolExecutor worker count.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-call Jev timeout (seconds).")
    parser.add_argument(
        "--confidence-floor", type=float, default=0.7, help="Confidence floor passed through to jev-route.py."
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases (smoke run).")
    parser.add_argument(
        "--split", choices=("dev", "test"), default=None, help="Run one split: tune on dev, report test."
    )
    parser.add_argument(
        "--workload-dir",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Repository directory for cases whose provenance.workload is NAME; passed to the router as --cwd.",
    )
    parser.add_argument(
        "--route-arg",
        action="append",
        default=[],
        help="Extra argument passed through to jev-route.py (repeatable), e.g. --route-arg=--shortlist --route-arg=6.",
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
        args.confidence_floor,
        args.limit,
        args.split,
        workload_dirs,
        args.only_workloads,
        args.route_arg,
    )
    summary = summarize(rows)
    write_verdict(args.out_dir, summary, load_corpus_version())

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
