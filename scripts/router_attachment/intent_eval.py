#!/usr/bin/env python3
"""Score scripts/jev_intent_align.py against labeled request/intent pairs.

expect: aligned (alignment == aligned), review (alignment == review and the
labeled issue fired), clarify (clarification_needed or alignment == review
with a clarification issue). Telemetry writes are disabled so eval runs do
not enter learning.db.

Usage: python3 scripts/router_attachment/intent_eval.py --out <fresh.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import jev_intent_align

jev_intent_align._record_intent_alignment = None

ISSUE_KEYS = {
    "constraints": ("proposed intent drops explicit constraints",),
    "adds": ("proposed intent adds unrequested work",),
    "narrow": ("proposed intent drops material scope", "selected route omits material scope"),
    "clarify": ("essential clarification is needed",),
}


def correct(case: dict, receipt: dict) -> bool:
    alignment = receipt.get("alignment")
    issues = receipt.get("issues") or []
    if case["expect"] == "aligned":
        return alignment == "aligned"
    if case["expect"] == "clarify":
        return bool(receipt.get("clarification_needed")) or (
            alignment == "review" and any(i in issues for i in ISSUE_KEYS["clarify"] + ISSUE_KEYS["narrow"])
        )
    return alignment == "review" and any(i in issues for i in ISSUE_KEYS[case["issue"]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    if args.out.exists():
        ap.error(f"{args.out} exists; give each run a fresh path")
    cases = json.loads((HERE / "intent-cases.json").read_text(encoding="utf-8"))["cases"]

    def one(case: dict) -> dict:
        receipt = jev_intent_align.evaluate_alignment(case["request"], case["route"], case["intent"])
        return {
            "id": case["id"],
            "kind": case["kind"],
            "correct": correct(case, receipt),
            "alignment": receipt.get("alignment"),
            "issues": receipt.get("issues"),
            "scores": receipt.get("scores"),
            "questions_version": receipt.get("questions_version"),
        }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(one, cases))
    by_kind: dict[str, list[bool]] = {}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row["correct"])
    summary = {
        "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 3),
        "errors": sum(r["alignment"] in ("error", "unavailable") for r in rows),
        "by_kind": {k: f"{sum(v)}/{len(v)}" for k, v in by_kind.items()},
    }
    args.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
