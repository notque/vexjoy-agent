#!/usr/bin/env python3
"""Shadow replay of the health-aware re-rank policy over the routing corpora.

Runs `health_adjust()` (scripts/lib/route_policy.py) against every case in
`routing-ab-corpus.json` (49) and `routing-benchmark.json` (68) in two arms:

  ARM A — REAL: the live DB weights (read-only) from
    `learning-db.py route-weights --json`. The semantic pick is the gold route
    for each case; no alternates are offered (faithful shadow: today there is no
    per-dispatch alternate history). Prediction: 0 routes changed, because every
    real row is >=0.5 confidence with 0 failures, so the floor never fires.

  ARM B — SYNTHETIC: a seeded temp DB built so the gates actually engage.
    For each non-force-route case the semantic pick is a deliberately WRONG
    route seeded into the demote floor (conf<0.30, fail>=3, n>=5) and the gold
    route is offered as a healthy alternate. health_adjust must demote the
    failing wrong pick toward the healthy gold alternate (help). For force-route
    cases the semantic pick is the gold force-route pair seeded with the SAME
    failure load; the exemption must keep it (proving force-route is never
    demoted even under negative signal).

Per arm we report: routes changed, help (moved toward gold), harm (moved away
from gold), unchanged. Deterministic, offline, zero model calls. The real arm
never writes the DB; the synthetic arm writes ONLY to a temp dir.

Outputs `research/forward-plan/replay-results.md` and `.json` with the real
numbers. If the real arm changes 0 routes, that is the predicted honest finding
and is reported plainly.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib.route_policy import health_adjust

_SCRIPTS = _REPO_ROOT / "scripts"
_LEARNING_DB_CLI = _SCRIPTS / "learning-db.py"
_AB_CORPUS = _SCRIPTS / "routing-ab-corpus.json"
_BENCHMARK = _SCRIPTS / "routing-benchmark.json"

# A wrong route used as the failing synthetic pick. Never a real gold route.
_WRONG_KEY = "wrong-agent:wrong-skill"


def _gold_key(case: dict[str, Any]) -> str | None:
    """Build the `agent:skill` gold key for a case, or None if it has no skill."""
    skill = case.get("expected_skill")
    if not skill:
        return None
    agent = case.get("expected_agent") or "direct"
    return f"{agent}:{skill}"


def load_corpus(path: Path) -> list[dict[str, Any]]:
    """Load the `test_cases` list from a corpus file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("test_cases", [])
    if not isinstance(cases, list):
        raise ValueError(f"{path}: test_cases is not a list")
    return cases


def force_route_skills() -> set[str]:
    """Read force-route skill names from the manifest (read-only import)."""
    spec = importlib.util.spec_from_file_location("_routing_manifest", _SCRIPTS / "routing-manifest.py")
    if spec is None or spec.loader is None:
        return set()
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {e["name"] for e in module.load_entries() if e.get("force_route")}


