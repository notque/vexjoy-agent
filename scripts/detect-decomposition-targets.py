#!/usr/bin/env python3
"""
Decomposition Target Detector — find skills/agents with bloated body files.

Scans all skills/*/SKILL.md and agents/*.md files for content that belongs in
references/ files but has not yet been extracted. Reports extractable blocks
with suggested reference file names and confidence levels.

Content types detected:
  code_blocks        Fenced code block clusters (3+ blocks in a section, >20 lines total)
  large_tables       Markdown tables with 10+ data rows
  detection_commands Sections containing grep/rg/find patterns
  agent_rosters      Sections with agent dispatch tables or agent list content
  error_catalogs     Error/fix/troubleshoot sections exceeding 30 lines
  spec_tables        Parameter/type/default specification tables

Usage:
    python3 scripts/detect-decomposition-targets.py
    python3 scripts/detect-decomposition-targets.py --skill data-analysis
    python3 scripts/detect-decomposition-targets.py --agent golang-general-engineer
    python3 scripts/detect-decomposition-targets.py --json
    python3 scripts/detect-decomposition-targets.py --min-lines 400

Exit code: always 0 (audit tool, not a gate).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent
_REPO_AGENTS_DIR = _REPO_ROOT / "agents"
_REPO_SKILLS_DIR = _REPO_ROOT / "skills"

_DEFAULT_MIN_LINES = 500

# ─── Regex Patterns ───────────────────────────────────────────

# Markdown section heading (## or ###)
_HEADING_RE = re.compile(r"^#{2,}\s+(.+)$")

# Fenced code block delimiter (``` or ~~~)
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

# Markdown table data row: | something | something |
_TABLE_ROW_RE = re.compile(r"^\|.+\|")

# Table separator row: |---|---|
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|")

# Detection commands in any context
_DETECTION_CMD_RE = re.compile(r"\b(grep|rg|find|awk)\b")

# Agent roster signals: dispatch/agent headings or agent-name patterns
_AGENT_HEADING_RE = re.compile(r"\b(dispatch|agent|roster)\b", re.IGNORECASE)

# Error/fix section heading signals
_ERROR_HEADING_RE = re.compile(r"\b(error|fix|troubleshoot|debug|issue|failure|problem)\b", re.IGNORECASE)

# Spec table column headers: Parameter, Type, Default, Description, etc.
_SPEC_HEADER_RE = re.compile(
    r"\b(parameter|param|type|default|description|required|optional|value|flag|option)\b",
    re.IGNORECASE,
)

# Agent name patterns in tables (e.g., golang-general-engineer, python-quality-gate)
_AGENT_NAME_RE = re.compile(r"\b[\w]+-[\w]+-(?:engineer|agent|analyzer|writer|coordinator)\b", re.IGNORECASE)


# ─── Data Classes ─────────────────────────────────────────────


@dataclass
class ExtractableBlock:
    """A block of content that could be moved to a reference file."""

    content_type: str
    section_heading: str
    start_line: int
    end_line: int
    line_count: int
    suggested_reference: str
    confidence: str  # "high" | "medium" | "low"


@dataclass
class DecompositionTarget:
    """A skill or agent file that has extractable content."""

    path: Path
    component: str
    kind: str  # "skill" | "agent"
    total_lines: int
    extractable_blocks: list[ExtractableBlock] = field(default_factory=list)

    @property
    def total_extractable_lines(self) -> int:
        # Deduplicate overlapping line ranges before summing
        if not self.extractable_blocks:
            return 0
        ranges = sorted((b.start_line, b.end_line) for b in self.extractable_blocks)
        merged: list[tuple[int, int]] = []
        for start, end in ranges:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return sum(end - start + 1 for start, end in merged)

    @property
    def potential_reduction_pct(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return round(self.total_extractable_lines / self.total_lines * 100, 1)


# ─── Section Splitting ────────────────────────────────────────


@dataclass
class Section:
    """A contiguous block of lines under a single ## heading."""

    heading: str
    start_line: int  # 1-based, line of the heading itself
    lines: list[str]  # lines after the heading until next heading


