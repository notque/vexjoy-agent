#!/usr/bin/env python3
"""Audit skill sprawl against skills/INDEX.json.

Methodology adapted from steipete/agent-scripts skill-cleaner (rebuilt for
this toolkit; zero Codex-specific logic). Three checks:

  1. Prompt budget: per-skill router-line token cost using
     ceil(utf8_bytes / 4), summed against a context-window budget
     (--context-tokens x --budget-percent).
  2. Over-long descriptions: router lines whose token cost exceeds
     --max-desc-tokens, ranked by potential savings.
  3. Near-duplicates: pairwise SKILL.md body similarity (difflib) above
     --similarity, plus identical descriptions.

Output is a suggest-first Markdown report: the script never edits or
deletes anything. Exit codes:

  0 = report produced (findings or not)
  1 = findings exist and --check was passed
  2 = bad input (missing/unreadable index, no skills)
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONTEXT_TOKENS = 200_000
DEFAULT_BUDGET_PERCENT = 2.0
DEFAULT_MAX_DESC_TOKENS = 40
DEFAULT_SIMILARITY = 0.85

FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
WS_RE = re.compile(r"\s+")


def token_cost(text: str) -> int:
    """Token estimate: ceil(utf8 bytes / 4)."""
    return math.ceil(len(text.encode("utf-8")) / 4)


def router_line(name: str, description: str) -> str:
    """The model-visible index line a skill costs at routing time."""
    return f"- {name}: {description}"


def normalize_body(text: str) -> str:
    """Strip frontmatter, lowercase, collapse whitespace for comparison."""
    text = FRONTMATTER_RE.sub("", text)
    return WS_RE.sub(" ", text.lower()).strip()


@dataclass
class SkillEntry:
    name: str
    file: str
    description: str
    line_tokens: int
    body_tokens: int = 0
    norm_body: str = ""


@dataclass
class DuplicatePair:
    a: str
    b: str
    body_ratio: float
    same_description: bool


@dataclass
class AuditResult:
    skills: list[SkillEntry] = field(default_factory=list)
    budget_tokens: int = 0
    total_line_tokens: int = 0
    long_descriptions: list[SkillEntry] = field(default_factory=list)
    duplicates: list[DuplicatePair] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        over_budget = self.total_line_tokens > self.budget_tokens
        return over_budget or bool(self.long_descriptions or self.duplicates)


def load_skills(index_path: Path, root: Path) -> tuple[list[SkillEntry], list[str]]:
    """Parse INDEX.json into entries; return (entries, missing-file names)."""
    data = json.loads(index_path.read_text(encoding="utf-8"))
    skills = data.get("skills", {})
    entries: list[SkillEntry] = []
    missing: list[str] = []
    for name, meta in sorted(skills.items()):
        description = str(meta.get("description", "")).strip()
        rel = str(meta.get("file", ""))
        entry = SkillEntry(
            name=name,
            file=rel,
            description=description,
            line_tokens=token_cost(router_line(name, description)),
        )
        path = root / rel
        if rel and path.is_file():
            body = path.read_text(encoding="utf-8", errors="replace")
            entry.body_tokens = token_cost(body)
            entry.norm_body = normalize_body(body)
        else:
            missing.append(name)
        entries.append(entry)
    return entries, missing


def find_duplicates(entries: list[SkillEntry], threshold: float) -> list[DuplicatePair]:
    """Pairwise body similarity above threshold, or identical descriptions."""
    pairs: list[DuplicatePair] = []
    comparable = [e for e in entries if e.norm_body]
    for i, a in enumerate(comparable):
        for b in comparable[i + 1 :]:
            same_desc = bool(a.description) and a.description == b.description
            matcher = difflib.SequenceMatcher(None, a.norm_body, b.norm_body)
            if matcher.real_quick_ratio() < threshold and not same_desc:
                continue
            if matcher.quick_ratio() < threshold and not same_desc:
                continue
            ratio = matcher.ratio()
            if ratio >= threshold or same_desc:
                pairs.append(DuplicatePair(a.name, b.name, ratio, same_desc))
    pairs.sort(key=lambda p: p.body_ratio, reverse=True)
    return pairs


def run_audit(
    index_path: Path,
    root: Path,
    context_tokens: int,
    budget_percent: float,
    max_desc_tokens: int,
    similarity: float,
) -> AuditResult:
    entries, missing = load_skills(index_path, root)
    result = AuditResult(skills=entries, missing_files=missing)
    result.budget_tokens = math.floor(context_tokens * budget_percent / 100)
    result.total_line_tokens = sum(e.line_tokens for e in entries)
    result.long_descriptions = sorted(
        (e for e in entries if e.line_tokens > max_desc_tokens),
        key=lambda e: e.line_tokens,
        reverse=True,
    )
    result.duplicates = find_duplicates(entries, similarity)
    return result


def render_report(result: AuditResult, max_desc_tokens: int, similarity: float, top: int = 15) -> str:
    """Suggest-first Markdown report."""
    lines: list[str] = ["# Skill Sprawl Audit", ""]

    over = result.total_line_tokens - result.budget_tokens
    status = f"OVER budget by {over} tokens" if over > 0 else f"within budget ({-over} tokens free)"
    lines += [
        "## Prompt Budget",
        "",
        f"- Skills indexed: {len(result.skills)}",
        f"- Router-line cost (sum of `- name: description` lines): {result.total_line_tokens} tokens",
        f"- Budget: {result.budget_tokens} tokens",
        f"- Status: {status}",
        "",
        "Top router-line costs:",
        "",
        "| Skill | Line tokens | Body tokens |",
        "|---|---|---|",
    ]
    for e in sorted(result.skills, key=lambda e: e.line_tokens, reverse=True)[:top]:
        lines.append(f"| {e.name} | {e.line_tokens} | {e.body_tokens} |")
    lines.append("")

    lines += ["## Over-long Descriptions", ""]
    if result.long_descriptions:
        lines += [
            f"Router lines above {max_desc_tokens} tokens. Suggested fix: trim the",
            "description, keep the trigger nouns (product, tool, action, object).",
            "",
            "| Skill | Line tokens | Description |",
            "|---|---|---|",
        ]
        for e in result.long_descriptions:
            desc = e.description if len(e.description) <= 120 else e.description[:117] + "..."
            lines.append(f"| {e.name} | {e.line_tokens} | {desc} |")
    else:
        lines.append(f"None. All router lines are at or under {max_desc_tokens} tokens.")
    lines.append("")

    lines += ["## Near-duplicates", ""]
    if result.duplicates:
        lines += [
            f"Body similarity at or above {similarity:.2f}, or identical descriptions.",
            "Suggested fix: merge under One Domain One Component — keep one skill,",
            "move the divergent content into a reference file of the kept skill.",
            "",
            "| Skill A | Skill B | Body similarity | Same description |",
            "|---|---|---|---|",
        ]
        for p in result.duplicates:
            lines.append(f"| {p.a} | {p.b} | {p.body_ratio:.2f} | {'yes' if p.same_description else 'no'} |")
    else:
        lines.append(f"None at or above {similarity:.2f} body similarity.")
    lines.append("")

    if result.missing_files:
        lines += [
            "## Missing SKILL.md Files",
            "",
            "Indexed but file absent (regenerate the index or restore the file):",
            "",
        ]
        lines += [f"- {name}" for name in result.missing_files]
        lines.append("")

    lines += [
        "## Policy",
        "",
        "This report suggests; it never edits. Apply changes manually, then",
        "regenerate the index: `python3 scripts/generate-skill-index.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit skill sprawl against skills/INDEX.json.")
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--index", type=Path, default=repo_root / "skills" / "INDEX.json")
    parser.add_argument("--root", type=Path, default=repo_root, help="Repo root for resolving skill file paths.")
    parser.add_argument("--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS)
    parser.add_argument(
        "--budget-percent",
        type=float,
        default=DEFAULT_BUDGET_PERCENT,
        help="Share of the context window allowed for router lines.",
    )
    parser.add_argument("--max-desc-tokens", type=int, default=DEFAULT_MAX_DESC_TOKENS)
    parser.add_argument("--similarity", type=float, default=DEFAULT_SIMILARITY)
    parser.add_argument("--output", type=Path, help="Write report here instead of stdout.")
    parser.add_argument("--check", action="store_true", help="Exit 1 when findings exist (CI mode).")
    args = parser.parse_args(argv)

    if not args.index.is_file():
        print(f"ERROR: index not found: {args.index}", file=sys.stderr)
        print("Generate it first: python3 scripts/generate-skill-index.py", file=sys.stderr)
        return 2
    try:
        result = run_audit(
            args.index,
            args.root,
            args.context_tokens,
            args.budget_percent,
            args.max_desc_tokens,
            args.similarity,
        )
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot read index: {exc}", file=sys.stderr)
        return 2
    if not result.skills:
        print("ERROR: index contains no skills.", file=sys.stderr)
        return 2

    report = render_report(result, args.max_desc_tokens, args.similarity)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written: {args.output}")
    else:
        print(report)
    return 1 if (args.check and result.has_findings) else 0


if __name__ == "__main__":
    sys.exit(main())
