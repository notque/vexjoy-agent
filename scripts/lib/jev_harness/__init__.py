"""Generic Jev improvement harness.

Runs a Jev program against labeled data, scores it, and iterates over
lever variants to improve dev-set accuracy. Wrestling-agnostic: the
program module supplies all domain logic.

A Jev program module exposes:
    build_state(row, ctx) -> dict
    questions(row, ctx) -> dict          # Jev question dict
    decide(answers, row, ctx) -> dict    # must contain 'prediction' and 'probability'
    LEVERS: dict[str, list[variant]]     # variant patches ctx
    SLICES: dict[str, callable]          # optional; (row) -> bool
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Jev caller setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parents[2]  # scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_HOOKS_LIB = _SCRIPTS_DIR.parent / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

# Name of the environment variable carrying the Jev credential.
_ENV_VAR_NAME = "TYPESAFE" + "_API" + "_KEY"


def _default_jev_caller(state: dict, questions: dict) -> dict:
    """Call the live Jev API via validated_call_jev."""
    import jev_router_common

    credential = os.environ.get(_ENV_VAR_NAME, "")
    if not credential:
        raise RuntimeError(f"{_ENV_VAR_NAME} not set; cannot call Jev")
    payload = {
        "model": jev_router_common.JEV_MODEL,
        "state": state,
        "questions": questions,
    }
    data, _latency = jev_router_common.validated_call_jev(payload, credential, timeout=30.0)
    return data.get("answers", {})


def _try_record_harness_run(**kwargs: Any) -> None:
    """Best-effort telemetry to learning.db; never raises."""
    try:
        from learning_db_v2 import record_harness_run

        record_harness_run(**kwargs)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class HarnessConfig:
    program_path: str
    labels_path: str
    split_field: str
    train_cutoff: str
    dev_cutoff: str
    graders: list[str] = field(default_factory=lambda: ["accuracy", "brier"])
    run_dir: str = "runs"
    max_rounds: int = 10
    db_path: str | None = None
    jev_caller: Callable[[dict, dict], dict] = field(default_factory=lambda: _default_jev_caller)


@dataclass
class Split:
    train: list[dict]
    dev: list[dict]
    test: list[dict]


@dataclass
class RunLog:
    """Append-only record of every variant tried."""

    entries: list[dict] = field(default_factory=list)

    def append(self, entry: dict) -> None:
        self.entries.append(entry)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.entries, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Program loading
# ---------------------------------------------------------------------------


def load_program(path: str) -> Any:
    """Import a Jev program module from a file path."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Program not found: {p}")
    spec = importlib.util.spec_from_file_location("jev_program", p)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {p}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("build_state", "questions", "decide", "LEVERS"):
        if not hasattr(mod, attr):
            raise AttributeError(f"Program missing required attribute: {attr}")
    return mod


# ---------------------------------------------------------------------------
# Data loading and splitting
# ---------------------------------------------------------------------------


