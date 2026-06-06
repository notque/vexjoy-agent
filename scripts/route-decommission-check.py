#!/usr/bin/env python3
"""Routing-loop decommission check (ADR: routing-loop-value-eval).

One question: should the outcome-routing shadow loop be removed today? The
answer is a count-based, shadow-inclusive verdict with an exit code — not prose.

Clock start = the Stage-0 wiring-fix commit (d943ba74, 2026-06-06 21:21:07 UTC),
hardcoded below. "Post-fix" events are decision/outcome events with ts >= that
epoch; pre-fix events are ignored (their health field was never wired).

Verdicts (the trigger contract):
  KEEP          interventions > 0 (real OR shadow). The loop demonstrably fires;
                keep it. Exit 0.
  DELETE        zero interventions AND the clock is valid AND
                (elapsed >= 90 days OR post-fix decisions >= 3000). The negative
                result is trustworthy: remove the loop. Exit 3.
  ACCRUING      zero interventions, clock valid, neither threshold reached.
                Keep collecting; prints exact remaining days/decisions. Exit 0.
  CLOCK-INVALID the recorded telemetry cannot support a DELETE/KEEP decision:
                post-fix INSTRUMENTED rate < 95% OR outcome unknown_rate > 5%.
                The zero cannot be trusted. Exit 4.

interventions:
  real    = decision events whose recorded `action` is demote or tiebreak (the
            router actually re-ranked the route).
  shadow  = replay `route_policy.health_adjust` on the RECORDED gate inputs of
            each decision (health_at_decision, n, failure, alternates); count
            where the replay action is demote or tiebreak. Gate inputs are read
            as recorded — never re-derived from current weights (ADR codex 29).
            Recorded alternates that carry their own weight fields let the shadow
            replay prefer them; bare-key alternates have no weight row, so the
            shadow replay cannot fire toward them (honest zero, not a hidden one).

Clock validity (else the zero is not trustworthy). Three instrumentation states,
keyed on what the do-route marker carried:
  (a) numeric  health=<float>  -> health_at_decision float.
  (b) no-row   health=-        -> health null, gate_inputs_present true. The pick
               had NO weight row — valid, expected data. Most live picks are
               state (b); reading it as missing kept the clock unreachable
               forever (the soundness gap this fixes).
  (c) legacy   no health= token -> health null, gate_inputs_present false/absent.
               The marker never carried a gate input (pre-fix / missing wiring).
  instrumented_rate = (a + b) / total post-fix decisions; must be >= 95%. Only
                 state (c) counts against it. The validity signal is "marker
                 carried gate inputs (incl. '-')", NOT "non-null health".
  unknown_rate = post-fix decisions with no joinable outcome / total post-fix
                 decisions; must be <= 5%. Join key (ADR): session id, nearest
                 preceding decision in that session.

Read-only: the default events path is the live route-events.jsonl; it is never
written. Tests pass explicit temp paths.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib.route_policy import health_adjust

# Clock start: the Stage-0 wiring-fix commit (records health gate inputs on the
# do-route marker). `git show -s --format=%ct d943ba74` == 1780780867.
STAGE0_FIX_COMMIT = "d943ba74"
STAGE0_FIX_EPOCH = 1780780867  # 2026-06-06 21:21:07 +0000

# DELETE thresholds (pre-registered, fixed before any run).
DELETE_DAYS = 90
DELETE_DECISIONS = 3000

# Clock-validity gates (else CLOCK-INVALID).
# instrumented = decision carried gate inputs on the marker: state (a) numeric
# health OR state (b) `health=-` (pick had no weight row — valid, expected). Only
# state (c) (no `health=` token on the marker, legacy/missing wiring) counts
# against this rate. Reading non-null health as the signal kept the clock
# unreachable forever, because most picks are state (b) (the soundness fix).
MIN_INSTRUMENTED_RATE = 0.95
MAX_UNKNOWN_RATE = 0.05

_DEFAULT_EVENTS = Path.home() / ".claude" / "learning" / "route-events.jsonl"
_SECONDS_PER_DAY = 86400


def _iter_events(events_path: Path):
    """Yield parsed events from a JSONL file. Skips blank/corrupt lines.

    Read-only: opens for reading, never writes. Missing file yields nothing.
    """
    if not events_path.exists():
        return
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _shadow_action(decision: dict[str, Any]) -> str:
    """Replay health_adjust on a decision's RECORDED gate inputs.

    Builds the weight map from what the decision recorded — the picked pair's
    {confidence=health_at_decision, n, failure} and any alternate that carries
    its own weight fields. Returns the replay action (keep | demote | tiebreak).
    Never reads current weights.
    """
    health = decision.get("health_at_decision")
    if health is None:
        return "keep"  # no health recorded => nothing to replay
    agent = decision.get("agent") or "direct"
    skill = decision.get("skill") or ""
    pick_key = f"{agent}:{skill}"
    weights: dict[str, dict[str, Any]] = {
        pick_key: {
            "confidence": health,
            "n": decision.get("n") or 0,
            "success": 0,
            "failure": decision.get("failure") or 0,
        }
    }
    alt_keys: list[str] = []
    for alt in decision.get("alternates") or []:
        if isinstance(alt, dict) and "key" in alt:
            k = alt["key"]
            weights[k] = {
                "confidence": alt.get("confidence", 0.0),
                "n": alt.get("n", 0),
                "success": alt.get("success", 0),
                "failure": alt.get("failure", 0),
            }
            alt_keys.append(k)
        elif isinstance(alt, str):
            alt_keys.append(alt)  # bare key: no weight row, cannot be preferred
    pick = {"key": pick_key, "confidence": health}
    return health_adjust(pick, alt_keys, weights, set())["action"]


def count_post_fix(events_path: Path) -> dict[str, Any]:
    """Count post-fix interventions, health rate, and outcome unknown rate.

    real_demote/real_tiebreak come from the recorded `action`; shadow_* from the
    health_adjust replay on recorded gate inputs. health_rate = non-null health /
    decisions. unknown_rate = decisions with no joinable outcome / decisions
    (join: nearest preceding decision in the same session).
    """
    decisions: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for ev in _iter_events(events_path):
        if ev.get("ts", 0) < STAGE0_FIX_EPOCH:
            continue
        t = ev.get("type")
        if t == "decision":
            decisions.append(ev)
        elif t == "outcome":
            outcomes.append(ev)

    real_demote = real_tiebreak = 0
    shadow_demote = shadow_tiebreak = 0
    state_a = state_b = state_c = 0
    for d in decisions:
        action = d.get("action")
        if action == "demote":
            real_demote += 1
        elif action == "tiebreak":
            real_tiebreak += 1
        state_a, state_b, state_c = _bump_state(d, state_a, state_b, state_c)
        sa = _shadow_action(d)
        if sa == "demote":
            shadow_demote += 1
        elif sa == "tiebreak":
            shadow_tiebreak += 1

    n_dec = len(decisions)
    # instrumented = state (a) + state (b): the marker carried the gate input.
    # Only state (c) (no gate input) counts against the 95% rate.
    instrumented = state_a + state_b
    instrumented_rate = (instrumented / n_dec) if n_dec else 0.0
    joined = _count_joined(decisions, outcomes)
    unknown_rate = ((n_dec - joined) / n_dec) if n_dec else 1.0

    interventions = real_demote + real_tiebreak + shadow_demote + shadow_tiebreak
    return {
        "post_fix_decisions": n_dec,
        "post_fix_outcomes": len(outcomes),
        "state_a_numeric": state_a,
        "state_b_norow": state_b,
        "state_c_legacy": state_c,
        "instrumented": instrumented,
        "instrumented_rate": round(instrumented_rate, 4),
        "joined_outcomes": joined,
        "unknown_rate": round(unknown_rate, 4),
        "real_demote": real_demote,
        "real_tiebreak": real_tiebreak,
        "shadow_demote": shadow_demote,
        "shadow_tiebreak": shadow_tiebreak,
        "interventions": interventions,
    }


def _bump_state(d: dict[str, Any], a: int, b: int, c: int) -> tuple[int, int, int]:
    """Classify one decision into the three instrumentation states.

    (a) numeric: health_at_decision is non-null (marker carried a real score).
    (b) no-row : health null AND gate_inputs_present true (marker said `health=-`;
        the pick had no weight row — valid, expected data).
    (c) legacy : neither (no `health=` token on the marker; pre-fix / missing
        wiring). A legacy event with no gate_inputs_present key lands here.
    """
    if d.get("health_at_decision") is not None:
        return a + 1, b, c
    if d.get("gate_inputs_present"):
        return a, b + 1, c
    return a, b, c + 1


def _count_joined(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> int:
    """Count decisions that join an outcome by session (nearest preceding).

    Each outcome attaches to the latest decision in its session at or before the
    outcome ts. A decision counts as joined once at least one outcome attaches to
    it. Mirrors the ADR join key (session id + nearest preceding decision).
    """
    by_session: dict[str, list[tuple[float, int]]] = {}
    for idx, d in enumerate(decisions):
        by_session.setdefault(d.get("session", ""), []).append((d.get("ts", 0.0), idx))
    for lst in by_session.values():
        lst.sort()
    joined_idx: set[int] = set()
    for o in outcomes:
        sess = o.get("session", "")
        lst = by_session.get(sess)
        if not lst:
            continue
        o_ts = o.get("ts", 0.0)
        cand = None
        for ts, idx in lst:
            if ts <= o_ts:
                cand = idx
            else:
                break
        if cand is not None:
            joined_idx.add(cand)
    return len(joined_idx)


def clock_valid(stats: dict[str, Any]) -> tuple[bool, str]:
    """True iff the recorded telemetry can support a DELETE/KEEP decision.

    Fails (with the offending number) when there are no post-fix decisions, the
    INSTRUMENTED rate is < 95%, or the outcome unknown_rate is > 5%. Instrumented
    = state (a) numeric health + state (b) `health=-` no-row; only state (c)
    (no gate input on the marker) counts against the rate.
    """
    if stats["post_fix_decisions"] == 0:
        return False, "no post-fix decisions recorded yet (clock cannot start)"
    if stats["instrumented_rate"] < MIN_INSTRUMENTED_RATE:
        return (
            False,
            f"instrumented rate {stats['instrumented_rate']:.4f} < {MIN_INSTRUMENTED_RATE} "
            f"(a numeric={stats['state_a_numeric']} + b no-row={stats['state_b_norow']} "
            f"= {stats['instrumented']}/{stats['post_fix_decisions']}; "
            f"c legacy={stats['state_c_legacy']} not instrumented)",
        )
    if stats["unknown_rate"] > MAX_UNKNOWN_RATE:
        return (
            False,
            f"outcome unknown_rate {stats['unknown_rate']:.4f} > {MAX_UNKNOWN_RATE} "
            f"({stats['post_fix_decisions'] - stats['joined_outcomes']}/{stats['post_fix_decisions']} unjoinable)",
        )
    return True, ""


def decide(events_path: Path, now: float | None = None) -> dict[str, Any]:
    """Compute the decommission verdict + exit code.

    Precedence: KEEP (interventions > 0) wins first — a firing loop is kept
    regardless of clock validity. Else the clock must be valid; an invalid clock
    yields CLOCK-INVALID (the zero is untrustworthy). With a valid clock and zero
    interventions: DELETE when a threshold is met, else ACCRUING with exact
    remaining.
    """
    now = time.time() if now is None else now
    stats = count_post_fix(events_path)
    elapsed_days = (now - STAGE0_FIX_EPOCH) / _SECONDS_PER_DAY
    remaining_days = max(0, DELETE_DAYS - int(elapsed_days))
    remaining_decisions = max(0, DELETE_DECISIONS - stats["post_fix_decisions"])
    valid, clock_reason = clock_valid(stats)

    res: dict[str, Any] = {
        **stats,
        "stage0_commit": STAGE0_FIX_COMMIT,
        "elapsed_days": round(elapsed_days, 3),
        "remaining_days": remaining_days,
        "remaining_decisions": remaining_decisions,
        "clock_valid": valid,
        "clock_reason": clock_reason,
    }

    if stats["interventions"] > 0:
        res["verdict"] = "KEEP"
        res["exit_code"] = 0
        res["reason"] = f"{stats['interventions']} intervention(s): the loop fires; keep it"
        return res

    if not valid:
        res["verdict"] = "CLOCK-INVALID"
        res["exit_code"] = 4
        res["reason"] = clock_reason
        return res

    time_met = elapsed_days >= DELETE_DAYS
    count_met = stats["post_fix_decisions"] >= DELETE_DECISIONS
    if time_met or count_met:
        res["verdict"] = "DELETE"
        res["exit_code"] = 3
        trig = "time" if time_met else "count"
        res["reason"] = f"0 interventions, valid clock, {trig} threshold met: remove the loop"
        return res

    res["verdict"] = "ACCRUING"
    res["exit_code"] = 0
    res["reason"] = (
        f"0 interventions, valid clock, neither threshold reached: "
        f"{remaining_days} day(s) OR {remaining_decisions} decision(s) remaining"
    )
    return res


def render_human(res: dict[str, Any]) -> str:
    """Render the verdict as a Dense-Complete human summary."""
    lines = [
        f"VERDICT: {res['verdict']} (exit {res['exit_code']})",
        f"  {res['reason']}",
        "",
        f"clock start: commit {res['stage0_commit']} (epoch {STAGE0_FIX_EPOCH})",
        f"elapsed: {res['elapsed_days']} days  | remaining to delete: "
        f"{res['remaining_days']} days OR {res['remaining_decisions']} decisions",
        f"post-fix decisions: {res['post_fix_decisions']}",
        f"instrumentation states: a numeric={res['state_a_numeric']} "
        f"b no-row={res['state_b_norow']} c legacy={res['state_c_legacy']} "
        f"(instrumented a+b={res['instrumented']}/{res['post_fix_decisions']})",
        f"interventions: {res['interventions']} "
        f"(real demote={res['real_demote']} tiebreak={res['real_tiebreak']}; "
        f"shadow demote={res['shadow_demote']} tiebreak={res['shadow_tiebreak']})",
        f"clock valid: {str(res['clock_valid']).lower()}  "
        f"(instrumented_rate={res['instrumented_rate']} >= {MIN_INSTRUMENTED_RATE}? ; "
        f"unknown_rate={res['unknown_rate']} <= {MAX_UNKNOWN_RATE}?)",
    ]
    if not res["clock_valid"]:
        lines.append(f"clock_reason: {res['clock_reason']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Routing-loop decommission check (ADR routing-loop-value-eval).")
    parser.add_argument("--events", type=Path, default=_DEFAULT_EVENTS, help="route-events.jsonl path (read-only).")
    parser.add_argument("--json", action="store_true", help="emit JSON only.")
    args = parser.parse_args(argv)

    res = decide(events_path=args.events)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(render_human(res))
        print()
        print(json.dumps(res, separators=(",", ":")))
    return res["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
