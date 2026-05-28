#!/usr/bin/env python3
"""Blind A/B benchmark: does the review-validation gate (#3) add value?

Commit a7814290 wired scripts/validate-review-output.py into the review-dispatch
flow: after a reviewer returns markdown, its output is validated against a JSON
Schema; schema-invalid output is caught (retry once, then stop). This harness
measures whether that gate ADDS VALUE over the prior status quo (prose accepted
as-is) on a labeled corpus of synthetic review outputs.

Two arms
--------
  Arm A (baseline / pre-#3): prose-only. Reviewer output is accepted as-is.
      There is NO detector, so the arm's decision is always ACCEPT.
  Arm B (with #3): output is piped through validate-review-output.py
      --type {parallel,systematic}. Exit 0 -> ACCEPT; exit 1/2 -> FLAG.

Blind property
--------------
Each corpus item carries a hidden ground-truth label ("valid" or "malformed").
The detector (Arm B) decides ACCEPT/FLAG from the *text only* — it never sees the
label. Labels are consulted exactly once, at the end, to build each arm's
confusion matrix. Arm A needs no detector (always ACCEPT) but is scored against
the same hidden labels.

Confusion matrix convention (positive class = "malformed", i.e. SHOULD be flagged)
  TP = malformed item correctly FLAGGED
  FN = malformed item wrongly ACCEPTED (gate missed a bad review)
  FP = valid item wrongly FLAGGED   (gate rejected a good review — the real risk)
  TN = valid item correctly ACCEPTED

Run:
  python3 scripts/tests/bench_review_gate_ab.py
  python3 scripts/tests/bench_review_gate_ab.py --json   # machine-readable

Exit 0 always (this is a measurement, not a pass/fail gate).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VALIDATOR = Path(__file__).resolve().parent.parent / "validate-review-output.py"


# ---------------------------------------------------------------------------
# Corpus: labeled synthetic review outputs.
#   label: "valid"  -> well-formed, SHOULD pass (FP if flagged)
#   label: "malformed" -> defective, SHOULD be flagged (FN if accepted)
#   defect: human description of the injected defect (for reconciliation only)
# ---------------------------------------------------------------------------


@dataclass
class Item:
    id: str
    review_type: str  # "parallel" | "systematic"
    label: str  # "valid" | "malformed"
    defect: str  # ground-truth note, hidden from the detector
    markdown: str = field(repr=False)


# ---- Well-formed parallel review ------------------------------------------
PARALLEL_VALID = """\
## Summary

Three reviewers examined the diff. One blocking issue in auth, otherwise sound.

## Severity Matrix

| Severity | Count | Summary |
|----------|-------|---------|
| Critical | 1     | Auth bypass |
| High     | 1     | N+1 query |
| Medium   | 0     | -         |
| Low      | 1     | Naming    |

## Findings

### Critical

1. **[Security] Auth token not verified** `internal/auth/mw.go:42`
   Issue: token signature is never checked before trusting claims.
   Recommendation: verify signature with the configured key.

### High

1. **[Business-Logic] N+1 query in list handler** `internal/api/list.go:88`
   Issue: query runs once per row.
   Recommendation: batch with a single IN query.

### Low

1. **[Architecture] Inconsistent receiver naming** `internal/api/list.go:12`
   Recommendation: standardize on `h`.

## Summary by Reviewer

| Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
|----------------|----------|------|--------|-----|
| Security       | 1        | 0    | 0      | 0   |
| Business-Logic | 0        | 1    | 0      | 0   |
| Architecture   | 0        | 0    | 0      | 1   |

**BLOCK** - One auth-bypass critical must be fixed before merge.
"""

# ---- Well-formed systematic review ---------------------------------------
SYSTEMATIC_VALID = """\
## Summary

Reviewed the cache layer. One should-fix around eviction; overall acceptable.

## Risk Level: MEDIUM

## Findings

### Should Fix

1. **Unbounded cache growth** `internal/cache/store.go:53`
   Issue: entries are never evicted under memory pressure.
   Recommendation: add an LRU bound.

### Suggestions

1. **Extract magic number** `internal/cache/store.go:17`
   Recommendation: name the 3600 TTL constant.

## What Was Done Well

- Clear separation between store and policy.
- Good table-driven tests.

## Verdict: REQUEST-CHANGES

Rationale: eviction gap should be addressed before merge.
"""


def _build_corpus() -> list[Item]:
    items: list[Item] = []

    # ===================== PARALLEL — VALID (negatives) ====================
    items.append(Item("P01", "parallel", "valid", "none — canonical well-formed", PARALLEL_VALID))

    # Valid but APPROVE with zero findings (edge: clean review still well-formed)
    items.append(
        Item(
            "P02",
            "parallel",
            "valid",
            "none — clean approve, empty findings, matrix all zero",
            """\
