#!/usr/bin/env python3
"""Deterministic check that every documented pattern in a SKILL.md carries an
explicit triple-validation verdict (KEEP / FOOTNOTE / DROP).

Pattern blocks are H3 sections inside a parent H2 whose heading matches one of
the recognized parents (case-insensitive substring match):

    Mental Models, Heuristics, Phrase Fingerprints, Patterns

For each pattern block the script looks for a verdict in this priority order:

    1. A line containing `**Verdict**: KEEP` / `FOOTNOTE` / `DROP`
       (markdown-bold "Verdict" label, colon, then the verdict word).
    2. An inline tag at the end of the H3 heading: `(KEEP)`, `(FOOTNOTE)`,
       or `(DROP)`.
    3. A blanket inline tag on the parent H2 -- `## Heuristics (KEEP-verdict)`
       or `## Phrase Fingerprints (FOOTNOTE-verdict, scoped use only)` --
       which applies to every H3 child that does not carry its own verdict.
       Matches the convention voice-feynman ships today.

The verdict requirement is stricter than "any verdict": a shipped SKILL.md
must carry only KEEP and FOOTNOTE patterns. DROP patterns belong in working
notes and never in the shipped file.

Exit codes:
    0 -- every pattern block has a KEEP or FOOTNOTE verdict.
    1 -- one or more pattern blocks lack a verdict OR carry DROP.

Usage:
    python3 scripts/check-skill-verdicts.py path/to/SKILL.md
    python3 scripts/check-skill-verdicts.py path/to/SKILL.md --json

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# H2 headings (case-insensitive substring) whose H3 children require verdicts.
# Substring match so "Mental Models (KEEP-verdict)" still counts as Mental Models.
PATTERN_PARENTS = (
    "mental models",
    "heuristics",
    "phrase fingerprints",
    "patterns",
)

VERDICT_WORDS = ("KEEP", "FOOTNOTE", "DROP")

# `**Verdict**: KEEP` -- bold label, colon, verdict word. Tolerant of optional
# whitespace and trailing punctuation.
VERDICT_LINE_RE = re.compile(
    r"\*\*Verdict\*\*\s*:\s*(KEEP|FOOTNOTE|DROP)\b",
    re.IGNORECASE,
)

# Inline tag at the end of an H3 heading: `### Pattern name (KEEP)` or
# `### Pattern name (KEEP-verdict, ...)` (blanket-verdict shorthand reused on a
# sub-section heading -- voice-feynman ships this for its FOOTNOTE phrase set).
HEADING_TAG_RE = re.compile(
    r"\((KEEP|FOOTNOTE|DROP)(?:-verdict\b[^)]*)?\)\s*$",
    re.IGNORECASE,
)

# Blanket verdict on a parent H2 heading: `## Heuristics (KEEP-verdict, ...)`.
# Matches anywhere inside the heading text, with `-verdict` suffix to avoid
# accidentally matching a stray "(KEEP)" elsewhere.
H2_BLANKET_RE = re.compile(r"\((KEEP|FOOTNOTE|DROP)-verdict\b", re.IGNORECASE)


@dataclass
class PatternBlock:
    """A single H3 section discovered under a recognized pattern parent."""

    name: str
    parent: str
    line: int
    verdict: str | None = None  # uppercase if found
    parent_blanket_verdict: str | None = None  # uppercase if parent H2 declares one
    body_lines: list[str] = field(default_factory=list)


def _is_pattern_parent(h2_text: str) -> bool:
    lower = h2_text.lower()
    return any(parent in lower for parent in PATTERN_PARENTS)


def _strip_heading(line: str, level: int) -> str:
    return line[level:].strip().rstrip("#").strip()


def _heading_inline_verdict(heading_text: str) -> str | None:
    match = HEADING_TAG_RE.search(heading_text)
    if not match:
        return None
    return match.group(1).upper()


def _h2_blanket_verdict(h2_text: str) -> str | None:
    match = H2_BLANKET_RE.search(h2_text)
    if not match:
        return None
    return match.group(1).upper()


def _body_verdict(body_lines: list[str]) -> str | None:
    for line in body_lines:
        match = VERDICT_LINE_RE.search(line)
        if match:
            return match.group(1).upper()
    return None


def discover_pattern_blocks(text: str) -> list[PatternBlock]:
    """Walk the markdown line-by-line and collect H3 blocks under pattern H2s."""
    blocks: list[PatternBlock] = []
    current_parent: str | None = None
    current_parent_blanket: str | None = None
    current_block: PatternBlock | None = None

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()

        if line.startswith("## ") and not line.startswith("### "):
            # Close any open block before switching parent context.
            if current_block is not None:
                blocks.append(current_block)
                current_block = None
            h2_text = _strip_heading(line, 2)
            if _is_pattern_parent(h2_text):
                current_parent = h2_text
                current_parent_blanket = _h2_blanket_verdict(h2_text)
            else:
                current_parent = None
                current_parent_blanket = None
            continue

        if line.startswith("### ") and current_parent is not None:
            if current_block is not None:
                blocks.append(current_block)
            h3_text = _strip_heading(line, 3)
            current_block = PatternBlock(
                name=h3_text,
                parent=current_parent,
                line=idx,
                parent_blanket_verdict=current_parent_blanket,
            )
            continue

        if line.startswith("### ") and current_parent is None:
            # H3 outside a recognized parent -- not a pattern block.
            continue

        if current_block is not None:
            current_block.body_lines.append(line)

    if current_block is not None:
        blocks.append(current_block)

    # Resolve verdict per block. Priority: explicit body line > heading tag >
    # parent H2 blanket. The body line wins because a per-block override is the
    # most specific signal a maintainer can leave; the parent blanket is the
    # convention voice-feynman ships and applies only when nothing more
    # specific is set.
    for block in blocks:
        verdict = _body_verdict(block.body_lines) or _heading_inline_verdict(block.name) or block.parent_blanket_verdict
        block.verdict = verdict

    return blocks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify every documented pattern in a SKILL.md carries a KEEP/FOOTNOTE verdict.",
    )
    parser.add_argument("skill_path", type=Path, help="Path to the SKILL.md file to check.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    args = parser.parse_args(argv)

    path: Path = args.skill_path
    if not path.exists():
        msg = f"check-skill-verdicts: file not found: {path}"
        print(msg, file=sys.stderr)
        if args.json:
            print(json.dumps({"ok": False, "error": "not_found", "path": str(path)}))
        return 1

    text = path.read_text(encoding="utf-8")
    blocks = discover_pattern_blocks(text)

    missing = [b for b in blocks if b.verdict is None]
    dropped = [b for b in blocks if b.verdict == "DROP"]
    ok_blocks = [b for b in blocks if b.verdict in ("KEEP", "FOOTNOTE")]

    failed = bool(missing or dropped)

    if args.json:
        report = {
            "ok": not failed,
            "path": str(path),
            "total_patterns": len(blocks),
            "keep_or_footnote": len(ok_blocks),
            "missing_verdict": [asdict(b) | {"body_lines": None} for b in missing],
            "drop_in_shipped": [asdict(b) | {"body_lines": None} for b in dropped],
        }
        print(json.dumps(report, indent=2))
        return 1 if failed else 0

    # Human-readable output.
    print(f"check-skill-verdicts: {path}")
    print(f"  pattern blocks found: {len(blocks)}")
    print(f"  KEEP or FOOTNOTE   : {len(ok_blocks)}")
    print(f"  missing verdict    : {len(missing)}")
    print(f"  DROP in shipped    : {len(dropped)}")

    if missing:
        print("\nPatterns missing a verdict:", file=sys.stderr)
        for b in missing:
            print(f"  - [{b.parent}] {b.name} (line {b.line})", file=sys.stderr)

    if dropped:
        print("\nDROP-verdict patterns leaked into shipped file:", file=sys.stderr)
        for b in dropped:
            print(f"  - [{b.parent}] {b.name} (line {b.line})", file=sys.stderr)

    if failed:
        print(
            "\nFAIL: every pattern block under Mental Models / Heuristics / "
            "Phrase Fingerprints / Patterns must carry **Verdict**: KEEP or "
            "FOOTNOTE (or an inline (KEEP)/(FOOTNOTE) tag in the heading). "
            "DROP patterns belong in working notes only.",
            file=sys.stderr,
        )
        return 1

    print("\nPASS: all pattern blocks carry KEEP or FOOTNOTE verdicts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
