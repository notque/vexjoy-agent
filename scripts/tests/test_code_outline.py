"""Tests for scripts/code-outline.py."""

from __future__ import annotations

# Import the module under test — the filename has a hyphen so we use importlib
import importlib
import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

_MODULE_NAME = "code_outline"
_spec = importlib.util.spec_from_file_location(
    _MODULE_NAME,
    Path(__file__).resolve().parent.parent / "code-outline.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = _mod  # Register so dataclass resolution works
_spec.loader.exec_module(_mod)

# Re-export for convenience
detect_language = _mod.detect_language
parse_file = _mod.parse_file
format_text_outline = _mod.format_text_outline
outline_to_dict = _mod.outline_to_dict
extract_vb6 = _mod.extract_vb6
extract_python = _mod.extract_python
extract_typescript = _mod.extract_typescript
extract_go = _mod.extract_go
extract_bash = _mod.extract_bash
regex_extract_python = _mod.regex_extract_python
regex_extract_go = _mod.regex_extract_go
regex_extract_typescript = _mod.regex_extract_typescript
regex_extract_generic = _mod.regex_extract_generic
get_parser = _mod.get_parser
collect_files = _mod.collect_files
FileOutline = _mod.FileOutline
FunctionInfo = _mod.FunctionInfo
ClassInfo = _mod.ClassInfo
ImportInfo = _mod.ImportInfo
TREE_SITTER_EXTRACTORS = _mod.TREE_SITTER_EXTRACTORS
EXTENSION_MAP = _mod.EXTENSION_MAP


# ============================================================
# 1. Parse a known Python file and verify function extraction
# ============================================================


class TestPythonExtraction:
    """Test Python tree-sitter extraction."""

    PYTHON_SOURCE = textwrap.dedent("""\
        import os
        from pathlib import Path
        from typing import Optional, List

        class MyClass:
            def __init__(self, name: str) -> None:
                self.name = name

            def greet(self, msg: str = "hello") -> str:
                return f"{self.name}: {msg}"

        def standalone(x: int, y: int = 0) -> int:
            return x + y

        async def async_func(data: bytes) -> None:
            pass
    """)

    def test_python_functions_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(self.PYTHON_SOURCE)
        outline = parse_file(f)

        assert outline.language == "python"
        assert outline.parser == "tree-sitter"

        func_names = [fn.name for fn in outline.functions]
        assert "standalone" in func_names
        assert "async_func" in func_names

    def test_python_function_params(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(self.PYTHON_SOURCE)
        outline = parse_file(f)

        standalone = next(fn for fn in outline.functions if fn.name == "standalone")
        assert "x: int" in standalone.params
        assert standalone.return_type == "int"

    def test_python_async_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(self.PYTHON_SOURCE)
        outline = parse_file(f)

        async_fn = next(fn for fn in outline.functions if fn.name == "async_func")
        assert async_fn.is_async is True

    def test_python_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(self.PYTHON_SOURCE)
        outline = parse_file(f)

        assert len(outline.imports) >= 3
        modules = [imp.module for imp in outline.imports]
        assert "os" in modules
        assert "pathlib" in modules

    def test_python_class_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(self.PYTHON_SOURCE)
        outline = parse_file(f)

        assert len(outline.classes) == 1
        cls = outline.classes[0]
        assert cls.name == "MyClass"
        method_names = [m.name for m in cls.methods]
        assert "__init__" in method_names
        assert "greet" in method_names

    def test_python_line_ranges(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(self.PYTHON_SOURCE)
        outline = parse_file(f)

        cls = outline.classes[0]
        assert cls.line == 5
        assert cls.end_line > cls.line

        standalone = next(fn for fn in outline.functions if fn.name == "standalone")
        assert standalone.line == 12
        assert standalone.end_line >= 13

    def test_python_decorated_function(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            import functools

            @functools.cache
            def cached(x: int) -> int:
                return x * 2
        """)
        f = tmp_path / "deco.py"
        f.write_text(source)
        outline = parse_file(f)

        assert len(outline.functions) == 1
        assert outline.functions[0].name == "cached"


# ============================================================
# 2. Parse TypeScript snippet and verify class/method extraction
# ============================================================


class TestTypeScriptExtraction:
    """Test TypeScript tree-sitter extraction."""

    TS_SOURCE = textwrap.dedent("""\
        import { Request, Response } from "express";
        import * as fs from "fs";

        export class Server {
            private port: number;

            constructor(port: number) {
                this.port = port;
            }

            start(): void {
                console.log(this.port);
            }

            async stop(): Promise<void> {
                return;
            }
        }

        export function handleRequest(req: Request, res: Response): Promise<void> {
            return res.send();
        }

        const arrow = (x: number): number => x + 1;
    """)

    def test_ts_class_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "server.ts"
        f.write_text(self.TS_SOURCE)
        outline = parse_file(f)

        assert outline.language == "typescript"
        assert outline.parser == "tree-sitter"
        assert len(outline.classes) == 1
        cls = outline.classes[0]
        assert cls.name == "Server"

    def test_ts_methods_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "server.ts"
        f.write_text(self.TS_SOURCE)
        outline = parse_file(f)

        cls = outline.classes[0]
        method_names = [m.name for m in cls.methods]
        assert "constructor" in method_names
        assert "start" in method_names
        assert "stop" in method_names

    def test_ts_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "server.ts"
        f.write_text(self.TS_SOURCE)
        outline = parse_file(f)

        assert len(outline.imports) >= 2
        express_imp = next(i for i in outline.imports if i.module == "express")
        assert "Request" in express_imp.names
        assert "Response" in express_imp.names

    def test_ts_exported_function(self, tmp_path: Path) -> None:
        f = tmp_path / "server.ts"
        f.write_text(self.TS_SOURCE)
        outline = parse_file(f)

        handle = next(fn for fn in outline.functions if fn.name == "handleRequest")
        assert handle.exported is True
        assert "req: Request" in handle.params
        assert handle.return_type == "Promise<void>"

    def test_ts_arrow_function(self, tmp_path: Path) -> None:
        f = tmp_path / "server.ts"
        f.write_text(self.TS_SOURCE)
        outline = parse_file(f)

        arrow = next((fn for fn in outline.functions if fn.name == "arrow"), None)
        assert arrow is not None
        assert "x: number" in arrow.params

    def test_javascript_detection(self, tmp_path: Path) -> None:
        f = tmp_path / "app.js"
        f.write_text("function hello() { return 1; }")
        outline = parse_file(f)
        assert outline.language == "javascript"


# ============================================================
# 3. Parse Go snippet and verify interface/struct extraction
# ============================================================


class TestGoExtraction:
    """Test Go tree-sitter extraction."""

    GO_SOURCE = textwrap.dedent("""\
        package main

        import (
            "fmt"
            "net/http"
        )

        type Server struct {
            Port int
            Name string
        }

        func (s *Server) Start() error {
            return nil
        }

        func (s *Server) Stop() {
        }

        type Handler interface {
            Handle(req *http.Request) error
        }

        func NewServer(port int) *Server {
            return &Server{Port: port}
        }
    """)

    def test_go_struct_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text(self.GO_SOURCE)
        outline = parse_file(f)

        assert outline.language == "go"
        assert outline.parser == "tree-sitter"

        struct = next(c for c in outline.classes if c.name == "Server")
        assert struct.kind == "struct"

    def test_go_interface_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text(self.GO_SOURCE)
        outline = parse_file(f)

        iface = next(c for c in outline.classes if c.name == "Handler")
        assert iface.kind == "interface"

    def test_go_methods_attached_to_struct(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text(self.GO_SOURCE)
        outline = parse_file(f)

        server = next(c for c in outline.classes if c.name == "Server")
        method_names = [m.name for m in server.methods]
        assert "Start" in method_names
        assert "Stop" in method_names

    def test_go_function_exported(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text(self.GO_SOURCE)
        outline = parse_file(f)

        new_server = next(fn for fn in outline.functions if fn.name == "NewServer")
        assert new_server.exported is True
        assert "port int" in new_server.params

    def test_go_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text(self.GO_SOURCE)
        outline = parse_file(f)

        modules = [imp.module for imp in outline.imports]
        assert "fmt" in modules
        assert "net/http" in modules


# ============================================================
# 4. Test VB6 regex parser
# ============================================================


class TestVB6Extraction:
    """Test VB6 regex parsing."""

    VB6_SOURCE = textwrap.dedent("""\
        Attribute VB_Name = "MyModule"
        Option Explicit

        Public Sub Initialize(ByVal name As String)
            ' setup code
        End Sub

        Private Function Calculate(ByVal x As Integer, ByVal y As Integer) As Integer
            Calculate = x + y
        End Function

        Public Property Get Name() As String
            Name = mName
        End Property

        Public Property Let Name(ByVal value As String)
            mName = value
        End Property
    """)

    def test_vb6_functions_extracted(self, tmp_path: Path) -> None:
        f = tmp_path / "module.bas"
        f.write_text(self.VB6_SOURCE)
        outline = parse_file(f)

        assert outline.language == "vb6"
        assert outline.parser == "regex"

    def test_vb6_class_name_from_attribute(self) -> None:
        outline = extract_vb6(self.VB6_SOURCE)
        assert len(outline.classes) == 1
        assert outline.classes[0].name == "MyModule"

    def test_vb6_sub_and_function(self) -> None:
        outline = extract_vb6(self.VB6_SOURCE)
        cls = outline.classes[0]
        method_names = [m.name for m in cls.methods]
        assert "Initialize" in method_names
        assert "Calculate" in method_names

    def test_vb6_properties(self) -> None:
        outline = extract_vb6(self.VB6_SOURCE)
        cls = outline.classes[0]
        method_names = [m.name for m in cls.methods]
        assert "Name" in method_names  # Property Get and Let

    def test_vb6_visibility(self) -> None:
        outline = extract_vb6(self.VB6_SOURCE)
        cls = outline.classes[0]
        init = next(m for m in cls.methods if m.name == "Initialize")
        assert init.exported is True  # Public

        calc = next(m for m in cls.methods if m.name == "Calculate")
        assert calc.exported is False  # Private

    def test_vb6_line_ranges(self) -> None:
        outline = extract_vb6(self.VB6_SOURCE)
        cls = outline.classes[0]
        init = next(m for m in cls.methods if m.name == "Initialize")
        assert init.line == 4
        assert init.end_line == 6

    def test_vb6_cls_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "MyClass.cls"
        f.write_text(self.VB6_SOURCE)
        outline = parse_file(f)
        assert outline.language == "vb6"

    def test_vb6_frm_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "Form1.frm"
        f.write_text(self.VB6_SOURCE)
        outline = parse_file(f)
        assert outline.language == "vb6"


# ============================================================
# 5. Test language detection from file extensions
# ============================================================


class TestLanguageDetection:
    """Test detect_language for all supported extensions."""

    @pytest.mark.parametrize(
        "ext,expected",
        [
            (".go", "go"),
            (".py", "python"),
            (".ts", "typescript"),
            (".tsx", "typescript"),
            (".js", "javascript"),
            (".jsx", "javascript"),
            (".php", "php"),
            (".kt", "kotlin"),
            (".kts", "kotlin"),
            (".swift", "swift"),
            (".sh", "bash"),
            (".bash", "bash"),
            (".bas", "vb6"),
            (".cls", "vb6"),
            (".frm", "vb6"),
        ],
    )
    def test_extension_mapping(self, ext: str, expected: str) -> None:
        assert detect_language(Path(f"test{ext}")) == expected

    def test_unknown_extension(self) -> None:
        assert detect_language(Path("test.rb")) is None
        assert detect_language(Path("test.rs")) is None
        assert detect_language(Path("test")) is None

    def test_case_insensitive(self) -> None:
        assert detect_language(Path("test.PY")) == "python"
        assert detect_language(Path("test.Go")) == "go"


# ============================================================
# 6. Test --format outline text output
# ============================================================


class TestTextOutlineFormat:
    """Test format_text_outline output."""

    def test_basic_outline_format(self) -> None:
        outline = FileOutline(
            file="src/server.ts",
            language="typescript",
            parser="tree-sitter",
            imports=[ImportInfo(module="express", names=["Request", "Response"], line=1)],
            functions=[
                FunctionInfo(
                    name="handleRequest",
                    line=42,
                    end_line=87,
                    params="req: Request, res: Response",
                    return_type="Promise<void>",
                    exported=True,
                )
            ],
            classes=[
                ClassInfo(
                    name="Server",
                    line=10,
                    end_line=200,
                    methods=[
                        FunctionInfo(name="start", line=15, end_line=30, params="port: number"),
                        FunctionInfo(name="stop", line=31, end_line=45),
                    ],
                )
            ],
        )

        text = format_text_outline(outline)
        lines = text.split("\n")

        assert lines[0] == "src/server.ts (typescript, tree-sitter)"
        assert "import express {Request, Response}" in lines[1]
        assert "[L1]" in lines[1]
        assert "class Server" in lines[2]
        assert "[L10-200]" in lines[2]
        assert ".start(port: number)" in lines[3]
        assert ".stop()" in lines[4]
        assert "export function handleRequest" in text
        assert "Promise<void>" in text

    def test_outline_with_async(self) -> None:
        outline = FileOutline(
            file="test.py",
            language="python",
            parser="tree-sitter",
            functions=[
                FunctionInfo(name="fetch", line=1, end_line=5, is_async=True),
            ],
        )
        text = format_text_outline(outline)
        assert "async function fetch" in text


# ============================================================
# 7. Test fallback when grammar is missing (mock the import)
# ============================================================


class TestFallbackBehavior:
    """Test regex fallback when tree-sitter grammars are unavailable."""

    def test_python_regex_fallback(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            import os
            from pathlib import Path

            def hello(name: str) -> str:
                return f"hello {name}"

            class Greeter:
                pass
        """)

        # Test regex extractor directly
        outline = regex_extract_python(source)
        assert outline.parser == "regex"

        func_names = [fn.name for fn in outline.functions]
        assert "hello" in func_names

        class_names = [cls.name for cls in outline.classes]
        assert "Greeter" in class_names

        modules = [imp.module for imp in outline.imports]
        assert "os" in modules
        assert "pathlib" in modules

    def test_go_regex_fallback(self) -> None:
        source = textwrap.dedent("""\
            package main

            func NewServer(port int) *Server {
                return &Server{}
            }

            type Server struct {
            }
        """)

        outline = regex_extract_go(source)
        assert outline.parser == "regex"
        assert any(fn.name == "NewServer" for fn in outline.functions)
        assert any(cls.name == "Server" for cls in outline.classes)

    def test_typescript_regex_fallback(self) -> None:
        source = textwrap.dedent("""\
            import { Foo } from "bar";

            export function hello(x: number): string {
                return "hello";
            }

            class Widget {
            }
        """)

        outline = regex_extract_typescript(source)
        assert outline.parser == "regex"
        assert any(fn.name == "hello" for fn in outline.functions)
        assert any(cls.name == "Widget" for cls in outline.classes)
        assert any(imp.module == "bar" for imp in outline.imports)

    def test_generic_regex_fallback(self) -> None:
        source = textwrap.dedent("""\
            public func doStuff() {
            }

            class MyClass {
            }
        """)

        outline = regex_extract_generic(source, "unknown")
        assert outline.parser == "regex"
        assert any(fn.name == "doStuff" for fn in outline.functions)
        assert any(cls.name == "MyClass" for cls in outline.classes)

    def test_fallback_when_treesitter_import_fails(self, tmp_path: Path) -> None:
        """Simulate tree-sitter grammar import failure."""
        f = tmp_path / "test.py"
        f.write_text("def hello(): pass\n")

        # Mock get_parser to return None (simulating missing grammar)
        with patch.object(_mod, "get_parser", return_value=None):
            outline = parse_file(f)
            assert outline.parser == "regex"
            assert outline.language == "python"


# ============================================================
# 8. Test --recursive on a directory with mixed languages
# ============================================================


class TestRecursiveDirectory:
    """Test recursive directory scanning."""

    def test_recursive_finds_nested_files(self, tmp_path: Path) -> None:
        # Create a directory tree
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib").mkdir()

        (tmp_path / "main.py").write_text("def main(): pass\n")
        (tmp_path / "src" / "server.ts").write_text("function serve() {}\n")
        (tmp_path / "src" / "lib" / "util.go").write_text("package lib\nfunc Util() {}\n")

        files = collect_files(tmp_path, recursive=True)
        extensions = {f.suffix for f in files}
        assert ".py" in extensions
        assert ".ts" in extensions
        assert ".go" in extensions

    def test_non_recursive_only_top_level(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "top.py").write_text("def top(): pass\n")
        (tmp_path / "sub" / "nested.py").write_text("def nested(): pass\n")

        files = collect_files(tmp_path, recursive=False)
        assert len(files) == 1
        assert files[0].name == "top.py"

    def test_single_file_input(self, tmp_path: Path) -> None:
        f = tmp_path / "single.py"
        f.write_text("x = 1\n")
        files = collect_files(f, recursive=False)
        assert len(files) == 1
        assert files[0] == f

    def test_cli_recursive_json(self, tmp_path: Path) -> None:
        """Test CLI with --recursive produces JSON array."""
        (tmp_path / "a.py").write_text("def a(): pass\n")
        (tmp_path / "b.py").write_text("def b(): pass\n")

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent.parent / "code-outline.py"),
                str(tmp_path),
                "-r",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2


# ============================================================
# 9. Test empty file handling
# ============================================================


class TestEmptyFile:
    """Test handling of empty files."""

    def test_empty_python_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        outline = parse_file(f)
        assert outline.language == "python"
        assert len(outline.functions) == 0
        assert len(outline.classes) == 0
        assert len(outline.imports) == 0

    def test_empty_go_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.go"
        f.write_text("")
        outline = parse_file(f)
        assert outline.language == "go"
        assert len(outline.functions) == 0

    def test_empty_ts_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.ts"
        f.write_text("")
        outline = parse_file(f)
        assert outline.language == "typescript"
        assert len(outline.functions) == 0

    def test_empty_vb6_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.bas"
        f.write_text("")
        outline = parse_file(f)
        assert outline.language == "vb6"
        assert len(outline.functions) == 0


# ============================================================
# 10. Test malformed file handling (should not crash)
# ============================================================


class TestMalformedFiles:
    """Test that malformed files don't crash the parser."""

    def test_malformed_python(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def (\n  class\n  if if if\n")
        # Should not raise
        outline = parse_file(f)
        assert outline.language == "python"

    def test_malformed_typescript(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.ts"
        f.write_text("function { { { export class\n")
        outline = parse_file(f)
        assert outline.language == "typescript"

    def test_malformed_go(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.go"
        f.write_text("package\nfunc {\ntype\n")
        outline = parse_file(f)
        assert outline.language == "go"

    def test_binary_content(self, tmp_path: Path) -> None:
        f = tmp_path / "binary.py"
        f.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")
        # Should handle gracefully (errors='replace' in read)
        outline = parse_file(f)
        assert outline.language == "python"

    def test_unknown_extension_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "test.rb"
        f.write_text("def hello; end")
        with pytest.raises(ValueError, match="Cannot detect language"):
            parse_file(f)

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises(OSError):
            parse_file(Path("/nonexistent/file.py"))


# ============================================================
# Additional tests: JSON serialization, CLI integration
# ============================================================


class TestJSONSerialization:
    """Test outline_to_dict produces valid JSON structure."""

    def test_outline_to_dict_structure(self) -> None:
        outline = FileOutline(
            file="test.py",
            language="python",
            parser="tree-sitter",
            imports=[ImportInfo(module="os", line=1)],
            functions=[FunctionInfo(name="main", line=1, end_line=5, params="", return_type="None")],
            classes=[
                ClassInfo(
                    name="Foo",
                    line=10,
                    end_line=20,
                    methods=[FunctionInfo(name="bar", line=12, end_line=15)],
                )
            ],
        )

        d = outline_to_dict(outline)
        assert d["file"] == "test.py"
        assert d["language"] == "python"
        assert d["parser"] == "tree-sitter"
        assert len(d["imports"]) == 1
        assert len(d["functions"]) == 1
        assert len(d["classes"]) == 1
        assert len(d["classes"][0]["methods"]) == 1

        # Verify it's JSON-serializable
        json_str = json.dumps(d)
        assert json_str  # No exception

    def test_empty_sections_omitted(self) -> None:
        outline = FileOutline(file="test.py", language="python", parser="tree-sitter")
        d = outline_to_dict(outline)
        assert "imports" not in d
        assert "functions" not in d
        assert "classes" not in d


class TestCLIIntegration:
    """Test CLI invocation via subprocess."""

    def test_cli_json_output(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("def hello(): pass\n")

        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "code-outline.py"), str(f)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["language"] == "python"
        assert any(fn["name"] == "hello" for fn in data.get("functions", []))

    def test_cli_outline_output(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("def hello(): pass\n")

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent.parent / "code-outline.py"),
                str(f),
                "--format",
                "outline",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "function hello" in result.stdout
        assert "(python, tree-sitter)" in result.stdout

    def test_cli_nonexistent_path(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "code-outline.py"), "/nonexistent/path.py"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_cli_no_supported_files(self, tmp_path: Path) -> None:
        # Directory with no supported files
        (tmp_path / "readme.txt").write_text("hello")

        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "code-outline.py"), str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1


# ============================================================
# Additional language tests
# ============================================================


class TestPHPExtraction:
    """Test PHP tree-sitter extraction."""

    def test_php_function(self, tmp_path: Path) -> None:
        source = "<?php\nfunction hello(string $name): string {\n    return $name;\n}\n"
        f = tmp_path / "test.php"
        f.write_text(source)
        outline = parse_file(f)
        assert outline.language == "php"
        assert any(fn.name == "hello" for fn in outline.functions)

    def test_php_class(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            <?php
            class UserController {
                public function index(): void {
                }

                public function show(int $id): void {
                }
            }
        """)
        f = tmp_path / "controller.php"
        f.write_text(source)
        outline = parse_file(f)
        assert len(outline.classes) == 1
        assert outline.classes[0].name == "UserController"
        method_names = [m.name for m in outline.classes[0].methods]
        assert "index" in method_names
        assert "show" in method_names


class TestBashExtraction:
    """Test Bash tree-sitter extraction."""

    def test_bash_functions(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            #!/bin/bash

            setup() {
                echo "setting up"
            }

            teardown() {
                echo "tearing down"
            }
        """)
        f = tmp_path / "script.sh"
        f.write_text(source)
        outline = parse_file(f)

        assert outline.language == "bash"
        func_names = [fn.name for fn in outline.functions]
        assert "setup" in func_names
        assert "teardown" in func_names


class TestKotlinExtraction:
    """Test Kotlin tree-sitter extraction."""

    def test_kotlin_function(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            fun greet(name: String): String {
                return "Hello, $name"
            }
        """)
        f = tmp_path / "main.kt"
        f.write_text(source)
        outline = parse_file(f)

        assert outline.language == "kotlin"
        assert any(fn.name == "greet" for fn in outline.functions)

    def test_kotlin_class(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            class Server {
                fun start() {
                }
                fun stop() {
                }
            }
        """)
        f = tmp_path / "server.kt"
        f.write_text(source)
        outline = parse_file(f)

        assert len(outline.classes) == 1
        assert outline.classes[0].name == "Server"
        method_names = [m.name for m in outline.classes[0].methods]
        assert "start" in method_names
        assert "stop" in method_names


class TestSwiftExtraction:
    """Test Swift tree-sitter extraction."""

    def test_swift_function(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""\
            import Foundation

            func greet(name: String) -> String {
                return "Hello, \\(name)"
            }
        """)
        f = tmp_path / "main.swift"
        f.write_text(source)
        outline = parse_file(f)

        assert outline.language == "swift"
        assert any(fn.name == "greet" for fn in outline.functions)
        assert any(imp.module == "Foundation" for imp in outline.imports)
