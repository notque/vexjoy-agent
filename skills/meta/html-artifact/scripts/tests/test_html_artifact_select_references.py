"""Tests for select-references.py — deterministic reference file selector."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "select-references.py")

# --- Import module directly for unit tests ---
sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib import import_module

select_mod = import_module("select-references")
select_references = select_mod.select_references


class TestSelectReferencesDirect:
    """Unit tests calling select_references() directly."""

    @pytest.mark.parametrize(
        "shape,expected_specific",
        [
            ("spec", "references/shape-spec-exploration.md"),
            ("code-review", "references/shape-code-review.md"),
            ("prototype", "references/shape-design-prototype.md"),
            ("report", "references/shape-report-research.md"),
            ("editor", "references/shape-custom-editor.md"),
            ("data-viz", "references/shape-data-visualization.md"),
        ],
    )
    def test_each_shape_returns_correct_specific(self, shape: str, expected_specific: str) -> None:
        result = select_references(shape)
        assert result["shape"] == shape
        assert result["shape_specific"] == [expected_specific]

    def test_always_load_present(self) -> None:
        result = select_references("spec")
        assert result["always_load"] == [
            "references/design-system.md",
            "references/interaction-patterns.md",
        ]

    def test_all_files_is_union(self) -> None:
        result = select_references("report")
        assert result["all_files"] == result["always_load"] + result["shape_specific"]

    def test_invalid_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid shape"):
            select_references("invalid")

    def test_deterministic_same_input_same_output(self) -> None:
        results = [select_references("data-viz") for _ in range(5)]
        assert all(r == results[0] for r in results)


@pytest.mark.slow
class TestCLIInterface:
    """Integration tests via subprocess."""

    def test_cli_valid_shape(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "spec"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result["shape"] == "spec"
        assert len(result["all_files"]) == 3

    def test_cli_invalid_shape_exits_1(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "banana"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1

    def test_cli_compact_json(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "editor", "--json-compact"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        output = proc.stdout.strip()
        assert "\n" not in output.rstrip("\n")
        parsed = json.loads(output)
        assert parsed["shape"] == "editor"

    @pytest.mark.parametrize("shape", ["spec", "code-review", "prototype", "report", "editor", "data-viz"])
    def test_cli_all_shapes_succeed(self, shape: str) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", shape]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result["shape"] == shape
