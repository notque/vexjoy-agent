#!/usr/bin/env python3
"""Blind A/B harness for the semantic-first routing experiment.

Compares two routing arms over a labeled corpus, using ONE Haiku semantic
decision per query (reused across both arms):

  Arm A (control, deterministic-first):
      A_route = pre_route  IF pre_route.matched AND confidence == "high"
                else haiku
      This is the CURRENT /do behaviour: a high-confidence keyword match
      short-circuits and skips the semantic router.

  Arm B (treatment, semantic-first + safety net = "Option B"):
      B_route = haiku
      THEN if pre_route is a high-confidence force_route for a SAFETY-critical
      skill (pr-workflow or security-review) and haiku disagrees, override
      B_route to the pre_route target. Semantic decides the long tail;
      deterministic guarantees the safety routes.

Cost model (Haiku calls):
  Arm A makes a Haiku call ONLY when pre_route is not high-confidence
  (i.e. it fell through). Arm B always makes a Haiku call.

This script can NOT call Haiku itself (no API key, by design). It runs in
two modes and a human/agent runner bridges them:

  --emit-prompts : writes routing-ab-results/prompts/<id>.txt (one prompt per
                   query, built from the verbatim Haiku template + manifest)
                   and routing-ab-results/queries.json (the ordered query list).
  --score        : reads collected Haiku answers from
                   routing-ab-results/answers/<id>.json, computes both arms +
                   per-query records + cost, and writes raw.json.
  --build-judge  : after --score, builds an arm-stripped, shuffled judge input
                   (judge-input.json) plus a private uid->arm map (uid-map.json
                   the judge never sees).
  --rejoin       : after the judge runs, reads judge-output.json + uid-map.json,
                   rejoins by uid, and writes the scoreboard (scoreboard.json)
                   with per-arm and per-bucket accuracy.
  --pre-route-map: runs the deterministic pre-router across the whole corpus and
                   writes pre-route-map.json — a fully reproducible (no model)
                   record of which queries Arm A short-circuits (high-confidence
                   keyword match, skips Haiku) vs. defers to the semantic router.
                   This is the verifiable evidence for the blog post's claim that
                   keyword-first routing drops paraphrased intents.

Stdlib only. Deterministic given fixed inputs (shuffle uses a fixed seed).

Usage:
    python3 scripts/routing-ab-test.py --emit-prompts
    python3 scripts/routing-ab-test.py --score
    python3 scripts/routing-ab-test.py --build-judge
    python3 scripts/routing-ab-test.py --rejoin
    python3 scripts/routing-ab-test.py --pre-route-map
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
CORPUS = SCRIPTS / "routing-ab-corpus.json"
RESULTS = SCRIPTS / "routing-ab-results"
PROMPTS_DIR = RESULTS / "prompts"
ANSWERS_DIR = RESULTS / "answers"

# Safety-critical force-route skills. Arm B's deterministic safety net only
# fires for these: a high-confidence force_route here overrides a disagreeing
# semantic decision so the commit->quality-gate and security guarantees hold.
SAFETY_SKILLS = {"pr-workflow", "security-review"}

# Verbatim Haiku routing prompt template (REQUEST + MANIFEST filled in).
PROMPT_TEMPLATE = """You are a routing agent. Given a user request and a manifest of available agents, skills, and pipelines, select the BEST agent+skill combination.
USER REQUEST: {request}
ROUTING MANIFEST:
{manifest}
Return your answer as JSON: {{"agent": "...|null","skill":"...|null","pipeline":"...|null","reasoning":"one sentence","confidence":"high/medium/low"}}
FORCE-ROUTE RULE: Entries marked "FORCE" MUST be selected when their domain clearly matches the user's intent. FORCE matching is SEMANTIC, not keyword-based — match what the user MEANS. For git operations (push, commit, PR, merge), ALWAYS select pr-workflow. Pick the most specific match. Return a single skill name as a string."""


