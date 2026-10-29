#!/usr/bin/env python3
"""Taste judge: decide, send back, or hold an agent's question using owner principles.

Pipeline (data lives in ~/.claude/taste/, never in the repo):
    taste-harvest.py            -> pairs.jsonl   (owner reply per assistant question)
    (labeler)                   -> labels.jsonl  (decidable, label, options, principle)
    taste-judge.py split        -> train.jsonl, test.jsonl (chronological)
    (distiller, train only)     -> principles.json
    taste-judge.py build        -> cases.jsonl   (blind Jev payloads, no labels)
    taste-judge.py run          -> answers-<tag>.jsonl via Jev
    taste-judge.py score        -> accuracy on decided cases, hold rate

Answers files from any engine score the same way: one JSON object per line
with `id` and `choice`.

Usage:
    python3 scripts/taste-judge.py split [--train-frac 0.7]
    python3 scripts/taste-judge.py build [--principles PATH | --no-principles] [--out PATH]
    python3 scripts/taste-judge.py run --cases PATH --out PATH [--timeout 90] [--dry-run]
    python3 scripts/taste-judge.py score --answers PATH [PATH ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TASTE_DIR = Path.home() / ".claude" / "taste"
LABELS = ("approve", "pick_other", "send_back")
HOLD = "hold"
ASSISTANT_CHARS = 900

CRITERIA = {
    "approve": {
        "what": "The owner would accept what the assistant proposed or leaned toward, as-is.",
        "not_for": "Cases where a principle says the proposal is the wrong move or the wrong order.",
    },
    "pick_other": {
        "what": "The owner would pick a different option that the assistant itself listed.",
        "not_for": "Redirects to something the assistant never offered.",
    },
    "send_back": {
        "what": "The question is wrong: the owner would reject the framing, say stop, or redirect "
        "to something not offered (often a more direct deliverable).",
        "not_for": "Disagreeing only on which listed option to take.",
    },
    HOLD: {
        "what": "No principle covers this case; it needs the owner's fresh judgment.",
        "not_for": "Cases a listed principle settles, even loosely.",
    },
}
INSTRUCTIONS = (
    "An AI agent working for the owner ended its turn with the message in case.assistant_message. "
    "Using only the owner's recorded principles, predict how the owner answers. "
    "Hold when the principles do not settle it."
)
INSTRUCTIONS_NO_PRINCIPLES = (
    "An AI agent working for the owner ended its turn with the message in case.assistant_message. "
    "Predict how the owner answers. Hold when you cannot tell."
)


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def split(pairs: list[dict], labels: list[dict], train_frac: float) -> tuple[list[dict], list[dict]]:
    """Join labels to pairs, keep decidable rows, split by time (oldest go to train).

    Desktop sessions can sit under two project folders; duplicates are dropped
    so one copy cannot land in train and the other in test.
    """
    rows = []
    seen: set[tuple[str, str]] = set()
    for lab in sorted(labels, key=lambda r: r["id"]):
        if not lab.get("decidable") or lab.get("label") not in LABELS:
            continue
        pair = pairs[lab["id"]]
        key = (pair["assistant"], pair["owner"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({**lab, "ts": pair["ts"], "assistant": pair["assistant"], "owner": pair["owner"]})
    rows.sort(key=lambda r: r["ts"] or "")
    cut = int(len(rows) * train_frac)
    return rows[:cut], rows[cut:]


def build_case(row: dict, principles: list[dict] | None) -> dict:
    """Blind Jev payload for one test row: no owner reply, no label."""
    case = {
        "assistant_message": row["assistant"][-ASSISTANT_CHARS:],
        "options_offered": row.get("options", []),
        "domain": row.get("domain", ""),
    }
    state: dict = {"case": case}
    if principles is not None:
        state["owner_principles"] = principles
    question = {
        "type": "choice",
        "instructions": INSTRUCTIONS if principles is not None else INSTRUCTIONS_NO_PRINCIPLES,
        "criteria": CRITERIA,
    }
    return {"id": row["id"], "state": state, "questions": {"verdict": question}}


def score(answers: list[dict], truth: dict[int, str]) -> dict:
    """Accuracy on decided cases, hold rate, and forced accuracy (hold counted wrong)."""
    n = decided = correct = 0
    confusion: Counter = Counter()
    for ans in answers:
        if ans["id"] not in truth:
            continue
        n += 1
        choice = ans.get("choice")
        confusion[(truth[ans["id"]], choice)] += 1
        if choice == HOLD:
            continue
        decided += 1
        correct += choice == truth[ans["id"]]
    majority = Counter(truth[a["id"]] for a in answers if a["id"] in truth).most_common(1)
    return {
        "cases": n,
        "decided": decided,
        "hold_rate": round(1 - decided / n, 3) if n else None,
        "accuracy_on_decided": round(correct / decided, 3) if decided else None,
        "forced_accuracy": round(correct / n, 3) if n else None,
        "majority_class_rate": round(majority[0][1] / n, 3) if n and majority else None,
        "confusion": {f"{t}->{c}": k for (t, c), k in sorted(confusion.items())},
    }


def cmd_split(args) -> int:
    pairs = _read_jsonl(TASTE_DIR / "pairs.jsonl")
    labels = _read_jsonl(TASTE_DIR / "labels.jsonl")
    train, test = split(pairs, labels, args.train_frac)
    _write_jsonl(TASTE_DIR / "train.jsonl", train)
    _write_jsonl(TASTE_DIR / "test.jsonl", test)
    print(f"train={len(train)} {dict(Counter(r['label'] for r in train))}")
    print(f"test={len(test)} {dict(Counter(r['label'] for r in test))}")
    return 0


def cmd_build(args) -> int:
    principles = None
    if not args.no_principles:
        principles = json.loads(Path(args.principles).read_text(encoding="utf-8"))
    test = _read_jsonl(TASTE_DIR / "test.jsonl")
    cases = [build_case(r, principles) for r in test]
    _write_jsonl(Path(args.out), cases)
    print(f"wrote {len(cases)} cases to {args.out}")
    return 0


def cmd_run(args) -> int:
    import jev_transport

    cases = _read_jsonl(Path(args.cases))
    if args.dry_run:
        import jev_limits

        sizes = [jev_limits.estimate_tokens({"state": c["state"], "questions": c["questions"]}) for c in cases]
        print(f"{len(cases)} cases, est request tokens max={max(sizes)} total={sum(sizes)}")
        return 0
    ok, why = jev_transport.available()
    if not ok:
        print(f"jev unavailable: {why}", file=sys.stderr)
        return 2
    out = []
    for case in cases:
        data = jev_transport.evaluate_packed(case["state"], case["questions"], timeout=args.timeout)
        verdict = data["answers"]["verdict"]
        out.append({"id": case["id"], "choice": verdict["choice"], "probabilities": verdict.get("probabilities")})
    _write_jsonl(Path(args.out), out)
    print(f"wrote {len(out)} answers to {args.out}")
    return 0


def cmd_score(args) -> int:
    truth = {r["id"]: r["label"] for r in _read_jsonl(TASTE_DIR / "test.jsonl")}
    for path in args.answers:
        print(Path(path).name, json.dumps(score(_read_jsonl(Path(path)), truth)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("split")
    p.add_argument("--train-frac", type=float, default=0.7)
    p.set_defaults(fn=cmd_split)
    p = sub.add_parser("build")
    p.add_argument("--principles", default=str(TASTE_DIR / "principles.json"))
    p.add_argument("--no-principles", action="store_true")
    p.add_argument("--out", default=str(TASTE_DIR / "cases.jsonl"))
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("run")
    p.add_argument("--cases", default=str(TASTE_DIR / "cases.jsonl"))
    p.add_argument("--out", default=str(TASTE_DIR / "answers-jev.jsonl"))
    p.add_argument("--timeout", type=float, default=90)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("score")
    p.add_argument("--answers", nargs="+", required=True)
    p.set_defaults(fn=cmd_score)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