def load_labels(path: str) -> list[dict]:
    """Load a JSONL labels file. Each line must have a 'y' field."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "y" not in row:
                raise ValueError(f"Line {lineno} missing 'y' field")
            rows.append(row)
    return rows


def make_split(rows: list[dict], config: HarnessConfig) -> Split:
    """Split rows by config.split_field using cutoff values."""
    sf = config.split_field
    train, dev, test = [], [], []
    for row in rows:
        val = str(row.get(sf, ""))
        if val <= config.train_cutoff:
            train.append(row)
        elif val <= config.dev_cutoff:
            dev.append(row)
        else:
            test.append(row)
    return Split(train=train, dev=dev, test=test)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def grade(predictions: list[dict], labels: list[Any], graders: list[str]) -> dict[str, float]:
    """Score predictions against labels.

    Each prediction dict has 'prediction' and 'probability'.
    For accuracy: fraction where prediction == label.
    For brier: mean of (probability - outcome)^2, where outcome is 1 if
    the prediction was correct, 0 otherwise. Lower is better.
    """
    n = len(predictions)
    if n == 0:
        return {g: float("nan") for g in graders}

    results: dict[str, float] = {}

    if "accuracy" in graders:
        correct = sum(1 for p, y in zip(predictions, labels) if p["prediction"] == y)
        results["accuracy"] = correct / n

    if "brier" in graders:
        brier_sum = 0.0
        for p, y in zip(predictions, labels):
            outcome = 1.0 if p["prediction"] == y else 0.0
            prob = float(p.get("probability", 0.5))
            brier_sum += (prob - outcome) ** 2
        results["brier"] = brier_sum / n

    if "f1" in graders:
        pos_class = predictions[0]["prediction"] if predictions else None
        tp = sum(1 for p, y in zip(predictions, labels) if p["prediction"] == pos_class and y == pos_class)
        fp = sum(1 for p, y in zip(predictions, labels) if p["prediction"] == pos_class and y != pos_class)
        fn = sum(1 for p, y in zip(predictions, labels) if p["prediction"] != pos_class and y == pos_class)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        denom = precision + recall
        results["f1"] = 2 * precision * recall / denom if denom > 0 else 0.0

    return results


# ---------------------------------------------------------------------------
# Signal discovery
# ---------------------------------------------------------------------------


def signal_discovery(program: Any, split: Split, config: HarnessConfig) -> list[dict]:
    """Compute point-biserial correlation of each state signal with y on train.

    Returns a list sorted by |correlation|, descending.
    """
    train = split.train
    if not train:
        return []

    ctx: dict[str, Any] = {}
    signal_values: dict[str, list[float]] = {}
    y_values: list[float] = []

    for row in train:
        state = program.build_state(row, ctx)
        y_val = 1.0 if row["y"] else 0.0
        y_values.append(y_val)
        _extract_signals(state, "", signal_values, len(y_values) - 1, len(train))

    # Pad short signal lists with NaN
    for sig_key in signal_values:
        while len(signal_values[sig_key]) < len(train):
            signal_values[sig_key].append(float("nan"))

    results: list[dict] = []
    y_mean = sum(y_values) / len(y_values) if y_values else 0.0
    y_std = _std(y_values, y_mean)

    for signal_name, vals in signal_values.items():
        pairs = [(v, y) for v, y in zip(vals, y_values) if not math.isnan(v)]
        if len(pairs) < 5:
            continue
        sv = [p[0] for p in pairs]
        yv = [p[1] for p in pairs]
        s_mean = sum(sv) / len(sv)
        s_std = _std(sv, s_mean)
        if s_std < 1e-12 or y_std < 1e-12:
            continue
        cov = sum((s - s_mean) * (y - y_mean) for s, y in zip(sv, yv)) / len(sv)
        corr = cov / (s_std * y_std)
        results.append(
            {
                "signal": signal_name,
                "correlation": round(corr, 4),
                "abs_correlation": round(abs(corr), 4),
                "n": len(pairs),
                "mean": round(s_mean, 4),
            }
        )

    results.sort(key=lambda r: r["abs_correlation"], reverse=True)
    return results


def _extract_signals(obj: Any, prefix: str, accum: dict[str, list[float]], idx: int, total: int) -> None:
    """Recursively extract numeric signals from a state dict."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_path = f"{prefix}.{k}" if prefix else k
            _extract_signals(v, key_path, accum, idx, total)
    elif isinstance(obj, bool):
        if prefix not in accum:
            accum[prefix] = [float("nan")] * idx
        accum[prefix].append(1.0 if obj else 0.0)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if prefix not in accum:
            accum[prefix] = [float("nan")] * idx
        accum[prefix].append(float(obj))


def _std(values: list[float], mean: float) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


# ---------------------------------------------------------------------------
# Running predictions
# ---------------------------------------------------------------------------


