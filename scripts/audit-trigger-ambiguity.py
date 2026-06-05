#!/usr/bin/env python3
"""
Report-only audit of cross-entry trigger collisions that lack disambiguation.

Scans skills/INDEX.json and agents/INDEX.json for triggers claimed by more than
one entry (exact or near-duplicate). Reports the subset where NEITHER colliding
entry carries a routing `not_for` — the router has no disambiguation signal for
these. Ranks worst-first so CI logs surface the highest-leverage fixes.

ADR: trigger-ambiguity-audit. ALWAYS exits 0 — advisory, never blocks a merge.
Missing/unparseable indexes print `ERROR:` to stderr and still exit 0. The
blocking gate for missing indexes is validate-index-integrity.py, which stays.

Usage:
    python scripts/audit-trigger-ambiguity.py
    python scripts/audit-trigger-ambiguity.py --json
    python scripts/audit-trigger-ambiguity.py --top 5
    python scripts/audit-trigger-ambiguity.py --skills-index PATH --agents-index PATH
"""

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "trigger-ambiguity-audit/v1"
NEAR_DUP_RATIO = 0.90
_ARTICLE_RE = re.compile(r"^(?:a|an|the)\s+")


def normalize(trigger: str) -> str:
    """Lowercase, collapse internal whitespace, strip surrounding quotes/punctuation."""
    t = trigger.strip().strip("\"'`")
    t = t.strip().strip(".,:;!?")
    t = re.sub(r"\s+", " ", t)
    return t.lower().strip()


def strip_article(trigger: str) -> str:
    """Remove a leading article (a/an/the) for near-duplicate matching."""
    return _ARTICLE_RE.sub("", trigger, count=1)


def load_index(path: Path, kind: str) -> dict:
    """Return the `{kind: {...}}` entry map from an INDEX file. Raises on I/O error."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get(kind, {})
    return entries if isinstance(entries, dict) else {}


def build_owner_map(skills: dict, agents: dict) -> dict[str, dict]:
    """Map normalized_trigger -> {owners: [...], any_not_for: bool}.

    owner is `skill:NAME` or `agent:NAME`. any_not_for is True when any owner of
    that trigger carries a non-empty routing `not_for`.
    """
    owner_map: dict[str, dict] = {}
    for kind, label, entries in (("skills", "skill", skills), ("agents", "agent", agents)):
        for name, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            has_not_for = bool(entry.get("not_for"))
            for trig in entry.get("triggers", []):
                norm = normalize(str(trig))
                if not norm:
                    continue
                slot = owner_map.setdefault(norm, {"owners": [], "any_not_for": False})
                owner = f"{label}:{name}"
                if owner not in slot["owners"]:
                    slot["owners"].append(owner)
                if has_not_for:
                    slot["any_not_for"] = True
    return owner_map


def _within_edit_distance_1(a: str, b: str) -> bool:
    """True if a and b are within Levenshtein distance 1 (stdlib-only, length-gated)."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        # One substitution: exactly one differing position.
        return sum(ca != cb for ca, cb in zip(a, b)) == 1
    # One insertion/deletion: shorter is the longer with one char removed.
    short, long = (a, b) if la < lb else (b, a)
    i = j = edits = 0
    while i < len(short) and j < len(long):
        if short[i] == long[j]:
            i += 1
            j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            j += 1
    return True


def _near_dup(a: str, b: str) -> bool:
    """True if two distinct triggers are near-duplicates.

    Matches on the article-stripping rule, Levenshtein distance 1, or a
    difflib ratio >= NEAR_DUP_RATIO. All stdlib-only; no third-party dependency.
    """
    if a == b:
        return False
    if strip_article(a) == strip_article(b) or strip_article(b) == a or strip_article(a) == b:
        return True
    if _within_edit_distance_1(a, b):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= NEAR_DUP_RATIO


