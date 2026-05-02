"""Tests for research-stats-checkpoint.py.

Covers happy path (gate passes), gate-fail on insufficient primaries, gate-fail
on single-agent dominance, and empty-directory handling.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the hyphenated script as a module via importlib.
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "research-stats-checkpoint.py"
_spec = importlib.util.spec_from_file_location("research_stats_checkpoint", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
checkpoint = importlib.util.module_from_spec(_spec)
sys.modules["research_stats_checkpoint"] = checkpoint
_spec.loader.exec_module(checkpoint)


# ---- Helpers ----------------------------------------------------------------


def write_artifact(path: Path, body: str) -> None:
    """Create parent dirs and write the artifact body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_research_tree(root: Path, layout: dict[str, dict[str, str]]) -> None:
    """Build a research/{topic}/ tree from a {agent: {filename: body}} dict."""
    for agent, files in layout.items():
        for filename, body in files.items():
            write_artifact(root / agent / filename, body)


PRIMARY_BODY = """---
source_type: primary
url: https://example.org/interview-1
---
Direct quote from the subject.
"""

SECONDARY_BODY = """---
source_type: secondary
url: https://wiki.example.org/about
---
Wikipedia summary.
"""


# ---- Happy path -------------------------------------------------------------


def test_happy_path_emits_table_and_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Three primary sources spread across three agents — gate passes, exit 0."""
    topic_dir = tmp_path / "feynman"
    make_research_tree(
        topic_dir,
        {
            "researcher-a": {
                "interview.md": PRIMARY_BODY,
                "lecture-notes.md": PRIMARY_BODY,
            },
            "researcher-b": {
                "biography.md": SECONDARY_BODY,
                "letters.md": PRIMARY_BODY,
            },
            "researcher-c": {
                "wiki.md": SECONDARY_BODY,
            },
        },
    )

    rc = checkpoint.main([str(topic_dir)])
    captured = capsys.readouterr()

    assert rc == 0, captured.out + captured.err
    assert "Research Stats Checkpoint" in captured.out
    assert "researcher-a" in captured.out
    assert "researcher-b" in captured.out
    assert "researcher-c" in captured.out
    # Total artifacts row.
    assert "5" in captured.out


# ---- Gate fail: insufficient primaries --------------------------------------


def test_gate_fails_on_insufficient_primary_sources(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Only one primary source — below the default min-primary=3 — exits non-zero."""
    topic_dir = tmp_path / "topic"
    make_research_tree(
        topic_dir,
        {
            "researcher-a": {"a.md": PRIMARY_BODY, "b.md": SECONDARY_BODY},
            "researcher-b": {"c.md": SECONDARY_BODY, "d.md": SECONDARY_BODY},
        },
    )

    rc = checkpoint.main([str(topic_dir)])
    captured = capsys.readouterr()

    assert rc != 0
    assert "primary" in captured.out.lower() or "primary" in captured.err.lower()


def test_min_primary_threshold_is_configurable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Same setup passes when --min-primary is lowered to 1."""
    topic_dir = tmp_path / "topic"
    make_research_tree(
        topic_dir,
        {
            "researcher-a": {"a.md": PRIMARY_BODY, "b.md": SECONDARY_BODY},
            "researcher-b": {"c.md": SECONDARY_BODY, "d.md": SECONDARY_BODY},
        },
    )

    rc = checkpoint.main([str(topic_dir), "--min-primary", "1", "--max-agent-share", "0.9"])
    _ = capsys.readouterr()

    assert rc == 0


# ---- Gate fail: single-agent dominance --------------------------------------


def test_gate_fails_on_single_agent_dominance(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """If one agent owns >75% of artifacts (default), exit non-zero."""
    topic_dir = tmp_path / "topic"
    make_research_tree(
        topic_dir,
        {
            "researcher-a": {
                "a.md": PRIMARY_BODY,
                "b.md": PRIMARY_BODY,
                "c.md": PRIMARY_BODY,
                "d.md": PRIMARY_BODY,
                "e.md": PRIMARY_BODY,
            },
            "researcher-b": {
                "f.md": SECONDARY_BODY,
            },
        },
    )

    rc = checkpoint.main([str(topic_dir)])
    captured = capsys.readouterr()

    assert rc != 0
    # Either word should surface in the human-readable failure reason.
    assert "agent" in captured.out.lower() or "share" in captured.out.lower()


# ---- Gate fail: empty directory --------------------------------------------


def test_empty_directory_exits_nonzero_with_helpful_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An empty research dir is a gate fail — emit a clear message."""
    topic_dir = tmp_path / "empty-topic"
    topic_dir.mkdir()

    rc = checkpoint.main([str(topic_dir)])
    captured = capsys.readouterr()

    assert rc != 0
    combined = (captured.out + captured.err).lower()
    assert "no artifacts" in combined or "empty" in combined


def test_missing_directory_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Pointing at a non-existent path is a gate fail with a clear message."""
    missing = tmp_path / "does-not-exist"

    rc = checkpoint.main([str(missing)])
    captured = capsys.readouterr()

    assert rc != 0
    assert (
        "not found" in (captured.out + captured.err).lower()
        or "does not exist" in (captured.out + captured.err).lower()
    )


# ---- Conflict detection -----------------------------------------------------


def test_conflict_detection_surfaces_disagreement(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two artifacts with different values for the same frontmatter key are flagged."""
    topic_dir = tmp_path / "topic"
    make_research_tree(
        topic_dir,
        {
            "researcher-a": {
                "a.md": "---\nsource_type: primary\nbirth_year: 1918\n---\nbody",
                "b.md": "---\nsource_type: primary\nbirth_year: 1918\n---\nbody",
            },
            "researcher-b": {
                "c.md": "---\nsource_type: primary\nbirth_year: 1919\n---\nbody",
                "d.md": "---\nsource_type: secondary\nurl: https://x\n---\nbody",
            },
        },
    )

    rc = checkpoint.main([str(topic_dir), "--max-agent-share", "0.9"])
    captured = capsys.readouterr()

    # Conflict on birth_year is reported even when other gates pass.
    assert "birth_year" in captured.out
    # Three primaries + below-default agent share = gate passes; conflicts are advisory.
    assert rc == 0


# ---- Filename-pattern agent detection --------------------------------------


def test_agent_inferred_from_filename_when_files_are_flat(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """When files sit at the topic root, agent is inferred from `{agent}__{name}` prefix."""
    topic_dir = tmp_path / "flat-topic"
    topic_dir.mkdir()
    write_artifact(topic_dir / "researcher-a__interview.md", PRIMARY_BODY)
    write_artifact(topic_dir / "researcher-a__notes.md", PRIMARY_BODY)
    write_artifact(topic_dir / "researcher-b__bio.md", PRIMARY_BODY)
    write_artifact(topic_dir / "researcher-c__wiki.md", SECONDARY_BODY)

    rc = checkpoint.main([str(topic_dir)])
    captured = capsys.readouterr()

    assert rc == 0, captured.out + captured.err
    assert "researcher-a" in captured.out
    assert "researcher-b" in captured.out
    assert "researcher-c" in captured.out
