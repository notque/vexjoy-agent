#!/usr/bin/env python3
"""
Reference Depth Audit — classify agents and skills by reference file richness.

Scans agent and skill directories for references/ subdirectories, measures each
reference file on line count and specificity, and classifies every component
into a depth level (0-3).

Levels:
  Level 0  No references/ directory at all
  Level 1  References exist but are thin (< 50 lines avg, mostly generic phrases)
  Level 2  References contain domain-specific patterns (versions, function names, code blocks)
  Level 3  Deep references — version-specific patterns, anti-pattern catalogs with
           detection commands, error-fix mappings

Usage:
    python3 scripts/audit-reference-depth.py
    python3 scripts/audit-reference-depth.py --agent golang-general-engineer
    python3 scripts/audit-reference-depth.py --skill python-quality-gate
    python3 scripts/audit-reference-depth.py --json
    python3 scripts/audit-reference-depth.py --verbose
    python3 scripts/audit-reference-depth.py --min-level 2
    python3 scripts/audit-reference-depth.py --json --verbose --min-level 1

Exit code: always 0 (audit tool, not a gate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────

_HOME = Path.home()
_CLAUDE_AGENTS_DIR = _HOME / ".claude" / "agents"
_CLAUDE_SKILLS_DIR = _HOME / ".claude" / "skills"
_REPO_ROOT = Path(__file__).parent.parent
_REPO_AGENTS_DIR = _REPO_ROOT / "agents"
_REPO_SKILLS_DIR = _REPO_ROOT / "skills"

# ─── Scoring Patterns ─────────────────────────────────────────

# Concrete indicators: version ranges, function names, grep/regex patterns, code blocks
_CONCRETE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d+\.\d+\+"),  # version range like Go 1.22+, Python 3.11+
    re.compile(r"\b\d+\.\d+\.\d+"),  # exact version like 1.21.3
    re.compile(r"```"),  # fenced code block delimiter
    re.compile(r"\bgrep\b|\brg\b|\bfind\b"),  # detection commands
    re.compile(r"func\s+\w+\s*\("),  # Go function signature
    re.compile(r"def\s+\w+\s*\("),  # Python function signature
    re.compile(r"\bimport\s+\w"),  # import statement
    re.compile(r"(?:goroutine|mutex|channel|waitgroup)", re.IGNORECASE),  # Go concurrency terms
    re.compile(r"(?:TypeError|ValueError|KeyError|AttributeError)", re.IGNORECASE),  # specific errors
    re.compile(r"line\s+\d+"),  # explicit line references
    re.compile(r"#\s*\w+:.*->"),  # error-fix mapping patterns
    re.compile(r"\|\s*\w.*\|\s*\w.*\|"),  # markdown table rows (structured data)
    re.compile(r"\bPEP\s*\d+\b"),  # Python PEP references
    re.compile(r"\bCVE-\d{4}-\d+\b"),  # CVE references
    re.compile(r":\s+`[^`]+`"),  # inline code snippets after colon
    re.compile(r"--\w[\w-]*"),  # CLI flags like --no-verify
    re.compile(r"\b(?:anti-pattern|forbidden|never use|do not use)\b", re.IGNORECASE),  # anti-pattern markers
]

# Generic phrases that indicate thin/low-value content
_GENERIC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bbest practices?\b", re.IGNORECASE),
    re.compile(r"\bcommon issues?\b", re.IGNORECASE),
    re.compile(r"\breview carefully\b", re.IGNORECASE),
    re.compile(r"\bensure quality\b", re.IGNORECASE),
    re.compile(r"\byou are an expert\b", re.IGNORECASE),
    re.compile(r"\bhigh.?quality\b", re.IGNORECASE),
    re.compile(r"\bfollowing best\b", re.IGNORECASE),
    re.compile(r"\bprofessional.?standards?\b", re.IGNORECASE),
    re.compile(r"\bcomprehensive(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bthorough(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bappropriate\b", re.IGNORECASE),
    re.compile(r"\bconsider[s]?\b", re.IGNORECASE),
]

# ─── Data Classes ─────────────────────────────────────────────


@dataclass
class RefFileMetrics:
    """Metrics for a single reference file."""

    path: Path
    line_count: int
    concrete_hits: int
    generic_hits: int
    has_code_blocks: bool
    has_detection_commands: bool

    @property
    def specificity_score(self) -> float:
        """Ratio of concrete hits to total hits; 0.0 when no hits at all."""
        total = self.concrete_hits + self.generic_hits
        if total == 0:
            return 0.0
        return self.concrete_hits / total


@dataclass
class ComponentResult:
    """Audit result for a single agent or skill."""

    name: str
    kind: str  # "agent" or "skill"
    md_path: Path
    ref_dir: Path | None
    ref_files: list[RefFileMetrics] = field(default_factory=list)
    level: int = 0

    @property
    def avg_line_count(self) -> float:
        if not self.ref_files:
            return 0.0
        return sum(f.line_count for f in self.ref_files) / len(self.ref_files)

    @property
    def total_concrete_hits(self) -> int:
        return sum(f.concrete_hits for f in self.ref_files)

    @property
    def total_generic_hits(self) -> int:
        return sum(f.generic_hits for f in self.ref_files)

    @property
    def has_any_code_blocks(self) -> bool:
        return any(f.has_code_blocks for f in self.ref_files)

    @property
    def has_any_detection_commands(self) -> bool:
        return any(f.has_detection_commands for f in self.ref_files)


# ─── Measurement ──────────────────────────────────────────────


def _measure_ref_file(path: Path) -> RefFileMetrics:
    """Measure a single reference file and return its metrics."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return RefFileMetrics(
            path=path,
            line_count=0,
            concrete_hits=0,
            generic_hits=0,
            has_code_blocks=False,
            has_detection_commands=False,
        )

    lines = text.splitlines()
    concrete_hits = 0
    generic_hits = 0
    has_code_blocks = False
    has_detection_commands = False

    for line in lines:
        for pat in _CONCRETE_PATTERNS:
            if pat.search(line):
                concrete_hits += 1
        for pat in _GENERIC_PATTERNS:
            if pat.search(line):
                generic_hits += 1

    has_code_blocks = "```" in text
    has_detection_commands = bool(re.search(r"\b(?:grep|rg|find)\s+", text))

    return RefFileMetrics(
        path=path,
        line_count=len(lines),
        concrete_hits=concrete_hits,
        generic_hits=generic_hits,
        has_code_blocks=has_code_blocks,
        has_detection_commands=has_detection_commands,
    )


