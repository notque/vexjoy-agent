#!/usr/bin/env python3
"""
Unblind and report on adaptive-thinking A/B test results.

Loads scores.json (blind scores) and mapping.json (hex_id -> variant),
joins them, and generates results.md with per-round tables, aggregate
statistics, and a winner determination.

Run AFTER score_results.py.
"""

import json
import statistics
import sys
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
SCORES_FILE = SCRIPT_DIR / "scores.json"
MAPPING_FILE = SCRIPT_DIR / "mapping.json"
REPORT_FILE = SCRIPT_DIR / "results.md"

DIMENSIONS = ["true_positives", "severity_calib", "actionability", "thoroughness"]

DIM_LABELS = {
    "true_positives": "True Positives",
    "severity_calib": "Severity Calibration",
    "actionability": "Actionability",
    "thoroughness": "Thoroughness",
}

# ── helpers ───────────────────────────────────────────────────────────────────


def load_json(path: Path) -> object:
    """Load and return JSON from path, exiting on error."""
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def composite_score(score: dict) -> float | None:
    """Return the mean of all four dimension scores, or None if any is missing."""
    vals = [score.get(d) for d in DIMENSIONS]
    if any(v is None for v in vals):
        return None
    return sum(vals) / len(vals)  # type: ignore[arg-type]


def fmt_float(val: float | None, decimals: int = 2) -> str:
    """Format a float or return 'N/A'."""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


def variant_stats(scores: list[dict], variant: str) -> dict:
    """Compute aggregate stats for one variant across all dimensions.

    Args:
        scores: All unblinded score records.
        variant: 'A' or 'B'.

    Returns:
        Dict mapping dimension -> {mean, median, stdev, count}.
    """
    subset = [s for s in scores if s.get("variant") == variant and s.get("error") == ""]
    result: dict = {}
    for dim in DIMENSIONS:
        vals = [s[dim] for s in subset if s.get(dim) is not None]
        result[dim] = {
            "mean": statistics.mean(vals) if vals else None,
            "median": statistics.median(vals) if vals else None,
            "stdev": statistics.stdev(vals) if len(vals) > 1 else None,
            "count": len(vals),
        }
    # composite
    composites = [composite_score(s) for s in subset]
    composites = [c for c in composites if c is not None]
    result["composite"] = {
        "mean": statistics.mean(composites) if composites else None,
        "median": statistics.median(composites) if composites else None,
        "stdev": statistics.stdev(composites) if len(composites) > 1 else None,
        "count": len(composites),
    }
    return result


def determine_winner(stats_a: dict, stats_b: dict) -> str:
    """Return 'A', 'B', or 'TIE' based on composite mean score.

    Args:
        stats_a: Stats dict for variant A.
        stats_b: Stats dict for variant B.

    Returns:
        String describing the winner.
    """
    mean_a = stats_a["composite"]["mean"]
    mean_b = stats_b["composite"]["mean"]

    if mean_a is None or mean_b is None:
        return "UNDETERMINED (insufficient data)"

    diff = abs(mean_a - mean_b)
    if diff < 0.25:
        return f"TIE (A={mean_a:.2f}, B={mean_b:.2f}, diff={diff:.2f} < 0.25 threshold)"
    elif mean_a > mean_b:
        return f"A — Adaptive DISABLED (A={mean_a:.2f} vs B={mean_b:.2f}, +{diff:.2f})"
    else:
        return f"B — Adaptive ENABLED (B={mean_b:.2f} vs A={mean_a:.2f}, +{diff:.2f})"


def duration_stats(scores: list[dict], variant: str) -> dict:
    """Compute duration statistics for a variant.

    Args:
        scores: All unblinded score records.
        variant: 'A' or 'B'.

    Returns:
        Dict with mean, median, stdev (seconds) for run_duration_s.
    """
    subset = [s for s in scores if s.get("variant") == variant]
    durations = [s["run_duration_s"] for s in subset if s.get("run_duration_s") is not None]
    return {
        "mean": statistics.mean(durations) if durations else None,
        "median": statistics.median(durations) if durations else None,
        "stdev": statistics.stdev(durations) if len(durations) > 1 else None,
        "count": len(durations),
    }


