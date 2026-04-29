"""Tests for diff-to-functions.py script.

Tests cover:
- Git diff parsing and line number extraction
- Function boundary detection (Python, Go, TypeScript, VB6)
- Line-to-function mapping
- Summary format output
- Edge cases: module-level changes, unparseable files
- Subprocess mocking for deterministic testing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts dir to path for import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use importlib since filename has hyphens
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "diff_to_functions",
    Path(__file__).parent.parent / "diff-to-functions.py",
)
_module = importlib.util.module_from_spec(_spec)
sys.modules["diff_to_functions"] = _module
_spec.loader.exec_module(_module)

# Import the module's public interface
parse_diff_output = _module.parse_diff_output
find_functions_regex = _module.find_functions_regex
map_lines_to_functions = _module.map_lines_to_functions
detect_language = _module.detect_language
format_summary = _module.format_summary
build_output = _module.build_output
run = _module.run
ChangedFunction = _module.ChangedFunction
UnparseableFile = _module.UnparseableFile
FunctionInfo = _module.FunctionInfo


# ============================================================
# Fixtures: sample diff outputs
# ============================================================

SAMPLE_DIFF_PYTHON = """\
diff --git a/src/utils.py b/src/utils.py
index abc1234..def5678 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -10,0 +11,3 @@ def parse_config(path):
+    # Added validation
+    if not path.exists():
+        raise FileNotFoundError(path)
@@ -25 +28 @@ def parse_config(path):
-    return config
+    return validated_config
"""

SAMPLE_DIFF_MULTI_FILE = """\
diff --git a/src/server.ts b/src/server.ts
index abc1234..def5678 100644
--- a/src/server.ts
+++ b/src/server.ts
@@ -55,0 +55,3 @@
+    // new middleware
+    app.use(cors());
+    app.use(helmet());
@@ -62 +65 @@
-    res.send("ok");
+    res.json({ status: "ok" });
diff --git a/config.json b/config.json
index abc1234..def5678 100644
--- a/config.json
+++ b/config.json
@@ -3,2 +3,3 @@
-  "port": 3000,
-  "host": "localhost"
+  "port": 8080,
+  "host": "0.0.0.0",
+  "debug": true
"""

SAMPLE_DIFF_DELETION = """\
diff --git a/old.py b/old.py
deleted file mode 100644
index abc1234..0000000
--- a/old.py
+++ /dev/null
@@ -1,10 +0,0 @@
-def old_function():
-    pass
"""

SAMPLE_PYTHON_SOURCE = """\
import os
from pathlib import Path


def parse_config(path):
    \"\"\"Parse configuration file.\"\"\"
    with open(path) as f:
        config = json.load(f)
    # Added validation
    if not path.exists():
        raise FileNotFoundError(path)
    return validated_config


def validate(data):
    \"\"\"Validate data structure.\"\"\"
    if not isinstance(data, dict):
        raise TypeError("Expected dict")
    return True


class ConfigManager:
    def __init__(self, base_path):
        self.base_path = base_path

    def load(self, name):
        path = self.base_path / name
        return parse_config(path)

    def save(self, name, data):
        path = self.base_path / name
        with open(path, "w") as f:
            json.dump(data, f)
"""

SAMPLE_GO_SOURCE = """\
package main

import "fmt"

func main() {
    fmt.Println("hello")
    server := NewServer()
    server.Start()
}

func NewServer() *Server {
    return &Server{
        port: 8080,
    }
}

func (s *Server) Start() error {
    fmt.Printf("Starting on port %d\\n", s.port)
    return s.listen()
}

func (s *Server) Stop() {
    s.shutdown()
}
"""

SAMPLE_VB6_SOURCE = """\
Option Explicit

Private Sub Form_Load()
    Dim x As Integer
    x = 10
    Call InitializeApp
End Sub

Public Function CalculateTotal(ByVal price As Double, ByVal qty As Integer) As Double
    Dim total As Double
    total = price * qty
    CalculateTotal = total
End Function

Private Sub CleanUp()
    Set objConn = Nothing
End Sub
"""

SAMPLE_TS_SOURCE = """\
import { Request, Response } from 'express';

export function handleRequest(req: Request, res: Response): Promise<void> {
    const data = req.body;
    // new middleware
    app.use(cors());
    app.use(helmet());
    return processData(data);
}

export class Server {
    private port: number;

    constructor(port: number) {
        this.port = port;
    }

    async start(): Promise<void> {
        console.log(`Starting on ${this.port}`);
        await this.listen();
    }

