#!/usr/bin/env python3
"""
Tests for the pretool-subagent-warmstart hook.

Run with: python3 -m pytest hooks/tests/test_pretool_subagent_warmstart.py -v
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-subagent-warmstart.py"

spec = importlib.util.spec_from_file_location("pretool_subagent_warmstart", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

load_recent_reads = mod.load_recent_reads
extract_task_plan = mod.extract_task_plan
extract_decisions = mod.extract_decisions
load_adr_session = mod.load_adr_session
list_discoveries = mod.list_discoveries
build_context_block = mod.build_context_block
MAX_OUTPUT_CHARS = mod.MAX_OUTPUT_CHARS
MAX_FILES_SHOWN = mod.MAX_FILES_SHOWN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Tool Name Filtering
# ---------------------------------------------------------------------------


class TestToolNameFiltering:
    """Only Agent tool events should be processed."""

    def test_nonagent_tools_exit_zero(self):
        """Non-Agent tool filtering is now handled by matcher 'Agent' in settings.json.

        When called directly (without matcher), the hook processes any tool_name.
        This test verifies the hook still exits 0 (non-blocking) for any input.
        """
        for tool, tool_input in [
            ("Read", {"file_path": "/x"}),
            ("Write", {"file_path": "/x"}),
            ("Bash", {"command": "ls"}),
        ]:
            stdout, stderr, code = run_hook({"tool_name": tool, "tool_input": tool_input})
            assert code == 0

    def test_processes_agent_tool(self, tmp_path, monkeypatch):
        """Agent tool events should produce warmstart context."""
        monkeypatch.chdir(tmp_path)
        event = {"tool_name": "Agent", "tool_input": {"prompt": "do work"}}
        stdout, stderr, code = run_hook(event)
        assert code == 0
        assert stdout.strip()
        output = json.loads(stdout)
        context = output["hookSpecificOutput"].get("additionalContext", "")
        assert "[warmstart]" in context


# ---------------------------------------------------------------------------
# load_recent_reads
# ---------------------------------------------------------------------------


class TestLoadRecentReads:
    """Test reading session-reads.txt."""

    def test_missing_file_returns_empty(self, tmp_path):
        """Non-existent file returns empty list."""
        result = load_recent_reads(tmp_path / "nonexistent.txt")
        assert result == []

    def test_reads_file_paths(self, tmp_path):
        """File with paths returns them as list."""
        reads_file = tmp_path / "session-reads.txt"
        reads_file.write_text("/a.py\n/b.go\n/c.rs\n")
        result = load_recent_reads(reads_file)
        assert result == ["/a.py", "/b.go", "/c.rs"]

    def test_caps_at_max_count(self, tmp_path):
        """Only returns up to max_count most recent entries."""
        reads_file = tmp_path / "session-reads.txt"
        paths = [f"/file{i}.py" for i in range(30)]
        reads_file.write_text("\n".join(paths) + "\n")
        result = load_recent_reads(reads_file, max_count=5)
        assert len(result) == 5
        # Should be the last 5 entries
        assert result == [f"/file{i}.py" for i in range(25, 30)]

    def test_skips_empty_lines(self, tmp_path):
        """Empty lines in the file are ignored."""
        reads_file = tmp_path / "session-reads.txt"
        reads_file.write_text("/a.py\n\n\n/b.py\n")
        result = load_recent_reads(reads_file)
        assert result == ["/a.py", "/b.py"]

    def test_default_max_is_20(self, tmp_path):
        """Default max_count should be MAX_FILES_SHOWN (20)."""
        reads_file = tmp_path / "session-reads.txt"
        paths = [f"/file{i}.py" for i in range(25)]
        reads_file.write_text("\n".join(paths) + "\n")
        result = load_recent_reads(reads_file)
        assert len(result) == MAX_FILES_SHOWN


# ---------------------------------------------------------------------------
# extract_task_plan
# ---------------------------------------------------------------------------


class TestExtractTaskPlan:
    """Test extraction of Goal and Status from task_plan.md."""

    def test_missing_file_returns_empty(self, tmp_path):
        """Non-existent task_plan.md returns empty dict."""
        result = extract_task_plan(tmp_path / "task_plan.md")
        assert result == {"goal": "", "status": ""}

    def test_extracts_goal_and_status(self, tmp_path):
        """Extracts Goal line and Status line from plan."""
        plan = tmp_path / "task_plan.md"
        plan.write_text(
            "# Task Plan: Test\n\n"
            "## Goal\n"
            "Implement the warmstart hook for subagents\n\n"
            "## Phases\n"
            "- [x] Phase 1: Understand\n\n"
            "## Status\n"
            "**Currently in Phase 2** - Implementing hooks\n"
        )
        result = extract_task_plan(plan)
        assert result["goal"] == "Implement the warmstart hook for subagents"
        assert "Phase 2" in result["status"]

    def test_extracts_goal_only(self, tmp_path):
        """Plan with goal but no status."""
        plan = tmp_path / "task_plan.md"
        plan.write_text("# Task Plan\n\n## Goal\nBuild the feature\n\n## Phases\n- [ ] Phase 1\n")
        result = extract_task_plan(plan)
        assert result["goal"] == "Build the feature"
        assert result["status"] == ""

    def test_extracts_status_only(self, tmp_path):
        """Plan with status but heading-only goal section."""
        plan = tmp_path / "task_plan.md"
        plan.write_text("# Task Plan\n\n## Goal\n## Phases\n**Currently in Phase 3** - Testing\n")
        result = extract_task_plan(plan)
        assert result["goal"] == ""
        assert "Phase 3" in result["status"]


# ---------------------------------------------------------------------------
# extract_decisions
# ---------------------------------------------------------------------------


class TestExtractDecisions:
    """Test extraction of decisions from task_plan.md."""

    def test_missing_file_returns_empty(self, tmp_path):
        """Non-existent file returns empty list."""
        result = extract_decisions(tmp_path / "task_plan.md")
        assert result == []

    def test_extracts_decisions(self, tmp_path):
        """Extracts bullet items from Decisions Made section."""
        plan = tmp_path / "task_plan.md"
        plan.write_text(
            "# Task Plan\n\n"
            "## Decisions Made\n"
            "- Use atomic file operations for safety\n"
            "- Cap output at 8000 chars\n\n"
            "## Errors Encountered\n"
            "- None yet\n"
        )
        result = extract_decisions(plan)
        assert len(result) == 2
        assert "atomic file operations" in result[0]
        assert "8000 chars" in result[1]

    def test_no_decisions_section_returns_empty(self, tmp_path):
        """Plan without Decisions Made section returns empty."""
        plan = tmp_path / "task_plan.md"
        plan.write_text("# Task Plan\n\n## Goal\nDo stuff\n")
        result = extract_decisions(plan)
        assert result == []

    def test_empty_decisions_section_returns_empty(self, tmp_path):
        """Decisions Made section with no items returns empty."""
        plan = tmp_path / "task_plan.md"
        plan.write_text("# Task Plan\n\n## Decisions Made\n\n## Errors Encountered\n")
        result = extract_decisions(plan)
        assert result == []


# ---------------------------------------------------------------------------
# load_adr_session
# ---------------------------------------------------------------------------


class TestLoadAdrSession:
    """Test loading ADR session metadata."""

    def test_missing_file_returns_empty(self, tmp_path):
        """Non-existent file returns empty dict."""
        result = load_adr_session(tmp_path / ".adr-session.json")
        assert result == {"adr_path": "", "domain": ""}

    def test_loads_adr_session(self, tmp_path):
        """Loads adr_path and domain from valid JSON."""
        session_file = tmp_path / ".adr-session.json"
        session_file.write_text(
            json.dumps(
                {
                    "adr_path": "adr/088-subagent-warmstart.md",
                    "domain": "hooks",
                    "adr_hash": "abc123",
                }
            )
        )
        result = load_adr_session(session_file)
        assert result["adr_path"] == "adr/088-subagent-warmstart.md"
        assert result["domain"] == "hooks"

    def test_malformed_json_returns_empty(self, tmp_path):
        """Malformed JSON returns empty dict gracefully."""
        session_file = tmp_path / ".adr-session.json"
        session_file.write_text("{broken json")
        result = load_adr_session(session_file)
        assert result == {"adr_path": "", "domain": ""}

    def test_missing_keys_returns_empty_strings(self, tmp_path):
        """JSON without expected keys returns empty strings."""
        session_file = tmp_path / ".adr-session.json"
        session_file.write_text(json.dumps({"other": "data"}))
        result = load_adr_session(session_file)
        assert result["adr_path"] == ""
        assert result["domain"] == ""


# ---------------------------------------------------------------------------
# list_discoveries
# ---------------------------------------------------------------------------


class TestListDiscoveries:
    """Test listing discovery brief files."""

    def test_missing_directory_returns_empty(self, tmp_path):
        """Non-existent directory returns empty list."""
        result = list_discoveries(tmp_path / "nonexistent")
        assert result == []

    def test_lists_files_sorted(self, tmp_path):
        """Lists files in sorted order."""
        disc_dir = tmp_path / "discoveries"
        disc_dir.mkdir()
        (disc_dir / "002-routing.md").write_text("routing")
        (disc_dir / "001-hooks.md").write_text("hooks")
        (disc_dir / "003-tests.md").write_text("tests")
        result = list_discoveries(disc_dir)
        assert result == ["001-hooks.md", "002-routing.md", "003-tests.md"]

    def test_empty_directory_returns_empty(self, tmp_path):
        """Empty directory returns empty list."""
        disc_dir = tmp_path / "discoveries"
        disc_dir.mkdir()
        result = list_discoveries(disc_dir)
        assert result == []

    def test_skips_subdirectories(self, tmp_path):
        """Only files are listed, not subdirectories."""
        disc_dir = tmp_path / "discoveries"
        disc_dir.mkdir()
        (disc_dir / "001-hooks.md").write_text("hooks")
        (disc_dir / "subdir").mkdir()
        result = list_discoveries(disc_dir)
        assert result == ["001-hooks.md"]


# ---------------------------------------------------------------------------
# build_context_block
# ---------------------------------------------------------------------------


class TestBuildContextBlock:
    """Test context block construction."""

    def test_all_empty_produces_minimal_output(self):
        """All empty inputs should produce a minimal block."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "", "status": ""},
            decisions=[],
            adr_session={"adr_path": "", "domain": ""},
            discoveries=[],
        )
        assert "[warmstart] Parent session context for subagent:" in result
        assert "[warmstart] Files seen (0): none" in result

    def test_includes_files(self):
        """Files are listed with count."""
        result = build_context_block(
            files=["/a.py", "/b.go"],
            task_plan={"goal": "", "status": ""},
            decisions=[],
            adr_session={"adr_path": "", "domain": ""},
            discoveries=[],
        )
        assert "[warmstart] Files seen (2): /a.py, /b.go" in result

    def test_includes_task_plan(self):
        """Task goal and status are included."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "Build the hooks", "status": "**Currently in Phase 2**"},
            decisions=[],
            adr_session={"adr_path": "", "domain": ""},
            discoveries=[],
        )
        assert "[warmstart] Task: Build the hooks" in result
        assert "[warmstart] Status: **Currently in Phase 2**" in result

    def test_includes_adr_session(self):
        """ADR session info is included."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "", "status": ""},
            decisions=[],
            adr_session={"adr_path": "adr/088.md", "domain": "hooks"},
            discoveries=[],
        )
        assert "[warmstart] ADR session: adr/088.md (domain: hooks)" in result

    def test_includes_decisions(self):
        """Decisions are included as semicolon-separated list."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "", "status": ""},
            decisions=["Use atomic ops", "Cap at 8000 chars"],
            adr_session={"adr_path": "", "domain": ""},
            discoveries=[],
        )
        assert "[warmstart] Decisions: Use atomic ops; Cap at 8000 chars" in result

    def test_includes_discoveries(self):
        """Discovery briefs are listed."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "", "status": ""},
            decisions=[],
            adr_session={"adr_path": "", "domain": ""},
            discoveries=["001-hooks.md", "002-routing.md"],
        )
        assert "[warmstart] Discovery briefs: 001-hooks.md, 002-routing.md" in result

    def test_full_context_block(self):
        """Full block with all sections populated."""
        result = build_context_block(
            files=["/a.py", "/b.go"],
            task_plan={"goal": "Build warmstart", "status": "**Currently in Phase 3**"},
            decisions=["Use file reads only"],
            adr_session={"adr_path": "adr/088.md", "domain": "hooks"},
            discoveries=["001-hooks.md"],
        )
        assert "[warmstart] Parent session context for subagent:" in result
        assert "[warmstart] Files seen (2):" in result
        assert "[warmstart] Task: Build warmstart" in result
        assert "[warmstart] Status:" in result
        assert "[warmstart] ADR session: adr/088.md" in result
        assert "[warmstart] Decisions:" in result
        assert "[warmstart] Discovery briefs:" in result

    def test_caps_at_max_chars(self):
        """Output exceeding MAX_OUTPUT_CHARS is truncated."""
        # Generate a huge file list
        big_files = [f"/very/long/path/to/file_{i:04d}.py" for i in range(500)]
        result = build_context_block(
            files=big_files,
            task_plan={"goal": "x" * 1000, "status": "y" * 1000},
            decisions=["z" * 500],
            adr_session={"adr_path": "adr/big.md", "domain": "huge"},
            discoveries=["d" * 100 for _ in range(50)],
        )
        assert len(result) <= MAX_OUTPUT_CHARS
        assert result.endswith("...")

    def test_skips_empty_goal(self):
        """Empty goal is not included in output."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "", "status": "**Phase 1**"},
            decisions=[],
            adr_session={"adr_path": "", "domain": ""},
            discoveries=[],
        )
        assert "[warmstart] Task:" not in result
        assert "[warmstart] Status:" in result

    def test_skips_empty_adr_path(self):
        """Empty ADR path means no ADR line in output."""
        result = build_context_block(
            files=[],
            task_plan={"goal": "", "status": ""},
            decisions=[],
            adr_session={"adr_path": "", "domain": "hooks"},
            discoveries=[],
        )
        assert "[warmstart] ADR session:" not in result


# ---------------------------------------------------------------------------
# Non-Blocking Guarantee
# ---------------------------------------------------------------------------


class TestNonBlocking:
    """Hook must always exit 0 regardless of errors."""

    def test_exits_zero_on_malformed_json(self):
        """Malformed JSON input should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json{{{",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_empty_input(self):
        """Empty stdin should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_missing_tool_name(self):
        """Event with no tool_name should still exit 0."""
        event = {"tool_input": {"prompt": "hello"}}
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Graceful Degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Hook should produce valid output even when context files are missing."""

    def test_no_context_files_produces_minimal_output(self, tmp_path, monkeypatch):
        """Agent event with no context files produces minimal warmstart block."""
        monkeypatch.chdir(tmp_path)
        event = {"tool_name": "Agent", "tool_input": {"prompt": "do work"}}
        stdout, stderr, code = run_hook(event)

        assert code == 0
        output = json.loads(stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "[warmstart] Parent session context for subagent:" in context
        assert "[warmstart] Files seen (0): none" in context

    def test_partial_context_files(self, tmp_path, monkeypatch):
        """Some context files present, some missing."""
        monkeypatch.chdir(tmp_path)

        # Only create session-reads.txt
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "session-reads.txt").write_text("/a.py\n/b.go\n")

        event = {"tool_name": "Agent", "tool_input": {"prompt": "do work"}}
        stdout, stderr, code = run_hook(event)

        assert code == 0
        output = json.loads(stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "[warmstart] Files seen (2):" in context
        # No task plan or ADR sections since those files don't exist
        assert "[warmstart] ADR session:" not in context


# ---------------------------------------------------------------------------
# Output Format Correctness
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Verify the hook JSON output structure."""

    def test_agent_event_produces_valid_json(self, tmp_path, monkeypatch):
        """Agent event output is valid JSON with correct structure."""
        monkeypatch.chdir(tmp_path)
        event = {"tool_name": "Agent", "tool_input": {"prompt": "work"}}
        stdout, stderr, code = run_hook(event)

        assert code == 0
        output = json.loads(stdout)
        assert "hookSpecificOutput" in output
        hook_out = output["hookSpecificOutput"]
        assert hook_out["hookEventName"] == "PreToolUse"
        assert "additionalContext" in hook_out
        assert "[warmstart]" in hook_out["additionalContext"]