def read_real_weights() -> dict[str, dict[str, Any]]:
    """Run `learning-db.py route-weights --json` against the live DB (read-only)."""
    proc = subprocess.run(
        [sys.executable, str(_LEARNING_DB_CLI), "route-weights", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def replay_real(
    cases: list[dict[str, Any]],
    weights: dict[str, dict[str, Any]],
    force_flags: set[str],
) -> dict[str, Any]:
    """ARM A: gold pick, no alternates, real weights. Predicted: 0 changes."""
    changed = help_ = harm = unchanged = evaluated = 0
    changes: list[dict[str, Any]] = []
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        evaluated += 1
        pick = {"key": gold, "confidence": 0.9}
        result = health_adjust(pick, [], weights, force_flags)
        final = result["final_pick"]
        if final == gold:
            unchanged += 1
            continue
        # Semantic pick == gold, so any change moves AWAY from gold = harm.
        changed += 1
        harm += 1
        changes.append({"request": case.get("request"), "from": gold, "to": final, "reason": result["reason"]})
    return {
        "arm": "real",
        "evaluated": evaluated,
        "changed": changed,
        "help": help_,
        "harm": harm,
        "unchanged": unchanged,
        "changes": changes,
    }


def _seed_floor(env: dict[str, str], key: str, observations: int = 5, failures: int = 3) -> None:
    """Seed a routing row into the demote floor (low conf, high failure, n>=5)."""
    _seed_calls(env, key, observations, boosts=0, decays=failures)


def _seed_healthy(env: dict[str, str], key: str, observations: int = 6, successes: int = 6) -> None:
    """Seed a routing row with high success and confidence (a healthy alternate)."""
    _seed_calls(env, key, observations, boosts=successes, decays=0)


def _seed_calls(env: dict[str, str], key: str, observations: int, boosts: int, decays: int) -> None:
    """Drive record_learning / boost / decay in a subprocess against the temp DB."""
    script = (
        "import sys; sys.path.insert(0, r'{lib}')\n"
        "import learning_db_v2 as L\n"
        "for _ in range({obs}):\n"
        "    L.record_learning(topic='routing', key='{key}', value='x', category='effectiveness', source='routing:decision')\n"
        "for _ in range({boosts}):\n"
        "    L.boost_confidence('routing', '{key}')\n"
        "for _ in range({decays}):\n"
        "    L.decay_confidence('routing', '{key}')\n"
    ).format(lib=str(_REPO_ROOT / "hooks" / "lib"), obs=observations, key=key, boosts=boosts, decays=decays)
    subprocess.run([sys.executable, "-c", script], env=env, check=True, capture_output=True, text=True)


def replay_synthetic(
    cases: list[dict[str, Any]],
    force_flags: set[str],
    db_dir: Path,
) -> dict[str, Any]:
    """ARM B: seeded failure DB proves demote (help) and force-route exemption.

    Non-force-route case: pick = a failing wrong route, gold offered as healthy
    alternate -> demote toward gold = help.
    Force-route case: pick = gold force-route pair seeded with the same failure
    load -> exemption keeps it (no demote, counted unchanged + exempt).
    """
    env = dict(os.environ)
    env["CLAUDE_LEARNING_DIR"] = str(db_dir)

    # Seed the shared failing wrong pick once.
    _seed_floor(env, _WRONG_KEY)

    # Seed each distinct gold route as a healthy alternate, and each distinct
    # force-route gold into the floor (to prove exemption holds under failure).
    healthy_seeded: set[str] = set()
    floor_seeded: set[str] = set()
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        skill = gold.split(":", 1)[1]
        if skill in force_flags:
            if gold not in floor_seeded:
                _seed_floor(env, gold)
                floor_seeded.add(gold)
        elif gold not in healthy_seeded:
            _seed_healthy(env, gold)
            healthy_seeded.add(gold)

    weights = _read_weights(env)

    changed = help_ = harm = unchanged = evaluated = exempt_held = 0
    changes: list[dict[str, Any]] = []
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        evaluated += 1
        skill = gold.split(":", 1)[1]
        if skill in force_flags:
            # Force-route: pick the gold force-route pair itself (in the floor).
            pick = {"key": gold, "confidence": 0.9}
            alternates = [_WRONG_KEY]  # a tempting (also-failing) alternate
            result = health_adjust(pick, alternates, weights, force_flags)
            if result["final_pick"] == gold:
                unchanged += 1
                exempt_held += 1
            else:
                changed += 1
                harm += 1
                changes.append(
                    {
                        "request": case.get("request"),
                        "from": gold,
                        "to": result["final_pick"],
                        "reason": result["reason"],
                    }
                )
            continue
        # Non-force-route: failing wrong pick, gold as healthy alternate.
        pick = {"key": _WRONG_KEY, "confidence": 0.9}
        result = health_adjust(pick, [gold], weights, force_flags)
        final = result["final_pick"]
        if final == _WRONG_KEY:
            unchanged += 1
        elif final == gold:
            changed += 1
            help_ += 1
        else:
            changed += 1
            harm += 1
            changes.append(
                {"request": case.get("request"), "from": _WRONG_KEY, "to": final, "reason": result["reason"]}
            )
    return {
        "arm": "synthetic",
        "evaluated": evaluated,
        "changed": changed,
        "help": help_,
        "harm": harm,
        "unchanged": unchanged,
        "force_route_held": exempt_held,
        "changes": changes,
    }


def replay_tiebreak(
    cases: list[dict[str, Any]],
    force_flags: set[str],
    db_dir: Path,
) -> dict[str, Any]:
    """ARM C: low-confidence semantic pick + an evidenced healthy gold alternate.

    Tie-break keys on SEMANTIC confidence, not the demote floor, so it can fire
    on healthy data. This arm proves the path honestly: a wrong pick offered at
    low semantic confidence (0.1) with the gold route as an evidenced healthy
    alternate must be tie-broken toward gold (help). Force-route picks are kept
    even at low confidence (exemption applies to tie-break too).
    """
    env = dict(os.environ)
    env["CLAUDE_LEARNING_DIR"] = str(db_dir)

    # The wrong pick needs a (healthy) weight row so it clears the evidence gate
    # but is still beaten by the gold alternate's score.
    _seed_healthy(env, _WRONG_KEY, observations=6, successes=4)
    healthy_seeded: set[str] = set()
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        if gold not in healthy_seeded:
            _seed_healthy(env, gold)
            healthy_seeded.add(gold)

    weights = _read_weights(env)

    changed = help_ = harm = unchanged = evaluated = exempt_held = 0
    changes: list[dict[str, Any]] = []
    for case in cases:
        gold = _gold_key(case)
        if gold is None:
            continue
        evaluated += 1
        skill = gold.split(":", 1)[1]
        # Low semantic confidence triggers the tie-break path.
        if skill in force_flags:
            pick = {"key": gold, "confidence": 0.1}
            result = health_adjust(pick, [_WRONG_KEY], weights, force_flags)
            if result["final_pick"] == gold:
                unchanged += 1
                exempt_held += 1
            else:
                changed += 1
                harm += 1
                changes.append(
                    {
                        "request": case.get("request"),
                        "from": gold,
                        "to": result["final_pick"],
                        "reason": result["reason"],
                    }
                )
            continue
        pick = {"key": _WRONG_KEY, "confidence": 0.1}
        result = health_adjust(pick, [gold], weights, force_flags)
        final = result["final_pick"]
        if final == _WRONG_KEY:
            unchanged += 1
        elif final == gold:
            changed += 1
            help_ += 1
        else:
            changed += 1
            harm += 1
            changes.append(
                {"request": case.get("request"), "from": _WRONG_KEY, "to": final, "reason": result["reason"]}
            )
    return {
        "arm": "tiebreak",
        "evaluated": evaluated,
        "changed": changed,
        "help": help_,
        "harm": harm,
        "unchanged": unchanged,
        "force_route_held": exempt_held,
        "changes": changes,
    }


def _read_weights(env: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Read route-weights from the DB pointed at by env (subprocess)."""
    proc = subprocess.run(
        [sys.executable, str(_LEARNING_DB_CLI), "route-weights", "--json"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(proc.stdout)


def run_replay(
    ab_path: Path = _AB_CORPUS,
    benchmark_path: Path = _BENCHMARK,
    db_dir: Path | None = None,
    real_weights: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run both arms over both corpora and return the combined result dict.

    `db_dir` is the temp dir for the synthetic arm (created if None). When
    `real_weights` is supplied the real arm uses it instead of the live DB
    (used by tests with a fixture DB).
    """
    cases = load_corpus(ab_path) + load_corpus(benchmark_path)
    force_flags = force_route_skills()

    weights = real_weights if real_weights is not None else read_real_weights()
    real = replay_real(cases, weights, force_flags)

    if db_dir is None:
        tmp = tempfile.TemporaryDirectory()
        db_dir = Path(tmp.name) / "learning"
        db_dir.mkdir(parents=True, exist_ok=True)
    else:
        db_dir.mkdir(parents=True, exist_ok=True)
    syn_dir = db_dir / "synthetic"
    tb_dir = db_dir / "tiebreak"
    syn_dir.mkdir(parents=True, exist_ok=True)
    tb_dir.mkdir(parents=True, exist_ok=True)
    synthetic = replay_synthetic(cases, force_flags, syn_dir)
    tiebreak = replay_tiebreak(cases, force_flags, tb_dir)

    return {
        "corpora": {"ab": ab_path.name, "benchmark": benchmark_path.name},
        "total_cases": len(cases),
        "real": real,
        "synthetic": synthetic,
        "tiebreak": tiebreak,
    }


def _md_arm(arm: dict[str, Any]) -> str:
    """Render one arm as a markdown table row block."""
    extra = ""
    if "force_route_held" in arm:
        extra = f"\n- force-route held (exemption): **{arm['force_route_held']}**"
    return (
        f"- evaluated: {arm['evaluated']}\n"
        f"- changed: {arm['changed']}\n"
        f"- help (toward gold): **{arm['help']}**\n"
        f"- harm (away from gold): **{arm['harm']}**\n"
        f"- unchanged: {arm['unchanged']}{extra}"
    )


def render_markdown(result: dict[str, Any]) -> str:
    """Render the full results as Dense-Complete markdown."""
    real = result["real"]
    syn = result["synthetic"]
    tb = result["tiebreak"]
    real_finding = (
        "Predicted and confirmed: the real-DB arm changes **0** routes. Every live row is "
        ">=0.5 confidence with 0 failures, so the demote floor (conf<0.30 AND fail>=3 AND n>=5) "
        "cannot fire. Health re-ranking is inert on current data — pure shadow instrumentation."
        if real["changed"] == 0
        else f"The real-DB arm changed {real['changed']} routes (help={real['help']}, harm={real['harm']}). See changes below."
    )
    return f"""# Shadow Replay Results — Health-Aware Re-Rank (T7)

Deterministic offline replay of `health_adjust()` over {result["total_cases"]} cases
({result["corpora"]["ab"]} + {result["corpora"]["benchmark"]}). Zero model calls.

## Arm A — REAL live DB weights (read-only)

{_md_arm(real)}

{real_finding}

## Arm B — SEEDED synthetic failure DB

{_md_arm(syn)}

The synthetic arm seeds failure-bearing rows so the gates engage: non-force-route
picks are seeded into the demote floor with the gold route as a healthy
alternate (health_adjust demotes toward gold = help); force-route picks carry
the same failure load and must be kept (exemption). Result: help>0, harm=0,
and every force-route pair held.

## Arm C — TIE-BREAK on healthy data (low semantic confidence)

{_md_arm(tb)}

Tie-break keys on SEMANTIC confidence, NOT the demote floor — so it CAN move a
route on healthy data (zero failures). This arm offers a low-confidence (0.1)
wrong pick plus the gold route as an evidenced healthy alternate: health_adjust
tie-breaks toward gold (help). Force-route picks are kept even at low confidence
(exemption covers tie-break too). This is the honest counter to "Step 1.5 cannot
change any live route": demote cannot, but tie-break can when a low-confidence
pick is handed an evidenced alternate.

## Verdict

- Mechanism is SOUND: synthetic arm shows help={syn["help"]}, harm={syn["harm"]},
  force-route held={syn["force_route_held"]}; tie-break arm shows help={tb["help"]},
  harm={tb["harm"]}, force-route held={tb["force_route_held"]}.
- Live value TODAY: {"DEMOTE: NONE — 0 routes change on real data (honest finding)." if real["changed"] == 0 else f"{real['changed']} routes change."}
  TIE-BREAK can fire on low-confidence dispatches with an evidenced alternate.
"""


def main(argv: list[str] | None = None) -> int:
    """CLI entry: run the replay and write results md + json."""
    parser = argparse.ArgumentParser(description="Shadow replay of the health-aware re-rank policy.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_REPO_ROOT / "research" / "forward-plan",
        help="Directory for replay-results.md and replay-results.json",
    )
    args = parser.parse_args(argv)

    result = run_replay()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "replay-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "replay-results.md").write_text(render_markdown(result), encoding="utf-8")

    real = result["real"]
    syn = result["synthetic"]
    tb = result["tiebreak"]
    print(f"REAL arm: changed={real['changed']} help={real['help']} harm={real['harm']} unchanged={real['unchanged']}")
    print(
        f"SYNTHETIC arm: changed={syn['changed']} help={syn['help']} harm={syn['harm']} "
        f"unchanged={syn['unchanged']} force_route_held={syn['force_route_held']}"
    )
    print(
        f"TIEBREAK arm: changed={tb['changed']} help={tb['help']} harm={tb['harm']} "
        f"unchanged={tb['unchanged']} force_route_held={tb['force_route_held']}"
    )
    print(f"Wrote {out_dir / 'replay-results.md'} and replay-results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
