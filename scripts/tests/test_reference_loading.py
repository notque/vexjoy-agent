"""Reference loading tables for agents: table/disk agreement, keyword matching, isolation.

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
# Test data
# ---------------------------------------------------------------------------

REFERENCE_LOADING_TESTS: list[dict[str, object]] = [
    {
        "agent": "react-native-engineer",
        "query": "optimize FlashList scrolling performance",
        "expected_refs": ["list-performance.md"],
        "unexpected_refs": ["animation-patterns.md", "navigation-patterns.md"],
    },
    {
        "agent": "react-native-engineer",
        "query": "add smooth Reanimated gesture animations",
        "expected_refs": ["animation-patterns.md"],
        "unexpected_refs": ["list-performance.md"],
    },
    {
        "agent": "react-native-engineer",
        "query": "set up native stack navigation with deep links",
        "expected_refs": ["navigation-patterns.md"],
        "unexpected_refs": ["animation-patterns.md"],
    },
    {
        "agent": "typescript-frontend-engineer",
        "query": "audit Server Action auth and the middleware bypass CVE",
        "expected_refs": ["nextjs-security.md"],
        "unexpected_refs": ["react-view-transitions.md"],
    },
    {
        "agent": "typescript-frontend-engineer",
        "query": "add ViewTransition animations between routes",
        "expected_refs": ["react-view-transitions.md"],
        "unexpected_refs": ["nextjs-security.md"],
    },
    {
        "agent": "performance-optimization-engineer",
        "query": "eliminate async waterfall in API calls",
        "expected_refs": ["react-async-patterns.md"],
        "unexpected_refs": ["js-algorithm-optimizations.md"],
    },
    {
        "agent": "performance-optimization-engineer",
        "query": "optimize Set and Map lookups in hot loop",
        "expected_refs": ["js-algorithm-optimizations.md"],
        "unexpected_refs": ["react-async-patterns.md"],
    },
]


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


def _match_refs_for_query(query: str, entries: list[ReferenceTableEntry]) -> list[str]:
    """Return reference filenames whose keywords appear in the query.

    Each table entry is checked: if ANY of its keywords match the query as a
    whole word or phrase (using word boundaries), the entry's reference file
    is included. Word-boundary matching prevents short keywords like "min" or
    "map" from matching inside longer words like "eliminate" or "bitmap".

    Args:
        query: Free-text task description.
        entries: Reference loading table rows to match against.

    Returns:
        Deduplicated list of matched reference file basenames.
    """
    query_lower = query.lower()
    matched: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        for keyword in entry.keywords:
            if not keyword:
                continue
            # Use word-boundary anchors so "min" does not match "eliminate"
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, query_lower):
                if entry.ref_file not in seen:
                    matched.append(entry.ref_file)
                    seen.add(entry.ref_file)
                break

    return matched


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
# Category 2: Keyword-to-Reference Mapping Validation
# ---------------------------------------------------------------------------


def _build_test_id(case: dict[str, object]) -> str:
    """Build a readable pytest ID from a test case dict.

    Args:
        case: A dict from REFERENCE_LOADING_TESTS.

    Returns:
        String in the form ``agent-name::first 30 chars of query``.
    """
    agent = str(case["agent"])
    query = str(case["query"])[:30]
    return f"{agent}::{query}"


class TestKeywordToReferenceMappingValidation:
    """Keyword matching resolves to correct reference files for known queries."""

    @pytest.mark.parametrize("case", REFERENCE_LOADING_TESTS, ids=[_build_test_id(c) for c in REFERENCE_LOADING_TESTS])
    def test_expected_refs_are_matched(self, case: dict[str, object]) -> None:
        """The expected reference file(s) must be selected for the given query.

        Args:
            case: A test case dict with agent, query, expected_refs, unexpected_refs.
        """
        agent_name = str(case["agent"])
        query = str(case["query"])
        expected_refs: list[str] = list(case["expected_refs"])  # type: ignore[arg-type]

        info = _load_agent_info(agent_name)
        if not info.has_table:
            pytest.skip(f"{agent_name} has no reference loading table")

        matched = _match_refs_for_query(query, info.table_entries)

        missing_from_match = [r for r in expected_refs if r not in matched]
        assert not missing_from_match, (
            f"{agent_name}: query '{query}' did not match expected refs:\n"
            + "\n".join(f"  - {r}" for r in missing_from_match)
            + f"\n  Matched: {matched}"
        )

    @pytest.mark.parametrize("case", REFERENCE_LOADING_TESTS, ids=[_build_test_id(c) for c in REFERENCE_LOADING_TESTS])
    def test_unexpected_refs_are_not_matched(self, case: dict[str, object]) -> None:
        """Reference files listed as unexpected must not be selected for the query.

        Args:
            case: A test case dict with agent, query, expected_refs, unexpected_refs.
        """
        agent_name = str(case["agent"])
        query = str(case["query"])
        unexpected_refs: list[str] = list(case["unexpected_refs"])  # type: ignore[arg-type]

        info = _load_agent_info(agent_name)
        if not info.has_table:
            pytest.skip(f"{agent_name} has no reference loading table")

        matched = _match_refs_for_query(query, info.table_entries)

        false_positives = [r for r in unexpected_refs if r in matched]
        assert not false_positives, (
            f"{agent_name}: query '{query}' incorrectly matched refs that should NOT be selected:\n"
            + "\n".join(f"  - {r}" for r in false_positives)
            + f"\n  All matched: {matched}"
        )


# ---------------------------------------------------------------------------
# Cross-agent reference isolation
# ---------------------------------------------------------------------------


def _extract_reference_links(md_text: str) -> list[str]:
    """Extract all relative markdown link targets from an agent file.

    Args:
        md_text: Raw markdown text of an agent file.

    Returns:
        List of link target strings (the href portion of ``[text](href)``).
    """
    return re.findall(r"\]\(([^)]+\.md)\)", md_text)


class TestCrossAgentReferenceIsolation:
    """Each agent must only reference files within its own directory."""

    AGENTS_WITH_TABLES: ClassVar[list[str]] = [
        "react-native-engineer",
        "typescript-frontend-engineer",
        "performance-optimization-engineer",
        "ui-design-engineer",
    ]

    @pytest.mark.parametrize("agent_name", AGENTS_WITH_TABLES)
    def test_agent_references_are_self_contained(self, agent_name: str) -> None:
        """An agent's reference loading table must not link into another agent's directory.

        Shared patterns (e.g. ``skills/shared-patterns/``) are excluded from this check
        as they are intentionally cross-cutting.

        Args:
            agent_name: Agent under test.
        """
        info = _load_agent_info(agent_name)
        agent_prefix = f"{agent_name}/references/"

        cross_agent_refs: list[str] = []
        for entry in info.table_entries:
            # Reconstruct the full link target the table entry came from by checking
            # the raw agent markdown for this filename
            md_text = info.agent_file.read_text(encoding="utf-8")
            all_links = _extract_reference_links(md_text)

            for link in all_links:
                if entry.ref_file in link:
                    # Shared skills/ paths are allowed
                    if link.startswith("../skills/") or link.startswith("skills/"):
                        continue
                    # Links must point into this agent's own directory
                    if agent_prefix not in link and entry.ref_file in link:
                        # Check it doesn't belong to another known agent
                        for other_agent_dir in AGENTS_DIR.iterdir():
                            if other_agent_dir.is_dir() and other_agent_dir.name != agent_name:
                                if other_agent_dir.name in link:
                                    cross_agent_refs.append(f"{link!r} (in {agent_name})")

        assert not cross_agent_refs, f"{agent_name}: reference loading table contains cross-agent links:\n" + "\n".join(
            f"  - {r}" for r in cross_agent_refs
        )


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