def _split_into_sections(all_lines: list[str]) -> list[Section]:
    """Split file lines into sections delimited by ## or ### headings."""
    sections: list[Section] = []
    current_heading = "(preamble)"
    current_start = 1
    current_lines: list[str] = []

    for i, line in enumerate(all_lines, start=1):
        m = _HEADING_RE.match(line)
        if m:
            if current_lines or sections:
                sections.append(Section(current_heading, current_start, current_lines))
            current_heading = m.group(0).rstrip()
            current_start = i
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(Section(current_heading, current_start, current_lines))

    return sections


# ─── Content Detection ────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert heading text to a filename slug."""
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text.lower()[:40].rstrip("-")


def _suggested_ref(section: Section, content_type: str) -> str:
    slug = _slugify(section.heading)
    suffixes = {
        "code_blocks": "patterns",
        "large_tables": "reference",
        "detection_commands": "detection-commands",
        "agent_rosters": "agent-roster",
        "error_catalogs": "error-catalog",
        "spec_tables": "spec",
    }
    suffix = suffixes.get(content_type, "reference")
    return f"references/{slug}-{suffix}.md"


def _detect_code_blocks(section: Section) -> ExtractableBlock | None:
    """Flag sections with 3+ fenced code blocks totalling >20 lines."""
    block_count = 0
    code_lines = 0
    in_block = False
    block_start_relative = 0

    for i, line in enumerate(section.lines):
        if _CODE_FENCE_RE.match(line):
            if not in_block:
                in_block = True
                block_start_relative = i
                block_count += 1
            else:
                in_block = False
        elif in_block:
            code_lines += 1

    if block_count < 3 or code_lines <= 20:
        return None

    # Block spans the full section
    start = section.start_line + 1
    end = section.start_line + len(section.lines)
    return ExtractableBlock(
        content_type="code_blocks",
        section_heading=section.heading,
        start_line=start,
        end_line=end,
        line_count=end - start + 1,
        suggested_reference=_suggested_ref(section, "code_blocks"),
        confidence="high" if block_count >= 5 else "medium",
    )


def _detect_large_tables(section: Section) -> list[ExtractableBlock]:
    """Flag tables with 10+ data rows. One section can have multiple tables."""
    results: list[ExtractableBlock] = []
    in_table = False
    past_separator = False
    row_count = 0
    table_start_abs = 0

    for i, line in enumerate(section.lines):
        abs_line = section.start_line + 1 + i
        is_table_row = bool(_TABLE_ROW_RE.match(line))
        is_separator = bool(_TABLE_SEP_RE.match(line)) if is_table_row else False

        if is_table_row and not in_table:
            in_table = True
            past_separator = False
            row_count = 0
            table_start_abs = abs_line

        if in_table:
            if is_separator:
                past_separator = True
            elif past_separator and is_table_row:
                row_count += 1
            elif not is_table_row:
                # Table ended
                if row_count >= 10:
                    results.append(
                        ExtractableBlock(
                            content_type="large_tables",
                            section_heading=section.heading,
                            start_line=table_start_abs,
                            end_line=abs_line - 1,
                            line_count=abs_line - table_start_abs,
                            suggested_reference=_suggested_ref(section, "large_tables"),
                            confidence="high",
                        )
                    )
                in_table = False
                past_separator = False
                row_count = 0

    # Close any open table at EOF of section
    if in_table and row_count >= 10:
        end_abs = section.start_line + len(section.lines)
        results.append(
            ExtractableBlock(
                content_type="large_tables",
                section_heading=section.heading,
                start_line=table_start_abs,
                end_line=end_abs,
                line_count=end_abs - table_start_abs + 1,
                suggested_reference=_suggested_ref(section, "large_tables"),
                confidence="high",
            )
        )

    return results