def _classify_level(result: ComponentResult) -> int:
    """Assign a depth level (0-3) to a component based on its metrics.

    Level 0: no references/ directory
    Level 1: references exist but thin (avg < 50 lines OR mostly generic)
    Level 2: domain-specific patterns present (code blocks or version patterns)
    Level 3: deep — detection commands AND substantial concrete content
    """
    if not result.ref_files:
        return 0

    avg_lines = result.avg_line_count
    has_code = result.has_any_code_blocks
    has_cmds = result.has_any_detection_commands
    concrete = result.total_concrete_hits
    generic = result.total_generic_hits
    specificity = concrete / (concrete + generic) if (concrete + generic) > 0 else 0.0

    # Level 3: substantial depth — detection commands AND rich concrete content
    if has_cmds and concrete >= 10 and avg_lines >= 80:
        return 3

    # Level 2: domain-specific — code blocks or enough concrete patterns
    if has_code or (concrete >= 5 and specificity >= 0.4 and avg_lines >= 30):
        return 2

    # Level 1: exists but thin
    return 1


# ─── Scanning ─────────────────────────────────────────────────


def _collect_ref_files(ref_dir: Path) -> list[RefFileMetrics]:
    """Collect and measure all markdown reference files in a directory."""
    if not ref_dir.is_dir():
        return []
    files = sorted(ref_dir.glob("*.md"))
    return [_measure_ref_file(f) for f in files]


def _scan_component(md_path: Path, kind: str) -> ComponentResult:
    """Scan a single agent or skill .md file and its optional references/ dir."""
    name = md_path.stem
    # References live at <parent>/<name>/references/ next to <name>.md
    ref_dir_candidate = md_path.parent / name / "references"
    # Also allow references/ as a sibling of the .md inside a named directory
    if not ref_dir_candidate.is_dir():
        # e.g. ~/.claude/agents/golang-general-engineer/references/
        ref_dir_candidate2 = md_path.parent / "references"
        if md_path.parent.name == name and ref_dir_candidate2.is_dir():
            ref_dir_candidate = ref_dir_candidate2
        else:
            ref_dir_candidate = None  # type: ignore[assignment]

    if ref_dir_candidate and ref_dir_candidate.is_dir():
        ref_dir: Path | None = ref_dir_candidate
        ref_files = _collect_ref_files(ref_dir)
    else:
        ref_dir = None
        ref_files = []

    result = ComponentResult(
        name=name,
        kind=kind,
        md_path=md_path,
        ref_dir=ref_dir,
        ref_files=ref_files,
    )
    result.level = _classify_level(result)
    return result


