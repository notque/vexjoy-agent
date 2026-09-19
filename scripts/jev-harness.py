#!/usr/bin/env python3
"""CLI entry point for the generic Jev improvement harness.

Usage:
    python3 scripts/jev-harness.py loop --program PATH --labels PATH \
        --split-field FIELD --train-cutoff VAL --dev-cutoff VAL \
        [--graders accuracy,brier] [--run-dir DIR] [--max-rounds N]

    python3 scripts/jev-harness.py variance --program PATH --labels PATH \
        --split-field FIELD --train-cutoff VAL --dev-cutoff VAL [--repeats 10]

    python3 scripts/jev-harness.py sweep --program PATH --labels PATH \
        --split-field FIELD --train-cutoff VAL --dev-cutoff VAL \
        [--cost-fp 1.0] [--cost-fn 1.0] [--thresholds 0.3,0.5,0.7,0.9] \
        [--select-split dev] [--report-split test]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_LIB_DIR = _SCRIPTS_DIR / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from jev_harness import (
    HarnessConfig,
    cost_threshold,
    grade,
    judge_variance,
    load_labels,
    load_program,
    make_split,
    run_loop,
    run_predictions,
    threshold_sweep,
)


def _add_common_args(sub: argparse.ArgumentParser) -> None:
    """Add arguments shared by all subcommands."""
    sub.add_argument("--program", required=True, help="Path to the Jev program module.")
    sub.add_argument("--labels", required=True, help="Path to JSONL labels file (each line has 'y').")
    sub.add_argument("--split-field", required=True, help="Field name to split on (e.g. 'date').")
    sub.add_argument("--train-cutoff", required=True, help="Values <= this go to train split.")
    sub.add_argument("--dev-cutoff", required=True, help="Values <= this go to dev split; rest goes to test.")


def _cmd_loop(args: argparse.Namespace) -> int:
    """Run the full improvement loop."""
    config = HarnessConfig(
        program_path=args.program,
        labels_path=args.labels,
        split_field=args.split_field,
        train_cutoff=args.train_cutoff,
        dev_cutoff=args.dev_cutoff,
        graders=args.graders.split(","),
        run_dir=args.run_dir,
        max_rounds=args.max_rounds,
        db_path=args.db_path,
    )

    report = run_loop(config)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    bl = report.get("baseline_metrics", {})
    fd = report.get("final_dev_metrics", {})
    tm = report.get("test_metrics", {})
    floors = report.get("sanity_floors", {})

    print(f"Sanity floors: {floors}")
    print(f"Baseline dev:  {bl}")
    print(f"Final dev:     {fd}")
    if tm:
        print(f"Test (once):   {tm}")

    kept = report.get("levers_kept", [])
    if kept:
        print(f"\nLevers kept ({len(kept)}):")
        for entry in kept:
            print(f"  R{entry['round']} {entry['lever']}: {entry['variant']}")
    else:
        print("\nNo levers improved over baseline.")

    ea = report.get("error_analysis_final", {})
    if ea:
        print(f"\nFinal error analysis: {ea}")

    return 0


def _cmd_variance(args: argparse.Namespace) -> int:
    """Measure judge variance over frozen rows."""
    program = load_program(args.program)
    rows = load_labels(args.labels)
    config = HarnessConfig(
        program_path=args.program,
        labels_path=args.labels,
        split_field=args.split_field,
        train_cutoff=args.train_cutoff,
        dev_cutoff=args.dev_cutoff,
    )
    split = make_split(rows, config)

    print(f"[variance] dev={len(split.dev)} rows, repeats={args.repeats}")
    result = judge_variance(program, split.dev, {}, config.jev_caller, n_repeats=args.repeats)

    summary = result["summary"]
    print(f"mean_std:  {summary['mean_std']:.6f}")
    print(f"max_std:   {summary['max_std']:.6f}")
    print(f"flip_rate: {summary['flip_rate']:.4f}")

    flipped_rows = [r for r in result["per_row"] if r["flipped"]]
    if flipped_rows:
        print(f"\n{len(flipped_rows)} row(s) with argmax flip:")
        for r in flipped_rows[:10]:
            print(f"  row {r['row_idx']}: mean_std={r['mean_std']:.6f} max_std={r['max_std']:.6f}")

    return 0


def _cmd_sweep(args: argparse.Namespace) -> int:
    """Sweep thresholds over predictions and report cost."""
    select_split = args.select_split
    report_split = args.report_split
    if select_split == report_split:
        print(f"error: --select-split and --report-split must differ (both are '{select_split}')", file=sys.stderr)
        return 1

    program = load_program(args.program)
    rows = load_labels(args.labels)
    config = HarnessConfig(
        program_path=args.program,
        labels_path=args.labels,
        split_field=args.split_field,
        train_cutoff=args.train_cutoff,
        dev_cutoff=args.dev_cutoff,
    )
    split = make_split(rows, config)

    splits_map = {"train": split.train, "dev": split.dev, "test": split.test}
    sel_rows = splits_map[select_split]
    rep_rows = splits_map[report_split]

    thresholds = [float(t) for t in args.thresholds.split(",")]
    c_fp = args.cost_fp
    c_fn = args.cost_fn
    ct = cost_threshold(c_fp, c_fn)

    print(f"[sweep] cost_threshold(c_fp={c_fp}, c_fn={c_fn}) = {ct:.4f}")
    print(f"[sweep] select on {select_split} ({len(sel_rows)} rows), report on {report_split} ({len(rep_rows)} rows)")

    # Run predictions on the select split.
    sel_preds = run_predictions(program, sel_rows, {}, config)
    sel_labels = [r["y"] for r in sel_rows]
    sel_results = threshold_sweep(sel_preds, sel_labels, thresholds, c_fp, c_fn)

    print(f"\n{'threshold':>10}{'coverage':>10}{'fp':>6}{'fn':>6}{'cost':>10}  (select: {select_split})")
    for s in sel_results:
        print(f"{s['threshold']:>10.3f}{s['coverage']:>10.3f}{s['fp']:>6}{s['fn']:>6}{s['cost']:>10.4f}")

    # Report on the report split.
    rep_preds = run_predictions(program, rep_rows, {}, config)
    rep_labels = [r["y"] for r in rep_rows]
    rep_results = threshold_sweep(rep_preds, rep_labels, thresholds, c_fp, c_fn)

    print(f"\n{'threshold':>10}{'coverage':>10}{'fp':>6}{'fn':>6}{'cost':>10}  (report: {report_split})")
    for s in rep_results:
        print(f"{s['threshold']:>10.3f}{s['coverage']:>10.3f}{s['fp']:>6}{s['fn']:>6}{s['cost']:>10.4f}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Jev improvement harness: iterate a Jev program on labeled data.")
    subparsers = parser.add_subparsers(dest="command")

    # --- loop (the original default behavior) ---
    loop_p = subparsers.add_parser("loop", help="Run the full improvement loop.")
    _add_common_args(loop_p)
    loop_p.add_argument("--graders", default="accuracy,brier", help="Comma-separated graders.")
    loop_p.add_argument("--run-dir", default="runs", help="Output directory.")
    loop_p.add_argument("--max-rounds", type=int, default=10, help="Max improvement rounds.")
    loop_p.add_argument("--db-path", default=None, help="Path to learning.db for telemetry.")

    # --- variance ---
    var_p = subparsers.add_parser("variance", help="Measure judge variance over frozen dev rows.")
    _add_common_args(var_p)
    var_p.add_argument("--repeats", type=int, default=10, help="Number of repeated calls per row.")

    # --- sweep ---
    sweep_p = subparsers.add_parser("sweep", help="Sweep thresholds and report coverage/cost.")
    _add_common_args(sweep_p)
    sweep_p.add_argument("--cost-fp", type=float, default=1.0, help="Cost per false positive.")
    sweep_p.add_argument("--cost-fn", type=float, default=1.0, help="Cost per false negative.")
    sweep_p.add_argument("--thresholds", default="0.3,0.5,0.7,0.9", help="Comma-separated thresholds.")
    sweep_p.add_argument("--select-split", default="dev", choices=["train", "dev", "test"], help="Split to select on.")
    sweep_p.add_argument("--report-split", default="test", choices=["train", "dev", "test"], help="Split to report on.")

    # Backward compatibility: if no subcommand and --program is present, run loop.
    args = parser.parse_args()
    if args.command is None:
        # Fall back: re-parse as the old flat arg layout for backward compatibility.
        parser.print_help()
        return 1

    if args.command == "loop":
        return _cmd_loop(args)
    if args.command == "variance":
        return _cmd_variance(args)
    if args.command == "sweep":
        return _cmd_sweep(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
