#!/usr/bin/env python3
"""Price a Jev program's run against the documented limits before sending it.

Checks per request (64k tokens; 32k state + longest question) AND per run and
per second (250k tokens/s; 1,200 requests/min). A design can pass every
per-request check and still fail in production because one run spends the
whole per-second limit; this script catches that.

Input: a JSON file holding everything one run sends, in any of these shapes:
  {"state": ..., "questions": {...}}              one request
  [{"state": ..., "questions": {...}}, ...]        many requests
  {"requests": [{"state": ..., "questions": ...}]}

Dump it from the program's own request builder, so what ships is what is
priced. Exit code: 0 ok, 1 warn (over 25% of a limit, or a design smell),
2 fail (over a documented limit).

Usage:
  python3 scripts/jev-budget-check.py --payload run.json --concurrency 8 \
      --concurrent-runs 3 --attempts 3 [--latency 0.35] [--measured-tokens N] \
      [--eval-cases 81] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jev_limits


def load_requests(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "requests" in data:
        data = data["requests"]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(r, dict) and "questions" in r for r in data):
        raise ValueError("payload must be a request, a list of requests, or {'requests': [...]}, each with 'questions'")
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--payload", type=Path, required=True, help="JSON of every request one run sends")
    p.add_argument("--concurrency", type=int, default=None, help="requests in flight at once (default: all)")
    p.add_argument(
        "--latency",
        type=float,
        default=jev_limits.TYPICAL_LATENCY_S,
        help="seconds per request on the production transport",
    )
    p.add_argument("--concurrent-runs", type=int, default=1, help="users or jobs that can run at the same time")
    p.add_argument("--attempts", type=int, default=1, help="worst-case attempts per request (1 + retries)")
    p.add_argument("--runs-per-minute", type=float, default=1.0, help="sustained runs per minute")
    p.add_argument("--measured-tokens", type=int, default=None, help="billed input tokens for one run, if measured")
    p.add_argument("--eval-cases", type=int, default=0, help="price an eval of this many runs")
    p.add_argument("--json", action="store_true", help="print JSON")
    a = p.parse_args(argv)
    try:
        result = jev_limits.check_run(
            load_requests(a.payload),
            concurrency=a.concurrency,
            latency_s=a.latency,
            concurrent_runs=a.concurrent_runs,
            attempts=a.attempts,
            runs_per_minute=a.runs_per_minute,
            measured_tokens_per_run=a.measured_tokens,
            eval_cases=a.eval_cases,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"jev-budget-check: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"verdict: {result['verdict'].upper()}")
        print(
            f"requests/run {result['requests']} in {result['waves']} wave(s) of {result['concurrency']}; "
            f"~{result['tokens_per_run']:,} tokens/run; largest request ~{result['largest_request_tokens']:,}"
        )
        print(
            f"peak ~{result['peak_tokens_per_second']:,} tokens/s (with retries ~{result['peak_tokens_per_second_with_retries']:,}); "
            f"~{result['requests_per_minute']:,} requests/min; limits {jev_limits.TOKENS_PER_SECOND_LIMIT:,} tokens/s, "
            f"{jev_limits.REQUESTS_PER_MINUTE_LIMIT:,} requests/min"
        )
        if "eval" in result:
            e = result["eval"]
            print(
                f"eval of {e['cases']} runs: ~{e['tokens']:,} tokens; pace at least {e['min_seconds_between_cases']} s between runs"
            )
        for f in result["findings"]:
            print(f"  {f['level'].upper()}: {f['message']}")
    return {"ok": 0, "warn": 1, "fail": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