def _scan_directory(base_dir: Path, kind: str) -> list[ComponentResult]:
    """Scan an agent or skill base directory for all .md components."""
    if not base_dir.is_dir():
        return []

    results: list[ComponentResult] = []
    for item in sorted(base_dir.iterdir()):
        if item.is_file() and item.suffix == ".md" and item.stem not in ("INDEX", "README"):
            results.append(_scan_component(item, kind))
        elif item.is_dir() and (item / (item.name + ".md")).is_file():
            # Named dir pattern: agents/golang-general-engineer/golang-general-engineer.md
            md_path = item / (item.name + ".md")
            result = _scan_component(md_path, kind)
            # Override ref_dir resolution: check inside the named dir directly
            ref_dir_inner = item / "references"
            if ref_dir_inner.is_dir():
                result.ref_dir = ref_dir_inner
                result.ref_files = _collect_ref_files(ref_dir_inner)
                result.level = _classify_level(result)
            results.append(result)

    return results


def _deduplicate(results: list[ComponentResult]) -> list[ComponentResult]:
    """Keep the first occurrence of each (name, kind) pair, preferring ~/.claude/ entries."""
    seen: set[tuple[str, str]] = set()
    deduped: list[ComponentResult] = []
    for r in results:
        key = (r.name, r.kind)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def scan_all() -> list[ComponentResult]:
    """Scan all agent and skill directories, deduplicating by name."""
    results: list[ComponentResult] = []

    # ~/.claude/ takes priority (live/deployed copies)
    results += _scan_directory(_CLAUDE_AGENTS_DIR, "agent")
    results += _scan_directory(_CLAUDE_SKILLS_DIR, "skill")

    # repo-local copies (may overlap; duplicates are dropped)
    results += _scan_directory(_REPO_AGENTS_DIR, "agent")
    results += _scan_directory(_REPO_SKILLS_DIR, "skill")

    return _deduplicate(results)


def scan_single(name: str, kind: str) -> ComponentResult | None:
    """Scan a single named agent or skill. Returns None if not found."""
    search_dirs: list[tuple[Path, str]] = []
    if kind == "agent":
        search_dirs = [(_CLAUDE_AGENTS_DIR, "agent"), (_REPO_AGENTS_DIR, "agent")]
    else:
        search_dirs = [(_CLAUDE_SKILLS_DIR, "skill"), (_REPO_SKILLS_DIR, "skill")]

    for base_dir, k in search_dirs:
        # Flat .md file
        md_flat = base_dir / f"{name}.md"
        if md_flat.is_file():
            return _scan_component(md_flat, k)
        # Named directory with inner .md
        named_dir = base_dir / name
        if named_dir.is_dir() and (named_dir / f"{name}.md").is_file():
            md_path = named_dir / f"{name}.md"
            result = _scan_component(md_path, k)
            ref_dir_inner = named_dir / "references"
            if ref_dir_inner.is_dir():
                result.ref_dir = ref_dir_inner
                result.ref_files = _collect_ref_files(ref_dir_inner)
                result.level = _classify_level(result)
            return result

    return None


# ─── Reporting ────────────────────────────────────────────────

_LEVEL_LABELS = {
    0: "None",
    1: "Thin",
    2: "Domain",
    3: "Deep",
}


def _level_label(level: int) -> str:
    return _LEVEL_LABELS.get(level, str(level))


