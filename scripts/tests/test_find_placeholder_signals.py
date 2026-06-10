"""Tests for validate-references.py find_placeholder_signals and orphan exit codes.

Covers PR #779 review findings F1-F3:
1. Every PLACEHOLDER_SIGNALS variant in a loading-table row is flagged.
2. Content-derived signals pass.
3. Matching is case-insensitive and exact per cell; prose lines are ignored.
4. build_json_results exit_code counts orphans as failures.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

vr = importlib.import_module("validate-references")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the validator at a temp repo; return a factory writing agents/*.md."""
    (tmp_path / "agents").mkdir()
    monkeypatch.setattr(vr, "REPO_ROOT", tmp_path)

    def _write(table_row: str, name: str = "test-agent.md") -> Path:
        f = tmp_path / "agents" / name
        f.write_text(f"# Agent\n\n| Signal | File | Why |\n|---|---|---|\n{table_row}\n", encoding="utf-8")
        return f

    return _write


class TestFindPlaceholderSignals:
    @pytest.mark.parametrize("signal", vr.PLACEHOLDER_SIGNALS)
    def test_each_variant_flagged(self, repo, signal: str) -> None:
        repo(f"| {signal} | `ref.md` | Loads guidance. |")
        hits = vr.find_placeholder_signals()
        assert [(h[0], h[2]) for h in hits] == [(str(Path("agents") / "test-agent.md"), signal)]

    def test_match_is_case_insensitive(self, repo) -> None:
        repo("| Implementation Patterns | `ref.md` | Loads guidance. |")
        assert len(vr.find_placeholder_signals()) == 1

    def test_content_derived_signal_passes(self, repo) -> None:
        repo("| debugging race conditions, memory leaks | `ref.md` | Workflows. |")
        assert vr.find_placeholder_signals() == []

    def test_superset_signal_not_flagged(self, repo) -> None:
        """Match is exact per cell — a signal containing a variant plus more passes."""
        repo("| tests, implementation patterns | `ref.md` | Loads guidance. |")
        assert vr.find_placeholder_signals() == []

    def test_prose_line_ignored(self, repo) -> None:
        f = repo("| real signal | `ref.md` | Why. |")
        f.write_text(
            f.read_text(encoding="utf-8") + "\nUse workflow steps to plan implementation patterns.\n", encoding="utf-8"
        )
        assert vr.find_placeholder_signals() == []


class TestRunCheckPlaceholders:
    def test_hit_returns_one_and_prints(self, repo, capsys: pytest.CaptureFixture) -> None:
        repo("| workflow steps | `ref.md` | Loads guidance. |")
        assert vr.run_check_placeholders(json_output=False) == 1
        out = capsys.readouterr().out
        assert "PLACEHOLDER_SIGNAL: " in out
        assert "1 placeholder signal(s) found" in out

    def test_clean_returns_zero(self, repo, capsys: pytest.CaptureFixture) -> None:
        repo("| real signal | `ref.md` | Why. |")
        assert vr.run_check_placeholders(json_output=False) == 0
        assert "all loading-table signals OK" in capsys.readouterr().out

    def test_json_output(self, repo, capsys: pytest.CaptureFixture) -> None:
        repo("| example-driven tasks | `ref.md` | Loads guidance. |")
        assert vr.run_check_placeholders(json_output=True) == 1
        out = json.loads(capsys.readouterr().out)
        assert out["exit_code"] == 1
        assert out["total"] == 1
        assert out["placeholder_signals"][0]["signal"] == "example-driven tasks"


class TestJsonExitCode:
    def test_orphans_set_exit_code(self) -> None:
        orphan = vr.AGENTS_DIR / "x" / "references" / "orphan.md"
        out = vr.build_json_results([], [orphan], [])
        assert out["exit_code"] == 1

    def test_clean_run_exit_code_zero(self) -> None:
        out = vr.build_json_results([], [], [])
        assert out["exit_code"] == 0
