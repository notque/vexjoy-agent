#!/usr/bin/env python3
"""Scan content for negative framing patterns.

VexJoy and WrestleJoy are joy-centered publications. Content should frame
experiences positively or neutrally, not through grievance, accusation,
or victimhood. This script detects negative framing patterns that don't
match the joy-centered editorial voice.

Usage:
    python3 scripts/scan-negative-framing.py <file>
    python3 scripts/scan-negative-framing.py <file> --format json
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Patterns that signal negative framing
NEGATIVE_PATTERNS = [
    # Victimhood framing
    (r"\bwithout credit\b", "victimhood", "Frames as being wronged. Reframe around the experience or observation."),
    (
        r"\bno attribution\b",
        "victimhood",
        "Frames as being wronged. Focus on the interesting question, not the grievance.",
    ),
    (r"\bstolen\b", "accusation", "Implies theft. Ideas spread, they aren't stolen."),
    (r"\btook my\b", "accusation", "Implies taking. Reframe around sharing or spreading."),
    (r"\bcopied\b", "accusation", "Implies copying. Use 'similar patterns appeared' or 'the same ideas showed up'."),
    (r"\bripped off\b", "accusation", "Direct accusation. Remove entirely."),
    (r"\bplagiari", "accusation", "Direct accusation. Remove entirely."),
    # Grievance language
    (r"\bunfair\b", "grievance", "Grievance framing. Reframe around what's interesting about the situation."),
    (r"\bdeserve\b", "grievance", "Entitlement framing. Nobody deserves credit, credit is given freely."),
    (r"\bowed\b", "grievance", "Entitlement framing. Reframe around generosity."),
    (r"\bshould have credited\b", "grievance", "Prescriptive grievance. Suggest, don't demand."),
    (r"\bdidn't even\b", "grievance", "Indignation marker. Reframe neutrally."),
    # Passive aggression
    (r"\bconvenient(ly)?\b", "passive_aggression", "Implies bad faith. State facts without implying motive."),
    (r"\binteresting timing\b", "passive_aggression", "Implies suspicion. State the timeline factually."),
    (
        r"\bcoincidence\b",
        "passive_aggression",
        "Often used sarcastically. If sincere, keep. If implying suspicion, reframe.",
    ),
    # Bitterness
    (
        r"\bpushed me over the edge\b",
        "bitterness",
        "Frames action as reactive to negative experience. Reframe as positive decision.",
    ),
    (r"\blast straw\b", "bitterness", "Frames as cumulative frustration. Reframe as moment of clarity."),
    (r"\bfed up\b", "bitterness", "Frustration framing. Reframe around what you decided to do instead."),
    (r"\btired of\b", "bitterness", "Fatigue/frustration framing. Reframe around energy and direction."),
    (r"\bsick of\b", "bitterness", "Strong frustration. Reframe entirely."),
    # Negative self-framing
    (
        r"\bnobody (cares|listens|noticed)\b",
        "self_pity",
        "Self-pity framing. Reframe around what you learned or built.",
    ),
    (
        r"\bno one (cares|listens|noticed)\b",
        "self_pity",
        "Self-pity framing. Reframe around what you learned or built.",
    ),
    (r"\bfelt (ignored|invisible|unheard)\b", "self_pity", "Victimhood framing. Reframe around the experience itself."),
    (r"\bfeels like being unheard\b", "self_pity", "Victimhood framing. Reframe around the interesting observation."),
    # Accusatory structures
    (
        r"\bclaim(s|ed|ing)? (to have|they|of)\b",
        "accusatory",
        "Implies the other person is lying. Use 'said' or 'explained' instead.",
    ),
    (r"\bso-called\b", "accusatory", "Dismissive. Use the actual term without scare quotes."),
    (r"\ballegedly\b", "accusatory", "Legal/adversarial framing. State facts directly."),
    # Negative emotional framing
    (
        r"\bfrustrat(ed|ing|ion)\b",
        "negative_emotion",
        "Names a negative emotion. Show it through structure or reframe positively.",
    ),
    (
        r"\bangry\b",
        "negative_emotion",
        "Names a negative emotion. Andy's voice shows emotion through structure, not naming.",
    ),
    (r"\bbothers? me\b", "negative_emotion", "Names a negative emotion. Reframe around what's interesting instead."),
    (r"\bupset\b", "negative_emotion", "Names a negative emotion. Reframe around what you learned."),
    (r"\bdisappoint", "negative_emotion", "Names a negative emotion. Reframe around what happened next."),
    (r"\bresent", "negative_emotion", "Names a negative emotion. Reframe entirely."),
    # Defensive framing
    (
        r"\bi'm not (accusing|attacking|blaming)\b",
        "defensive",
        "Defensive disclaimer implies you might be. Remove the disclaimer and the content won't read as accusatory.",
    ),
    (
        r"\bthis isn't about (blame|credit|theft)\b",
        "defensive",
        "Defensive disclaimer. If you have to say what it isn't, the framing might still be negative.",
    ),
    (
        r"\bi don't want (credit|recognition|fame)\b",
        "defensive",
        "Protesting too much. Just don't mention credit at all.",
    ),
]


def scan_file(filepath: str) -> list[dict]:
    """Scan a file for negative framing patterns."""
    content = Path(filepath).read_text()
    lines = content.split("\n")
    hits = []

    for i, line in enumerate(lines, 1):
        # Skip frontmatter
        if i <= 8 and (
            line.startswith("---")
            or line.startswith("title:")
            or line.startswith("date:")
            or line.startswith("description:")
            or line.startswith("tags:")
            or line.startswith("categories:")
            or line.startswith("draft:")
        ):
            continue

        for pattern, category, suggestion in NEGATIVE_PATTERNS:
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for match in matches:
                hits.append(
                    {
                        "line": i,
                        "column": match.start() + 1,
                        "category": category,
                        "matched": match.group(),
                        "context": line.strip()[:120],
                        "suggestion": suggestion,
                    }
                )

    return hits


def main():
    parser = argparse.ArgumentParser(description="Scan for negative framing patterns")
    parser.add_argument("file", help="File to scan")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    hits = scan_file(args.file)

    if args.format == "json":
        print(json.dumps({"hits": hits, "total": len(hits)}, indent=2))
    else:
        if not hits:
            print(f"JOY CHECK PASSED. {args.file}: zero negative framing patterns detected.")
            sys.exit(0)

        print(f"{args.file}: {len(hits)} negative framing pattern(s) detected\n")
        for hit in hits:
            print(f'  L{hit["line"]} [{hit["category"]}] "{hit["matched"]}"')
            print(f"    {hit['context']}")
            print(f"    -> {hit['suggestion']}")
            print()

        # Summary by category
        categories = {}
        for hit in hits:
            categories[hit["category"]] = categories.get(hit["category"], 0) + 1
        print("Summary:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