def find_collisions(owner_map: dict[str, dict]) -> tuple[list[dict], int]:
    """Return (reportable_rows, total_collision_count).

    A collision is exact (one normalized trigger owned by >1 entry) or near-dup
    (two triggers from different owners that are near-duplicates). Reportable =
    collisions where NO owner has a not_for.
    """
    collisions: list[dict] = []
    seen_pairs: set[frozenset] = set()

    # Exact collisions: a single normalized trigger with >1 owner.
    for trig in sorted(owner_map):
        slot = owner_map[trig]
        if len(slot["owners"]) > 1:
            collisions.append(
                {
                    "trigger": trig,
                    "kind": "exact",
                    "owners": sorted(slot["owners"]),
                    "owner_count": len(slot["owners"]),
                    "any_not_for": slot["any_not_for"],
                }
            )

    # Near-duplicate collisions: distinct triggers, different owners, near match.
    triggers = sorted(owner_map)
    for i, a in enumerate(triggers):
        for b in triggers[i + 1 :]:
            owners_a = set(owner_map[a]["owners"])
            owners_b = set(owner_map[b]["owners"])
            # Require at least one differing owner across the two triggers.
            if owners_a == owners_b and len(owners_a) <= 1:
                continue
            if not _near_dup(a, b):
                continue
            key = frozenset((a, b))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            owners = sorted(owners_a | owners_b)
            any_not_for = owner_map[a]["any_not_for"] or owner_map[b]["any_not_for"]
            collisions.append(
                {
                    "trigger": f"{a}~{b}",
                    "kind": "near-dup",
                    "owners": owners,
                    "owner_count": len(owners),
                    "any_not_for": any_not_for,
                }
            )

    reportable = [c for c in collisions if not c["any_not_for"]]
    return reportable, len(collisions)


def rank(reportable: list[dict]) -> list[dict]:
    """Sort worst-first: owner_count desc, exact before near-dup, trigger alpha."""
    kind_order = {"exact": 0, "near-dup": 1}
    return sorted(
        reportable,
        key=lambda c: (-c["owner_count"], kind_order.get(c["kind"], 9), c["trigger"]),
    )


def build_report(skills_path: Path, agents_path: Path) -> dict:
    """Load both indexes and compute the audit report. Raises on I/O error."""
    skills = load_index(skills_path, "skills")
    agents = load_index(agents_path, "agents")
    owner_map = build_owner_map(skills, agents)
    reportable, total = find_collisions(owner_map)
    reportable = rank(reportable)
    return {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "collisions": total,
            "undisambiguated": len(reportable),
            "skills_indexed": len(skills),
            "agents_indexed": len(agents),
        },
        "reportable": reportable,
    }


def print_human(report: dict, top: int | None) -> None:
    totals = report["totals"]
    print(
        f"trigger-ambiguity-audit: {totals['collisions']} collisions, "
        f"{totals['undisambiguated']} undisambiguated (report-only, non-blocking)"
    )
    rows = report["reportable"]
    if not rows:
        print("No undisambiguated collisions. Nothing to fix.")
        return
    print("WORST UNDISAMBIGUATED COLLISIONS (neither side has not_for):")
    shown = rows if top is None else rows[:top]
    for row in shown:
        owners = ", ".join(row["owners"])
        print(f"  {row['kind']:<9} {row['trigger']!r}  {owners}")
    if top is not None and len(rows) > top:
        print(f"  ... and {len(rows) - top} more (use --json for the full list)")
    print("Fix: add a routing.not_for line to at least one owner per pair. Report-only; exit 0.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report-only trigger-collision audit (always exits 0).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--top", type=int, default=None, help="Limit human summary to worst N (JSON always full).")
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--skills-index", type=Path, default=repo_root / "skills" / "INDEX.json")
    parser.add_argument("--agents-index", type=Path, default=repo_root / "agents" / "INDEX.json")
    args = parser.parse_args()

    try:
        report = build_report(args.skills_index, args.agents_index)
    except (OSError, json.JSONDecodeError) as exc:
        # Advisory: a missing/unparseable index must not block. Report and exit 0.
        print(f"ERROR: cannot read index: {exc}", file=sys.stderr)
        return 0

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report, args.top)
    return 0


if __name__ == "__main__":
    # main() returns 0 unconditionally; advisory script never blocks.
    sys.exit(main())