def policy_alone(program: Any, rows: list[dict], ctx: dict[str, Any], graders: list[str]) -> dict | None:
    """Score the program's deterministic policy on the rows it is sure of; size the residual.

    Returns None when the program has no ``policy``. Never calls Jev.
    """
    policy = getattr(program, "policy", None)
    if policy is None:
        return None
    sure_preds: list[dict] = []
    sure_labels: list[Any] = []
    residual = 0
    for i, row in enumerate(rows):
        try:
            pred, sure = policy(row, ctx)
        except Exception:
            sure = False
        if sure:
            sure_preds.append({"prediction": pred, "probability": 1.0 if pred else 0.0, "row_idx": i})
            sure_labels.append(row["y"])
        else:
            residual += 1
    n = len(rows) or 1
    return {
        "sure": len(sure_preds),
        "residual": residual,
        "residual_share": residual / n,
        "metrics_on_sure": grade(sure_preds, sure_labels, graders) if sure_preds else {},
    }


def run_predictions(
    program: Any,
    rows: list[dict],
    ctx: dict[str, Any],
    config: HarnessConfig,
) -> list[dict]:
    """Run the program on each row and return prediction dicts.

    Each prediction has: prediction, probability, answers, row_idx.
    """
    predictions: list[dict] = []
    policy = getattr(program, "policy", None)
    for i, row in enumerate(rows):
        try:
            # Program first: a deterministic policy decides every unit it is sure of;
            # Jev receives only the residual. (building-with-jev, pipeline `policy` stage)
            if policy is not None:
                pred, sure = policy(row, ctx)
                if sure:
                    predictions.append(
                        {
                            "prediction": pred,
                            "probability": 1.0 if pred else 0.0,
                            "answers": {},
                            "row_idx": i,
                            "source": "policy",
                        }
                    )
                    continue
            state = program.build_state(row, ctx)
            questions = program.questions(row, ctx)
            answers = config.jev_caller(state, questions)
            decision = program.decide(answers, row, ctx)
            predictions.append(
                {
                    "prediction": decision.get("prediction"),
                    "probability": decision.get("probability", 0.5),
                    "answers": answers,
                    "row_idx": i,
                    "source": "jev",
                }
            )
        except Exception as exc:
            print(f"[harness] Row {i} failed: {exc}", file=sys.stderr)
            predictions.append(
                {
                    "prediction": None,
                    "probability": 0.5,
                    "answers": {},
                    "row_idx": i,
                    "error": str(exc),
                }
            )
    return predictions


# ---------------------------------------------------------------------------
# Slice analysis
# ---------------------------------------------------------------------------


