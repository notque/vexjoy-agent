#!/usr/bin/env python3
"""Routing-loop value eval orchestrator (ADR: routing-loop-value-eval).

Two SEPARATE verdicts, never one gate:

  MECHANISM (Stage 1, deterministic, no model) — does the health re-rank policy
    fire correctly on constructed cases? REAL arm must change 0 routes (honest
    zero on live data); SYNTHETIC and TIEBREAK arms must show help>0, harm==0,
    force-route held. This is conformance, NOT value.

  VALUE (Stage 3, blind A/B) — does health re-rank beat pure semantic routing on
    the k health-affected cases? value_measured is true only when k>0 AND
    non-null health telemetry exists AND live health interventions exist. Today
    all three are false, so value_measured=false and the verdict is "unmeasured"
    — never PASS, never FAIL.

Stage 2 (no model) is a measurement-availability check: it counts recorded
decisions/outcomes/non-null-health and recorded_failures (routing-relevant
outcome=="failure" events only) in a read-only copy of route-events.jsonl and
decides whether faithful replay can run. Today it prints non_null_health=0
recorded_failures=0 and sets value_measured=false.

Exit codes (no consumer can mistake mechanism for value):
  0 = MECHANISM PASS AND value_measured AND VALUE PASS
  2 = MECHANISM PASS AND value_measured=false (today's expected outcome)
  1 = any MECHANISM clause fails, OR VALUE FAIL when measured

Writes research/forward-plan/route-value-eval-results.{md,json} (gitignored
working dir). Stage 3 needs live Haiku calls to produce real picks; --stage3-stub
runs the full stats path over a supplied scoreboard so the pipeline is verifiable
offline. Without a scoreboard, Stage 3 reports value_measured=false.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SCRIPTS = _REPO_ROOT / "scripts"
_OUT_DIR = _REPO_ROOT / "research" / "forward-plan"
_DEFAULT_EVENTS = Path.home() / ".claude" / "learning" / "route-events.jsonl"

# Stage-2 gate: faithful per-decision replay runs only with enough non-null
# health AND at least one recorded failure. Pre-registered, fixed before any run.
MIN_NON_NULL_HEALTH = 20


def _load_module(name: str, filename: str):
    """Import a hyphenated script as a module (the test_health_replay shim)."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Stage 1 — deterministic mechanism gate (reuses route-replay.run_replay)