    stop(): void {
        this.cleanup();
    }
}
"""


# ============================================================
# Tests: Diff Parsing
# ============================================================


class TestParseDiffOutput:
    """Tests for parse_diff_output function."""

    def test_parses_python_diff_lines(self):
        """Parse a Python diff and extract correct line numbers."""
        result = parse_diff_output(SAMPLE_DIFF_PYTHON)

        assert "src/utils.py" in result
        lines = result["src/utils.py"]
        # First hunk: +11,3 -> lines 11, 12, 13
        assert 11 in lines
        assert 12 in lines
        assert 13 in lines
        # Second hunk: +28 (single line change)
        assert 28 in lines

    def test_parses_multi_file_diff(self):
        """Parse a diff with multiple files."""
        result = parse_diff_output(SAMPLE_DIFF_MULTI_FILE)

        assert "src/server.ts" in result
        assert "config.json" in result
        # server.ts: +55,3 and +65,1
        ts_lines = result["src/server.ts"]
        assert 55 in ts_lines
        assert 56 in ts_lines
        assert 57 in ts_lines
        assert 65 in ts_lines
        # config.json: +3,3
        json_lines = result["config.json"]
        assert 3 in json_lines
        assert 4 in json_lines
        assert 5 in json_lines

    def test_handles_deleted_file(self):
        """Deleted files (going to /dev/null) should not produce entries."""
        result = parse_diff_output(SAMPLE_DIFF_DELETION)
        # /dev/null means file was deleted; should not appear
        assert "old.py" not in result

    def test_empty_diff_returns_empty_dict(self):
        """Empty diff input produces empty result."""
        result = parse_diff_output("")
        assert result == {}

    def test_pure_deletion_hunk_produces_no_lines(self):
        """A hunk with +N,0 (pure deletion) should not produce lines."""
        diff = """\
