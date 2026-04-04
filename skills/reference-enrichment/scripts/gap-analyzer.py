#!/usr/bin/env python3
"""
Gap Analyzer — deterministic gap detection for reference file enrichment.

Reads an agent or skill's .md file, extracts stated domains from the description,
triggers, and body content, compares against existing reference file coverage, and
outputs a JSON report of sub-domains missing reference coverage.

Usage:
    python3 skills/reference-enrichment/scripts/gap-analyzer.py --agent golang-general-engineer
    python3 skills/reference-enrichment/scripts/gap-analyzer.py --skill systematic-code-review
    python3 skills/reference-enrichment/scripts/gap-analyzer.py --agent python-general-engineer --verbose

Exit code: always 0 (analysis tool, not a gate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────

_HOME = Path.home()
_CLAUDE_AGENTS_DIR = _HOME / ".claude" / "agents"
_CLAUDE_SKILLS_DIR = _HOME / ".claude" / "skills"
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_REPO_AGENTS_DIR = _REPO_ROOT / "agents"
_REPO_SKILLS_DIR = _REPO_ROOT / "skills"

# ─── Domain Extraction ─────────────────────────────────────────

# Technology terms to extract as candidate domains.
# Each tuple: (pattern, canonical_domain_name)
_DOMAIN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Languages
    (re.compile(r"\bGo\b(?:lang)?", re.IGNORECASE), "go"),
    (re.compile(r"\bPython\b", re.IGNORECASE), "python"),
    (re.compile(r"\bTypeScript\b", re.IGNORECASE), "typescript"),
    (re.compile(r"\bJavaScript\b", re.IGNORECASE), "javascript"),
    (re.compile(r"\bRust\b", re.IGNORECASE), "rust"),
    (re.compile(r"\bKotlin\b", re.IGNORECASE), "kotlin"),
    (re.compile(r"\bSwift\b", re.IGNORECASE), "swift"),
    (re.compile(r"\bRuby\b", re.IGNORECASE), "ruby"),
    (re.compile(r"\bPHP\b", re.IGNORECASE), "php"),
    (re.compile(r"\bJava\b", re.IGNORECASE), "java"),
    # Concurrency / async
    (re.compile(r"\bconcurren(?:cy|t)\b", re.IGNORECASE), "concurrency"),
    (re.compile(r"\basync(?:hronous)?\b", re.IGNORECASE), "async"),
    (re.compile(r"\bgoroutine\b", re.IGNORECASE), "goroutines"),
    (re.compile(r"\bchannel\b", re.IGNORECASE), "channels"),
    (re.compile(r"\bTaskGroup\b"), "task-groups"),
    (re.compile(r"\bactor\b", re.IGNORECASE), "actors"),
    # Testing
    (re.compile(r"\btesting\b|\btest\b", re.IGNORECASE), "testing"),
    (re.compile(r"\bpytest\b", re.IGNORECASE), "pytest"),
    (re.compile(r"\bJUnit\b", re.IGNORECASE), "junit"),
    (re.compile(r"\bmock(?:ing)?\b", re.IGNORECASE), "mocking"),
    # Error handling
    (re.compile(r"\berror.handl\w+\b", re.IGNORECASE), "error-handling"),
    (re.compile(r"\bexception\b", re.IGNORECASE), "exceptions"),
    # Performance
    (re.compile(r"\bperformance\b|\boptimiz\w+\b", re.IGNORECASE), "performance"),
    (re.compile(r"\bbenchmark\b", re.IGNORECASE), "benchmarking"),
    (re.compile(r"\bprofil\w+\b", re.IGNORECASE), "profiling"),
    # Security
    (re.compile(r"\bsecurity\b", re.IGNORECASE), "security"),
    (re.compile(r"\bSQL injection\b", re.IGNORECASE), "sql-injection"),
    (re.compile(r"\bXSS\b", re.IGNORECASE), "xss"),
    (re.compile(r"\bauth(?:entication|orization)?\b", re.IGNORECASE), "auth"),
    # Data / types
    (re.compile(r"\btype.hint\b|\btype.safe\b|\btyping\b", re.IGNORECASE), "type-hints"),
    (re.compile(r"\bPydantic\b", re.IGNORECASE), "pydantic"),
    (re.compile(r"\bdataclass\b", re.IGNORECASE), "dataclasses"),
    (re.compile(r"\bgenerics?\b", re.IGNORECASE), "generics"),
    (re.compile(r"\binterface\b", re.IGNORECASE), "interfaces"),
    # Infrastructure
    (re.compile(r"\bKubernetes\b|\bk8s\b", re.IGNORECASE), "kubernetes"),
    (re.compile(r"\bDocker\b", re.IGNORECASE), "docker"),
    (re.compile(r"\bSQL\b", re.IGNORECASE), "sql"),
    (re.compile(r"\bPostgres\b", re.IGNORECASE), "postgres"),
    (re.compile(r"\bMySQL\b", re.IGNORECASE), "mysql"),
    # Frameworks
    (re.compile(r"\bFastAPI\b", re.IGNORECASE), "fastapi"),
    (re.compile(r"\bDjango\b", re.IGNORECASE), "django"),
    (re.compile(r"\bFlask\b", re.IGNORECASE), "flask"),
    (re.compile(r"\bReact\b", re.IGNORECASE), "react"),
    (re.compile(r"\bNext\.js\b|\bNextJS\b", re.IGNORECASE), "nextjs"),
    # Toolkit-specific
    (re.compile(r"\banti.pattern\b", re.IGNORECASE), "anti-patterns"),
    (re.compile(r"\bcode.review\b", re.IGNORECASE), "code-review"),
    (re.compile(r"\brefactor\b", re.IGNORECASE), "refactoring"),
    (re.compile(r"\blogging\b|\bstructured.log\b", re.IGNORECASE), "logging"),
    (re.compile(r"\bmetrics?\b", re.IGNORECASE), "metrics"),
    (re.compile(r"\btracing\b", re.IGNORECASE), "tracing"),
    (re.compile(r"\bmodule\b", re.IGNORECASE), "modules"),
    (re.compile(r"\bpackage.manag\w+\b", re.IGNORECASE), "package-management"),
]

# Coverage mapping: reference filename keywords → domain names they cover.
# A reference file "go-concurrency.md" is treated as covering "concurrency", "goroutines", etc.
_COVERAGE_MAP: dict[str, list[str]] = {
    "concurren": ["concurrency", "goroutines", "channels", "task-groups", "actors", "async"],
    "async": ["async", "concurrency", "task-groups"],
    "goroutine": ["goroutines", "concurrency", "channels"],
    "channel": ["channels", "concurrency"],
    "testing": ["testing", "mocking", "pytest", "junit"],
    "test": ["testing", "mocking"],
    "mock": ["mocking", "testing"],
    "error": ["error-handling", "exceptions"],
    "exception": ["exceptions", "error-handling"],
    "performance": ["performance", "benchmarking", "profiling"],
    "benchmark": ["benchmarking", "performance"],
    "profil": ["profiling", "performance"],
    "security": ["security", "sql-injection", "xss", "auth"],
    "auth": ["auth", "security"],
    "anti.pattern": ["anti-patterns"],
    "pattern": ["anti-patterns"],
    "type": ["type-hints", "generics"],
    "typing": ["type-hints"],
    "dataclass": ["dataclasses"],
    "pydantic": ["pydantic"],
    "generic": ["generics"],
    "interface": ["interfaces"],
    "logging": ["logging"],
    "log": ["logging"],
    "metric": ["metrics"],
    "tracing": ["tracing"],
    "sql": ["sql", "sql-injection"],
    "module": ["modules", "package-management"],
    "package": ["package-management", "modules"],
    "modern": [],  # "modern" alone doesn't indicate a specific covered domain
    "feature": [],
    "idiom": [],
    "review": ["code-review"],
    "refactor": ["refactoring"],
}


def _extract_domains_from_text(text: str) -> set[str]:
    """Extract candidate domain names from free text using pattern matching."""
    found: set[str] = set()
    for pattern, domain in _DOMAIN_PATTERNS:
        if pattern.search(text):
            found.add(domain)
    return found


def _domains_covered_by_filename(filename: str) -> set[str]:
    """Infer which domains a reference file covers based on its filename."""
    name_lower = filename.lower().replace("-", " ").replace("_", " ")
    covered: set[str] = set()
    for keyword, domains in _COVERAGE_MAP.items():
        if re.search(keyword, name_lower):
            covered.update(domains)
    # Also add the stem words themselves as covered domains
    stem = Path(filename).stem.lower()
    parts = re.split(r"[-_]", stem)
    covered.update(parts)
    return covered


def _filename_for_domain(domain: str) -> str:
    """Suggest a reference filename for a domain gap."""
    return f"{domain}.md"


# ─── Data Classes ─────────────────────────────────────────────


@dataclass
class RecommendedRef:
    """A recommended reference file to create for a gap."""

    filename: str
    domain: str
    reason: str


@dataclass
class GapReport:
    """Gap analysis result for a single component."""

    component: str
    kind: str  # "agent" or "skill"
    current_level: int
    existing_references: list[str] = field(default_factory=list)
    stated_domains: list[str] = field(default_factory=list)
    covered_domains: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommended_references: list[RecommendedRef] = field(default_factory=list)


# ─── Scanning ─────────────────────────────────────────────────


def _find_component(name: str, kind: str) -> tuple[Path | None, Path | None]:
    """Locate a component's .md file and its references/ directory.

    Returns (md_path, ref_dir) — either may be None if not found.
    """
    search_dirs: list[Path] = []
    if kind == "agent":
        search_dirs = [_CLAUDE_AGENTS_DIR, _REPO_AGENTS_DIR]
    else:
        search_dirs = [_CLAUDE_SKILLS_DIR, _REPO_SKILLS_DIR]

    for base in search_dirs:
        # Flat .md file: agents/foo.md
        flat = base / f"{name}.md"
        if flat.is_file():
            ref_dir_candidate = flat.parent / name / "references"
            ref_dir = ref_dir_candidate if ref_dir_candidate.is_dir() else None
            return flat, ref_dir

        # Named directory: agents/foo/foo.md  OR  skills/foo/SKILL.md
        named_dir = base / name
        if named_dir.is_dir():
            inner_md = named_dir / f"{name}.md"
            if not inner_md.is_file():
                # Skills use SKILL.md convention
                inner_md = named_dir / "SKILL.md"
            if inner_md.is_file():
                ref_dir_inner = named_dir / "references"
                ref_dir = ref_dir_inner if ref_dir_inner.is_dir() else None
                return inner_md, ref_dir

    return None, None


def _read_md(md_path: Path) -> str:
    """Read a markdown file, returning empty string on error."""
    try:
        return md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _current_level(ref_dir: Path | None) -> int:
    """Return a rough depth level for the component's current state.

    This is a lightweight approximation — for authoritative scoring, run
    scripts/audit-reference-depth.py.
    """
    if ref_dir is None or not ref_dir.is_dir():
        return 0

    ref_files = list(ref_dir.glob("*.md"))
    if not ref_files:
        return 0

    total_lines = 0
    has_code = False
    has_commands = False
    concrete_hits = 0

    for f in ref_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        total_lines += len(lines)
        if "```" in text:
            has_code = True
        if re.search(r"\b(?:grep|rg|find)\s+", text):
            has_commands = True
        concrete_hits += len(re.findall(r"\b\d+\.\d+\+", text))
        concrete_hits += len(re.findall(r"```", text))

    avg_lines = total_lines / len(ref_files) if ref_files else 0

    if has_commands and concrete_hits >= 10 and avg_lines >= 80:
        return 3
    if has_code or (concrete_hits >= 5 and avg_lines >= 30):
        return 2
    return 1


def _build_gap_report(name: str, kind: str) -> GapReport | None:
    """Build a gap report for the named component."""
    md_path, ref_dir = _find_component(name, kind)
    if md_path is None:
        return None

    md_text = _read_md(md_path)
    level = _current_level(ref_dir)

    # Collect existing reference filenames
    existing: list[str] = []
    if ref_dir and ref_dir.is_dir():
        existing = sorted(f.name for f in ref_dir.glob("*.md"))

    # Extract domains from the .md content
    stated = _extract_domains_from_text(md_text)

    # Determine which domains are already covered by existing reference filenames
    covered: set[str] = set()
    for ref_filename in existing:
        covered.update(_domains_covered_by_filename(ref_filename))

    # Gaps: stated domains with no coverage
    gaps = sorted(stated - covered)

    # Build recommendations — filter out domains too vague to act on
    _LOW_SIGNAL_DOMAINS = {"go", "python", "typescript", "javascript", "rust", "kotlin", "swift", "ruby", "php", "java"}

    recommendations: list[RecommendedRef] = []
    for domain in gaps:
        if domain in _LOW_SIGNAL_DOMAINS:
            # The primary language domain — too broad for a single reference file;
            # skip and let sub-domain gaps (concurrency, testing, etc.) drive files instead.
            continue
        filename = _filename_for_domain(domain)
        reason = (
            f"Component mentions '{domain}' but no reference file covers it. "
            f"Add concrete patterns, anti-patterns with detection commands, and version notes."
        )
        recommendations.append(RecommendedRef(filename=filename, domain=domain, reason=reason))

    return GapReport(
        component=name,
        kind=kind,
        current_level=level,
        existing_references=existing,
        stated_domains=sorted(stated),
        covered_domains=sorted(covered),
        gaps=gaps,
        recommended_references=recommendations,
    )


# ─── Reporting ─────────────────────────────────────────────────


def _to_dict(report: GapReport) -> dict:
    """Convert a GapReport to a JSON-serialisable dict."""
    return {
        "component": report.component,
        "type": report.kind,
        "current_level": report.current_level,
        "existing_references": report.existing_references,
        "stated_domains": report.stated_domains,
        "covered_domains": report.covered_domains,
        "gaps": report.gaps,
        "recommended_references": [
            {
                "filename": r.filename,
                "domain": r.domain,
                "reason": r.reason,
            }
            for r in report.recommended_references
        ],
    }


def _format_text(report: GapReport) -> str:
    """Render a human-readable gap report."""
    lines: list[str] = []
    lines.append(f"GAP ANALYSIS: {report.component} ({report.kind})")
    lines.append("=" * 50)
    lines.append(f"  Current level : {report.current_level}")
    lines.append(f"  Existing refs : {len(report.existing_references)}")
    if report.existing_references:
        for ref in report.existing_references:
            lines.append(f"    - {ref}")
    lines.append("")

    lines.append(f"  Stated domains ({len(report.stated_domains)}):")
    for d in report.stated_domains:
        covered = " [covered]" if d in report.covered_domains else " [GAP]"
        lines.append(f"    - {d}{covered}")
    lines.append("")

    if report.recommended_references:
        lines.append(f"  Recommended reference files ({len(report.recommended_references)}):")
        for rec in report.recommended_references:
            lines.append(f"    → {rec.filename}")
            lines.append(f"      {rec.reason}")
    else:
        lines.append("  No gaps found — references cover all stated domains.")

    return "\n".join(lines)


# ─── Main ──────────────────────────────────────────────────────


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze reference file gaps for an agent or skill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--agent",
        metavar="NAME",
        help="Analyze gaps for an agent by name",
    )
    group.add_argument(
        "--skill",
        metavar="NAME",
        help="Analyze gaps for a skill by name",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show additional detail in text output",
    )
    args = parser.parse_args()

    name = args.agent or args.skill
    kind = "agent" if args.agent else "skill"

    report = _build_gap_report(name, kind)
    if report is None:
        print(f"[error] {kind} '{name}' not found in agents/ or skills/ directories.", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(_to_dict(report), indent=2))
    else:
        print(_format_text(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