## Summary

All three reviewers found the diff clean. No issues across domains.

## Severity Matrix

| Severity | Count | Summary |
|----------|-------|---------|
| Critical | 0     | -       |
| High     | 0     | -       |
| Medium   | 0     | -       |
| Low      | 0     | -       |

## Summary by Reviewer

| Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
|----------------|----------|------|--------|-----|
| Security       | 0        | 0    | 0      | 0   |
| Business-Logic | 0        | 0    | 0      | 0   |
| Architecture   | 0        | 0    | 0      | 0   |

**APPROVE** - No issues found across security, logic, or architecture.
""",
        )
    )

    # =================== PARALLEL — MALFORMED (positives) ==================
    # Missing verdict line entirely.
    items.append(
        Item(
            "P03",
            "parallel",
            "malformed",
            "missing verdict",
            PARALLEL_VALID.replace("**BLOCK** - One auth-bypass critical must be fixed before merge.", ""),
        )
    )

    # Finding missing file:line location.
    items.append(
        Item(
            "P04",
            "parallel",
            "malformed",
            "finding missing file:line location",
            PARALLEL_VALID.replace("`internal/auth/mw.go:42`", ""),
        )
    )

    # Finding missing [Reviewer] attribution on the critical item.
    items.append(
        Item(
            "P05",
            "parallel",
            "malformed",
            "finding missing reviewer attribution",
            PARALLEL_VALID.replace("**[Security] Auth token not verified**", "**Auth token not verified**"),
        )
    )

    # Truncated / unparseable (cut mid-table).
    items.append(
        Item(
            "P06",
            "parallel",
            "malformed",
            "truncated output (cut mid-document)",
            "## Summary\n\nThree reviewers examined the diff. One blocking issue in au",
        )
    )

    # Invalid verdict value (not in enum BLOCK/FIX/APPROVE).
    items.append(
        Item(
            "P07",
            "parallel",
            "malformed",
            "invalid verdict value (REJECTED not in enum)",
            PARALLEL_VALID.replace(
                "**BLOCK** - One auth-bypass critical must be fixed before merge.",
                "## Verdict: REJECTED\n",
            ),
        )
    )

    # ==================== SYSTEMATIC — VALID (negatives) ===================
    items.append(Item("S01", "systematic", "valid", "none — canonical well-formed", SYSTEMATIC_VALID))

    # Valid APPROVE, low risk, only positives.
    items.append(
        Item(
            "S02",
            "systematic",
            "valid",
            "none — clean approve with positives only",
            """\
## Summary

Small, well-scoped refactor. No correctness concerns.

## Risk Level: LOW

## What Was Done Well

- Pure rename with no behavior change.
- Tests updated alongside.

## Verdict: APPROVE

Rationale: low-risk mechanical change, safe to merge.
""",
        )
    )

    # ================= SYSTEMATIC — MALFORMED (positives) ==================
    # Missing risk_level (required for systematic).
    items.append(
        Item(
            "S03",
            "systematic",
            "malformed",
            "missing risk_level",
            SYSTEMATIC_VALID.replace("## Risk Level: MEDIUM\n\n", ""),
        )
    )

    # Invalid severity bucket: uses parallel's "Critical" heading in a
    # systematic review (systematic buckets are blocking/should_fix/suggestions).
    # The blocking finding therefore lands in no recognized bucket -> the real
    # should-fix content is lost; combined with removing the legit should-fix
    # this yields a structurally thin review. Here we additionally strip the
    # location to guarantee a schema violation on the surviving finding.
    items.append(
        Item(
            "S04",
            "systematic",
            "malformed",
            "invalid severity bucket heading + finding missing file:line",
            SYSTEMATIC_VALID.replace("### Should Fix", "### Critical").replace(
                "`internal/cache/store.go:53`", "the store file"
            ),
        )
    )

    # Invalid verdict value (not in systematic enum).
    items.append(
        Item(
            "S05",
            "systematic",
            "malformed",
            "invalid verdict value (LGTM not in enum)",
            SYSTEMATIC_VALID.replace("## Verdict: REQUEST-CHANGES", "## Verdict: LGTM"),
        )
    )

    # Completely unparseable prose (no structure at all).
    items.append(
        Item(
            "S06",
            "systematic",
            "malformed",
            "unstructured prose (no headings/verdict/findings)",
            "Looks fine to me, ship it. A couple of small things but nothing blocking really.",
        )
    )

    return items


# ---------------------------------------------------------------------------
# Detectors (blind: receive markdown + type only, NOT the label)
# ---------------------------------------------------------------------------


def detect_arm_a(markdown: str, review_type: str) -> str:
    """Arm A (baseline, pre-#3): prose accepted as-is. Always ACCEPT."""
    return "ACCEPT"


def detect_arm_b(markdown: str, review_type: str) -> tuple[str, int]:
    """Arm B (#3): run the real validator. Exit 0 -> ACCEPT, 1/2 -> FLAG."""
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "--type", review_type, "-"],
        input=markdown,
        capture_output=True,
        text=True,
    )
    decision = "ACCEPT" if proc.returncode == 0 else "FLAG"
    return decision, proc.returncode


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _matrix(decisions: list[tuple[str, str]]) -> dict[str, int]:
    """decisions: list of (label, decision). positive class = 'malformed'."""
    m = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    for label, decision in decisions:
        flagged = decision == "FLAG"
        malformed = label == "malformed"
        if malformed and flagged:
            m["tp"] += 1
        elif malformed and not flagged:
            m["fn"] += 1
        elif not malformed and flagged:
            m["fp"] += 1
        else:
            m["tn"] += 1
    return m


