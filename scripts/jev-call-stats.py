#!/usr/bin/env python3
"""Per-script Jev call counts from learning.db (recorded by jev_router_common.call_jev).

python3 scripts/jev-call-stats.py            # last 7 days
python3 scripts/jev-call-stats.py --days 30
python3 scripts/jev-call-stats.py --json
python3 scripts/jev-call-stats.py --answers jev-route.py  # answer distribution per question key
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "lib"))
from learning_db_v2 import jev_call_stats, jev_calls_with_answers


def _print_answer_distribution(script: str | None, days: float) -> int:
    """Print per-question-key distribution summary from stored answers. No raw text."""
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = jev_calls_with_answers(script=script or None, since=since, limit=5000)
    if not rows:
        print(f"no stored answers for script={script!r} in the last {days:g} days")
        return 0

    # Accumulate per question key: top probability (or noul) values.
    key_values: dict[str, list[float]] = {}
    for r in rows:
        answers = r.get("answers")
        if not isinstance(answers, dict):
            continue
        for qkey, ans in answers.items():
            if not isinstance(ans, dict):
                continue
            # Extract the primary numeric signal: noul, top probability, or score.
            val: float | None = None
            if "noul" in ans and isinstance(ans["noul"], (int, float)):
                val = float(ans["noul"])
            elif "probabilities" in ans and isinstance(ans["probabilities"], dict):
                probs = ans["probabilities"]
                float_probs = [float(v) for v in probs.values() if isinstance(v, (int, float))]
                if float_probs:
                    val = max(float_probs)
            elif "score" in ans and isinstance(ans["score"], (int, float)):
                val = float(ans["score"])
            if val is not None:
                key_values.setdefault(qkey, []).append(val)

    if not key_values:
        print("no numeric answer values found in stored answers")
        return 0

    print(f"{'question key':<40}{'count':>7}{'mean':>8}{'p10':>8}{'p50':>8}{'p90':>8}")
    for qkey in sorted(key_values):
        vals = sorted(key_values[qkey])
        n = len(vals)
        mean = sum(vals) / n
        p10 = vals[int(n * 0.1)] if n >= 10 else vals[0]
        p50 = vals[n // 2]
        p90 = vals[int(n * 0.9)] if n >= 10 else vals[-1]
        print(f"{qkey:<40}{n:>7}{mean:>8.3f}{p10:>8.3f}{p50:>8.3f}{p90:>8.3f}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--never-called", action="store_true", help="List Jev scripts on disk with zero recorded calls in the window."
    )
    ap.add_argument(
        "--answers",
        metavar="SCRIPT",
        default=None,
        help="Print per-question-key distribution summary from stored answers for SCRIPT.",
    )
    a = ap.parse_args()

    if a.answers is not None:
        return _print_answer_distribution(a.answers, a.days)

    rows = jev_call_stats(a.days)
    if a.never_called:
        called = {r["script"] for r in rows}
        on_disk = sorted(p.name for p in Path(__file__).resolve().parent.glob("jev-*.py"))
        never = [n for n in on_disk if n not in called]
        print(f"{len(never)}/{len(on_disk)} Jev scripts never called in the last {a.days:g} days:")
        for n in never:
            print(f"  {n}")
        return 0
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print(f"no Jev calls recorded in the last {a.days:g} days")
        return 0
    total = sum(r["calls"] for r in rows)
    print(f"{'script':<40}{'calls':>7}{'failed':>8}{'avg ms':>9}{'input tok':>11}{'questions':>11}")
    for r in rows:
        print(
            f"{r['script']:<40}{r['calls']:>7}{r['failed'] or 0:>8}{(r['avg_ms'] or 0):>9.0f}{r['input_tokens'] or 0:>11}{r['questions'] or 0:>11}"
        )
    print(f"{'total':<40}{total:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
