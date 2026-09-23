"""Documented Jev service limits and the arithmetic that keeps a program under them.

Source: https://docs.typesafe.ai/models.md and https://docs.typesafe.ai/api.md
(checked 2026-09-22). The docs say rate limits "are subject to dynamic
adjustment": re-read the models page when a run starts failing with 429/529,
or with 503 through Vercel AI Gateway.

Why this module exists: a program can keep every request far under the
64k-token request limit and still fail, because one run fans out enough
requests to spend the whole per-second token limit. Per-request fit is not
enough; price the run per second too. ``jev-budget-check.py`` is the CLI.
"""

from __future__ import annotations

import json
import math
import random
from typing import Any

# --- Documented limits (models.md) ---
REQUEST_TOKEN_LIMIT = 64_000  # state + every question, per request
STATE_PLUS_LONGEST_QUESTION_LIMIT = 32_000  # state + the longest single question
TOKENS_PER_SECOND_LIMIT = 250_000  # input tokens per second
REQUESTS_PER_MINUTE_LIMIT = 1_200

# --- Planning margins ---
# Plan one program's peak at <= 25% of a limit. Other programs on the same
# account, retries, and dynamic adjustment share the rest.
SAFE_FRACTION = 0.25
# Measured ~4.3 characters per billed token on JSON Jev payloads. Dividing by 4
# overestimates slightly, which errs on the safe side.
CHARS_PER_TOKEN = 4.0
# Typical wall time of one request. Measure on the production transport; the
# direct API and Vercel AI Gateway differ.
TYPICAL_LATENCY_S = 0.35
# Above this many input tokens per run, a single-stage design is a smell:
# use a cascade (cheap wide stage over every unit, full detail for survivors).
CASCADE_TOKENS_PER_RUN = 50_000

# --- Request size (the most common failure) ---
# Through Vercel AI Gateway, too much context is the failure that keeps
# recurring: oversized requests fail consistently while small ones return fine.
# TARGET: pack_questions() splits questions into requests at or under this.
# MAX: the transports refuse to send anything larger (no wasted call, no retry).
TARGET_REQUEST_TOKENS = 3_500
MAX_REQUEST_TOKENS = 4_500
# A request over MAX is split into as many requests as it takes (2, 15, ...),
# each carrying the full state, sent at once with at most this many in flight:
# floor(SAFE_FRACTION * TOKENS_PER_SECOND_LIMIT / TARGET_REQUEST_TOKENS) is 17.
SPLIT_MAX_IN_FLIGHT = 16


class RequestTooLarge(ValueError):
    """A Jev request passes the size limit and was not sent.

    Shrink the state (bound fields, send only what the questions need) or split
    the questions with ``pack_questions``.
    """


# --- Retry policy (api.md: exponential backoff for 429 and 529) ---
# Vercel AI Gateway reports upstream rate limiting and overload as HTTP 503
# (GatewayInternalServerError, "Service temporarily unavailable"). It uses the
# same 503 for fast transient failures whose rate grew with tokens per request
# (measured 2026-09-22: ~3k tokens failed ~1 in 8, ~13k about 5 in 8). Retry a
# 503 with jittered backoff; narrow concurrency on 429/529 or repeated 503s.
RETRY_STATUSES_DIRECT = frozenset({429, 529})
RETRY_STATUSES_GATEWAY = frozenset({429, 503, 529})
RETRY_BASE_S = 0.5
RETRY_MAX_S = 8.0


