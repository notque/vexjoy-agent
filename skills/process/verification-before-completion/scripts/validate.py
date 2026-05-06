#!/usr/bin/env python3
"""
Automated validation script for verification-before-completion skill.
Performs comprehensive checks on changed files before declaring completion.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple


class ValidationError(Exception):
    """Custom exception for validation failures."""

    pass


class FileValidator:
    """Validates individual files for syntax and common issues."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = []

    def log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"  {message}", file=sys.stderr)

    def validate_python_file(self, file_path: Path) -> Tuple[bool, str]:
        """Validate Python file syntax and common issues."""
        self.log(f"Validating Python file: {file_path}")

        # Check file exists
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Syntax check with py_compile
        try:
            import py_compile

            py_compile.compile(str(file_path), doraise=True)
            self.log("✓ Syntax valid")
        except py_compile.PyCompileError as e:
            return False, f"Syntax error: {e}"

        # Check for common issues
        content = file_path.read_text()

        issues = []

        # Check for debug statements
        if "print(" in content and "def print" not in content:
            # Count print statements (excluding function definitions)
            print_count = content.count("print(")
            if print_count > 0:
                issues.append(f"Found {print_count} print() statements (consider using logging)")

        # Check for TODO/FIXME
        if "TODO" in content or "FIXME" in content:
            todo_count = content.count("TODO") + content.count("FIXME")
            issues.append(f"Found {todo_count} TODO/FIXME comments")

        # Check for common dangerous patterns
        if "eval(" in content:
            issues.append("Found eval() usage (security risk)")
        if "exec(" in content:
            issues.append("Found exec() usage (security risk)")

        # Check imports
        try:
            import ast

            tree = ast.parse(content)
            import_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
            self.log(f"✓ Found {import_count} import statements")
        except SyntaxError as e:
            return False, f"AST parse error: {e}"

        if issues:
            return True, f"Syntax valid but warnings: {'; '.join(issues)}"

        return True, "Python file validation passed"

    def validate_javascript_file(self, file_path: Path) -> Tuple[bool, str]:
        """Validate JavaScript file syntax."""
        self.log(f"Validating JavaScript file: {file_path}")

        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Try to use node to check syntax
        try:
            result = subprocess.run(
                ["node", "-c", str(file_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False, f"Syntax error: {result.stderr}"
            self.log("✓ Syntax valid")
        except FileNotFoundError:
            self.log("⚠ node not found, skipping syntax check")
        except subprocess.TimeoutExpired:
            return False, "Syntax check timeout"

        # Check for common issues
        content = file_path.read_text()
        issues = []

        if "console.log(" in content:
            console_count = content.count("console.log(")
            issues.append(f"Found {console_count} console.log() statements")

        if "debugger;" in content:
            issues.append("Found debugger statement")

        if "TODO" in content or "FIXME" in content:
            todo_count = content.count("TODO") + content.count("FIXME")
            issues.append(f"Found {todo_count} TODO/FIXME comments")

        if issues:
            return True, f"Syntax valid but warnings: {'; '.join(issues)}"

        return True, "JavaScript file validation passed"

    def validate_go_file(self, file_path: Path) -> Tuple[bool, str]:
        """Validate Go file syntax."""
        self.log(f"Validating Go file: {file_path}")

        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Check with gofmt
        try:
            result = subprocess.run(
                ["gofmt", "-e", str(file_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stderr:
                return False, f"Syntax error: {result.stderr}"
            self.log("✓ Syntax valid")
        except FileNotFoundError:
            self.log("⚠ gofmt not found, skipping syntax check")
        except subprocess.TimeoutExpired:
            return False, "Syntax check timeout"

        # Check for common issues
        content = file_path.read_text()
        issues = []

        if "fmt.Println(" in content:
            println_count = content.count("fmt.Println(")
            issues.append(f"Found {println_count} fmt.Println() statements (use structured logging)")

        if "TODO" in content or "FIXME" in content:
            todo_count = content.count("TODO") + content.count("FIXME")
            issues.append(f"Found {todo_count} TODO/FIXME comments")

        if issues:
            return True, f"Syntax valid but warnings: {'; '.join(issues)}"

        return True, "Go file validation passed"

    def validate_file(self, file_path: Path) -> Tuple[bool, str]:
        """Validate file based on extension."""
        suffix = file_path.suffix.lower()

        if suffix == ".py":
            return self.validate_python_file(file_path)
        elif suffix in [".js", ".jsx", ".ts", ".tsx"]:
            return self.validate_javascript_file(file_path)
        elif suffix == ".go":
            return self.validate_go_file(file_path)
        else:
            return True, f"No validation available for {suffix} files"


class ProjectValidator:
    """Validates entire project based on detected project type."""

    def __init__(self, project_root: Path, verbose: bool = False):
        self.project_root = project_root
        self.verbose = verbose
        self.project_type = self.detect_project_type()

    def log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"  {message}", file=sys.stderr)

    def detect_project_type(self) -> str:
        """Detect project type based on files present."""
        if (self.project_root / "package.json").exists():
            return "javascript"
        elif (self.project_root / "go.mod").exists():
            return "go"
        elif (
            (self.project_root / "requirements.txt").exists()
            or (self.project_root / "setup.py").exists()
            or (self.project_root / "pyproject.toml").exists()
        ):
            return "python"
        else:
            return "unknown"

    def run_tests(self) -> Tuple[bool, str, str]:
        """Run project tests based on project type."""
        if self.project_type == "python":
            return self._run_python_tests()
        elif self.project_type == "go":
            return self._run_go_tests()
        elif self.project_type == "javascript":
            return self._run_javascript_tests()
        else:
            return True, "No tests run (unknown project type)", ""

    def _run_python_tests(self) -> Tuple[bool, str, str]:
        """Run Python tests."""
        self.log("Running pytest...")

        # Check if pytest is available
        try:
            result = subprocess.run(["pytest", "--version"], capture_output=True, timeout=5)
            if result.returncode != 0:
                return True, "pytest not available, skipping tests", ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return True, "pytest not available, skipping tests", ""

        # Run tests
        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root,
            )

            passed = result.returncode == 0
            message = "Tests passed" if passed else "Tests failed"
            return passed, message, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, "Tests timeout after 5 minutes", ""
        except Exception as e:
            return False, f"Test execution error: {e}", ""

    def _run_go_tests(self) -> Tuple[bool, str, str]:
        """Run Go tests."""
        self.log("Running go test...")

        try:
            result = subprocess.run(
                ["go", "test", "./...", "-v"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root,
            )

            passed = result.returncode == 0
            message = "Tests passed" if passed else "Tests failed"
            return passed, message, result.stdout + result.stderr

        except FileNotFoundError:
            return True, "go not available, skipping tests", ""
        except subprocess.TimeoutExpired:
            return False, "Tests timeout after 5 minutes", ""
        except Exception as e:
            return False, f"Test execution error: {e}", ""

    def _run_javascript_tests(self) -> Tuple[bool, str, str]:
        """Run JavaScript tests."""
        self.log("Running npm test...")

        # Check if npm is available
        try:
            result = subprocess.run(["npm", "--version"], capture_output=True, timeout=5)
            if result.returncode != 0:
                return True, "npm not available, skipping tests", ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return True, "npm not available, skipping tests", ""

        # Check if test script exists
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                import json as json_module

                with open(package_json) as f:
                    pkg = json_module.load(f)
                    if "test" not in pkg.get("scripts", {}):
                        return True, "No test script defined in package.json", ""
            except Exception:
                pass

        # Run tests
        try:
            result = subprocess.run(
                ["npm", "test", "--", "--watchAll=false"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root,
            )

            passed = result.returncode == 0
            message = "Tests passed" if passed else "Tests failed"
            return passed, message, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, "Tests timeout after 5 minutes", ""
        except Exception as e:
            return False, f"Test execution error: {e}", ""


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate changed files before declaring completion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--changed-files",
        type=str,
        help="Comma-separated list of changed files to validate",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument("--run-tests", action="store_true", help="Run project test suite")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    # Results collection
    results = {
        "success": True,
        "checks_total": 0,
        "checks_passed": 0,
        "file_validations": [],
        "test_results": None,
        "messages": [],
    }

    print("=" * 60)
    print("VERIFICATION VALIDATION REPORT")
    print("=" * 60)
    print()

    # Validate changed files
    if args.changed_files:
        print("File Validation:")
        print("-" * 60)

        file_validator = FileValidator(verbose=args.verbose)
        changed_files = [f.strip() for f in args.changed_files.split(",")]

        for file_path_str in changed_files:
            file_path = Path(file_path_str)
            results["checks_total"] += 1

            passed, message = file_validator.validate_file(file_path)

            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status} - {file_path}")
            print(f"         {message}")

            results["file_validations"].append({"file": str(file_path), "passed": passed, "message": message})

            if passed:
                results["checks_passed"] += 1
            else:
                results["success"] = False

        print()

    # Run project tests
    if args.run_tests:
        print("Project Tests:")
        print("-" * 60)

        project_validator = ProjectValidator(args.project_root, verbose=args.verbose)
        print(f"  Project type: {project_validator.project_type}")

        results["checks_total"] += 1
        test_passed, test_message, test_output = project_validator.run_tests()

        status = "✓ PASS" if test_passed else "✗ FAIL"
        print(f"  {status} - {test_message}")

        if test_output and args.verbose:
            print("\nTest Output:")
            print(test_output[:2000])  # Limit output length
            if len(test_output) > 2000:
                print(f"\n... (truncated, {len(test_output) - 2000} more characters)")

        results["test_results"] = {
            "passed": test_passed,
            "message": test_message,
            "output": test_output if args.output_format == "json" else None,
        }

        if test_passed:
            results["checks_passed"] += 1
        else:
            results["success"] = False

        print()

    # Summary
    print("=" * 60)
    print(f"SUMMARY: {results['checks_passed']}/{results['checks_total']} checks passed")

    if results["success"]:
        print("✓ Validation PASSED")
    else:
        print("✗ Validation FAILED")

    print("=" * 60)

    # Output results
    if args.output_format == "json":
        print(json.dumps(results, indent=2))

    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
