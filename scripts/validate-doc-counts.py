#!/usr/bin/env python3
"""Validate count claims in docs against filesystem ground truth.

Greps docs/ + root markdown for "N agents", "N skills", "N hooks", "N scripts",
"N pipelines", "N hook events", "N banned patterns", "N AI patterns", and
verifies each count against the actual filesystem.

Also emits a hook-event registration table from `.claude/settings.json` for
spot-checking the docs/for-ai-wizards.md hook table (B2 auto-regen helper).

Exits 0 on full agreement (within tolerance), 1 when any claim drifts.

Usage:
    python3 scripts/validate-doc-counts.py
    python3 scripts/validate-doc-counts.py --emit-hook-table
    python3 scripts/validate-doc-counts.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ROOT_MARKDOWN = ["README.md", "CONTRIBUTING.md", "CLAUDE.md"]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
BANNED_PATTERNS = REPO_ROOT / "scripts" / "data" / "banned-patterns.json"

CLAIM = re.compile(
    r"\b(\d{1,4})\+?\s+"
    r"(agents?|skills?|hooks?|scripts?|pipelines?|hook events?|"
    r"banned patterns?|AI patterns?|workflow skills?)\b",
    re.IGNORECASE,
)

# Phrases that mark a count as scoped/local rather than a global toolkit claim.
# When any of these qualifiers appear within ~40 chars of the match, skip it —
# "12 agents (Wave 1)" or "Phase 1 hooks" or "collective of 7 agents" are
# describing a subset, not the toolkit total.
SCOPED_QUALIFIERS = re.compile(
    r"\b(?:wave|phase|collective|cluster|cohort|group|subset|"
    r"of these|of the|out of|in this|in the [a-z]+ (?:test|study|experiment|review|wave)|"
    r"experiment|test|study|fabricated|consultation|consensus|"
    r"per[-\s]package|cascading|adversarial|deep[-\s]dive|"
    r"reviewer|consultations?)\b",
    re.IGNORECASE,
)


def is_scoped_claim(line: str, start: int, end: int) -> bool:
    """Return True when the claim sits inside a scoped/local context.

    Looks at ~40 chars before and after the match for qualifier words like
    "wave", "phase", "collective", "experiment". These words mark the count as
    a subset reference, not a toolkit-wide total.
    """
    window = line[max(0, start - 60) : min(len(line), end + 40)]
    return bool(SCOPED_QUALIFIERS.search(window))


def count_files(root: Path, pattern: str = "*") -> int:
    if not root.is_dir():
        return 0
    return sum(1 for _ in root.glob(pattern))


def count_dir_children(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for p in root.iterdir() if p.is_dir())


def ground_truth() -> dict[str, int]:
    truth: dict[str, int] = {}
    truth["agents"] = count_files(REPO_ROOT / "agents", "*.md")
    truth["scripts"] = count_files(REPO_ROOT / "scripts", "*.py")
    truth["hooks"] = count_files(REPO_ROOT / "hooks", "*.py")

    # skills: top-level dirs under skills/ + nested SKILL.md count
    skills_dir = REPO_ROOT / "skills"
    skill_count = 0
    if skills_dir.is_dir():
        for skill_md in skills_dir.rglob("SKILL.md"):
            skill_count += 1
        # Plus voice-* and other simple-named skill dirs without SKILL.md (rare)
    truth["skills"] = skill_count

    # workflow skills (pipelines)
    pipelines_dir = skills_dir / "workflow" / "references"
    truth["pipelines"] = count_files(pipelines_dir, "*.md")

    # hook events
    if SETTINGS.is_file():
        try:
            data = json.loads(SETTINGS.read_text())
            truth["hook events"] = len(data.get("hooks", {}))
        except Exception:
            truth["hook events"] = 0

    # banned patterns
    if BANNED_PATTERNS.is_file():
        try:
            data = json.loads(BANNED_PATTERNS.read_text())
            categories = data.get("categories", {}) if isinstance(data, dict) else {}
            patterns = 0
            for v in categories.values():
                if isinstance(v, list):
                    patterns += len(v)
                elif isinstance(v, dict) and "patterns" in v:
                    patterns += len(v["patterns"])
            truth["banned patterns"] = patterns
            truth["banned categories"] = len(categories)
            truth["AI patterns"] = patterns
        except Exception:
            pass

    return truth


def collect_markdown_files() -> list[Path]:
    files = []
    if DOCS_DIR.is_dir():
        files.extend(sorted(DOCS_DIR.rglob("*.md")))
    for name in ROOT_MARKDOWN:
        p = REPO_ROOT / name
        if p.is_file():
            files.append(p)
    return files


def normalize(thing: str) -> str:
    t = thing.lower().rstrip("s")
    if t == "hook event":
        return "hook events"
    if t == "ai pattern":
        return "AI patterns"
    if t == "banned pattern":
        return "banned patterns"
    if t == "workflow skill":
        return "skills"
    return t + "s"


def emit_hook_table() -> str:
    if not SETTINGS.is_file():
        return "(settings.json missing)"
    data = json.loads(SETTINGS.read_text())
    out = ["| Event | Hooks Registered |", "|-------|-----------------|"]
    for event in sorted(data.get("hooks", {}).keys()):
        names: list[str] = []
        for item in data["hooks"][event]:
            for h in item.get("hooks", []):
                cmd = h.get("command", "")
                m = re.search(r"hooks/([a-z0-9_-]+)\.py", cmd)
                if m:
                    names.append(m.group(1).replace("_", "-"))
        out.append(f"| `{event}` | {', '.join(names)} |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--emit-hook-table", action="store_true")
    parser.add_argument(
        "--tolerance",
        type=int,
        default=0,
        help="allow claims within N of ground truth (default: 0)",
    )
    args = parser.parse_args()

    if args.emit_hook_table:
        print(emit_hook_table())
        return 0

    truth = ground_truth()
    drifts: list[dict] = []
    checked = 0

    for md in collect_markdown_files():
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = md.relative_to(REPO_ROOT)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in CLAIM.finditer(line):
                claimed = int(match.group(1))
                key = normalize(match.group(2))
                if key not in truth:
                    continue
                checked += 1
                actual = truth[key]
                # Skip scoped local references ("Wave 1, 12 agents", "Phase 1 hooks", etc.)
                if is_scoped_claim(line, match.start(), match.end()):
                    continue
                # Some claims include "+" suffix meaning "at least N"; respect intent
                approx = "+" in line[match.start() : match.end() + 1]
                if approx:
                    if claimed > actual:
                        drifts.append(
                            {
                                "source": str(rel),
                                "line": line_no,
                                "claim": match.group(0),
                                "actual": actual,
                            }
                        )
                else:
                    if abs(claimed - actual) > args.tolerance:
                        drifts.append(
                            {
                                "source": str(rel),
                                "line": line_no,
                                "claim": match.group(0),
                                "actual": actual,
                            }
                        )

    if args.json:
        print(json.dumps({"truth": truth, "checked": checked, "drifts": drifts}, indent=2))
    else:
        print("Ground truth:")
        for k, v in sorted(truth.items()):
            print(f"  {k}: {v}")
        print(f"\nChecked {checked} count claims across {len(collect_markdown_files())} files.")
        if drifts:
            print(f"\nDrifts: {len(drifts)}")
            for d in drifts:
                print(f"  {d['source']}:{d['line']}  {d['claim']!r}  actual={d['actual']}")
        else:
            print("All count claims agree with filesystem.")

    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