diff --git a/foo.py b/foo.py
index abc..def 100644
--- a/foo.py
+++ b/foo.py
@@ -5,3 +5,0 @@
-removed line 1
-removed line 2
-removed line 3
"""
        result = parse_diff_output(diff)
        assert result.get("foo.py", []) == []


# ============================================================
# Tests: Function Detection (Regex Fallback)
# ============================================================


class TestFindFunctionsRegex:
    """Tests for regex-based function boundary detection."""

    def test_python_functions(self):
        """Detect Python function definitions with correct boundaries."""
        functions = find_functions_regex(SAMPLE_PYTHON_SOURCE, "python")

        names = [f.name for f in functions]
        assert "parse_config" in names
        assert "validate" in names
        assert "__init__" in names
        assert "load" in names
        assert "save" in names

    def test_python_function_line_ranges(self):
        """Python function line ranges are accurate."""
        functions = find_functions_regex(SAMPLE_PYTHON_SOURCE, "python")

        parse_config = next(f for f in functions if f.name == "parse_config")
        # parse_config starts at line 5
        assert parse_config.line == 5
        # Should end after the return statement
        assert parse_config.end_line >= 12

    def test_go_functions(self):
        """Detect Go function and method declarations."""
        functions = find_functions_regex(SAMPLE_GO_SOURCE, "go")

        names = [f.name for f in functions]
        assert "main" in names
        assert "NewServer" in names
        assert "Start" in names
        assert "Stop" in names

    def test_go_function_boundaries(self):
        """Go function boundaries are accurate using brace counting."""
        functions = find_functions_regex(SAMPLE_GO_SOURCE, "go")

        main_func = next(f for f in functions if f.name == "main")
        assert main_func.line == 5
        assert main_func.end_line == 9

    def test_vb6_functions(self):
        """Detect VB6 Sub and Function definitions."""
        functions = find_functions_regex(SAMPLE_VB6_SOURCE, "vb6")

        names = [f.name for f in functions]
        assert "Form_Load" in names
        assert "CalculateTotal" in names
        assert "CleanUp" in names

    def test_vb6_function_end_detection(self):
        """VB6 functions end at 'End Sub' or 'End Function'."""
        functions = find_functions_regex(SAMPLE_VB6_SOURCE, "vb6")

        form_load = next(f for f in functions if f.name == "Form_Load")
        # Should end at "End Sub" line
        assert form_load.end_line == 7

        calc = next(f for f in functions if f.name == "CalculateTotal")
        assert calc.end_line == 13

    def test_typescript_functions(self):
        """Detect TypeScript function and method declarations."""
        functions = find_functions_regex(SAMPLE_TS_SOURCE, "typescript")

        names = [f.name for f in functions]
        assert "handleRequest" in names

    def test_unknown_language_returns_empty(self):
        """Unknown language returns no functions."""
        functions = find_functions_regex("some code", "unknown_lang")
        assert functions == []


# ============================================================
# Tests: Line-to-Function Mapping
# ============================================================


class TestMapLinesToFunctions:
    """Tests for mapping changed lines to containing functions."""

    def test_maps_lines_to_correct_function(self):
        """Changed lines are mapped to their containing function."""
        functions = [
            FunctionInfo(name="func_a", line=5, end_line=15),
            FunctionInfo(name="func_b", line=20, end_line=30),
        ]
        changed_lines = [7, 8, 22, 25]

        result = map_lines_to_functions(functions, changed_lines)

        assert 0 in result  # func_a
        assert 1 in result  # func_b
        assert result[0] == [7, 8]
        assert result[1] == [22, 25]

    def test_lines_outside_functions_not_mapped(self):
        """Lines outside any function are not in the result."""
        functions = [
            FunctionInfo(name="func_a", line=10, end_line=20),
        ]
        changed_lines = [1, 2, 3, 25]

        result = map_lines_to_functions(functions, changed_lines)

        assert result == {}

    def test_line_on_function_boundary_is_included(self):
        """Lines exactly on start/end boundaries are included."""
        functions = [
            FunctionInfo(name="func_a", line=10, end_line=20),
        ]
        changed_lines = [10, 20]

        result = map_lines_to_functions(functions, changed_lines)

        assert 0 in result
        assert result[0] == [10, 20]

    def test_empty_changed_lines(self):
        """No changed lines produces empty mapping."""
        functions = [
            FunctionInfo(name="func_a", line=10, end_line=20),
        ]

        result = map_lines_to_functions(functions, [])
        assert result == {}


# ============================================================
# Tests: Language Detection
# ============================================================


class TestDetectLanguage:
    """Tests for file extension language detection."""

    @pytest.mark.parametrize(
        "filepath,expected",
        [
            ("src/main.py", "python"),
            ("pkg/server.go", "go"),
            ("src/app.ts", "typescript"),
            ("src/app.tsx", "typescript"),
            ("lib/utils.js", "javascript"),
            ("lib/comp.jsx", "javascript"),
            ("src/Handler.php", "php"),
            ("src/Main.kt", "kotlin"),
            ("Sources/App.swift", "swift"),
            ("scripts/deploy.sh", "bash"),
            ("Module1.bas", "vb6"),
            ("Form1.frm", "vb6"),
            ("Class1.cls", "vb6"),
            ("config.json", None),
            ("README.md", None),
            ("Makefile", None),
        ],
    )
    def test_language_detection(self, filepath: str, expected: str | None):
        """Language is correctly detected from file extension."""
        assert detect_language(filepath) == expected


# ============================================================
# Tests: Summary Format
# ============================================================


class TestFormatSummary:
    """Tests for compact text summary output."""

    def test_summary_format_structure(self):
        """Summary output has correct structure with file grouping."""
        changed_functions = [
            ChangedFunction(
                file="src/server.ts",
                language="typescript",
                function="handleRequest",
                class_name=None,
                line=42,
                end_line=87,
                params="req: Request, res: Response",
                source="...",
                diff_lines=[55, 56, 57, 62],
            ),
            ChangedFunction(
                file="src/server.ts",
                language="typescript",
                function="stop",
                class_name="Server",
                line=31,
                end_line=45,
                params="",
                source="...",
                diff_lines=[35, 36],
            ),
            ChangedFunction(
                file="src/utils.py",
                language="python",
                function="parse_config",
                class_name=None,
                line=10,
                end_line=25,
                params="path",
                source="...",
                diff_lines=[15],
            ),
        ]
        unparseable = [
            UnparseableFile(file="config.json", reason="no parseable functions", changed_line_count=3),
        ]

        result = format_summary(changed_functions, unparseable, ref="main", staged=False)

        assert "Changed functions (diff against main):" in result
        assert "src/server.ts:" in result
        assert "handleRequest(req: Request, res: Response)" in result
        assert "4 lines changed" in result
        assert "Server.stop()" in result
        assert "2 lines changed" in result
        assert "src/utils.py:" in result
        assert "parse_config(path)" in result
        assert "1 line" in result  # "1 lines changed"
        assert "config.json" in result
        assert "no parseable functions" in result

    def test_summary_with_no_changes(self):
        """Summary with empty lists still has header."""
        result = format_summary([], [], ref=None, staged=True)
        assert "diff against staged" in result


# ============================================================
# Tests: Module-Level Changes
# ============================================================


class TestModuleLevelChanges:
    """Tests for changes outside any function."""

    def test_changes_outside_functions_reported(self):
        """Changes in module-level code are reported as unparseable."""
        source = """\
import os
import sys

CONSTANT = 42

def my_func():
    return CONSTANT