def estimate_tokens(value: Any) -> int:
    """Estimated billed input tokens for a JSON-serializable value or string."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def request_tokens(state: Any, questions: dict[str, Any]) -> dict[str, int]:
    """Token estimate for one request, split the way the documented limits are."""
    state_tokens = estimate_tokens(state)
    per_question = [estimate_tokens(q) for q in questions.values()] or [0]
    return {
        "state": state_tokens,
        "questions": sum(per_question),
        "question_count": len(questions),
        "longest_question": max(per_question),
        "total": state_tokens + sum(per_question),
        "state_plus_longest": state_tokens + max(per_question),
    }


def backoff_delay(
    attempt: int,
    retry_after: float | None = None,
    *,
    rng=random.random,
    base: float = RETRY_BASE_S,
    cap: float = RETRY_MAX_S,
) -> float:
    """Seconds before retry number ``attempt + 1`` (``attempt`` starts at 0).

    Exponential with equal jitter: half the step is fixed, half is random, so
    parallel callers that failed together do not retry together. A server
    ``Retry-After`` is a floor, never shortened.
    """
    step = min(cap, base * (2**attempt))
    delay = step / 2 + rng() * step / 2
    if retry_after is not None and retry_after >= 0:
        delay = max(delay, min(float(retry_after), cap))
    return delay


def check_run(
    requests: list[dict[str, Any]],
    *,
    concurrency: int | None = None,
    latency_s: float = TYPICAL_LATENCY_S,
    concurrent_runs: int = 1,
    attempts: int = 1,
    runs_per_minute: float = 1.0,
    measured_tokens_per_run: int | None = None,
    eval_cases: int = 0,
) -> dict[str, Any]:
    """Price one run of a Jev program against the documented limits.

    ``requests`` holds ``{"state": ..., "questions": {...}}`` items: everything
    one run sends. Requests start in waves of ``concurrency``; each wave takes
    about ``latency_s``. ``attempts`` is the worst case per request (1 + retries).
    ``concurrent_runs`` is how many users or jobs can run at once.
    Returns the numbers plus ``findings`` and a verdict: ok, warn, or fail.
    """
    if not requests:
        raise ValueError("no requests to price")
    sizes = [request_tokens(r.get("state"), r.get("questions") or {}) for r in requests]
    totals = [s["total"] for s in sizes]
    per_run = sum(totals)
    scale = (measured_tokens_per_run / per_run) if measured_tokens_per_run else 1.0
    per_run_billed = round(per_run * scale)
    width = max(1, min(concurrency or len(requests), len(requests)))
    waves = math.ceil(len(requests) / width)
    peak_wave = max(sum(totals[i : i + width]) for i in range(0, len(totals), width)) * scale
    peak_tps = peak_wave / max(latency_s, 0.05) * concurrent_runs
    retry_tps = peak_tps * attempts
    rpm = len(requests) * attempts * max(runs_per_minute, concurrent_runs)

    findings: list[dict[str, str]] = []

    def add(level: str, msg: str) -> None:
        findings.append({"level": level, "message": msg})

    worst = max(sizes, key=lambda s: s["total"])
    if worst["total"] > REQUEST_TOKEN_LIMIT:
        add("fail", f"largest request ~{worst['total']:,} tokens exceeds the {REQUEST_TOKEN_LIMIT:,} request limit")
    widest = max(sizes, key=lambda s: s["state_plus_longest"])
    if widest["state_plus_longest"] > STATE_PLUS_LONGEST_QUESTION_LIMIT:
        add(
            "fail",
            f"state + longest question ~{widest['state_plus_longest']:,} exceeds {STATE_PLUS_LONGEST_QUESTION_LIMIT:,}",
        )
    for label, value, limit in (
        ("peak tokens/s", peak_tps, TOKENS_PER_SECOND_LIMIT),
        ("tokens/s with worst-case retries", retry_tps, TOKENS_PER_SECOND_LIMIT),
        ("requests/min", rpm, REQUESTS_PER_MINUTE_LIMIT),
    ):
        if value > limit:
            add("fail", f"{label} ~{value:,.0f} exceeds the documented {limit:,} limit")
        elif value > limit * SAFE_FRACTION:
            add("warn", f"{label} ~{value:,.0f} is over {SAFE_FRACTION:.0%} of the documented {limit:,} limit")
    if per_run_billed > CASCADE_TOKENS_PER_RUN:
        add(
            "warn",
            f"~{per_run_billed:,} tokens per run: use a cascade (cheap wide stage over every unit, full detail only for survivors)",
        )
    q_text = sum(s["questions"] for s in sizes)
    if q_text > 2 * sum(s["state"] for s in sizes):
        add(
            "warn",
            "question text is over twice the state: shorten questions or move shared definitions into state once per request",
        )

    result: dict[str, Any] = {
        "requests": len(requests),
        "concurrency": width,
        "waves": waves,
        "tokens_per_run": per_run_billed,
        "largest_request_tokens": round(worst["total"] * scale),
        "peak_tokens_per_second": round(peak_tps),
        "peak_tokens_per_second_with_retries": round(retry_tps),
        "requests_per_minute": round(rpm),
        "limits": {
            "request_tokens": REQUEST_TOKEN_LIMIT,
            "state_plus_longest_question": STATE_PLUS_LONGEST_QUESTION_LIMIT,
            "tokens_per_second": TOKENS_PER_SECOND_LIMIT,
            "requests_per_minute": REQUESTS_PER_MINUTE_LIMIT,
            "safe_fraction": SAFE_FRACTION,
        },
    }
    if eval_cases:
        total = per_run_billed * eval_cases
        safe_rate = TOKENS_PER_SECOND_LIMIT * SAFE_FRACTION
        result["eval"] = {
            "cases": eval_cases,
            "tokens": total,
            "min_seconds_at_safe_rate": math.ceil(total / safe_rate),
            "min_seconds_between_cases": round(per_run_billed / safe_rate, 2),
        }
        if total > 5_000_000:
            add(
                "warn",
                f"eval spends ~{total:,} tokens: use a smaller split while iterating and retune thresholds from stored probabilities",
            )
    result["findings"] = findings
    result["verdict"] = "fail" if any(f["level"] == "fail" for f in findings) else "warn" if findings else "ok"
    return result


def check_request_size(state: Any, questions: dict[str, Any], limit: int = MAX_REQUEST_TOKENS) -> int:
    """Return the request's estimated tokens; raise RequestTooLarge above ``limit``."""
    total = request_tokens(state, questions)["total"]
    if total > limit:
        raise RequestTooLarge(
            f"Jev request is ~{total} tokens (limit {limit}); shrink the state or split questions with pack_questions()"
        )
    return total


