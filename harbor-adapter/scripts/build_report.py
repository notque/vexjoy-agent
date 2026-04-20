#!/usr/bin/env python3
"""Assemble the per-task report from a completed Harbor run.

Reads:
  <run-dir>/raw/<trial>/reward.txt         -> pass/fail (1 or 0)
  <run-dir>/raw/<trial>/context.json       -> token usage (claude_do_router)
  <run-dir>/raw/<trial>/timing.json        -> wall time if Harbor emits it

Writes a markdown report with per-task rows + aggregates.

Pricing for cost estimate (anthropic.com/pricing as of 2026-04):
  claude-opus-4-1:    $15 / M input, $75 / M output
  claude-sonnet-4-5:  $3  / M input, $15 / M output
  claude-haiku-4-5:   $1  / M input, $5  / M output

The adapter does not know which model /do picked per trial; we apply Sonnet
pricing as a conservative estimate and note it in the report. If per-trial
model info is available in context.json, prefer that.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

# (input_per_mtok, output_per_mtok) in USD
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-opus-4-1": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
DEFAULT_MODEL_KEY = "claude-sonnet-4-5"


@dataclass
class TrialRow:
    task: str
    passed: bool | None
    wall_seconds: float | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_creation_tokens: int | None
    usage_parse_error: str | None
    exit_code: int | None
    estimated_cost_usd: float | None


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _read_reward(path: Path) -> bool | None:
    if not path.is_file():
        return None
    text = path.read_text().strip()
    if text == "1":
        return True
    if text == "0":
        return False
    return None


def _estimate_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    model_key: str,
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    price_in, price_out = PRICE_TABLE.get(model_key, PRICE_TABLE[DEFAULT_MODEL_KEY])
    return (input_tokens / 1_000_000.0) * price_in + (output_tokens / 1_000_000.0) * price_out


def collect_trials(raw_dir: Path) -> list[TrialRow]:
    rows: list[TrialRow] = []
    if not raw_dir.is_dir():
        return rows

    for trial_dir in sorted(raw_dir.iterdir()):
        if not trial_dir.is_dir():
            continue
        reward_path = trial_dir / "verifier" / "reward.txt"
        if not reward_path.is_file():
            # Fallback: some Harbor versions drop it at trial root.
            reward_path = trial_dir / "reward.txt"
        passed = _read_reward(reward_path)

        context = _read_json(trial_dir / "context.json") or {}
        usage = (
            context.get("metadata", {}).get("claude_do_router", {}) if isinstance(context.get("metadata"), dict) else {}
        )
        timing = _read_json(trial_dir / "timing.json") or {}

        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        cost = _estimate_cost(input_tokens, output_tokens, DEFAULT_MODEL_KEY)

        rows.append(
            TrialRow(
                task=trial_dir.name,
                passed=passed,
                wall_seconds=timing.get("wall_seconds"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=usage.get("cache_read_tokens"),
                cache_creation_tokens=usage.get("cache_creation_tokens"),
                usage_parse_error=usage.get("usage_parse_error"),
                exit_code=usage.get("exit_code"),
                estimated_cost_usd=cost,
            )
        )
    return rows


def render_report(rows: list[TrialRow], run_dir: Path) -> str:
    lines: list[str] = []
    lines.append("# /do Router Dry Run: terminal-bench-2 x 5")
    lines.append("")
    lines.append(f"Run directory: `{run_dir}`")
    lines.append("")

    if not rows:
        lines.append("No trials found. The Harbor run did not produce any trial")
        lines.append("directories under `raw/`. Inspect `harbor-run.log` for the")
        lines.append("failure mode.")
        return "\n".join(lines) + "\n"

    lines.append("## Per-task results")
    lines.append("")
    lines.append("| Task | Pass | Wall (s) | Input tok | Output tok | Cache read | Est. cost (USD) | Notes |")
    lines.append("|------|------|----------|-----------|------------|-----------|-----------------|-------|")
    for row in rows:
        pass_cell = "pass" if row.passed is True else "fail" if row.passed is False else "?"
        wall = f"{row.wall_seconds:.1f}" if row.wall_seconds is not None else "?"
        in_tok = f"{row.input_tokens:,}" if row.input_tokens is not None else "?"
        out_tok = f"{row.output_tokens:,}" if row.output_tokens is not None else "?"
        cache = f"{row.cache_read_tokens:,}" if row.cache_read_tokens is not None else "?"
        cost = f"${row.estimated_cost_usd:.4f}" if row.estimated_cost_usd is not None else "?"
        notes_parts: list[str] = []
        if row.exit_code is not None and row.exit_code != 0:
            notes_parts.append(f"exit={row.exit_code}")
        if row.usage_parse_error:
            notes_parts.append(row.usage_parse_error)
        notes = "; ".join(notes_parts) or ""
        lines.append(f"| {row.task} | {pass_cell} | {wall} | {in_tok} | {out_tok} | {cache} | {cost} | {notes} |")

    # Aggregates
    passed = sum(1 for r in rows if r.passed is True)
    failed = sum(1 for r in rows if r.passed is False)
    unknown = sum(1 for r in rows if r.passed is None)
    total_in = sum(r.input_tokens or 0 for r in rows)
    total_out = sum(r.output_tokens or 0 for r in rows)
    total_cost = sum(r.estimated_cost_usd or 0.0 for r in rows)

    lines.append("")
    lines.append("## Aggregates")
    lines.append("")
    lines.append(f"- Trials: {len(rows)} ({passed} pass, {failed} fail, {unknown} unknown)")
    lines.append(f"- Total input tokens: {total_in:,}")
    lines.append(f"- Total output tokens: {total_out:,}")
    lines.append(f"- Estimated total cost (Sonnet pricing): ${total_cost:.4f}")
    lines.append("")
    lines.append(
        "Cost estimate uses claude-sonnet-4-5 pricing as a conservative "
        "approximation. /do routes to different agents per task; replace "
        "this estimate with actual per-agent pricing once per-trial model "
        "info is wired through."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = collect_trials(args.run_dir / "raw")
    report = render_report(rows, args.run_dir)
    args.output.write_text(report)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