"""
        functions = find_functions_regex(source, "python")
        # Change is at line 4 (CONSTANT = 42), outside any function
        changed_lines = [4]
        line_map = map_lines_to_functions(functions, changed_lines)

        # No function contains line 4
        assert line_map == {}


# ============================================================
# Tests: Unparseable Files
# ============================================================


class TestUnparseableFiles:
    """Tests for files that cannot have functions extracted."""

    def test_json_file_is_unparseable(self):
        """JSON files have no parseable functions."""
        language = detect_language("config.json")
        assert language is None

    def test_markdown_file_is_unparseable(self):
        """Markdown files have no parseable functions."""
        language = detect_language("README.md")
        assert language is None


# ============================================================
# Tests: End-to-End with Mocked Git
# ============================================================


class TestRunWithMockedGit:
    """Integration tests using mocked subprocess calls."""

    @patch("subprocess.run")
    def test_run_with_ref(self, mock_run):
        """Run with --ref produces JSON output."""
        # Mock git diff output
        mock_run.return_value = type(
            "Result",
            (),
            {
                "stdout": SAMPLE_DIFF_PYTHON,
                "stderr": "",
                "returncode": 0,
            },
        )()

        # Mock file reading by patching read_file_content
        with (
            patch.object(_module, "read_file_content", return_value=SAMPLE_PYTHON_SOURCE),
            patch("builtins.print") as mock_print,
        ):
            exit_code = run(ref="main", output_format="json")

        assert exit_code == 0
        # Verify JSON was printed
        printed = mock_print.call_args[0][0]
        output = json.loads(printed)
        assert output["ref"] == "main"
        assert len(output["changed_functions"]) > 0
        assert output["changed_functions"][0]["function"] == "parse_config"

    @patch("subprocess.run")
    def test_run_no_changes(self, mock_run):
        """Run with no diff output returns exit code 1."""
        mock_run.return_value = type(
            "Result",
            (),
            {
                "stdout": "",
                "stderr": "",
                "returncode": 0,
            },
        )()

        with patch("builtins.print"):
            exit_code = run(ref="main", output_format="json")

        assert exit_code == 1

    @patch("subprocess.run")
    def test_run_summary_format(self, mock_run):
        """Run with --format summary produces text output."""
        mock_run.return_value = type(
            "Result",
            (),
            {
                "stdout": SAMPLE_DIFF_PYTHON,
                "stderr": "",
                "returncode": 0,
            },
        )()

        with (
            patch.object(_module, "read_file_content", return_value=SAMPLE_PYTHON_SOURCE),
            patch("builtins.print") as mock_print,
        ):
            exit_code = run(ref="main", output_format="summary")

        assert exit_code == 0
        printed = mock_print.call_args[0][0]
        assert "Changed functions" in printed
        assert "parse_config" in printed

    @patch("subprocess.run")
    def test_run_with_unparseable_file(self, mock_run):
        """Files without language detection go to unparseable list."""
        diff_with_json = """\
diff --git a/config.json b/config.json
index abc..def 100644
--- a/config.json
+++ b/config.json
@@ -1,2 +1,3 @@
+{"new": true}
"""
        mock_run.return_value = type(
            "Result",
            (),
            {
                "stdout": diff_with_json,
                "stderr": "",
                "returncode": 0,
            },
        )()

        with patch("builtins.print") as mock_print:
            exit_code = run(ref="main", output_format="json")

        assert exit_code == 0
        printed = mock_print.call_args[0][0]
        output = json.loads(printed)
        assert len(output["changed_files_without_functions"]) == 1
        assert output["changed_files_without_functions"][0]["file"] == "config.json"


# ============================================================
# Tests: Build Output Structure
# ============================================================


class TestBuildOutput:
    """Tests for JSON output structure building."""

    def test_output_has_required_fields(self):
        """Output dict has all required top-level fields."""
        output = build_output([], [], ref="main", staged=False)

        assert "ref" in output
        assert "changed_functions" in output
        assert "changed_files_without_functions" in output
        assert output["ref"] == "main"

    def test_output_function_fields(self):
        """Each changed function has all required fields."""
        cf = ChangedFunction(
            file="test.py",
            language="python",
            function="my_func",
            class_name="MyClass",
            line=10,
            end_line=20,
            params="x: int, y: int",
            source="def my_func(x: int, y: int):\n    pass",
            diff_lines=[15, 16],
        )
        output = build_output([cf], [], ref=None, staged=True)

        func = output["changed_functions"][0]
        assert func["file"] == "test.py"
        assert func["language"] == "python"
        assert func["function"] == "my_func"
        assert func["class"] == "MyClass"
        assert func["line"] == 10
        assert func["end_line"] == 20
        assert func["params"] == "x: int, y: int"
        assert "def my_func" in func["source"]
        assert func["diff_lines"] == [15, 16]
