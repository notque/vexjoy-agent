#!/usr/bin/env python3
"""
Report-only audit of cross-entry trigger collisions that lack disambiguation.

Scans skills/INDEX.json and agents/INDEX.json for triggers claimed by more than
one entry (exact or near-duplicate). Reports the subset where no colliding
entry's routing `not_for` actually names (or closely paraphrases) another
entry in the same collision — a `not_for` that exists but talks about
something else gives the router no real disambiguation signal. Ranks
worst-first so CI logs surface the highest-leverage fixes.

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


def build_owner_map(skills: dict, agents: dict) -> dict[str, list[str]]:
    """Map normalized_trigger -> [owners...]. owner is `skill:NAME` or `agent:NAME`."""
    owner_map: dict[str, list[str]] = {}
    for kind, label, entries in (("skills", "skill", skills), ("agents", "agent", agents)):
        for name, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            for trig in entry.get("triggers", []):
                norm = normalize(str(trig))
                if not norm:
                    continue
                owners = owner_map.setdefault(norm, [])
                owner = f"{label}:{name}"
                if owner not in owners:
                    owners.append(owner)
    return owner_map


def build_not_for_map(skills: dict, agents: dict) -> dict[str, str]:
    """Map owner (`skill:NAME`/`agent:NAME`) -> its routing `not_for` text ("" if absent)."""
    not_for_map: dict[str, str] = {}
    for label, entries in (("skill", skills), ("agent", agents)):
        for name, entry in entries.items():
            if isinstance(entry, dict):
                not_for_map[f"{label}:{name}"] = str(entry.get("not_for") or "")
    return not_for_map


_WORD_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
_CUE_RE = re.compile(r"\b(?:use|is)\b")
_WINDOW_END_RE = re.compile(r"[.;)\n]")
_WINDOW_SPAN = 100  # chars scanned after a cue word before giving up on a terminator


def _bare_name(owner: str) -> str:
    """Strip the `skill:`/`agent:` label, leaving the entry's bare slug."""
    return owner.split(":", 1)[1] if ":" in owner else owner


def _name_forms(slug: str) -> set[str]:
    """Slug spellings to search for: as-is, space-joined, underscore-joined."""
    lowered = slug.lower()
    return {lowered, lowered.replace("-", " "), lowered.replace("_", " ")}


def _cue_windows(text: str) -> list[str]:
    """Text spans that follow a routing cue ('use'/'is'), cut at the next clause break.

    Every disambiguating `not_for` in this repo points at its target with
    "(use X)" or "that is X" — never a bare mention. Scoping the name search
    to these cue windows (instead of the whole not_for text) is what stops an
    ordinary skill name that happens to be a common word (e.g. "design") from
    matching every not_for that merely uses that word in prose.
    """
    windows = []
    for m in _CUE_RE.finditer(text):
        rest = text[m.end() : m.end() + _WINDOW_SPAN]
        end = _WINDOW_END_RE.search(rest)
        windows.append(rest[: end.start()] if end else rest)
    return windows


def _mentions_owner(not_for_text: str, owner: str) -> bool:
    """True if a cue window in not_for_text names owner outright, or closely paraphrases its slug.

    Outright: the slug (or its space/underscore spelling) appears as a whole
    phrase inside a cue window. Paraphrase: some same-length run of words in
    a cue window is a near-duplicate (difflib ratio >= NEAR_DUP_RATIO) of the
    slug. A not_for that is merely non-empty but never points at this owner
    does not count — that was the prior bug.
    """
    if not not_for_text:
        return False
    slug = _bare_name(owner).lower()
    forms = _name_forms(slug)
    slug_words = slug.split("-")
    span = len(slug_words)
    slug_joined = "-".join(slug_words)
    for window in _cue_windows(not_for_text.lower()):
        for form in forms:
            if re.search(rf"\b{re.escape(form)}\b", window):
                return True
        words = _WORD_RE.findall(window)
        for i in range(len(words) - span + 1):
            candidate = "-".join(words[i : i + span])
            if difflib.SequenceMatcher(None, candidate, slug_joined).ratio() >= NEAR_DUP_RATIO:
                return True
    return False


def _disambiguated(owners: list[str], not_for_map: dict[str, str]) -> bool:
    """True only when every owner in the collision is linked to another by name.

    A link is a not_for on either owner that names (or paraphrases) the other.
    Owners left with no link to anyone else in the collision leave the router
    without a real disambiguation signal, so the whole collision stays reportable.
    """
    if len(owners) < 2:
        return True
    linked: set[str] = set()
    for a in owners:
        for b in owners:
            if a == b:
                continue
            if _mentions_owner(not_for_map.get(a, ""), b):
                linked.add(a)
                linked.add(b)
    return linked == set(owners)


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


def find_collisions(owner_map: dict[str, list[str]], not_for_map: dict[str, str]) -> tuple[list[dict], int]:
    """Return (reportable_rows, total_collision_count).

    A collision is exact (one normalized trigger owned by >1 entry) or near-dup
    (two triggers from different owners that are near-duplicates). Reportable =
    collisions where no owner's not_for names another owner in the collision.
    """
    collisions: list[dict] = []
    seen_pairs: set[frozenset] = set()

    # Exact collisions: a single normalized trigger with >1 owner.
    for trig in sorted(owner_map):
        owners = owner_map[trig]
        if len(owners) > 1:
            collisions.append(
                {
                    "trigger": trig,
                    "kind": "exact",
                    "owners": sorted(owners),
                    "owner_count": len(owners),
                    "disambiguated": _disambiguated(owners, not_for_map),
                }
            )

    # Near-duplicate collisions: distinct triggers, different owners, near match.
    triggers = sorted(owner_map)
    for i, a in enumerate(triggers):
        for b in triggers[i + 1 :]:
            owners_a = set(owner_map[a])
            owners_b = set(owner_map[b])
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
            collisions.append(
                {
                    "trigger": f"{a}~{b}",
                    "kind": "near-dup",
                    "owners": owners,
                    "owner_count": len(owners),
                    "disambiguated": _disambiguated(owners, not_for_map),
                }
            )

    reportable = [c for c in collisions if not c["disambiguated"]]
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
    not_for_map = build_not_for_map(skills, agents)
    reportable, total = find_collisions(owner_map, not_for_map)
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
    print("WORST UNDISAMBIGUATED COLLISIONS (no not_for names the other owner):")
    shown = rows if top is None else rows[:top]
    for row in shown:
        owners = ", ".join(row["owners"])
        print(f"  {row['kind']:<9} {row['trigger']!r}  {owners}")
    if top is not None and len(rows) > top:
        print(f"  ... and {len(rows) - top} more (use --json for the full list)")
    print("Fix: add a routing.not_for that names the colliding owner. Report-only; exit 0.")


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