def _rates(m: dict[str, int]) -> dict[str, float]:
    pos = m["tp"] + m["fn"]
    neg = m["fp"] + m["tn"]
    return {
        "detection_rate": m["tp"] / pos if pos else 0.0,  # recall on malformed
        "false_negative_rate": m["fn"] / pos if pos else 0.0,
        "false_positive_rate": m["fp"] / neg if neg else 0.0,
        "specificity": m["tn"] / neg if neg else 0.0,
    }


def run() -> dict:
    corpus = _build_corpus()
    n_valid = sum(1 for i in corpus if i.label == "valid")
    n_malformed = sum(1 for i in corpus if i.label == "malformed")

    per_item = []
    arm_a_dec: list[tuple[str, str]] = []
    arm_b_dec: list[tuple[str, str]] = []

    for it in corpus:
        a = detect_arm_a(it.markdown, it.review_type)
        b, b_exit = detect_arm_b(it.markdown, it.review_type)
        arm_a_dec.append((it.label, a))
        arm_b_dec.append((it.label, b))
        per_item.append(
            {
                "id": it.id,
                "type": it.review_type,
                "label": it.label,  # revealed only now, at reconciliation
                "defect": it.defect,
                "arm_a": a,
                "arm_b": b,
                "arm_b_exit": b_exit,
            }
        )

    return {
        "corpus_size": len(corpus),
        "n_valid": n_valid,
        "n_malformed": n_malformed,
        "arm_a": {"matrix": _matrix(arm_a_dec), "rates": _rates(_matrix(arm_a_dec))},
        "arm_b": {"matrix": _matrix(arm_b_dec), "rates": _rates(_matrix(arm_b_dec))},
        "per_item": per_item,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt_matrix(name: str, m: dict[str, int], r: dict[str, float]) -> str:
    return (
        f"  {name}\n"
        f"    confusion: TP={m['tp']} FN={m['fn']} FP={m['fp']} TN={m['tn']}\n"
        f"    detection_rate (recall on malformed) = {r['detection_rate']:.0%}\n"
        f"    false_negative_rate                  = {r['false_negative_rate']:.0%}\n"
        f"    false_positive_rate (good rejected)  = {r['false_positive_rate']:.0%}\n"
        f"    specificity (good accepted)          = {r['specificity']:.0%}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    res = run()

    if args.json:
        print(json.dumps(res, indent=2))
        return 0

    print("Blind A/B: review-validation gate (#3)")
    print(f"Corpus: {res['corpus_size']} items ({res['n_valid']} valid, {res['n_malformed']} malformed)\n")

    print(_fmt_matrix("Arm A (baseline, prose-only — no validator)", res["arm_a"]["matrix"], res["arm_a"]["rates"]))
    print()
    print(_fmt_matrix("Arm B (with #3 — validate-review-output.py)", res["arm_b"]["matrix"], res["arm_b"]["rates"]))
    print()

    # Per-item table
    print("Per-item (label revealed at reconciliation only):")
    print(f"  {'ID':4} {'TYPE':11} {'LABEL':10} {'ARM_A':7} {'ARM_B':7} {'EXIT':4}  DEFECT")
    for r in res["per_item"]:
        print(
            f"  {r['id']:4} {r['type']:11} {r['label']:10} {r['arm_a']:7} {r['arm_b']:7} "
            f"{str(r['arm_b_exit']):4}  {r['defect']}"
        )

    # False positives = valid items Arm B flagged.
    fps = [r for r in res["per_item"] if r["label"] == "valid" and r["arm_b"] == "FLAG"]
    print(f"\nFalse positives (valid review wrongly flagged by #3): {len(fps)}")
    for r in fps:
        print(f"  - {r['id']} ({r['type']}): {r['defect']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