def pack_questions(
    state: Any,
    questions: dict[str, Any],
    *,
    target: int = TARGET_REQUEST_TOKENS,
    max_questions: int | None = None,
) -> list[dict[str, Any]]:
    """Split ``questions`` into groups that each fit one request with the full ``state``.

    Order is preserved. Raises RequestTooLarge when the state plus a single
    question already passes ``target``: that state must be shrunk, not split.
    """
    state_tokens = estimate_tokens(state)
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    current_tokens = state_tokens
    for key, question in questions.items():
        q_tokens = estimate_tokens(question)
        if state_tokens + q_tokens > target:
            raise RequestTooLarge(
                f"state plus question {key!r} is ~{state_tokens + q_tokens} tokens (target {target}); shrink the state"
            )
        full = max_questions is not None and len(current) >= max_questions
        if current and (current_tokens + q_tokens > target or full):
            groups.append(current)
            current, current_tokens = {}, state_tokens
        current[key] = question
        current_tokens += q_tokens
    if current:
        groups.append(current)
    return groups


def _merge_split_results(results: list[dict[str, Any]], groups: list[dict[str, Any]], state: Any) -> dict[str, Any]:
    """Merge answers from split requests into one response shaped like a single one."""
    answers: dict[str, Any] = {}
    receipts: list[Any] = []
    attempts = retries = 0
    usage_in = usage_out = 0
    usage_complete = True
    for result in results:
        answers.update(result.get("answers") or {})
        meta = result.get("_meta") if isinstance(result.get("_meta"), dict) else {}
        retry = meta.get("retry") if isinstance(meta.get("retry"), dict) else {}
        attempts += int(retry.get("attempts") or 1)
        retries += int(retry.get("retries") or 0)
        receipts.extend(retry.get("attempt_receipts") or [])
        usage = result.get("usage")
        if (
            isinstance(usage, dict)
            and isinstance(usage.get("input_tokens"), int)
            and isinstance(usage.get("output_tokens"), int)
        ):
            usage_in += usage["input_tokens"]
            usage_out += usage["output_tokens"]
        else:
            usage_complete = False
    merged: dict[str, Any] = {
        "answers": answers,
        "_meta": {
            "retry": {"attempts": attempts, "retries": retries, "error": None, "attempt_receipts": receipts},
            "split": {
                "requests": len(groups),
                "questions": [len(g) for g in groups],
                "estimated_tokens": [request_tokens(state, g)["total"] for g in groups],
            },
        },
    }
    if results and "model" in results[0]:
        merged["model"] = results[0]["model"]
    if usage_complete and results:
        merged["usage"] = {"input_tokens": usage_in, "output_tokens": usage_out}
    return merged


def split_and_run(
    state: Any,
    questions: dict[str, Any],
    send_one: Any,
    *,
    limit: int = MAX_REQUEST_TOKENS,
    target: int = TARGET_REQUEST_TOKENS,
    max_in_flight: int = SPLIT_MAX_IN_FLIGHT,
) -> dict[str, Any]:
    """Send one request when it fits ``limit``; otherwise split it into as many as it takes.

    ``send_one(state, questions)`` sends one request and returns its response.
    Split requests each carry the full state and are sent at once (at most
    ``max_in_flight`` in flight); answers are merged. Any failed request raises,
    so partial answers are never returned as complete. Raises RequestTooLarge,
    without sending, only when the state plus a single question passes ``target``.
    """
    if request_tokens(state, questions)["total"] <= limit:
        return send_one(state, questions)
    groups = pack_questions(state, questions, target=target)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max(1, min(len(groups), max_in_flight))) as pool:
        results = list(pool.map(lambda group: send_one(state, group), groups))
    return _merge_split_results(results, groups, state)