def _format_text(results: list[ComponentResult], verbose: bool, min_level: int) -> str:
    """Render a human-readable audit report."""
    lines: list[str] = []
    today = date.today().isoformat()

    lines.append(f"REFERENCE DEPTH AUDIT — {today}")
    lines.append("=" * 50)
    lines.append("")

    # Summary counts per level
    for level in (3, 2, 1, 0):
        agents = [r for r in results if r.kind == "agent" and r.level == level]
        skills = [r for r in results if r.kind == "skill" and r.level == level]
        label = _level_label(level)
        lines.append(f"  Level {level} ({label:<6}):  {len(agents):>4} agents,  {len(skills):>4} skills")
    lines.append("")

    # Gaps: components below min_level
    gaps = sorted(
        [r for r in results if r.level < min_level],
        key=lambda r: (r.kind, r.name),
    )

    if gaps:
        lines.append(f"GAPS (level < {min_level}):")
        lines.append("-" * 50)
        for r in gaps:
            ref_note = f"refs/{r.ref_dir.name}" if r.ref_dir else "no refs/"
            lines.append(f"  [{r.kind:<5}] {r.name:<45}  Level {r.level} ({_level_label(r.level)})  — {ref_note}")
            if verbose and r.ref_files:
                for f in r.ref_files:
                    lines.append(
                        f"           {f.path.name:<40}  {f.line_count:>4} lines  "
                        f"concrete={f.concrete_hits}  generic={f.generic_hits}  "
                        f"code={'Y' if f.has_code_blocks else 'N'}  "
                        f"cmds={'Y' if f.has_detection_commands else 'N'}"
                    )
        lines.append("")
    else:
        lines.append(f"No gaps found at min-level {min_level}.")
        lines.append("")

    if verbose:
        lines.append("ALL COMPONENTS:")
        lines.append("-" * 50)
        for r in sorted(results, key=lambda r: (r.kind, r.level, r.name)):
            lines.append(f"  [{r.kind:<5}] {r.name:<45}  Level {r.level} ({_level_label(r.level)})")
            if r.ref_files:
                for f in r.ref_files:
                    lines.append(
                        f"           {f.path.name:<40}  {f.line_count:>4} lines  "
                        f"concrete={f.concrete_hits}  generic={f.generic_hits}  "
                        f"code={'Y' if f.has_code_blocks else 'N'}  "
                        f"cmds={'Y' if f.has_detection_commands else 'N'}"
                    )
        lines.append("")

    total = len(results)
    agents_total = sum(1 for r in results if r.kind == "agent")
    skills_total = sum(1 for r in results if r.kind == "skill")
    lines.append(f"Total scanned: {total} ({agents_total} agents, {skills_total} skills)")

    return "\n".join(lines)


def _result_to_dict(r: ComponentResult) -> dict:
    """Convert a ComponentResult to a JSON-serialisable dict."""
    return {
        "name": r.name,
        "kind": r.kind,
        "level": r.level,
        "level_label": _level_label(r.level),
        "md_path": str(r.md_path),
        "ref_dir": str(r.ref_dir) if r.ref_dir else None,
        "avg_line_count": round(r.avg_line_count, 1),
        "total_concrete_hits": r.total_concrete_hits,
        "total_generic_hits": r.total_generic_hits,
        "has_code_blocks": r.has_any_code_blocks,
        "has_detection_commands": r.has_any_detection_commands,
        "ref_files": [
            {
                "path": str(f.path),
                "line_count": f.line_count,
                "concrete_hits": f.concrete_hits,
                "generic_hits": f.generic_hits,
                "specificity_score": round(f.specificity_score, 3),
                "has_code_blocks": f.has_code_blocks,
                "has_detection_commands": f.has_detection_commands,
            }
            for f in r.ref_files
        ],
    }


def _format_json(results: list[ComponentResult], min_level: int) -> str:
    """Render audit results as JSON."""
    level_counts: dict[str, dict[str, int]] = {str(lvl): {"agents": 0, "skills": 0} for lvl in range(4)}
    for r in results:
        level_counts[str(r.level)][r.kind + "s"] += 1

    payload = {
        "date": date.today().isoformat(),
        "summary": {
            f"level_{lvl}": {
                "label": _level_label(lvl),
                "agents": level_counts[str(lvl)]["agents"],
                "skills": level_counts[str(lvl)]["skills"],
            }
            for lvl in range(4)
        },
        "gaps": [_result_to_dict(r) for r in results if r.level < min_level],
        "all": [_result_to_dict(r) for r in results],
    }
    return json.dumps(payload, indent=2)


# ─── Main ─────────────────────────────────────────────────────


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Audit reference file depth for agents and skills.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent",
        metavar="NAME",
        help="Audit a single agent by name",
    )
    parser.add_argument(
        "--skill",
        metavar="NAME",
        help="Audit a single skill by name",
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
        help="Show per-file detail for every component",
    )
    parser.add_argument(
        "--min-level",
        type=int,
        default=2,
        metavar="N",
        help="Show components below this level in the gaps section (default: 2)",
    )
    args = parser.parse_args()

    # Single-component mode
    if args.agent or args.skill:
        name = args.agent or args.skill
        kind = "agent" if args.agent else "skill"
        result = scan_single(name, kind)
        if result is None:
            print(f"[error] {kind} '{name}' not found.", file=sys.stderr)
            return 0
        results = [result]
    else:
        results = scan_all()

    if args.as_json:
        print(_format_json(results, args.min_level))
    else:
        print(_format_text(results, verbose=args.verbose, min_level=args.min_level))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
