#!/usr/bin/env python3
"""Validate that every pipeline in pipeline-index.json points at a real doc.

``skills/process/workflow/references/pipeline-index.json`` is hand-maintained — the
generator that builds skills/INDEX.json and agents/INDEX.json skips it. Nothing
else checks it either: ``scripts/validate-do-references.py`` resolves component
*names* mentioned in prose, so an entry whose ``file`` points at a deleted doc
passes clean. That gap is not hypothetical. Commit b2db049e deleted
perses-dac-pipeline.md and perses-plugin-pipeline.md and claimed in its own
message to have cleaned this index; it never touched the file. Both entries
survived as routable pipelines backed by nothing, and every check in CI passed.

Three ways an entry goes wrong, one check each:

  P1 MISSING-FILE    ``file`` is absent, or names a path that does not exist.
                     The router can select the pipeline and the orchestrator
                     then has no phases to run.

  P2 PHANTOM-PHASE   A name in ``phases`` appears in no heading of the
                     referenced doc. The index advertises a phase the doc does
                     not define, so the manifest promises work that cannot run.
                     Live case: the voice pipeline declared 13 phases while its
                     ``file`` pointed at a seven-line pointer stub defining none.

  P3 NO-PHASES       ``phases`` is absent or empty. Phases are what makes a
                     pipeline a pipeline rather than a skill, and /do's
                     PIPELINE-SELECTION RULE keys on having real phases. Live
                     case: comprehensive-review and toolkit-improvement each
                     declared none while their docs defined 13 and 10.

  P4 FRONTMATTER-DRIFT  ``pairs_with`` (or ``triggers``) differs from the
                     ``routing:`` frontmatter of the referenced doc, which is
                     the source of truth (/do SKILL.md). Live case: 14 of 26
                     entries disagreed after hand edits; game-dev paired with
                     itself. Retired names in frontmatter compare as their
                     successor (RETIRED_PAIRS). Triggers compare only for
                     pipeline docs: a SKILL.md's triggers route the skill, and
                     its pipeline entry keeps its own narrower set.

  P5 DUPLICATE       A name repeats in ``pairs_with`` or ``triggers``.

Phase matching is deliberately loose — a declared phase counts as present when
it appears anywhere in any heading line, case-insensitively. Docs number and
decorate their headings ("## Phase 3c: WAVE 3 DISPATCH — Adversarial
Perspectives"), so anchoring tighter would fail on formatting rather than on
substance. The check catches a phase that is absent, not one that is styled
differently.

Exit codes:
    0 — every entry resolves to a doc that defines the phases it declares
    1 — one or more failures

Usage:
    python3 scripts/validate-pipeline-index.py
    python3 scripts/validate-pipeline-index.py --verbose
    python3 scripts/validate-pipeline-index.py --index path/to/other-index.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.frontmatter import parse_frontmatter

DEFAULT_INDEX = REPO_ROOT / "skills" / "process" / "workflow" / "references" / "pipeline-index.json"


# Components #993 retired that pipeline frontmatter still names, mapped to the
# name the index uses instead (None: dropped, no routable successor). Fixing
# the frontmatter shrinks this map; stale_retired_names() fails on a name no
# frontmatter uses any more, so the map cannot outlive the debt.
RETIRED_PAIRS: dict[str, str | None] = {
    "agent-evaluation": "toolkit",
    "codebase-overview": "assessment",
    "parallel-code-review": "review",
    "pipeline-retro": None,
    "planning": "workflow",
    "research-pipeline": "research",
    "routing-table-updater": "toolkit",
    "systematic-code-review": "review",
    "voice-validator": "writing",
}


def _dedup(items: list) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item)
        if text not in out:
            out.append(text)
    return out


def _routing_frontmatter(doc: Path) -> dict | None:
    """The doc's ``routing:`` mapping, or None when it has no frontmatter routing block."""
    try:
        fm, _ = parse_frontmatter(doc.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    routing = (fm or {}).get("routing")
    return routing if isinstance(routing, dict) else None


def expected_pairs(frontmatter_pairs: list) -> list[str]:
    """The index's pairs_with for a frontmatter list: retired names mapped, duplicates dropped."""
    mapped = [RETIRED_PAIRS.get(str(n), str(n)) for n in frontmatter_pairs]
    return _dedup([n for n in mapped if n])


def drift_failures(name: str, entry: dict, doc: Path, rel: str) -> list[str]:
    """P4 and P5 failures for one entry whose doc exists."""
    failures: list[str] = []
    for key in ("pairs_with", "triggers"):
        values = entry.get(key) or []
        dups = sorted({str(v) for v in values if values.count(v) > 1})
        if dups:
            failures.append(f"  [P5 DUPLICATE] '{name}': {key} repeats {dups}. List each name once.")
    routing = _routing_frontmatter(doc)
    if routing is None:
        return failures
    fm_pairs = routing.get("pairs_with")
    if isinstance(fm_pairs, list):
        want = expected_pairs(fm_pairs)
        if list(entry.get("pairs_with") or []) != want:
            failures.append(
                f"  [P4 FRONTMATTER-DRIFT] '{name}': pairs_with {entry.get('pairs_with') or []} differs from "
                f"'{rel}' frontmatter, which gives {want}. The frontmatter is the source; copy it into the index."
            )
    fm_triggers = routing.get("triggers")
    if doc.name != "SKILL.md" and isinstance(fm_triggers, list) and "triggers" in entry:
        want = _dedup(fm_triggers)
        if list(entry.get("triggers") or []) != want:
            failures.append(
                f"  [P4 FRONTMATTER-DRIFT] '{name}': triggers differ from '{rel}' frontmatter, which gives "
                f"{want}. The frontmatter is the source; copy it into the index."
            )
    return failures


def stale_retired_names(index_path: Path, repo_root: Path) -> list[str]:
    """RETIRED_PAIRS names that no indexed doc's frontmatter pairs_with uses any more."""
    try:
        pipelines = json.loads(index_path.read_text(encoding="utf-8")).get("pipelines") or {}
    except (OSError, json.JSONDecodeError):
        return []
    used: set[str] = set()
    for entry in pipelines.values():
        rel = entry.get("file") if isinstance(entry, dict) else None
        doc = repo_root / rel if rel else None
        routing = _routing_frontmatter(doc) if doc and doc.is_file() else None
        if routing and isinstance(routing.get("pairs_with"), list):
            used |= {str(n) for n in routing["pairs_with"]}
    return sorted(set(RETIRED_PAIRS) - used)


def heading_text(doc: Path) -> str:
    """Every markdown heading in the doc, upper-cased and joined.

    Joined with a separator so a phase cannot match by spanning two headings.
    """
    try:
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return " || ".join(ln for ln in lines if ln.lstrip().startswith("#")).upper()


def check(index_path: Path, repo_root: Path, verbose: bool = False) -> list[str]:
    """Return a list of failure messages, empty when the index is clean."""
    failures: list[str] = []

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"  [P1 MISSING-FILE] cannot read {index_path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"  [P1 MISSING-FILE] {index_path} is not valid JSON: {exc}"]

    pipelines = data.get("pipelines")
    if not isinstance(pipelines, dict):
        return [f"  [P1 MISSING-FILE] {index_path} has no 'pipelines' object"]

    for name in sorted(pipelines):
        entry = pipelines[name] if isinstance(pipelines[name], dict) else {}
        rel = entry.get("file")

        if not rel:
            failures.append(
                f"  [P1 MISSING-FILE] '{name}': no 'file' key. Every pipeline must name "
                f"the doc that defines its phases, so the orchestrator has something to "
                f"read once the router selects it."
            )
            continue

        doc = repo_root / rel
        if not doc.is_file():
            failures.append(
                f"  [P1 MISSING-FILE] '{name}': file '{rel}' does not exist. The router "
                f"can still select this pipeline, and the orchestrator would then have no "
                f"phases to run. Point 'file' at a real doc, or remove the entry."
            )
            continue

        phases = entry.get("phases")
        if not phases:
            failures.append(
                f"  [P3 NO-PHASES] '{name}': no phases declared. Phases are what "
                f"distinguishes a pipeline from a skill and what /do's PIPELINE-SELECTION "
                f"RULE keys on. Add the phase names from the headings in '{rel}'."
            )
            continue

        failures.extend(drift_failures(name, entry, doc, rel))

        headings = heading_text(doc)
        absent = [p for p in phases if str(p).upper() not in headings]
        if absent:
            failures.append(
                f"  [P2 PHANTOM-PHASE] '{name}': phase(s) {absent} appear in no heading of "
                f"'{rel}'. The index advertises work the doc does not define. Correct the "
                f"phases list, or point 'file' at the doc that actually defines them."
            )
        elif verbose:
            print(f"  OK   {name}: {len(phases)} phase(s) resolve in {rel}")

    if verbose:
        print(f"\nChecked {len(pipelines)} pipeline(s)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="Show every pipeline checked")
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help="Index to validate (default: skills/process/workflow/references/pipeline-index.json)",
    )
    args = parser.parse_args()

    print("Checking pipeline index...")
    failures = check(args.index, REPO_ROOT, verbose=args.verbose)
    stale = stale_retired_names(args.index, REPO_ROOT)
    if stale:
        failures.append(
            f"  [P4 FRONTMATTER-DRIFT] RETIRED_PAIRS lists {stale}, which no pipeline frontmatter "
            f"names any more. Remove them from the map."
        )

    for msg in failures:
        print(f"FAIL: {msg}")

    print("\n" + "=" * 60)
    print(f"Total failures: {len(failures)}")
    if failures:
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