def _norm(value: object) -> str | None:
    """Normalize a route field: treat null-likes as None, else stripped str."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"null", "none", "n/a", "na"}:
        return None
    return text


def load_corpus() -> list[dict]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    return data["test_cases"]


def query_id(index: int) -> str:
    """Stable per-query id: q00, q01, ... (zero-padded, corpus order)."""
    return f"q{index:02d}"


def run_pre_route(request: str) -> dict:
    """Invoke pre-route.py for one request and parse its JSON output."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "pre-route.py"), "--request", request, "--json-compact"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
        check=False,
    )
    return json.loads(proc.stdout)


def build_manifest() -> str:
    """Generate the compact routing manifest the semantic router consumes."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "routing-manifest.py"), "--compact"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
        check=False,
    )
    return proc.stdout.strip()


# --------------------------------------------------------------------------- #
# Mode: emit-prompts
# --------------------------------------------------------------------------- #
def emit_prompts() -> int:
    """Write one Haiku routing prompt per query plus the ordered query list."""
    corpus = load_corpus()
    manifest = build_manifest()
    if not manifest:
        print("ERROR: empty manifest from routing-manifest.py", file=sys.stderr)
        return 1

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

    queries = []
    for i, case in enumerate(corpus):
        qid = query_id(i)
        request = case["request"]
        prompt = PROMPT_TEMPLATE.format(request=request, manifest=manifest)
        (PROMPTS_DIR / f"{qid}.txt").write_text(prompt, encoding="utf-8")
        queries.append(
            {
                "id": qid,
                "request": request,
                "expected_agent": case.get("expected_agent"),
                "expected_skill": case.get("expected_skill"),
                "category": case.get("category"),
                "bucket": case.get("bucket"),
                "notes": case.get("notes"),
            }
        )

    (RESULTS / "queries.json").write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
    # Persist the manifest used, so the experiment is reproducible.
    (RESULTS / "manifest-used.txt").write_text(manifest, encoding="utf-8")
    print(f"Wrote {len(queries)} prompts to {PROMPTS_DIR}")
    print(f"Query list: {RESULTS / 'queries.json'}")
    print(f"Manifest snapshot: {RESULTS / 'manifest-used.txt'}")
    print(f"Drop Haiku JSON answers into {ANSWERS_DIR}/<id>.json, then run --score")
    return 0


# --------------------------------------------------------------------------- #
# Mode: score
# --------------------------------------------------------------------------- #
def _haiku_skill(haiku: dict) -> str | None:
    return _norm(haiku.get("skill"))


def _haiku_agent(haiku: dict) -> str | None:
    return _norm(haiku.get("agent"))


def compute_arms(pre_route: dict, haiku: dict) -> dict:
    """Compute Arm A and Arm B routes + cost flags from one Haiku decision."""
    pr_high = bool(pre_route.get("matched")) and pre_route.get("confidence") == "high"
    pr_skill = _norm(pre_route.get("skill"))
    pr_agent = _norm(pre_route.get("agent"))
    pr_force = pre_route.get("match_type") == "force_route"

    h_skill = _haiku_skill(haiku)
    h_agent = _haiku_agent(haiku)

    # Arm A: deterministic-first short-circuit.
    if pr_high:
        a_skill, a_agent, a_source = pr_skill, pr_agent, "pre_route"
        a_haiku_calls = 0
    else:
        a_skill, a_agent, a_source = h_skill, h_agent, "haiku"
        a_haiku_calls = 1

    # Arm B: semantic-first, then safety net.
    b_skill, b_agent, b_source = h_skill, h_agent, "haiku"
    safety_override = False
    if pr_high and pr_force and pr_skill in SAFETY_SKILLS and h_skill != pr_skill:
        b_skill, b_agent, b_source = pr_skill, pr_agent, "safety_net"
        safety_override = True
    b_haiku_calls = 1  # Arm B always asks the model.

    return {
        "pre_route_high": pr_high,
        "pre_route_force": pr_force,
        "A_skill": a_skill,
        "A_agent": a_agent,
        "A_source": a_source,
        "A_haiku_calls": a_haiku_calls,
        "B_skill": b_skill,
        "B_agent": b_agent,
        "B_source": b_source,
        "B_haiku_calls": b_haiku_calls,
        "B_safety_override": safety_override,
    }


def score() -> int:
    """Read collected Haiku answers, compute both arms, write raw.json."""
    queries_path = RESULTS / "queries.json"
    if not queries_path.exists():
        print("ERROR: run --emit-prompts first (queries.json missing)", file=sys.stderr)
        return 1
    queries = json.loads(queries_path.read_text(encoding="utf-8"))

    records = []
    missing = []
    cost_a = cost_b = 0
    for q in queries:
        qid = q["id"]
        ans_path = ANSWERS_DIR / f"{qid}.json"
        if not ans_path.exists():
            missing.append(qid)
            continue
        haiku = json.loads(ans_path.read_text(encoding="utf-8"))
        pre_route = run_pre_route(q["request"])
        arms = compute_arms(pre_route, haiku)
        cost_a += arms["A_haiku_calls"]
        cost_b += arms["B_haiku_calls"]
        records.append(
            {
                "id": qid,
                "query": q["request"],
                "bucket": q["bucket"],
                "category": q["category"],
                "expected_agent": q["expected_agent"],
                "expected_skill": q["expected_skill"],
                "notes": q["notes"],
                "pre_route": pre_route,
                "haiku_raw": haiku,
                "A_route": {"agent": arms["A_agent"], "skill": arms["A_skill"], "source": arms["A_source"]},
                "B_route": {"agent": arms["B_agent"], "skill": arms["B_skill"], "source": arms["B_source"]},
                "A_haiku_calls": arms["A_haiku_calls"],
                "B_haiku_calls": arms["B_haiku_calls"],
                "B_safety_override": arms["B_safety_override"],
            }
        )

    if missing:
        print(f"ERROR: missing Haiku answers for {len(missing)} queries: {missing}", file=sys.stderr)
        print(f"Drop each as {ANSWERS_DIR}/<id>.json then re-run --score", file=sys.stderr)
        return 1

    out = {
        "n_queries": len(records),
        "cost": {
            "A_haiku_calls_total": cost_a,
            "B_haiku_calls_total": cost_b,
            "A_calls_per_request": round(cost_a / len(records), 3) if records else 0,
            "B_calls_per_request": round(cost_b / len(records), 3) if records else 0,
            "delta_calls_per_request": round((cost_b - cost_a) / len(records), 3) if records else 0,
        },
        "records": records,
    }
    (RESULTS / "raw.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Scored {len(records)} queries -> {RESULTS / 'raw.json'}")
    print(
        f"Cost: A={cost_a} Haiku calls, B={cost_b} Haiku calls (delta {out['cost']['delta_calls_per_request']}/request)"
    )
    return 0


# --------------------------------------------------------------------------- #
# Mode: build-judge
# --------------------------------------------------------------------------- #
def build_judge() -> int:
    """Build a shuffled, arm-stripped judge input + private uid->arm map.

    Each arm's prediction becomes its own row with a fresh uid. Rows carry NO
    arm field and NO method hint. A and B rows are interleaved by a seeded
    shuffle so the judge cannot infer arm from position.
    """
    raw_path = RESULTS / "raw.json"
    if not raw_path.exists():
        print("ERROR: run --score first (raw.json missing)", file=sys.stderr)
        return 1
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    rows = []
    uid_map = {}
    uid = 0
    for rec in raw["records"]:
        for arm_key in ("A_route", "B_route"):
            arm = arm_key[0]  # "A" or "B"
            uid_str = f"u{uid:03d}"
            uid += 1
            route = rec[arm_key]
            rows.append(
                {
                    "uid": uid_str,
                    "query": rec["query"],
                    "expected_agent": rec["expected_agent"],
                    "expected_skill": rec["expected_skill"],
                    "notes": rec["notes"],
                    "predicted_agent": route["agent"],
                    "predicted_skill": route["skill"],
                }
            )
            uid_map[uid_str] = {"query_id": rec["id"], "arm": arm, "bucket": rec["bucket"]}

    rng = random.Random(20260527)  # fixed seed: reproducible interleave
    rng.shuffle(rows)

    (RESULTS / "judge-input.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (RESULTS / "uid-map.json").write_text(json.dumps(uid_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(rows)} arm-stripped rows -> {RESULTS / 'judge-input.json'}")
    print(f"Private map (judge never sees) -> {RESULTS / 'uid-map.json'}")
    print("Dispatch ONE judge agent over judge-input.json; save its JSON to judge-output.json; then --rejoin")
    return 0


# --------------------------------------------------------------------------- #
# Mode: rejoin
# --------------------------------------------------------------------------- #
def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def rejoin() -> int:
    """Rejoin judge output by uid -> per-arm and per-bucket accuracy."""
    jo_path = RESULTS / "judge-output.json"
    map_path = RESULTS / "uid-map.json"
    if not jo_path.exists() or not map_path.exists():
        print("ERROR: need judge-output.json and uid-map.json (run --build-judge + judge)", file=sys.stderr)
        return 1
    judged = json.loads(jo_path.read_text(encoding="utf-8"))
    uid_map = json.loads(map_path.read_text(encoding="utf-8"))

    # Accept either {uid: verdict} or {uid: {"verdict": ...}} shapes.
    def verdict_of(value: object) -> str:
        if isinstance(value, dict):
            return str(value.get("verdict", "")).strip().lower()
        return str(value).strip().lower()

    # arm -> verdict -> count ; arm -> bucket -> verdict -> count
    arm_tally: dict[str, dict[str, int]] = {"A": {}, "B": {}}
    bucket_tally: dict[str, dict[str, dict[str, int]]] = {"A": {}, "B": {}}
    per_uid = {}
    missing = []
    for uid, meta in uid_map.items():
        if uid not in judged:
            missing.append(uid)
            continue
        v = verdict_of(judged[uid])
        if v not in {"correct", "partial", "incorrect"}:
            v = "incorrect"
        arm = meta["arm"]
        bucket = meta["bucket"]
        arm_tally[arm][v] = arm_tally[arm].get(v, 0) + 1
        bucket_tally[arm].setdefault(bucket, {})
        bucket_tally[arm][bucket][v] = bucket_tally[arm][bucket].get(v, 0) + 1
        per_uid[uid] = {"arm": arm, "bucket": bucket, "query_id": meta["query_id"], "verdict": v}

    if missing:
        print(f"ERROR: judge output missing {len(missing)} uids: {missing}", file=sys.stderr)
        return 1

    def summarize(tally: dict[str, int]) -> dict:
        c = tally.get("correct", 0)
        p = tally.get("partial", 0)
        i = tally.get("incorrect", 0)
        n = c + p + i
        return {
            "n": n,
            "correct": c,
            "partial": p,
            "incorrect": i,
            "correct_pct": _pct(c, n),
            "partial_pct": _pct(p, n),
            "incorrect_pct": _pct(i, n),
            # accuracy = correct + half credit for partial (reported separately too)
            "accuracy_strict_pct": _pct(c, n),
            "accuracy_lenient_pct": round(_pct(c, n) + 0.5 * _pct(p, n), 1),
        }

    buckets = sorted({m["bucket"] for m in uid_map.values()})
    scoreboard = {
        "overall": {arm: summarize(arm_tally[arm]) for arm in ("A", "B")},
        "per_bucket": {
            bucket: {arm: summarize(bucket_tally[arm].get(bucket, {})) for arm in ("A", "B")} for bucket in buckets
        },
        "per_uid": per_uid,
    }
    (RESULTS / "scoreboard.json").write_text(json.dumps(scoreboard, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable summary to stdout.
    print("=== OVERALL (strict = correct only) ===")
    for arm in ("A", "B"):
        s = scoreboard["overall"][arm]
        print(
            f"  Arm {arm}: {s['correct']}/{s['n']} correct ({s['correct_pct']}%), "
            f"{s['partial']} partial, {s['incorrect']} incorrect"
        )
    print("=== PER BUCKET (correct% A -> B) ===")
    for bucket in buckets:
        a = scoreboard["per_bucket"][bucket]["A"]
        b = scoreboard["per_bucket"][bucket]["B"]
        print(
            f"  {bucket:24s} A={a['correct']}/{a['n']} ({a['correct_pct']}%)  "
            f"B={b['correct']}/{b['n']} ({b['correct_pct']}%)"
        )
    print(f"Scoreboard -> {RESULTS / 'scoreboard.json'}")
    return 0


# --------------------------------------------------------------------------- #
# Mode: pre-route-map (deterministic, no model required)
# --------------------------------------------------------------------------- #
def pre_route_map() -> int:
    """Record, per corpus query, what the deterministic pre-router decides.

    Fully reproducible: depends only on pre-route.py + the INDEX files. This is
    the Arm A short-circuit map — queries with confidence == high skip Haiku;
    everything else defers to the semantic router. Quantifies the keyword-first
    coverage gap on paraphrased intents.
    """
    corpus = load_corpus()
    RESULTS.mkdir(parents=True, exist_ok=True)

    rows = []
    bucket_stats: dict[str, dict[str, int]] = {}
    for i, case in enumerate(corpus):
        pr = run_pre_route(case["request"])
        high = bool(pr.get("matched")) and pr.get("confidence") == "high"
        bucket = case["bucket"]
        bucket_stats.setdefault(bucket, {"total": 0, "short_circuit": 0, "deferred": 0})
        bucket_stats[bucket]["total"] += 1
        bucket_stats[bucket]["short_circuit" if high else "deferred"] += 1
        rows.append(
            {
                "id": query_id(i),
                "query": case["request"],
                "bucket": bucket,
                "expected_skill": case.get("expected_skill"),
                "expected_agent": case.get("expected_agent"),
                "pre_route_matched": bool(pr.get("matched")),
                "pre_route_confidence": pr.get("confidence"),
                "pre_route_skill": _norm(pr.get("skill")),
                "pre_route_agent": _norm(pr.get("agent")),
                "pre_route_match_type": pr.get("match_type"),
                "arm_A_short_circuits": high,
                "arm_A_skips_haiku": high,
            }
        )

    short = sum(1 for r in rows if r["arm_A_short_circuits"])
    out = {
        "n_queries": len(rows),
        "short_circuit_count": short,
        "deferred_to_semantic_count": len(rows) - short,
        "per_bucket": bucket_stats,
        "rows": rows,
    }
    (RESULTS / "pre-route-map.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Pre-route map -> {RESULTS / 'pre-route-map.json'}")
    print(
        f"{short}/{len(rows)} queries short-circuit (Arm A skips Haiku); "
        f"{len(rows) - short} defer to the semantic router"
    )
    print("Per bucket (short_circuit/total):")
    for b in sorted(bucket_stats):
        s = bucket_stats[b]
        print(f"  {b:24s} {s['short_circuit']}/{s['total']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Blind A/B routing experiment harness.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit-prompts", action="store_true", help="Write per-query Haiku prompts.")
    group.add_argument("--score", action="store_true", help="Score collected answers into raw.json.")
    group.add_argument("--build-judge", action="store_true", help="Build arm-stripped judge input.")
    group.add_argument("--rejoin", action="store_true", help="Rejoin judge output into scoreboard.")
    group.add_argument(
        "--pre-route-map",
        action="store_true",
        help="Deterministic pre-router map across the corpus (no model needed).",
    )
    args = parser.parse_args()

    if args.emit_prompts:
        return emit_prompts()
    if args.score:
        return score()
    if args.build_judge:
        return build_judge()
    if args.rejoin:
        return rejoin()
    if args.pre_route_map:
        return pre_route_map()
    return 1


if __name__ == "__main__":
    sys.exit(main())
