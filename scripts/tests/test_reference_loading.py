"""Reference loading tables for agents: table/disk agreement.

File size limits, the oversized-file debt registers, and empty references/
dirs are checked by `scripts/validate-references.py --check-size` (a CI step);
the tests at the bottom prove that check catches a bad fixture.
"""

from __future__ import annotations

import importlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReferenceTableEntry:
    """One row from an agent's reference loading table.

    Attributes:
        keywords: Trigger keywords from the first column (lowercased, comma-split).
        ref_file: Basename of the target reference file.
        raw_keywords: Raw first column text before splitting.
    """

    keywords: list[str]
    ref_file: str
    raw_keywords: str = field(repr=False)


@dataclass
class AgentReferenceInfo:
    """Parsed reference metadata for a single agent.

    Attributes:
        agent_name: Agent name (matches the .md filename stem).
        agent_file: Path to the agent .md file.
        refs_dir: Path to the agent's references/ directory (may not exist).
        table_entries: Rows parsed from the reference loading table.
        files_on_disk: Basenames of .md files found in refs_dir.
        has_table: Whether the agent has a keyword-based reference loading table.
    """

    agent_name: str
    agent_file: Path
    refs_dir: Path
    table_entries: list[ReferenceTableEntry]
    files_on_disk: list[str]
    has_table: bool


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_reference_loading_table(md_text: str) -> list[ReferenceTableEntry]:
    """Extract rows from an agent's reference loading table.

    Supports two header patterns:
    - ``| Task involves | Load reference |``
    - ``| Task Keywords | Reference File |`` (with optional extra columns)

    Args:
        md_text: Full markdown text of an agent file.

    Returns:
        List of ReferenceTableEntry. Empty list if no matching table found.
    """
    entries: list[ReferenceTableEntry] = []

    # Find table sections with headers matching known patterns.
    # Match a header row that contains both a keyword column and a file column.
    header_pattern = re.compile(
        r"^\|[^\n]*(?:task involves|task keywords)[^\n]*\|[^\n]*(?:load reference|reference file)[^\n]*\|",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in header_pattern.finditer(md_text):
        start = match.start()
        # Collect lines from this header forward until a blank line or non-table line
        block = md_text[start:]
        rows: list[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                rows.append(stripped)
            elif rows:
                # Stop at first non-table line after we've started collecting
                break

        # rows[0] = header, rows[1] = separator, rows[2:] = data rows
        if len(rows) < 3:
            continue

        for row in rows[2:]:
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if len(cells) < 2:
                continue
            keyword_col = cells[0]
            ref_col = cells[1]

            # Extract filename from markdown link or plain text
            link_match = re.search(r"\[([^\]]+\.md)\]", ref_col)
            if link_match:
                ref_filename = link_match.group(1)
            else:
                # Plain text — extract last path segment
                ref_filename = ref_col.strip().split("/")[-1].strip("`")

            if not ref_filename.endswith(".md"):
                continue

            # Split comma-separated keywords, strip whitespace, lowercase
            keywords = [kw.strip().lower() for kw in keyword_col.split(",") if kw.strip()]

            entries.append(
                ReferenceTableEntry(
                    keywords=keywords,
                    ref_file=ref_filename,
                    raw_keywords=keyword_col,
                )
            )

    return entries


def _load_agent_info(agent_name: str) -> AgentReferenceInfo:
    """Load reference metadata for a named agent.

    Args:
        agent_name: Agent stem name (e.g. ``react-native-engineer``).

    Returns:
        AgentReferenceInfo populated from the agent .md file and references/ directory.

    Raises:
        FileNotFoundError: If the agent .md file does not exist.
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file}")

    md_text = agent_file.read_text(encoding="utf-8")
    table_entries = _parse_reference_loading_table(md_text)

    refs_dir = AGENTS_DIR / agent_name / "references"
    files_on_disk: list[str] = []
    if refs_dir.exists():
        files_on_disk = [p.name for p in sorted(refs_dir.glob("*.md"))]

    return AgentReferenceInfo(
        agent_name=agent_name,
        agent_file=agent_file,
        refs_dir=refs_dir,
        table_entries=table_entries,
        files_on_disk=files_on_disk,
        has_table=len(table_entries) > 0,
    )


# ---------------------------------------------------------------------------
# Category 1: Reference Loading Table Completeness
# ---------------------------------------------------------------------------


class TestReferenceLoadingTableCompleteness:
    """Every reference file on disk must have a table entry, and vice versa."""

    AGENTS_WITH_TABLES: ClassVar[list[str]] = [
        "react-native-engineer",
        "typescript-frontend-engineer",
        "performance-optimization-engineer",
    ]

    @pytest.mark.parametrize("agent_name", AGENTS_WITH_TABLES)
    def test_table_and_disk_agree(self, agent_name: str) -> None:
        """The table has rows, every row names a file on disk, and every file on disk has a row.

        A file on disk with no row is dead: the agent never loads it.

        Args:
            agent_name: Agent under test.
        """
        info = _load_agent_info(agent_name)
        assert info.has_table, f"{agent_name}: no reference loading table found in agent markdown"
        assert info.table_entries, f"{agent_name}: reference loading table is empty"

        missing = [e.ref_file for e in info.table_entries if not (info.refs_dir / e.ref_file).exists()]
        assert not missing, f"{agent_name}: table rows point to missing files: {missing}"

        table_files = {e.ref_file for e in info.table_entries}
        orphaned = [f for f in info.files_on_disk if f not in table_files]
        assert not orphaned, f"{agent_name}: files on disk have no table row (never loaded): {orphaned}"


# ---------------------------------------------------------------------------
# Reference size + discoverability: `validate-references.py --check-size` (CI)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO_ROOT / "scripts"))
validate_references = importlib.import_module("validate-references")


def _skill_tree(tmp_path: Path, ref_lines: int) -> tuple[Path, Path]:
    agents = tmp_path / "agents"
    (agents / "demo" / "references").mkdir(parents=True)
    (agents / "demo" / "references" / "a.md").write_text("x\n", encoding="utf-8")
    skills = tmp_path / "skills"
    ref = skills / "cat" / "demo" / "references" / "nested" / "big.md"
    ref.parent.mkdir(parents=True)
    ref.write_text("line\n" * ref_lines, encoding="utf-8")
    (skills / "cat" / "demo" / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    return agents, skills


def test_check_size_passes_clean_tree(tmp_path: Path) -> None:
    agents, skills = _skill_tree(tmp_path, 10)
    assert validate_references.check_reference_sizes(agents, skills, set(), {}) == []


def test_check_size_catches_unregistered_nested_oversize_and_stale_entry(tmp_path: Path) -> None:
    agents, skills = _skill_tree(tmp_path, validate_references.REFERENCE_LINE_LIMIT + 1)
    failures = validate_references.check_reference_sizes(
        agents, skills, {"demo/references/gone.md"}, {"cat/other/references/x.md": "not-a-date"}
    )
    text = "\n".join(failures)
    assert "skills/cat/demo/references/nested/big.md: 501 lines" in text
    assert "agents/demo/references/gone.md: stale" in text
    assert "skills/cat/other/references/x.md: stale" in text
    assert "invalid baseline date" in text


def test_check_size_registered_debt_passes_and_empty_refs_dir_fails(tmp_path: Path) -> None:
    agents, skills = _skill_tree(tmp_path, validate_references.REFERENCE_LINE_LIMIT + 1)
    (skills / "cat" / "empty" / "references").mkdir(parents=True)
    (skills / "cat" / "empty" / "SKILL.md").write_text("# Empty\n", encoding="utf-8")
    failures = validate_references.check_reference_sizes(
        agents, skills, set(), {"cat/demo/references/nested/big.md": "2026-09-18"}
    )
    assert failures == ["skills/cat/empty/references/ has no .md files"]
