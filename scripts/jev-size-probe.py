#!/usr/bin/env python3
"""Measure Jev's transient failure rate against request size on the production transport.

Why: a request far under the documented 64k-token limit can still fail
transiently, and through Vercel AI Gateway the fast-503 rate grew with input
tokens per request (2026-09-22: ~1.6k tokens 0/8, ~3k ~1/8, ~5k 3/8, ~13k 5/8).
A retry resends the whole request, so the right request size comes from this
curve, not from the limit.

Method: pick up to --variants real requests spread across sizes, add a tiny
one-question control, and send them round-robin, one at a time, retries and
cache off, for --rounds rounds. Round-robin puts every variant in the same
time windows, so drift in service health cannot pose as a size effect.

Input: the same payload shapes as jev-budget-check.py (one request, a list, or
{"requests": [...]}). Output: failures per variant, billed tokens, and the
request size with the fewest tokens per successful answer. Costs roughly
rounds x the sum of the variants' tokens; the default is well under 1M tokens.

Usage:
  python3 scripts/jev-size-probe.py --payload run.json [--rounds 10] [--variants 4] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jev_limits

CONTROL = {
    "state": {"items": ["payroll", "invoice", "banana", "warehouse"]},
    "questions": {
        "q0": {"type": "noul", "instructions": "Is the first entry in `items` a kind of enterprise software?"}
    },
}
# A size whose failure rate is at or under this counts as "reliable" in the report.
RELIABLE_FAILURE_RATE = 0.125


def load_requests(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "requests" in data:
        data = data["requests"]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(r, dict) and "questions" in r for r in data):
        raise ValueError("payload must be a request, a list of requests, or {'requests': [...]}, each with 'questions'")
    return data


def pick_variants(requests: list[dict], count: int) -> list[dict]:
    """Up to `count` requests spread evenly from smallest to largest estimated size."""
    ranked = sorted(requests, key=lambda r: jev_limits.request_tokens(r.get("state"), r["questions"])["total"])
    if len(ranked) <= count:
        return ranked
    step = (len(ranked) - 1) / (count - 1)
    return [ranked[round(i * step)] for i in range(count)]


def status_of(exc: BaseException) -> str:
    """HTTP status from a transport error when one is present, else the error class. Never the message body."""
    for source in (getattr(exc, "code", None), getattr(exc, "status", None)):
        if isinstance(source, int):
            return str(source)
    telemetry = getattr(exc, "telemetry", None) or {}
    for receipt in telemetry.get("receipts", []) if isinstance(telemetry, dict) else []:
        if isinstance(receipt, dict) and isinstance(receipt.get("status"), int):
            return str(receipt["status"])
    match = re.search(r"\b(4\d\d|5\d\d)\b", str(exc))
    return match.group(1) if match else type(exc).__name__


def probe(variants: list[dict], send: Callable[[dict], int | None], rounds: int, pause_s: float = 0.0) -> list[dict]:
    """Round-robin `variants`, one request at a time. `send` returns billed input tokens or raises."""
    rows = [
        {
            "estimated_tokens": jev_limits.request_tokens(v.get("state"), v["questions"])["total"],
            "questions": len(v["questions"]),
            "ok": 0,
            "failed": 0,
            "statuses": {},
            "billed_tokens": None,
            "ms": [],
        }
        for v in variants
    ]
    for _ in range(rounds):
        for variant, row in zip(variants, rows, strict=True):
            started = time.monotonic()
            try:
                billed = send(variant)
                row["ok"] += 1
                row["ms"].append(round((time.monotonic() - started) * 1000))
                if billed:
                    row["billed_tokens"] = billed
            except Exception as exc:  # every failure is data here
                row["failed"] += 1
                key = status_of(exc)
                row["statuses"][key] = row["statuses"].get(key, 0) + 1
            if pause_s:
                time.sleep(pause_s)
    for row in rows:
        total = row["ok"] + row["failed"]
        row["failure_rate"] = round(row["failed"] / total, 3) if total else None
        size = row["billed_tokens"] or row["estimated_tokens"]
        row["tokens_per_answer"] = round(size * total / row["ok"]) if row["ok"] else None
        row["p50_ms"] = sorted(row.pop("ms"))[row["ok"] // 2] if row["ok"] else None
    return rows


def recommend(rows: list[dict]) -> dict[str, Any]:
    reliable = [r for r in rows if r["failure_rate"] is not None and r["failure_rate"] <= RELIABLE_FAILURE_RATE]
    largest_reliable = max((r["billed_tokens"] or r["estimated_tokens"] for r in reliable), default=None)
    return {
        "largest_reliable_request_tokens": largest_reliable,
        "reliable_means_failure_rate_at_most": RELIABLE_FAILURE_RATE,
        "advice": (
            "Pack requests at or under the largest reliable size. If even the smallest real request fails often, "
            "the cause is not size: check rate (jev-budget-check.py) and other spenders on the account."
            if largest_reliable
            else "No real request size was reliable. Probe smaller requests, and check rate and other spenders."
        ),
    }


def make_sender(timeout: float) -> tuple[Callable[[dict], int | None], str]:
    """A single-attempt, uncached sender on the configured production transport."""
    os.environ["JEV_RETRY_MAX"] = "0"  # direct transport: no internal retries
    os.environ["JEV_CACHE_TTL_S"] = "0"  # direct transport: never answer from cache
    import jev_transport

    transport, reason = jev_transport.select()
    if transport is None:
        raise RuntimeError(f"no Jev transport available: {reason}")
    if transport == jev_transport.VERCEL:
        import jev_vercel

        def send(req: dict) -> int | None:
            data = jev_vercel.evaluate(
                req.get("state") or {},
                req["questions"],
                timeout=timeout,
                max_attempts=1,
                # The probe measures failure rate by size, so it may send above the guard.
                max_request_tokens=jev_limits.REQUEST_TOKEN_LIMIT,
            )
            return (data.get("usage") or {}).get("input_tokens")

        return send, "vercel"
    import jev_router_common

    key = os.environ["TYPESAFE_API_KEY"]

    def send(req: dict) -> int | None:
        payload = {"state": req.get("state") or {}, "model": jev_router_common.JEV_MODEL, "questions": req["questions"]}
        data, _ = jev_router_common.call_jev(payload, key, timeout, script_name="jev-size-probe.py")
        return (data.get("usage") or {}).get("input_tokens")

    return send, "direct"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--payload", type=Path, required=True, help="JSON of real requests (e.g. one run's requests)")
    p.add_argument("--rounds", type=int, default=10)
    p.add_argument("--variants", type=int, default=4, help="real request sizes to test, besides the control")
    p.add_argument("--timeout", type=float, default=8.0)
    p.add_argument("--pause", type=float, default=0.0, help="seconds between requests")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        variants = [CONTROL, *pick_variants(load_requests(a.payload), max(1, a.variants))]
        send, transport = make_sender(a.timeout)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"jev-size-probe: {exc}", file=sys.stderr)
        return 2
    rows = probe(variants, send, max(1, a.rounds), a.pause)
    rows[0]["control"] = True
    result = {"transport": transport, "rounds": a.rounds, "variants": rows, **recommend(rows[1:])}
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"transport: {transport}; {a.rounds} rounds, round-robin, one at a time, retries and cache off")
    print(f"{'tokens':>8} {'questions':>9} {'failed':>8} {'p50 ms':>7} {'tokens/answer':>13}  statuses")
    for r in rows:
        size = r["billed_tokens"] or f"~{r['estimated_tokens']}"
        label = " (control)" if r.get("control") else ""
        print(
            f"{size!s:>8} {r['questions']:>9} {r['failed']:>3}/{r['ok'] + r['failed']:<4} {r['p50_ms']!s:>7} "
            f"{r['tokens_per_answer']!s:>13}  {r['statuses'] or ''}{label}"
        )
    print(f"largest reliable request: {result['largest_reliable_request_tokens']} tokens. {result['advice']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