# ── report generation ─────────────────────────────────────────────────────────


def build_report(scores: list[dict]) -> str:
    """Build the full markdown report string.

    Args:
        scores: All unblinded score records (variant field populated).

    Returns:
        Markdown string.
    """
    lines: list[str] = []

    # ── header ────────────────────────────────────────────────────────────────
    lines.append("# Adaptive Thinking A/B Test Results")
    lines.append("")
    lines.append("**Variant A**: `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` (fixed high reasoning budget)")
    lines.append("**Variant B**: `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=0` (adaptive, model chooses budget)")
    lines.append("")
    lines.append("**Task**: Code review of `hooks/pretool-unified-gate.py`")
    lines.append("**Judge**: Blind `claude -p` scoring on 4 dimensions (1-10 each)")
    lines.append("")

    # ── winner ────────────────────────────────────────────────────────────────
    stats_a = variant_stats(scores, "A")
    stats_b = variant_stats(scores, "B")
    winner = determine_winner(stats_a, stats_b)

    lines.append("## Winner")
    lines.append("")
    lines.append(f"**{winner}**")
    lines.append("")

    # ── aggregate stats ───────────────────────────────────────────────────────
    lines.append("## Aggregate Statistics")
    lines.append("")
    lines.append("| Dimension | A mean | A median | A stdev | B mean | B median | B stdev | Delta (B-A) |")
    lines.append("|-----------|--------|----------|---------|--------|----------|---------|-------------|")

    all_dims = DIMENSIONS + ["composite"]
    for dim in all_dims:
        label = DIM_LABELS.get(dim, dim.replace("_", " ").title())
        sa = stats_a[dim]
        sb = stats_b[dim]

        mean_a = sa["mean"]
        mean_b = sb["mean"]
        delta = (mean_b - mean_a) if (mean_a is not None and mean_b is not None) else None
        delta_str = f"{delta:+.2f}" if delta is not None else "N/A"

        lines.append(
            f"| {label} "
            f"| {fmt_float(mean_a)} "
            f"| {fmt_float(sa['median'])} "
            f"| {fmt_float(sa['stdev'])} "
            f"| {fmt_float(mean_b)} "
            f"| {fmt_float(sb['median'])} "
            f"| {fmt_float(sb['stdev'])} "
            f"| {delta_str} |"
        )
    lines.append("")

    # ── duration stats ────────────────────────────────────────────────────────
    dur_a = duration_stats(scores, "A")
    dur_b = duration_stats(scores, "B")

    lines.append("## Duration Comparison (wall-clock seconds)")
    lines.append("")
    lines.append("| Variant | Mean | Median | Stdev | N |")
    lines.append("|---------|------|--------|-------|---|")
    lines.append(
        f"| A (disabled) "
        f"| {fmt_float(dur_a['mean'], 1)} "
        f"| {fmt_float(dur_a['median'], 1)} "
        f"| {fmt_float(dur_a['stdev'], 1)} "
        f"| {dur_a['count']} |"
    )
    lines.append(
        f"| B (enabled)  "
        f"| {fmt_float(dur_b['mean'], 1)} "
        f"| {fmt_float(dur_b['median'], 1)} "
        f"| {fmt_float(dur_b['stdev'], 1)} "
        f"| {dur_b['count']} |"
    )
    lines.append("")

    # ── per-round table ───────────────────────────────────────────────────────
    lines.append("## Per-Round Comparison")
    lines.append("")
    lines.append("| Round | Hex ID | Variant | TP | SC | AC | TH | Composite | Duration (s) | Notes |")
    lines.append("|-------|--------|---------|----|----|----|----|-----------|--------------|-------|")

    # Group by round, sort A before B within each round
    rounds: dict[int, list[dict]] = {}
    for s in scores:
        rnd = s.get("round", 0)
        rounds.setdefault(rnd, []).append(s)

    for rnd in sorted(rounds):
        pair = sorted(rounds[rnd], key=lambda x: x.get("variant", ""))
        for s in pair:
            comp = composite_score(s)
            error_note = f"ERROR: {s['error'][:40]}" if s.get("error") else s.get("notes", "")[:50]
            lines.append(
                f"| {s.get('round', '?'):02d} "
                f"| `{s.get('hex_id', '?')}` "
                f"| {s.get('variant', '?')} "
                f"| {s.get('true_positives') or 'N/A'} "
                f"| {s.get('severity_calib') or 'N/A'} "
                f"| {s.get('actionability') or 'N/A'} "
                f"| {s.get('thoroughness') or 'N/A'} "
                f"| {fmt_float(comp)} "
                f"| {fmt_float(s.get('run_duration_s'), 1)} "
                f"| {error_note} |"
            )
    lines.append("")

    # ── statistical significance note ─────────────────────────────────────────
    count_a = stats_a["composite"]["count"]
    count_b = stats_b["composite"]["count"]

    lines.append("## Statistical Significance Note")
    lines.append("")
    lines.append(f"N = {count_a} (A), {count_b} (B). With N=10 per variant, this test has limited statistical")
    lines.append("power. A composite score difference under ~0.5 points should be treated as noise.")
    lines.append("A difference of 1.0+ points is more likely to be real, but replication is recommended.")
    lines.append("")
    lines.append("This is a single-judge evaluation (another `claude -p` call). Judge variance adds noise.")
    lines.append("For higher confidence: increase rounds to 30+, use 3 independent judges and average scores,")
    lines.append("or apply a Wilcoxon signed-rank test on the paired round scores.")
    lines.append("")

    # ── scoring rubric reminder ───────────────────────────────────────────────
    lines.append("## Scoring Rubric")
    lines.append("")
    lines.append("| Dimension | Description |")
    lines.append("|-----------|-------------|")
    lines.append("| True Positives | Real bugs found; no fabricated issues. 10 = only real issues. |")
    lines.append("| Severity Calibration | Labels match actual risk. 10 = perfectly calibrated. |")
    lines.append("| Actionability | Developer can fix from review alone. 10 = specific code fixes. |")
    lines.append("| Thoroughness | Coverage of distinct logic paths. 10 = comprehensive. |")
    lines.append("")

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Unblind results, generate report, write results.md."""
    scores_raw: list[dict] = load_json(SCORES_FILE)  # type: ignore[assignment]
    mapping: dict[str, dict] = load_json(MAPPING_FILE)  # type: ignore[assignment]

    # Unblind: join variant from mapping into each score record
    unblinded: list[dict] = []
    for score in scores_raw:
        hex_id = score.get("hex_id", "")
        if hex_id in mapping:
            score = dict(score)
            score["variant"] = mapping[hex_id]["variant"]
            score["disable_adaptive"] = mapping[hex_id]["disable_adaptive"]
            # Use round from mapping if not in score
            if "round" not in score or score["round"] is None:
                score["round"] = mapping[hex_id].get("round")
        else:
            print(f"WARN: hex_id {hex_id!r} not found in mapping.json", file=sys.stderr)
            score = dict(score)
            score["variant"] = "UNKNOWN"
        unblinded.append(score)

    # Sort by round then variant
    unblinded.sort(key=lambda x: (x.get("round", 0), x.get("variant", "")))

    report = build_report(unblinded)

    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write(report)

    print(f"Report written to: {REPORT_FILE}")

    # Print summary to stdout
    stats_a = variant_stats(unblinded, "A")
    stats_b = variant_stats(unblinded, "B")
    winner = determine_winner(stats_a, stats_b)

    print("\n--- Summary ---")
    print(f"Winner: {winner}")
    print(
        f"A composite: mean={fmt_float(stats_a['composite']['mean'])} stdev={fmt_float(stats_a['composite']['stdev'])}"
    )
    print(
        f"B composite: mean={fmt_float(stats_b['composite']['mean'])} stdev={fmt_float(stats_b['composite']['stdev'])}"
    )


if __name__ == "__main__":
    main()
