#!/usr/bin/env python3
"""Routing-loop decommission check (ADR: routing-loop-value-eval).

One question: should the outcome-routing shadow loop be removed today? The
answer is a count-based, shadow-inclusive verdict with an exit code — not prose.

Clock start = the Step-1.5 wiring-fix commit (d943ba74, 2026-06-06 21:21:07 UTC),
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
            router actually re-ranked the route). A recorded tiebreak counts as a
            real intervention here: it is ground truth, the router fired.
  shadow  = replay `route_policy.health_adjust` on the RECORDED gate inputs of
            each decision (health_at_decision, n, failure, alternates); count
            ONLY where the replay action is demote. Gate inputs are read as
            recorded — never re-derived from current weights (ADR codex 29).
            Recorded alternates that carry their own weight fields let the shadow
            replay prefer them; bare-key alternates have no weight row, so the
            shadow replay cannot fire toward them (honest zero, not a hidden one).

  Shadow tiebreak is UNMEASURABLE and is never counted as shadow. The tiebreak
  gate keys on SEMANTIC confidence (< 0.35), which decision events do not record
  — only the weight-row confidence (health_at_decision) is stored. Replaying
  tiebreak from health_at_decision would conflate two unrelated values (a
  high-semantic-confidence pick with a low historical weight row would fire a
  spurious shadow tiebreak, pushing the verdict toward KEEP). So the criterion
  is: real tiebreaks (recorded action) + real demotes + shadow demotes.

  Shadow replay also passes the canonical force-route skill set (same source
  production uses: routing-manifest force_route entries via route-replay
  force_route_skills). A force-routed pair is hard-exempt and can never count as
  a shadow demote, mirroring production.

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
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib.route_policy import health_adjust


def _load_force_route_skills() -> set[str]:
    """Load the canonical force-route skill set production uses.

    Reuses route-replay's force_route_skills (routing-manifest force_route
    entries) — do not duplicate the list. Best-effort: an empty set on any load
    failure means no pair is treated as exempt, which can only INFLATE shadow
    demote (never hide a real one). Fail-safe direction: a load failure can only
    produce a conservative KEEP (loop survives), never a false DELETE.
    """
    try:
        spec = importlib.util.spec_from_file_location("_route_replay_force", _REPO_ROOT / "scripts" / "route-replay.py")
        if spec is None or spec.loader is None:
            return set()
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return set(module.force_route_skills())
    except Exception:
        return set()


# Canonical force-route set, loaded once. A force-routed pair is hard-exempt in
# production and must never count as a shadow demote (codex #6).
_FORCE_ROUTE_SKILLS = _load_force_route_skills()

# Clock start: the Step-1.5 wiring-fix commit (records health gate inputs on the
# do-route marker). `git show -s --format=%ct d943ba74` == 1780780867.
# Naming: the health gate is "Step 1.5" (do/SKILL.md, the producer); it was
# called "Stage 0" during development. The constants and the `stage0_commit`
# output key keep the historical name — they label a fixed commit, not the step.
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


def _shadow_demote(decision: dict[str, Any]) -> bool:
    """True iff replaying the demote FLOOR on recorded gate inputs would demote.

    Evaluates ONLY the floor-demote path (codex finding 3): the tiebreak gate
    reads SEMANTIC confidence, which decision events do not record, so a tiebreak
    replay would conflate the weight-row confidence with semantic confidence.
    We force semantic confidence to 1.0 (>= LOW_CONFIDENCE) so the tiebreak gate
    can never fire — the replay returns demote only when the floor truly engages.

    The picked pair's weight row is the recorded gate inputs the floor reads:
    confidence=health_at_decision, n, failure (the floor never reads `success`,
    so no field is fabricated). Recorded alternates that carry their own weight
    fields can be demoted toward; bare-key alternates have no weight row and
    cannot be preferred. The canonical force-route set is passed so a hard-exempt
    pair is never shadow-demoted (codex #6). Never reads current weights.
    """
    health = decision.get("health_at_decision")
    if health is None:
        return False  # no health recorded => nothing to replay
    agent = decision.get("agent") or "direct"
    skill = decision.get("skill") or ""
    pick_key = f"{agent}:{skill}"
    weights: dict[str, dict[str, Any]] = {
        pick_key: {
            "confidence": health,
            "n": decision.get("n") or 0,
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
    # Semantic confidence forced to 1.0 so the tiebreak gate cannot fire; only
    # the floor-demote path can return "demote".
    pick = {"key": pick_key, "confidence": 1.0}
    return health_adjust(pick, alt_keys, weights, _FORCE_ROUTE_SKILLS)["action"] == "demote"


def count_post_fix(events_path: Path) -> dict[str, Any]:
    """Count post-fix interventions, health rate, and outcome unknown rate.

    real_demote/real_tiebreak come from the recorded `action`; shadow_demote
    from the floor-only health_adjust replay on recorded gate inputs (shadow
    tiebreak is unmeasurable and never counted). health_rate = non-null health /
    decisions. unknown_rate = decisions with no joinable outcome / decisions
    (join: nearest preceding decision in the same session). Sessionless rows
    (empty session) are excluded from the join and reported in a separate bucket
    so they distort neither unknown_rate nor instrumented_rate (codex #7).
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
    shadow_demote = 0
    state_a = state_b = state_c = 0
    for d in decisions:
        action = d.get("action")
        if action == "demote":
            real_demote += 1
        elif action == "tiebreak":
            real_tiebreak += 1
        state_a, state_b, state_c = _bump_state(d, state_a, state_b, state_c)
        if _shadow_demote(d):
            shadow_demote += 1

    n_dec = len(decisions)
    # instrumented = state (a) + state (b): the marker carried the gate input.
    # Only state (c) (no gate input) counts against the 95% rate.
    instrumented = state_a + state_b
    instrumented_rate = (instrumented / n_dec) if n_dec else 0.0
    joined, sessionless_decisions, sessionless_outcomes = _count_joined(decisions, outcomes)
    # Sessionless decisions cannot be joined to an outcome by session id, so they
    # are excluded from the unknown_rate denominator rather than counted unknown.
    joinable_dec = n_dec - sessionless_decisions
    unknown_rate = ((joinable_dec - joined) / joinable_dec) if joinable_dec else 1.0

    interventions = real_demote + real_tiebreak + shadow_demote
    return {
        "post_fix_decisions": n_dec,
        "post_fix_outcomes": len(outcomes),
        "state_a_numeric": state_a,
        "state_b_norow": state_b,
        "state_c_legacy": state_c,
        "instrumented": instrumented,
        "instrumented_rate": round(instrumented_rate, 4),
        "joined_outcomes": joined,
        "joinable_decisions": joinable_dec,
        "sessionless_decisions": sessionless_decisions,
        "sessionless_outcomes": sessionless_outcomes,
        "unknown_rate": round(unknown_rate, 4),
        "real_demote": real_demote,
        "real_tiebreak": real_tiebreak,
        "shadow_demote": shadow_demote,
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


def _count_joined(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Join decisions to outcomes by session; report sessionless rows separately.

    Each outcome attaches to the latest decision in its session at or before the
    outcome ts. A decision counts as joined once at least one outcome attaches to
    it. Mirrors the ADR join key (session id + nearest preceding decision).

    Empty-session rows are EXCLUDED from the join (codex #7): grouping them under
    "" would join unrelated sessionless outcomes across dispatches and distort
    the rates. They are counted in explicit sessionless buckets so nothing is
    silently dropped. Returns ``(joined, sessionless_decisions,
    sessionless_outcomes)``.
    """
    sessionless_decisions = sum(1 for d in decisions if not d.get("session"))
    sessionless_outcomes = sum(1 for o in outcomes if not o.get("session"))
    by_session: dict[str, list[tuple[float, int]]] = {}
    for idx, d in enumerate(decisions):
        sess = d.get("session")
        if not sess:
            continue  # sessionless: cannot be joined, counted in its own bucket
        by_session.setdefault(sess, []).append((d.get("ts", 0.0), idx))
    for lst in by_session.values():
        lst.sort()
    joined_idx: set[int] = set()
    for o in outcomes:
        sess = o.get("session")
        if not sess:
            continue  # sessionless outcome: never joins
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
    return len(joined_idx), sessionless_decisions, sessionless_outcomes


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
            f"({stats['joinable_decisions'] - stats['joined_outcomes']}/{stats['joinable_decisions']} "
            f"unjoinable; {stats['sessionless_decisions']} sessionless decision(s) excluded)",
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
        f"shadow demote={res['shadow_demote']}; shadow tiebreak unmeasurable — not counted)",
        f"sessionless (left out of the session match): decisions={res['sessionless_decisions']} "
        f"outcomes={res['sessionless_outcomes']}",
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