# --------------------------------------------------------------------------- #
def run_stage1(
    ab_path: Path | None = None,
    benchmark_path: Path | None = None,
    db_dir: Path | None = None,
    real_weights: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the three-arm replay and apply the MECHANISM thresholds.

    Returns the replay result plus a `mechanism` block with per-clause pass flags
    and the overall mechanism_pass. REAL must change 0 routes; SYNTHETIC and
    TIEBREAK must each show help>0, harm==0, force-route held == force count.
    """
    rr = _load_module("route_replay", "route-replay.py")
    kwargs: dict[str, Any] = {}
    ab = ab_path if ab_path is not None else rr._AB_CORPUS
    bm = benchmark_path if benchmark_path is not None else rr._BENCHMARK
    kwargs["ab_path"] = ab
    kwargs["benchmark_path"] = bm
    if db_dir is not None:
        kwargs["db_dir"] = db_dir
    if real_weights is not None:
        kwargs["real_weights"] = real_weights
    result = rr.run_replay(**kwargs)

    # Force-route case count, counted independently from the corpora + manifest
    # flags — so the held clause is a real equality, not a tautology against the
    # arm's own held tally.
    force_total = _force_case_count(rr, ab, bm)

    real, syn, tb = result["real"], result["synthetic"], result["tiebreak"]
    clauses = {
        "real_changed_zero": real["changed"] == 0,
        "synthetic_help_positive": syn["help"] > 0,
        "synthetic_harm_zero": syn["harm"] == 0,
        "synthetic_force_route_held": syn["force_route_held"] == force_total,
        "tiebreak_help_positive": tb["help"] > 0,
        "tiebreak_harm_zero": tb["harm"] == 0,
        "tiebreak_force_route_held": tb["force_route_held"] == force_total,
    }
    result["force_case_count"] = force_total
    result["mechanism"] = {
        "clauses": clauses,
        "mechanism_pass": all(clauses.values()),
        "failing_clauses": [k for k, v in clauses.items() if not v],
    }
    return result


def _force_case_count(rr, ab_path: Path, benchmark_path: Path) -> int:
    """Count gold-bearing corpus cases whose skill is force-routed (manifest flags).

    Independent of the replay's held tally, so the held==force_total clause is a
    genuine equality check, not held==held.
    """
    cases = rr.load_corpus(ab_path) + rr.load_corpus(benchmark_path)
    flags = rr.force_route_skills()
    count = 0
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        if gold.split(":", 1)[1] in flags:
            count += 1
    return count


# --------------------------------------------------------------------------- #
# Stage 2 — recorded-events measurement-availability check (no model)
# --------------------------------------------------------------------------- #
def run_stage2(events_path: Path | None = None) -> dict[str, Any]:
    """Read-only copy of route-events.jsonl; count and gate faithful replay.

    Counts decisions, outcomes, non-null health_at_decision, and recorded
    failures. A recorded failure is ONLY a routing-relevant outcome event with
    ``outcome=="failure"``: a real dispatch that ended in failure. Decision
    events contribute no failures — a decision's ``failure`` field is the weight
    row's historical failure_count snapshotted at decision time, not this
    dispatch's result, so counting it conflates history with outcome (finding
    [51]). Legacy outcome events without ``routing_relevant`` count as relevant;
    events explicitly ``routing_relevant: false`` are excluded.

    Faithful replay runs only when non_null_health >= MIN_NON_NULL_HEALTH AND
    recorded_failures > 0. Today it is skipped; the exact blocking numbers are
    returned. Neutral outcomes are censored (counted separately, excluded from
    value).
    """
    src = events_path if events_path is not None else _DEFAULT_EVENTS
    decisions = outcomes = non_null_health = recorded_failures = neutral = 0
    if src.exists():
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "route-events.jsonl"
            shutil.copyfile(src, copy)  # read-only: never touch the live file
            for line in copy.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = ev.get("type")
                if t == "decision":
                    decisions += 1
                    if ev.get("health_at_decision") is not None:
                        non_null_health += 1
                elif t == "outcome":
                    outcomes += 1
                    oc = ev.get("outcome")
                    # routing_relevant defaults True for legacy events; only an
                    # explicit False excludes the failure from the count.
                    if oc == "failure" and ev.get("routing_relevant", True):
                        recorded_failures += 1
                    elif oc == "neutral":
                        neutral += 1

    can_replay = non_null_health >= MIN_NON_NULL_HEALTH and recorded_failures > 0
    return {
        "events_path": str(src),
        "events_present": src.exists(),
        "decisions": decisions,
        "outcomes": outcomes,
        "non_null_health": non_null_health,
        "recorded_failures": recorded_failures,
        "neutral_censored": neutral,
        "min_non_null_health": MIN_NON_NULL_HEALTH,
        "faithful_replay_ran": can_replay,
        "skip_reason": (
            ""
            if can_replay
            else f"non_null_health={non_null_health} (<{MIN_NON_NULL_HEALTH}) "
            f"AND/OR recorded_failures={recorded_failures} (need >0)"
        ),
        # Stage 2 contributes NO value evidence; it is availability only.
        "value_measured": False,
    }


# --------------------------------------------------------------------------- #
# Stage 3 — blind A/B arms + alternate builder (Arm A vs health_adjust Arm B)
#
# build_alternates, compute_health_arms, build_judge_rows and
# _JUDGE_FORBIDDEN_FIELDS are the offline Stage-3 fixture-rebuild pipeline. They
# have no argparse CLI entry by design: live Stage 3 needs Haiku calls, so the
# fixture is built out-of-band by the rebuild scripts (build_fixture.py +
# build_judge.py), which import this module and call these symbols, then feed the
# resulting scoreboard back through --stage3-stub. They are NOT dead code; each
# is exercised by the rebuild tooling and unit-tested.
# --------------------------------------------------------------------------- #
def _gold_key(case: dict[str, Any]) -> str | None:
    skill = case.get("expected_skill")
    if not skill:
        return None
    agent = case.get("expected_agent") or "direct"
    return f"{agent}:{skill}"


def build_alternates(cases: list[dict[str, Any]], seed: int = 20260527) -> dict[int, list[str]]:
    """Per case, build a mixed alternate pool: gold-sibling routes (same bucket)
    AND at least one plausibly-WRONG route (gold for a different bucket). Mixing a
    wrong route in makes harm a real risk, so harm==0 is meaningful, not built-in.
    Deterministic given the seed. Keyed by case index.
    """
    rng = random.Random(seed)
    bucket_golds: dict[str, list[str]] = {}
    all_golds: list[str] = []
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        bucket = case.get("bucket") or case.get("category") or "default"
        bucket_golds.setdefault(bucket, [])
        if gold not in bucket_golds[bucket]:
            bucket_golds[bucket].append(gold)
        if gold not in all_golds:
            all_golds.append(gold)

    out: dict[int, list[str]] = {}
    for i, case in enumerate(cases):
        gold = _gold_key(case)
        if gold is None:
            continue
        bucket = case.get("bucket") or case.get("category") or "default"
        siblings = [k for k in bucket_golds.get(bucket, []) if k != gold]
        wrong_pool = [k for k in all_golds if k not in siblings and k != gold]
        alts: list[str] = list(siblings[:2])
        if wrong_pool:
            alts.append(rng.choice(wrong_pool))  # at least one plausibly-wrong route
        out[i] = alts
    return out


# Fields the judge prompt MUST NOT carry (codex 1/2/3/5). The judge sees ONLY
# the request and two candidate route picks; it never sees which arm produced a
# pick, the seed kind, weights, alternates, confidence, n, failure, or health.
_JUDGE_FORBIDDEN_FIELDS = frozenset(
    {
        "arm",
        "arm_label",
        "seed_kind",
        "weights",
        "synthetic_weights",
        "alternates",
        "confidence",
        "n",
        "failure",
        "health",
        "health_at_decision",
        "action",
        "bucket",
        "provenance",
    }
)


def compute_health_arms(
    semantic_picks: dict[int, dict[str, Any]],
    cases: list[dict[str, Any]],
    weights: dict[str, dict[str, Any]],
    force_flags: set[str],
    alternates: dict[int, list[str]] | None = None,
) -> dict[str, Any]:
    """Stage-3 live arm computation. Arm A = semantic pick; Arm B = health_adjust.

    semantic_picks: case index -> {"key": "agent:skill", "confidence": float} (the
    one Haiku decision per case, reused across both arms — the ADR's reuse rule).
    Arm B applies health_adjust(pick, mixed-alternates, synthetic-weights,
    force_flags) to Arm A's pick. Returns the per-case A/B picks and the indices of
    the k health-affected cases (Arm B pick != Arm A pick) — only those are scored.
    """
    from scripts.lib.route_policy import health_adjust

    alts = alternates if alternates is not None else build_alternates(cases)
    per_case: list[dict[str, Any]] = []
    health_affected: list[int] = []
    for i, _case in enumerate(cases):
        pick = semantic_picks.get(i)
        if pick is None:
            continue
        a_key = pick.get("key")
        adjusted = health_adjust(pick, alts.get(i, []), weights, force_flags)
        b_key = adjusted["final_pick"]
        affected = b_key != a_key
        if affected:
            health_affected.append(i)
        per_case.append(
            {
                "case_index": i,
                "a_pick": a_key,
                "b_pick": b_key,
                "action": adjusted["action"],
                "health_affected": affected,
            }
        )
    return {
        "per_case": per_case,
        "k_health_affected": len(health_affected),
        "health_affected_indices": health_affected,
    }


def build_judge_rows(
    arm_picks: dict[str, Any],
    cases: list[dict[str, Any]],
    seed: int = 20260527,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build arm-stripped, shuffled judge rows + a private uid->arm map.

    Only the k health-affected cases are scored. Each arm's pick becomes its own
    row carrying request text + the candidate pick ONLY — none of the forbidden
    fields. The uid-map (which the judge never sees) records the arm for rejoin.
    Mirrors routing-ab-test --build-judge (fixed-seed interleave).
    """
    rows: list[dict[str, Any]] = []
    uid_map: dict[str, dict[str, Any]] = {}
    uid = 0
    for rec in arm_picks["per_case"]:
        if not rec["health_affected"]:
            continue
        i = rec["case_index"]
        request = cases[i].get("request", "")
        for arm, pick_key in (("A", rec["a_pick"]), ("B", rec["b_pick"])):
            uid_str = f"u{uid:03d}"
            uid += 1
            agent, _, skill = (pick_key or "").partition(":")
            row = {"uid": uid_str, "query": request, "predicted_agent": agent or None, "predicted_skill": skill or None}
            assert _JUDGE_FORBIDDEN_FIELDS.isdisjoint(row.keys()), "judge row leaks a forbidden field"
            rows.append(row)
            uid_map[uid_str] = {"case_index": i, "arm": arm}
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows, uid_map


def compute_value_stats(
    per_case: list[dict[str, Any]],
    baseline_runs: list[list[bool]] | None = None,
    seed: int = 20260527,
    bootstrap_iters: int = 5000,
) -> dict[str, Any]:
    """Compute the VALUE verdict from per-case A/B correctness on the k cases.

    per_case: list of {"a_correct": bool, "b_correct": bool} for the k
    health-affected cases (Arm B pick != Arm A pick). Returns D, the 95% paired
    bootstrap CI, the McNemar p-value, harm count, and value_pass.
    """
    k = len(per_case)
    a = [bool(c["a_correct"]) for c in per_case]
    b = [bool(c["b_correct"]) for c in per_case]
    a_strict = sum(a)
    b_strict = sum(b)
    d = (b_strict - a_strict) / k if k else 0.0

    # Per-case harm: B wrong where A was right. Hard one-sided gate.
    harm = sum(1 for ai, bi in zip(a, b, strict=True) if ai and not bi)
    help_ = sum(1 for ai, bi in zip(a, b, strict=True) if (not ai) and bi)

    # Paired bootstrap CI on D (resample the k cases with replacement).
    ci_low = ci_high = 0.0
    if k:
        rng = random.Random(seed)
        deltas = []
        diffs = [int(bi) - int(ai) for ai, bi in zip(a, b, strict=True)]
        for _ in range(bootstrap_iters):
            sample = [diffs[rng.randrange(k)] for _ in range(k)]
            deltas.append(sum(sample) / k)
        deltas.sort()
        ci_low = deltas[int(0.025 * bootstrap_iters)]
        ci_high = deltas[min(int(0.975 * bootstrap_iters), bootstrap_iters - 1)]

    # McNemar exact (paired): discordant pairs b01 (A wrong, B right) vs b10.
    b01 = help_  # A wrong, B right
    b10 = harm  # A right, B wrong
    mcnemar_p = _mcnemar_exact_p(b01, b10)

    # Baseline variance: self-disagreement between two semantic-only runs.
    baseline_variance = None
    if baseline_runs and len(baseline_runs) >= 2 and k:
        r1, r2 = baseline_runs[0], baseline_runs[1]
        m = min(len(r1), len(r2), k)
        if m:
            baseline_variance = sum(1 for i in range(m) if r1[i] != r2[i]) / m

    value_pass = (
        k > 0
        and d > 0
        and ci_low > 0
        and mcnemar_p < 0.05
        and harm == 0
        and (baseline_variance is None or baseline_variance <= abs(d))
    )
    return {
        "k_health_affected": k,
        "arm_a_strict": a_strict,
        "arm_b_strict": b_strict,
        "D": d,
        "D_ci_low": ci_low,
        "D_ci_high": ci_high,
        "mcnemar_p": mcnemar_p,
        "harm": harm,
        "help": help_,
        "baseline_variance": baseline_variance,
        "value_pass": value_pass,
    }


def _mcnemar_exact_p(b01: int, b10: int) -> float:
    """Two-sided exact McNemar p over the n=b01+b10 discordant pairs (binomial,
    p=0.5). Returns 1.0 when there are no discordant pairs."""
    n = b01 + b10
    if n == 0:
        return 1.0
    k = min(b01, b10)
    # Two-sided: 2 * sum_{i=0..k} C(n,i) (0.5)^n, clamped to 1.
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    return min(1.0, 2.0 * tail)


def run_stage3(
    scoreboard_per_case: list[dict[str, Any]] | None = None,
    baseline_runs: list[list[bool]] | None = None,
    stage2_can_measure: bool = False,
) -> dict[str, Any]:
    """Stage 3 VALUE verdict.

    value_measured is true ONLY when k>0 AND non-null health telemetry exists AND
    live health interventions exist (stage2_can_measure) AND a real scored
    per-case set is supplied. Without those, value is unmeasured (never PASS,
    never FAIL). The full stats path runs whenever per-case data is supplied (the
    --stage3-stub offline path), but value_measured stays false unless the live
    telemetry preconditions also hold.
    """
    if not scoreboard_per_case:
        return {
            "value_measured": False,
            "value_verdict": "unmeasured",
            "reason": "no scored A/B per-case data (Stage 3 needs live Haiku picks; "
            "run --emit-prompts/--score/--build-judge/--rejoin then pass the scoreboard)",
            "k_health_affected": 0,
            "D": None,
            "D_ci_low": None,
            "D_ci_high": None,
            "mcnemar_p": None,
            "baseline_variance": None,
        }

    stats = compute_value_stats(scoreboard_per_case, baseline_runs=baseline_runs)
    value_measured = bool(stats["k_health_affected"] > 0 and stage2_can_measure)
    if not value_measured:
        verdict = "unmeasured"
    else:
        verdict = "pass" if stats["value_pass"] else "fail"
    return {
        "value_measured": value_measured,
        "value_verdict": verdict,
        "reason": (
            "value measured over k health-affected cases"
            if value_measured
            else "stats computed on supplied per-case set, but live health telemetry "
            "preconditions are unmet (non-null health + live interventions) — value unmeasured"
        ),
        **stats,
    }


# --------------------------------------------------------------------------- #
# Orchestrator — combine verdicts, write results, set exit code
# --------------------------------------------------------------------------- #
def orchestrate(
    events_path: Path | None = None,
    stage3_per_case: list[dict[str, Any]] | None = None,
    baseline_runs: list[list[bool]] | None = None,
) -> dict[str, Any]:
    """Run all stages and assemble the two-verdict result dict + exit code."""
    s1 = run_stage1()
    s2 = run_stage2(events_path)
    stage2_can_measure = bool(s2["non_null_health"] >= MIN_NON_NULL_HEALTH and s2["recorded_failures"] > 0)
    s3 = run_stage3(stage3_per_case, baseline_runs=baseline_runs, stage2_can_measure=stage2_can_measure)

    mechanism_pass = s1["mechanism"]["mechanism_pass"]
    value_measured = s3["value_measured"]
    value_verdict = s3["value_verdict"]

    if not mechanism_pass:
        exit_code = 1
    elif not value_measured:
        exit_code = 2
    elif value_verdict == "pass":
        exit_code = 0
    else:
        exit_code = 1

    return {
        "mechanism_verdict": "pass" if mechanism_pass else "fail",
        "value_measured": value_measured,
        "value_verdict": value_verdict,
        "D": s3.get("D"),
        "D_ci_low": s3.get("D_ci_low"),
        "D_ci_high": s3.get("D_ci_high"),
        "mcnemar_p": s3.get("mcnemar_p"),
        "k_health_affected": s3.get("k_health_affected", 0),
        "baseline_variance": s3.get("baseline_variance"),
        "neutral_censored": s2["neutral_censored"],
        "exit_code": exit_code,
        "stage1": s1,
        "stage2": s2,
        "stage3": s3,
    }


def render_markdown(res: dict[str, Any]) -> str:
    """Render the two-verdict result as a Dense-Complete Markdown table."""
    s1, s2, s3 = res["stage1"], res["stage2"], res["stage3"]
    real, syn, tb = s1["real"], s1["synthetic"], s1["tiebreak"]
    mech = s1["mechanism"]
    lines = [
        "# Route Value Eval — Two Verdicts",
        "",
        "Mechanism (deterministic) and value (blind A/B) are SEPARATE verdicts. A",
        "synthetic mechanism pass is never production value.",
        "",
        f"- **mechanism_verdict**: {res['mechanism_verdict'].upper()}",
        f"- **value_measured**: {str(res['value_measured']).lower()}",
        f"- **value_verdict**: {res['value_verdict']}",
        f"- **exit_code**: {res['exit_code']}  "
        "(0=mechanism+value pass; 2=mechanism pass, value unmeasured; 1=mechanism fail or value fail)",
        "",
        "## Stage 1 — MECHANISM (no model)",
        "",
        "| arm | evaluated | changed | help | harm | force-route held |",
        "|-----|-----------|---------|------|------|------------------|",
        f"| REAL | {real['evaluated']} | {real['changed']} | {real['help']} | {real['harm']} | - |",
        f"| SYNTHETIC | {syn['evaluated']} | {syn['changed']} | {syn['help']} | {syn['harm']} | {syn['force_route_held']} |",
        f"| TIEBREAK | {tb['evaluated']} | {tb['changed']} | {tb['help']} | {tb['harm']} | {tb['force_route_held']} |",
        "",
        f"Mechanism clauses: {json.dumps(mech['clauses'])}",
        f"Failing clauses: {mech['failing_clauses'] or 'none'}",
        "",
        "REAL changes 0 routes — the honest-zero finding on live data (demote floor",
        "unreachable: live rows are >=0.5 confidence, 0 failures). SYNTHETIC and",
        "TIEBREAK prove the branches fire on constructed cases ONLY (conformance).",
        "",
        "## Stage 2 — recorded-events availability (no model)",
        "",
        f"- decisions: {s2['decisions']}",
        f"- outcomes: {s2['outcomes']}",
        f"- non_null_health: {s2['non_null_health']} (need >= {s2['min_non_null_health']})",
        f"- recorded_failures: {s2['recorded_failures']} (need > 0)",
        f"- neutral_censored: {s2['neutral_censored']}",
        f"- faithful_replay_ran: {str(s2['faithful_replay_ran']).lower()}",
        f"- skip_reason: {s2['skip_reason'] or 'n/a (ran)'}",
        "",
        "Stage 2 contributes NO value evidence. It is a measurement-availability",
        "check. Neutral outcomes are censored (pre-registered), excluded from value.",
        "",
        "## Stage 3 — VALUE (blind A/B)",
        "",
        f"- value_measured: {str(s3['value_measured']).lower()}",
        f"- value_verdict: {s3['value_verdict']}",
        f"- k_health_affected: {s3.get('k_health_affected', 0)}",
        f"- D: {s3.get('D')}",
        f"- D 95% CI: [{s3.get('D_ci_low')}, {s3.get('D_ci_high')}]",
        f"- McNemar p: {s3.get('mcnemar_p')}",
        f"- baseline_variance: {s3.get('baseline_variance')}",
        f"- reason: {s3.get('reason', '')}",
        "",
        "Value PASS requires D>0 AND CI lower bound>0 AND McNemar p<0.05 AND harm==0.",
        "Today value is UNMEASURED: 0 non-null health, 0 recorded failures, k=0.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Routing-loop value evaluation (two verdicts).")
    parser.add_argument("--out-dir", type=Path, default=_OUT_DIR)
    parser.add_argument("--events", type=Path, default=None, help="route-events.jsonl path (read-only).")
    parser.add_argument(
        "--stage3-stub",
        type=Path,
        default=None,
        help="JSON file with {per_case:[{a_correct,b_correct}], baseline_runs:[[...],[...]]} "
        "to run the Stage-3 stats path offline (no LLM).",
    )
    args = parser.parse_args(argv)

    stage3_per_case = None
    baseline_runs = None
    if args.stage3_stub is not None:
        stub = json.loads(args.stage3_stub.read_text(encoding="utf-8"))
        stage3_per_case = stub.get("per_case")
        baseline_runs = stub.get("baseline_runs")

    res = orchestrate(events_path=args.events, stage3_per_case=stage3_per_case, baseline_runs=baseline_runs)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "route-value-eval-results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    (out_dir / "route-value-eval-results.md").write_text(render_markdown(res), encoding="utf-8")

    print(
        f"mechanism_verdict={res['mechanism_verdict']} value_measured={str(res['value_measured']).lower()} "
        f"value_verdict={res['value_verdict']}"
    )
    s2 = res["stage2"]
    print(
        f"Stage 2: non_null_health={s2['non_null_health']} recorded_failures={s2['recorded_failures']} "
        f"value_measured={str(res['value_measured']).lower()}"
    )
    # Exit 1 has two distinct causes; name which one on stderr so an automated
    # consumer can tell them apart without parsing the JSON output (finding [81]).
    if res["mechanism_verdict"] == "fail":
        print(f"MECHANISM FAIL: {res['stage1']['mechanism']['failing_clauses']}", file=sys.stderr)
    elif res["value_measured"] and res["value_verdict"] == "fail":
        ci_low, ci_high = res.get("D_ci_low"), res.get("D_ci_high")
        print(f"VALUE FAIL: D={res.get('D')} CI=[{ci_low},{ci_high}] mcnemar_p={res.get('mcnemar_p')}", file=sys.stderr)
    print(f"exit_code={res['exit_code']}")
    print(f"Wrote {out_dir / 'route-value-eval-results.md'} and .json")
    return res["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