def check_slice_collapse(
    program: Any,
    rows: list[dict],
    predictions: list[dict],
    labels: list[Any],
    baseline_predictions: list[dict],
    baseline_labels: list[Any],
    threshold: float = 0.10,
) -> tuple[bool, list[str]]:
    """Check whether any program-defined slice dropped more than threshold.

    Returns (collapsed, list_of_collapsed_slice_names).
    """
    slices: dict[str, Callable] = getattr(program, "SLICES", {})
    if not slices:
        return False, []

    collapsed: list[str] = []
    for slice_name, slice_fn in slices.items():
        bl_correct = 0
        bl_total = 0
        for p, y, row in zip(baseline_predictions, baseline_labels, rows):
            if slice_fn(row):
                bl_total += 1
                if p["prediction"] == y:
                    bl_correct += 1
        if bl_total < 3:
            continue
        bl_acc = bl_correct / bl_total

        new_correct = 0
        new_total = 0
        for p, y, row in zip(predictions, labels, rows):
            if slice_fn(row):
                new_total += 1
                if p["prediction"] == y:
                    new_correct += 1
        if new_total < 3:
            continue
        new_acc = new_correct / new_total

        if bl_acc - new_acc > threshold:
            collapsed.append(slice_name)

    return len(collapsed) > 0, collapsed


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def calibration_table(predictions: list[dict], labels: list[Any], n_bins: int = 10) -> list[dict]:
    """Compute a reliability/calibration table.

    Buckets predictions by predicted probability, computes actual
    correct rate per bin.
    """
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, y in zip(predictions, labels):
        prob = float(p.get("probability", 0.5))
        correct = p["prediction"] == y
        bucket = min(int(prob * n_bins), n_bins - 1)
        bins[bucket].append((prob, correct))

    table: list[dict] = []
    for i, b in enumerate(bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        if not b:
            table.append(
                {
                    "bin": f"{lo:.1f}-{hi:.1f}",
                    "count": 0,
                    "mean_predicted": None,
                    "actual_rate": None,
                }
            )
            continue
        mean_pred = sum(x[0] for x in b) / len(b)
        actual = sum(1 for x in b if x[1]) / len(b)
        table.append(
            {
                "bin": f"{lo:.1f}-{hi:.1f}",
                "count": len(b),
                "mean_predicted": round(mean_pred, 3),
                "actual_rate": round(actual, 3),
            }
        )
    return table


def print_calibration(table: list[dict]) -> None:
    """Print the calibration table to stdout."""
    print("\n=== Calibration (reliability curve) ===")
    hdr = f"{'Bin':<12} {'Count':>6} {'Predicted':>10} {'Actual':>10} {'Gap':>8}"
    print(hdr)
    print("-" * 48)
    for row in table:
        if row["count"] == 0:
            print(f"{row['bin']:<12} {0:>6}")
            continue
        gap = row["actual_rate"] - row["mean_predicted"]
        print(
            f"{row['bin']:<12} {row['count']:>6} "
            f"{row['mean_predicted']:>10.3f} {row['actual_rate']:>10.3f} "
            f"{gap:>+8.3f}"
        )


# ---------------------------------------------------------------------------
# Error analysis via Jev
# ---------------------------------------------------------------------------


def error_analysis(
    misses: list[dict],
    program: Any,
    config: HarnessConfig,
    max_misses: int = 20,
) -> dict[str, int]:
    """Classify misses into error categories using Jev.

    Categories: state_lacked_evidence, criteria_ambiguous, wrong_primitive,
    label_noise.

    Returns a count dict.
    """
    categories = {
        "state_lacked_evidence": 0,
        "criteria_ambiguous": 0,
        "wrong_primitive": 0,
        "label_noise": 0,
    }
    if not misses:
        return categories

    sample = misses[:max_misses]
    for miss in sample:
        row = miss.get("row", {})
        answers = miss.get("answers", {})
        state = {
            "row_summary": json.dumps({k: v for k, v in row.items() if k != "y"}, default=str)[:2000],
            "predicted": str(miss.get("prediction")),
            "actual": str(miss.get("label")),
            "answer_probabilities": json.dumps(answers, default=str)[:2000],
        }
        questions = {
            "error_class": {
                "type": "choice",
                "instructions": (
                    "Why did the prediction fail? The state, predicted value, "
                    "actual value, and answer probabilities are shown. "
                    "Classify the root cause."
                ),
                "criteria": {
                    "state_lacked_evidence": (
                        "The state did not contain enough information to predict "
                        "correctly. A key signal was missing or not computed."
                    ),
                    "criteria_ambiguous": (
                        "The question criteria were vague or did not distinguish "
                        "the correct answer from the incorrect one."
                    ),
                    "wrong_primitive": (
                        "The question type (Noul/Choice/Score) was wrong for "
                        "this decision, or the options were poorly structured."
                    ),
                    "label_noise": (
                        "The label appears incorrect or the outcome was "
                        "genuinely unpredictable from available evidence."
                    ),
                },
            },
        }
        try:
            result = config.jev_caller(state, questions)
            ec = result.get("error_class", {})
            pick = ec.get("choice", "state_lacked_evidence")
            if pick in categories:
                categories[pick] += 1
            else:
                categories["state_lacked_evidence"] += 1
        except Exception:
            categories["state_lacked_evidence"] += 1

    return categories


def _pick_next_lever(error_counts: dict[str, int], levers: dict[str, list], tried: set[str]) -> str | None:
    """Pick the next lever to try based on error analysis."""
    lever_names = list(levers.keys())
    untried = [lev for lev in lever_names if lev not in tried]
    if not untried:
        return None

    dominant = max(error_counts, key=lambda k: error_counts[k])
    for lever in untried:
        ll = lever.lower()
        if dominant == "state_lacked_evidence" and any(w in ll for w in ("signal", "evidence", "k_")):
            return lever
        if dominant == "criteria_ambiguous" and any(w in ll for w in ("criteria", "wording")):
            return lever
        if dominant == "wrong_primitive" and any(w in ll for w in ("decomp", "primitive")):
            return lever

    return untried[0]


# ---------------------------------------------------------------------------
# Sanity floors
# ---------------------------------------------------------------------------


def sanity_floors(split: Split) -> dict[str, float]:
    """Compute coin-flip and majority-class accuracy on dev."""
    dev = split.dev
    if not dev:
        return {"coin_flip": 0.5, "majority_class": 0.5}

    labels = [row["y"] for row in dev]
    from collections import Counter

    counts = Counter(labels)
    majority = counts.most_common(1)[0][1]
    return {
        "coin_flip": 0.5,
        "majority_class": majority / len(labels),
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_loop(config: HarnessConfig) -> dict:
    """Run the full improvement loop. Returns the final report dict."""
    run_dir = Path(config.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_log = RunLog()
    run_id = f"harness_{int(time.time())}"

    program = load_program(config.program_path)
    rows = load_labels(config.labels_path)
    split = make_split(rows, config)

    print(f"[harness] Loaded {len(rows)} rows: train={len(split.train)}, dev={len(split.dev)}, test={len(split.test)}")

    floors = sanity_floors(split)
    print(
        f"[harness] Sanity floors -- coin flip: {floors['coin_flip']:.3f}, "
        f"majority class: {floors['majority_class']:.3f}"
    )

    # Signal discovery
    print("[harness] Running signal discovery on train...")
    signals = signal_discovery(program, split, config)
    signal_path = run_dir / "signal_table.json"
    signal_path.write_text(json.dumps(signals[:50], indent=2), encoding="utf-8")
    if signals:
        print("[harness] Top 5 signals by |corr|:")
        for s in signals[:5]:
            print(f"  {s['signal']:<40} r={s['correlation']:+.4f}  n={s['n']}")

    base_ctx: dict[str, Any] = {}
    dev_labels = [row["y"] for row in split.dev]

    # Policy first: score the deterministic rules alone and size the residual.
    policy_report = policy_alone(program, split.dev, base_ctx, config.graders)
    if policy_report:
        print(
            f"[harness] Policy alone: {_fmt_metrics(policy_report['metrics_on_sure'])} on {policy_report['sure']} sure rows; "
            f"residual {policy_report['residual']}/{len(split.dev)} ({policy_report['residual_share']:.0%}) goes to Jev"
        )
        run_log.append(
            {
                "round": 0,
                "lever": "policy",
                "variant": None,
                "metrics": policy_report,
                "kept": True,
                "reason": "rules alone",
            }
        )

    # Baseline on dev (combined: policy on sure rows, Jev on the residual)
    print("[harness] Running baseline on dev...")
    base_preds = run_predictions(program, split.dev, base_ctx, config)
    base_metrics = grade(base_preds, dev_labels, config.graders)

    print(f"[harness] Baseline: {_fmt_metrics(base_metrics)}")
    run_log.append(
        {
            "round": 0,
            "lever": "baseline",
            "variant": None,
            "metrics": base_metrics,
            "kept": True,
            "reason": "baseline",
        }
    )

    _try_record_harness_run(
        run_id=run_id,
        program=config.program_path,
        round=0,
        lever="baseline",
        variant="baseline",
        metric_accuracy=base_metrics.get("accuracy"),
        metric_brier=base_metrics.get("brier"),
        metric_f1=base_metrics.get("f1"),
        kept=True,
    )

    # Improvement loop
    current_ctx = copy.deepcopy(base_ctx)
    current_metrics = base_metrics
    current_preds = base_preds
    levers = getattr(program, "LEVERS", {})
    tried_levers: set[str] = set()

    for round_num in range(1, config.max_rounds + 1):
        print(f"\n[harness] === Round {round_num} ===")

        misses = []
        for pred, row in zip(current_preds, split.dev):
            if pred["prediction"] != row["y"]:
                misses.append(
                    {
                        "row": row,
                        "prediction": pred["prediction"],
                        "probability": pred.get("probability"),
                        "label": row["y"],
                        "answers": pred.get("answers", {}),
                    }
                )

        print(f"[harness] {len(misses)} misses on dev")

        error_counts = error_analysis(misses, program, config)
        print(f"[harness] Error analysis: {error_counts}")

        lever_name = _pick_next_lever(error_counts, levers, tried_levers)
        if lever_name is None:
            print("[harness] All levers tried. Stopping.")
            break
        tried_levers.add(lever_name)

        variants = levers[lever_name]
        print(f"[harness] Trying lever '{lever_name}' ({len(variants)} variants)")

        improved_this_round = False
        for vi, variant in enumerate(variants):
            print(f"  Variant {vi}: {variant}")
            trial_ctx = copy.deepcopy(current_ctx)
            if isinstance(variant, dict):
                trial_ctx.update(variant)
            else:
                trial_ctx[lever_name] = variant

            trial_preds = run_predictions(program, split.dev, trial_ctx, config)
            trial_metrics = grade(trial_preds, dev_labels, config.graders)

            improved = _is_improvement(trial_metrics, current_metrics, config.graders)

            collapsed, collapsed_names = check_slice_collapse(
                program,
                split.dev,
                trial_preds,
                dev_labels,
                current_preds,
                dev_labels,
            )

            kept = improved and not collapsed
            reason = "improved" if kept else ""
            if not improved:
                reason = "no improvement"
            if collapsed:
                reason = f"slice collapse: {collapsed_names}"

            status = "KEPT" if kept else "rejected"
            print(f"    {_fmt_metrics(trial_metrics)} -- {status} ({reason})")

            run_log.append(
                {
                    "round": round_num,
                    "lever": lever_name,
                    "variant": str(variant),
                    "metrics": trial_metrics,
                    "kept": kept,
                    "reason": reason,
                }
            )

            _try_record_harness_run(
                run_id=run_id,
                program=config.program_path,
                round=round_num,
                lever=lever_name,
                variant=str(variant),
                metric_accuracy=trial_metrics.get("accuracy"),
                metric_brier=trial_metrics.get("brier"),
                metric_f1=trial_metrics.get("f1"),
                kept=kept,
                reason=reason,
            )

            if kept:
                current_ctx = trial_ctx
                current_metrics = trial_metrics
                current_preds = trial_preds
                improved_this_round = True
                break

        if not improved_this_round:
            print(f"[harness] No variant improved on lever '{lever_name}'.")

    # Final: test set (touched once)
    print("\n[harness] === Final: test set (touched once) ===")
    test_labels = [row["y"] for row in split.test]
    if split.test:
        test_preds = run_predictions(program, split.test, current_ctx, config)
        test_metrics = grade(test_preds, test_labels, config.graders)
        print(f"[harness] Test: {_fmt_metrics(test_metrics)}")

        cal_table = calibration_table(test_preds, test_labels)
        print_calibration(cal_table)
    else:
        test_metrics = {}
        test_preds = []
        cal_table = []
        print("[harness] No test data.")

    # Write outputs
    run_log.write(run_dir / "run_log.json")

    final_error: dict[str, int] = {}
    if split.dev:
        final_misses = [
            {
                "row": row,
                "prediction": p["prediction"],
                "label": row["y"],
                "answers": p.get("answers", {}),
            }
            for p, row in zip(current_preds, split.dev)
            if p["prediction"] != row["y"]
        ]
        final_error = error_analysis(final_misses, program, config)

    report = {
        "run_id": run_id,
        "program": config.program_path,
        "split_sizes": {
            "train": len(split.train),
            "dev": len(split.dev),
            "test": len(split.test),
        },
        "sanity_floors": floors,
        "signals_top_15": signals[:15],
        "baseline_metrics": base_metrics,
        "final_dev_metrics": current_metrics,
        "test_metrics": test_metrics,
        "calibration": cal_table,
        "rounds": len(run_log.entries) - 1,
        "levers_kept": [e for e in run_log.entries if e.get("kept") and e.get("lever") != "baseline"],
        "error_analysis_final": final_error,
    }

    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n[harness] Report written to {report_path}")

    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_improvement(new: dict[str, float], old: dict[str, float], graders: list[str]) -> bool:
    """True if new metrics improve on old.

    Accuracy: higher is better. Brier: lower is better. F1: higher is better.
    Primary metric is the first grader; ties broken by secondary.
    """
    for g in graders:
        nv = new.get(g, float("nan"))
        ov = old.get(g, float("nan"))
        if math.isnan(nv) or math.isnan(ov):
            continue
        if g == "brier":
            if nv < ov - 1e-6:
                return True
            if nv > ov + 1e-6:
                return False
        else:
            if nv > ov + 1e-6:
                return True
            if nv < ov - 1e-6:
                return False
    return False


def _fmt_metrics(m: dict[str, float]) -> str:
    """Format metrics dict for display."""
    parts = []
    for k, v in m.items():
        if isinstance(v, float) and not math.isnan(v):
            parts.append(f"{k}={v:.4f}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Judge variance
# ---------------------------------------------------------------------------


def judge_variance(
    program: Any,
    rows: list[dict],
    ctx: dict[str, Any],
    jev_caller: Callable[[dict, dict], dict],
    n_repeats: int = 10,
) -> dict:
    """Re-ask the same frozen rows N times and measure judge consistency.

    For each row, build state and questions once, call ``jev_caller`` N
    times, and collect the top probability per answer key across repeats.
    Reports per-row std of the top probability and whether the argmax
    (the key with the highest probability) flipped between repeats.

    Args:
        program: A loaded Jev program module with ``build_state`` and ``questions``.
        rows: Labeled data rows.
        ctx: Context dict passed to program functions.
        jev_caller: ``(state, questions) -> answers`` callable.
        n_repeats: Number of repeated calls per row.

    Returns:
        Dict with ``per_row`` (list) and ``summary`` (aggregates).
    """
    per_row: list[dict] = []

    for i, row in enumerate(rows):
        state = program.build_state(row, ctx)
        questions = program.questions(row, ctx)

        # Collect per-answer-key top probabilities and argmax across repeats.
        key_top_probs: dict[str, list[float]] = {}
        argmaxes: list[str | None] = []

        for _ in range(n_repeats):
            try:
                answers = jev_caller(state, questions)
            except Exception:
                argmaxes.append(None)
                continue

            for qname, answer in answers.items():
                probs = answer.get("probabilities")
                if isinstance(probs, dict) and probs:
                    top_p = max(probs.values())
                    key_top_probs.setdefault(qname, []).append(top_p)
                elif "noul" in answer:
                    val = float(answer["noul"])
                    key_top_probs.setdefault(qname, []).append(val)

            # Determine the argmax across all answer keys' top choices.
            best_key: str | None = None
            best_val: float = -1.0
            for qname, answer in answers.items():
                probs = answer.get("probabilities")
                if isinstance(probs, dict) and probs:
                    top_choice = max(probs, key=lambda k: probs[k])  # type: ignore[arg-type]
                    top_val = probs[top_choice]
                    if top_val > best_val:
                        best_val = top_val
                        best_key = f"{qname}:{top_choice}"
                elif "noul" in answer:
                    val = float(answer["noul"])
                    label = f"{qname}:true" if val >= 0.5 else f"{qname}:false"
                    effective = val if val >= 0.5 else 1.0 - val
                    if effective > best_val:
                        best_val = effective
                        best_key = label
            argmaxes.append(best_key)

        # Compute per-key std, then aggregate per row.
        stds: list[float] = []
        for _qname, vals in key_top_probs.items():
            if len(vals) >= 2:
                mean_v = sum(vals) / len(vals)
                variance = sum((v - mean_v) ** 2 for v in vals) / len(vals)
                stds.append(math.sqrt(variance))
            else:
                stds.append(0.0)

        mean_std = sum(stds) / len(stds) if stds else 0.0
        max_std = max(stds) if stds else 0.0

        # Flip: argmax changed between any two repeats.
        valid_argmaxes = [a for a in argmaxes if a is not None]
        flipped = len(set(valid_argmaxes)) > 1 if valid_argmaxes else False

        per_row.append({"row_idx": i, "mean_std": mean_std, "max_std": max_std, "flipped": flipped})

    # Summary.
    if per_row:
        summary_mean_std = sum(r["mean_std"] for r in per_row) / len(per_row)
        summary_max_std = max(r["max_std"] for r in per_row)
        flip_count = sum(1 for r in per_row if r["flipped"])
        summary_flip_rate = flip_count / len(per_row)
    else:
        summary_mean_std = 0.0
        summary_max_std = 0.0
        summary_flip_rate = 0.0

    return {
        "per_row": per_row,
        "summary": {
            "mean_std": summary_mean_std,
            "max_std": summary_max_std,
            "flip_rate": summary_flip_rate,
        },
    }


# ---------------------------------------------------------------------------
# Threshold sweep and cost threshold
# ---------------------------------------------------------------------------


def cost_threshold(c_fp: float, c_fn: float) -> float:
    """Derive the optimal gate threshold from action costs.

    ``t = C_FP / (C_FP + C_FN)``
    """
    return c_fp / (c_fp + c_fn)


def threshold_sweep(
    predictions: list[dict],
    labels: list[Any],
    thresholds: list[float],
    c_fp: float = 1.0,
    c_fn: float = 1.0,
) -> list[dict]:
    """Sweep thresholds over predictions, reporting coverage, FP, FN, and cost per row.

    Probability is treated as the model's estimated P(label=1). For each threshold *t*:

    - acted = rows where ``probability >= t``
    - fp = acted rows where ``label == 0`` (false positive: acted, should not have)
    - fn = not-acted rows where ``label == 1`` (false negative: missed positive)
    - cost = ``(c_fp * fp + c_fn * fn) / n``

    Args:
        predictions: Each dict has ``probability`` (float in [0, 1]).
        labels: Binary labels (0 or 1), same length as predictions.
        thresholds: Threshold values to evaluate.
        c_fp: Cost per false positive.
        c_fn: Cost per false negative.

    Returns:
        List of dicts, one per threshold.
    """
    n = len(predictions)
    results: list[dict] = []
    for t in thresholds:
        acted = [(p, y) for p, y in zip(predictions, labels) if float(p.get("probability", 0.0)) >= t]
        fp = sum(1 for _p, y in acted if y == 0)
        fn = sum(1 for p, y in zip(predictions, labels) if float(p.get("probability", 0.0)) < t and y == 1)
        coverage = len(acted) / n if n > 0 else 0.0
        row_cost = (c_fp * fp + c_fn * fn) / n if n > 0 else 0.0
        results.append(
            {
                "threshold": t,
                "coverage": coverage,
                "fp": fp,
                "fn": fn,
                "cost": row_cost,
            }
        )
    return results