def _detect_detection_commands(section: Section) -> ExtractableBlock | None:
    """Flag sections containing grep/rg/find in code blocks."""
    cmd_lines: list[int] = []
    in_block = False

    for i, line in enumerate(section.lines):
        if _CODE_FENCE_RE.match(line):
            in_block = not in_block
        elif in_block and _DETECTION_CMD_RE.search(line):
            cmd_lines.append(i)

    if len(cmd_lines) < 2:
        return None

    start = section.start_line + 1
    end = section.start_line + len(section.lines)
    return ExtractableBlock(
        content_type="detection_commands",
        section_heading=section.heading,
        start_line=start,
        end_line=end,
        line_count=end - start + 1,
        suggested_reference=_suggested_ref(section, "detection_commands"),
        confidence="high" if len(cmd_lines) >= 5 else "medium",
    )


def _detect_agent_rosters(section: Section) -> ExtractableBlock | None:
    """Flag sections that look like agent dispatch rosters."""
    heading_matches = bool(_AGENT_HEADING_RE.search(section.heading))
    agent_name_hits = sum(1 for line in section.lines if _AGENT_NAME_RE.search(line))
    table_rows = sum(1 for line in section.lines if _TABLE_ROW_RE.match(line))

    # Need heading signal + multiple agent references or a structured table
    if not (heading_matches or agent_name_hits >= 3):
        return None
    if agent_name_hits < 2 and table_rows < 5:
        return None

    start = section.start_line + 1
    end = section.start_line + len(section.lines)
    return ExtractableBlock(
        content_type="agent_rosters",
        section_heading=section.heading,
        start_line=start,
        end_line=end,
        line_count=end - start + 1,
        suggested_reference=_suggested_ref(section, "agent_rosters"),
        confidence="high" if agent_name_hits >= 5 else "medium",
    )


def _detect_error_catalogs(section: Section) -> ExtractableBlock | None:
    """Flag error/troubleshoot sections exceeding 30 lines."""
    if not _ERROR_HEADING_RE.search(section.heading):
        return None
    if len(section.lines) <= 30:
        return None

    start = section.start_line + 1
    end = section.start_line + len(section.lines)
    return ExtractableBlock(
        content_type="error_catalogs",
        section_heading=section.heading,
        start_line=start,
        end_line=end,
        line_count=end - start + 1,
        suggested_reference=_suggested_ref(section, "error_catalogs"),
        confidence="high" if len(section.lines) > 60 else "medium",
    )


def _detect_spec_tables(section: Section) -> ExtractableBlock | None:
    """Flag specification/parameter tables (Parameter | Type | Default | Description)."""
    if not section.lines:
        return None

    # Find the first header row of a table
    spec_table_start: int | None = None
    data_rows = 0
    past_sep = False

    for i, line in enumerate(section.lines):
        abs_line = section.start_line + 1 + i
        if _TABLE_ROW_RE.match(line):
            if spec_table_start is None:
                # Check if this header line has spec column signals
                if _SPEC_HEADER_RE.search(line):
                    spec_table_start = abs_line
                    past_sep = False
                    data_rows = 0
            elif _TABLE_SEP_RE.match(line):
                past_sep = True
            elif past_sep:
                data_rows += 1
        elif spec_table_start is not None and not _TABLE_ROW_RE.match(line):
            break

    if spec_table_start is None or data_rows < 5:
        return None

    # Determine end line
    end = spec_table_start + data_rows + 2  # header + sep + rows (approx)
    end = min(end, section.start_line + len(section.lines))

    return ExtractableBlock(
        content_type="spec_tables",
        section_heading=section.heading,
        start_line=spec_table_start,
        end_line=end,
        line_count=end - spec_table_start + 1,
        suggested_reference=_suggested_ref(section, "spec_tables"),
        confidence="high" if data_rows >= 10 else "medium",
    )


# ─── File Analysis ────────────────────────────────────────────


def _analyze_file(path: Path, component: str, kind: str, min_lines: int) -> DecompositionTarget | None:
    """Analyze a single markdown file for decomposition opportunities."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    all_lines = text.splitlines()
    total_lines = len(all_lines)

    if total_lines < min_lines:
        return None

    target = DecompositionTarget(
        path=path,
        component=component,
        kind=kind,
        total_lines=total_lines,
    )

    sections = _split_into_sections(all_lines)

    for section in sections:
        if not section.lines:
            continue

        # code_blocks
        cb = _detect_code_blocks(section)
        if cb:
            target.extractable_blocks.append(cb)

        # large_tables
        for lt in _detect_large_tables(section):
            target.extractable_blocks.append(lt)

        # detection_commands
        dc = _detect_detection_commands(section)
        if dc:
            target.extractable_blocks.append(dc)

        # agent_rosters
        ar = _detect_agent_rosters(section)
        if ar:
            target.extractable_blocks.append(ar)

        # error_catalogs
        ec = _detect_error_catalogs(section)
        if ec:
            target.extractable_blocks.append(ec)

        # spec_tables
        st = _detect_spec_tables(section)
        if st:
            target.extractable_blocks.append(st)

    # Only return if there is at least one extractable block
    if not target.extractable_blocks:
        return None

    return target


# ─── Scanning ─────────────────────────────────────────────────


def _scan_skills(base_dir: Path, min_lines: int) -> list[DecompositionTarget]:
    """Scan skills/*/SKILL.md files."""
    if not base_dir.is_dir():
        return []
    results: list[DecompositionTarget] = []
    for item in sorted(base_dir.iterdir()):
        if not item.is_dir():
            continue
        skill_md = item / "SKILL.md"
        if not skill_md.is_file():
            continue
        target = _analyze_file(skill_md, item.name, "skill", min_lines)
        if target:
            results.append(target)
    return results


def _scan_agents(base_dir: Path, min_lines: int) -> list[DecompositionTarget]:
    """Scan agents/*.md files, excluding agents/*/references/*.md."""
    if not base_dir.is_dir():
        return []
    results: list[DecompositionTarget] = []
    for item in sorted(base_dir.iterdir()):
        if not item.is_file() or item.suffix != ".md":
            continue
        if item.stem in ("INDEX", "README"):
            continue
        target = _analyze_file(item, item.stem, "agent", min_lines)
        if target:
            results.append(target)
    return results


def scan_all(min_lines: int) -> list[DecompositionTarget]:
    """Scan all repo skills and agents."""
    results: list[DecompositionTarget] = []
    results += _scan_skills(_REPO_SKILLS_DIR, min_lines)
    results += _scan_agents(_REPO_AGENTS_DIR, min_lines)
    return sorted(results, key=lambda t: (-t.total_lines, t.kind, t.component))


def scan_single_skill(name: str, min_lines: int) -> DecompositionTarget | None:
    """Scan a single skill by name."""
    skill_dir = _REPO_SKILLS_DIR / name
    if not skill_dir.is_dir():
        return None
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    return _analyze_file(skill_md, name, "skill", min_lines)


def scan_single_agent(name: str, min_lines: int) -> DecompositionTarget | None:
    """Scan a single agent by name."""
    agent_md = _REPO_AGENTS_DIR / f"{name}.md"
    if agent_md.is_file():
        return _analyze_file(agent_md, name, "agent", min_lines)
    return None


# ─── Reporting ────────────────────────────────────────────────

_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def _format_text(results: list[DecompositionTarget], min_lines: int) -> str:
    """Render human-readable report."""
    lines: list[str] = []
    lines.append("DECOMPOSITION TARGET REPORT")
    lines.append("=" * 60)
    lines.append(f"  Threshold: {min_lines}+ lines  |  Targets found: {len(results)}")
    lines.append("")

    if not results:
        lines.append("No decomposition targets found above the line threshold.")
        return "\n".join(lines)

    for t in results:
        rel_path = t.path.relative_to(_REPO_ROOT)
        lines.append(f"[{t.kind}]  {t.component}  ({t.total_lines} lines)")
        lines.append(f"  Path: {rel_path}")
        lines.append(f"  Extractable: {t.total_extractable_lines} lines  ({t.potential_reduction_pct}% reduction)")

        sorted_blocks = sorted(t.extractable_blocks, key=lambda b: _CONFIDENCE_ORDER.get(b.confidence, 9))
        for b in sorted_blocks:
            conf_tag = f"[{b.confidence}]"
            lines.append(
                f"    {conf_tag:<8}  {b.content_type:<22}  L{b.start_line}-{b.end_line}  ({b.line_count} lines)"
            )
            lines.append(f"             section: {b.section_heading}")
            lines.append(f"             suggest: {b.suggested_reference}")
        lines.append("")

    # Summary
    total_extractable = sum(t.total_extractable_lines for t in results)
    skills = [t for t in results if t.kind == "skill"]
    agents = [t for t in results if t.kind == "agent"]
    lines.append("-" * 60)
    lines.append(f"Totals: {len(skills)} skills, {len(agents)} agents  |  ~{total_extractable} lines extractable")

    return "\n".join(lines)


def _target_to_dict(t: DecompositionTarget) -> dict:
    """Convert a DecompositionTarget to a JSON-serialisable dict."""
    rel_path = str(t.path.relative_to(_REPO_ROOT))
    return {
        "path": rel_path,
        "component": t.component,
        "type": t.kind,
        "total_lines": t.total_lines,
        "extractable_blocks": [
            {
                "content_type": b.content_type,
                "section_heading": b.section_heading,
                "start_line": b.start_line,
                "end_line": b.end_line,
                "line_count": b.line_count,
                "suggested_reference": b.suggested_reference,
                "confidence": b.confidence,
            }
            for b in t.extractable_blocks
        ],
        "total_extractable_lines": t.total_extractable_lines,
        "potential_reduction_pct": t.potential_reduction_pct,
    }


def _format_json(results: list[DecompositionTarget]) -> str:
    """Render results as JSON."""
    payload = {
        "targets": [_target_to_dict(t) for t in results],
        "summary": {
            "total_targets": len(results),
            "skill_targets": sum(1 for t in results if t.kind == "skill"),
            "agent_targets": sum(1 for t in results if t.kind == "agent"),
            "total_extractable_lines": sum(t.total_extractable_lines for t in results),
        },
    }
    return json.dumps(payload, indent=2)


# ─── Main ─────────────────────────────────────────────────────


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Detect skills/agents with bloated body files that have extractable content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skill",
        metavar="NAME",
        help="Scan a single skill by name",
    )
    parser.add_argument(
        "--agent",
        metavar="NAME",
        help="Scan a single agent by name",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=_DEFAULT_MIN_LINES,
        metavar="N",
        help=f"Only report files with at least N lines (default: {_DEFAULT_MIN_LINES})",
    )
    args = parser.parse_args()

    if args.skill and args.agent:
        print("[error] Specify --skill or --agent, not both.", file=sys.stderr)
        return 0

    if args.skill:
        result = scan_single_skill(args.skill, args.min_lines)
        if result is None:
            print(f"[error] skill '{args.skill}' not found or below threshold.", file=sys.stderr)
            return 0
        results = [result]
    elif args.agent:
        result = scan_single_agent(args.agent, args.min_lines)
        if result is None:
            print(f"[error] agent '{args.agent}' not found or below threshold.", file=sys.stderr)
            return 0
        results = [result]
    else:
        results = scan_all(args.min_lines)

    if args.as_json:
        print(_format_json(results))
    else:
        print(_format_text(results, args.min_lines))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
