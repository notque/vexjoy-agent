#!/usr/bin/env python3
"""
Code Cartographer: Statistical Analysis for Rule Extraction
Maps the structural DNA of a Go codebase to discover implicit coding rules.

This tool does NOT "read" code. It MEASURES code attributes and aggregates them.
The LLM then interprets the statistics to find the rules.

Why This Works:
- Avoids "Training Bias Override" where LLMs default to general best practices
- Discovers actual local conventions through statistical evidence
- Complements pr-workflow (miner) (explicit rules) with implicit rules (what they actually do)
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class CodebaseProfile:
    """Statistical profile of a codebase"""

    repo_name: str
    total_go_files: int = 0
    total_lines: int = 0

    # Lens 1: Consistency (Frequency)
    imports: Counter = field(default_factory=Counter)
    test_libraries: Counter = field(default_factory=Counter)

    # Lens 2: Signature (Structure)
    func_names: List[str] = field(default_factory=list)
    constructor_patterns: Counter = field(default_factory=Counter)
    receiver_names: Counter = field(default_factory=Counter)

    # Lens 3: Idiom (Implementation)
    error_patterns: Counter = field(default_factory=Counter)
    context_patterns: Counter = field(default_factory=Counter)
    defer_patterns: Counter = field(default_factory=Counter)
    logging_patterns: Counter = field(default_factory=Counter)
    nil_check_patterns: Counter = field(default_factory=Counter)

    # Advanced patterns
    guard_clause_usage: int = 0
    else_block_usage: int = 0
    interface_definitions: int = 0
    struct_definitions: int = 0

    # Error variable naming
    error_var_names: Counter = field(default_factory=Counter)

    # Comment patterns
    comment_types: Counter = field(default_factory=Counter)

    # Modern Go features
    modern_features: Counter = field(default_factory=Counter)


class CodeCartographer:
    """Maps the structural DNA of a Go codebase"""

    def __init__(self, root_path: str, repo_name: str = None):
        self.root = Path(root_path)
        self.profile = CodebaseProfile(repo_name=repo_name or self.root.name)

    def scan(self) -> CodebaseProfile:
        """Scan the entire codebase and build statistical profile"""
        print(f"🗺️  Mapping codebase: {self.profile.repo_name}")
        print(f"📂 Root path: {self.root}")

        go_files = list(self.root.glob("**/*.go"))
        # Filter out vendor and generated files
        go_files = [f for f in go_files if not any(p in str(f) for p in ["vendor/", ".git/", "node_modules/"])]

        self.profile.total_go_files = len(go_files)
        print(f"📄 Found {len(go_files)} Go files")

        for i, file_path in enumerate(go_files, 1):
            if i % 50 == 0:
                print(f"   Analyzed {i}/{len(go_files)} files...")
            self._analyze_file(file_path)

        print(f"✓ Analysis complete: {self.profile.total_lines:,} lines analyzed")
        return self.profile

    def _analyze_file(self, file_path: Path):
        """Analyze a single Go file"""
        try:
            content = file_path.read_text(errors="ignore")
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return

        lines = content.split("\n")
        self.profile.total_lines += len(lines)

        is_test_file = file_path.name.endswith("_test.go")

        # Lens 1: Imports (What tools do they use?)
        self._analyze_imports(content, is_test_file)

        # Lens 2: Signatures (Naming conventions)
        self._analyze_signatures(content)

        # Lens 3: Error Handling (How do they handle errors?)
        self._analyze_error_handling(content)

        # Additional analyses
        self._analyze_context_usage(content)
        self._analyze_defer_patterns(content)
        self._analyze_control_flow(content)
        self._analyze_logging(content)
        self._analyze_nil_checks(content)
        self._analyze_comments(content)
        self._analyze_modern_go(content)

    def _analyze_imports(self, content: str, is_test: bool):
        """Analyze import patterns"""
        import_block = re.search(r"import \((.*?)\)", content, re.DOTALL)
        if import_block:
            imports = re.findall(r'"([^"]+)"', import_block.group(1))
        else:
            imports = re.findall(r'import\s+"([^"]+)"', content)

        for imp in imports:
            # Filter for real packages (contain domain or known paths)
            if "." in imp or "/" in imp:
                self.profile.imports[imp] += 1

                # Track test library usage
                if is_test:
                    if "testify" in imp:
                        self.profile.test_libraries["testify"] += 1
                    elif "ginkgo" in imp or "gomega" in imp:
                        self.profile.test_libraries["ginkgo/gomega"] += 1
                    elif imp == "testing":
                        self.profile.test_libraries["standard_testing"] += 1

    def _analyze_signatures(self, content: str):
        """Analyze function and method signatures"""
        # Find all function declarations
        funcs = re.findall(r"func\s+(?:\([^)]+\)\s+)?([A-Z][a-zA-Z0-9_]*)", content)
        self.profile.func_names.extend(funcs)

        # Constructor patterns
        for func in funcs:
            if func.startswith("New"):
                self.profile.constructor_patterns["New_prefix"] += 1
            elif func.startswith("Create"):
                self.profile.constructor_patterns["Create_prefix"] += 1
            elif func.startswith("Make"):
                self.profile.constructor_patterns["Make_prefix"] += 1

        # Receiver naming patterns
        receivers = re.findall(r"func\s+\((\w+)\s+\*?(\w+)\)", content)
        for receiver_name, _type_name in receivers:
            self.profile.receiver_names[receiver_name] += 1

    def _analyze_error_handling(self, content: str):
        """Analyze error handling patterns"""
        # Find all error checks
        error_checks = re.finditer(r"if\s+err\s*!=\s*nil\s*\{([^}]+)\}", content, re.DOTALL)

        for match in error_checks:
            block = match.group(1).strip()

            # Categorize error handling
            if "fmt.Errorf" in block and "%w" in block:
                self.profile.error_patterns["fmt_errorf_with_w"] += 1
            elif "fmt.Errorf" in block:
                self.profile.error_patterns["fmt_errorf_without_w"] += 1
            elif "errors.Wrap" in block:
                self.profile.error_patterns["pkg_errors_wrap"] += 1
            elif "log.Fatal" in block or "log.Panic" in block:
                self.profile.error_patterns["log_fatal_or_panic"] += 1
            elif "log.Error" in block or "log.Warn" in block:
                self.profile.error_patterns["log_error_or_warn"] += 1
            elif re.search(r"return\s+err\b", block):
                self.profile.error_patterns["return_raw_err"] += 1
            elif re.search(r"return\s+nil", block):
                self.profile.error_patterns["return_nil_on_error"] += 1

        # Error variable naming
        error_vars = re.findall(r"(\w+)\s*:?=\s*[^=].*?\berr\b", content)
        for var in error_vars:
            if var in ["err", "e", "error", "er"]:
                self.profile.error_var_names[var] += 1

    def _analyze_context_usage(self, content: str):
        """Analyze context.Context usage patterns"""
        # Check if context is first parameter
        ctx_first = re.findall(r"func\s+\w+\s*\(\s*ctx\s+context\.Context\s*,", content)
        ctx_not_first = re.findall(r"func\s+\w+\s*\([^)]*,\s*ctx\s+context\.Context", content)

        self.profile.context_patterns["ctx_first_param"] += len(ctx_first)
        self.profile.context_patterns["ctx_not_first"] += len(ctx_not_first)

        # Context variable naming
        ctx_vars = re.findall(r"(\w+)\s+context\.Context", content)
        for var in ctx_vars:
            if var == "ctx":
                self.profile.context_patterns["named_ctx"] += 1
            elif var == "context":
                self.profile.context_patterns["named_context"] += 1

    def _analyze_defer_patterns(self, content: str):
        """Analyze defer usage patterns"""
        defers = re.findall(r"defer\s+(\w+)", content)

        for defer_call in defers:
            if "Close" in defer_call:
                self.profile.defer_patterns["defer_close"] += 1
            elif "Unlock" in defer_call:
                self.profile.defer_patterns["defer_unlock"] += 1
            elif "Rollback" in defer_call:
                self.profile.defer_patterns["defer_rollback"] += 1
            else:
                self.profile.defer_patterns["defer_other"] += 1

    def _analyze_control_flow(self, content: str):
        """Analyze control flow patterns"""
        # Guard clauses (early return)
        guard_clauses = re.findall(r"if\s+.*?\s*\{\s*return", content)
        self.profile.guard_clause_usage += len(guard_clauses)

        # Else blocks
        else_blocks = re.findall(r"\}\s*else\s*\{", content)
        self.profile.else_block_usage += len(else_blocks)

    def _analyze_logging(self, content: str):
        """Analyze logging patterns"""
        if "logg." in content or "log." in content:
            if "logg.Debug" in content or "log.Debug" in content:
                self.profile.logging_patterns["debug"] += content.count("Debug")
            if "logg.Info" in content or "log.Info" in content:
                self.profile.logging_patterns["info"] += content.count("Info")
            if "logg.Error" in content or "log.Error" in content:
                self.profile.logging_patterns["error"] += content.count("Error")
            if "logg.Fatal" in content or "log.Fatal" in content:
                self.profile.logging_patterns["fatal"] += content.count("Fatal")

    def _analyze_nil_checks(self, content: str):
        """Analyze nil checking patterns"""
        # Check for != nil vs == nil
        not_nil = len(re.findall(r"!=\s*nil", content))
        is_nil = len(re.findall(r"==\s*nil", content))

        self.profile.nil_check_patterns["not_nil_checks"] = not_nil
        self.profile.nil_check_patterns["is_nil_checks"] = is_nil

    def _analyze_comments(self, content: str):
        """Analyze comment patterns"""
        # Multi-line comments explaining WHY
        multiline_comments = re.findall(r"//.*\n(?://.*\n)+", content)
        self.profile.comment_types["multiline_why_comments"] += len(
            [c for c in multiline_comments if len(c.split("\n")) >= 3]
        )

        # TODO comments
        self.profile.comment_types["todo_comments"] += len(re.findall(r"//\s*TODO", content))

        # FIXME comments
        self.profile.comment_types["fixme_comments"] += len(re.findall(r"//\s*FIXME", content))

    def _analyze_modern_go(self, content: str):
        """Analyze usage of modern Go features"""
        # slices package (Go 1.21+)
        if "slices." in content:
            self.profile.modern_features["slices_package"] += 1

        # maps package (Go 1.21+)
        if "maps." in content:
            self.profile.modern_features["maps_package"] += 1

        # min/max builtin (Go 1.21+)
        if re.search(r"\bmin\(", content) or re.search(r"\bmax\(", content):
            self.profile.modern_features["min_max_builtin"] += 1

        # clear builtin (Go 1.21+)
        if re.search(r"\bclear\(", content):
            self.profile.modern_features["clear_builtin"] += 1

    def generate_report(self, output_path: Path = None) -> Dict:
        """Generate statistical report"""
        report = {
            "metadata": {
                "repo_name": self.profile.repo_name,
                "total_files": self.profile.total_go_files,
                "total_lines": self.profile.total_lines,
                "analysis_date": "2025-11-20",
            },
            "lens_1_consistency": {
                "top_dependencies": dict(self.profile.imports.most_common(20)),
                "test_framework_usage": dict(self.profile.test_libraries),
                "test_framework_percentages": self._calculate_percentages(self.profile.test_libraries),
            },
            "lens_2_structure": {
                "constructor_patterns": dict(self.profile.constructor_patterns),
                "constructor_percentages": self._calculate_percentages(self.profile.constructor_patterns),
                "receiver_naming": dict(self.profile.receiver_names.most_common(10)),
                "top_function_prefixes": self._analyze_function_prefixes(),
            },
            "lens_3_implementation": {
                "error_handling": dict(self.profile.error_patterns),
                "error_handling_percentages": self._calculate_percentages(self.profile.error_patterns),
                "error_variable_names": dict(self.profile.error_var_names),
                "context_usage": dict(self.profile.context_patterns),
                "defer_patterns": dict(self.profile.defer_patterns),
                "logging_levels": dict(self.profile.logging_patterns),
            },
            "control_flow": {
                "guard_clauses": self.profile.guard_clause_usage,
                "else_blocks": self.profile.else_block_usage,
                "guard_clause_ratio": round(self.profile.guard_clause_usage / max(self.profile.else_block_usage, 1), 2),
            },
            "modern_go_adoption": dict(self.profile.modern_features),
            "derived_rules": self._derive_rules(),
        }

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📊 Report saved to: {output_path}")

        return report

    def _calculate_percentages(self, counter: Counter) -> Dict[str, float]:
        """Calculate percentages from counter"""
        total = sum(counter.values())
        if total == 0:
            return {}
        return {k: round((v / total) * 100, 1) for k, v in counter.items()}

    def _analyze_function_prefixes(self) -> Dict[str, int]:
        """Analyze common function name prefixes"""
        prefixes = [name[:3] for name in self.profile.func_names if len(name) >= 3]
        return dict(Counter(prefixes).most_common(15))

    def _derive_rules(self) -> List[Dict]:
        """Derive coding rules from statistical evidence"""
        rules = []

        # Rule 1: Error wrapping
        error_total = sum(self.profile.error_patterns.values())
        if error_total > 0:
            fmt_w_pct = (self.profile.error_patterns.get("fmt_errorf_with_w", 0) / error_total) * 100
            if fmt_w_pct >= 70:
                rules.append(
                    {
                        "category": "error_handling",
                        "rule": "All errors must be wrapped using fmt.Errorf with %w verb",
                        "evidence": f"{fmt_w_pct:.0f}% consistency across {error_total} error checks",
                        "confidence": "HIGH" if fmt_w_pct >= 85 else "MEDIUM",
                    }
                )

        # Rule 2: Constructor naming
        ctor_total = sum(self.profile.constructor_patterns.values())
        if ctor_total > 0:
            new_pct = (self.profile.constructor_patterns.get("New_prefix", 0) / ctor_total) * 100
            if new_pct >= 70:
                rules.append(
                    {
                        "category": "naming",
                        "rule": "Constructors must use New{Type} naming pattern",
                        "evidence": f"{new_pct:.0f}% of {ctor_total} constructors follow this pattern",
                        "confidence": "HIGH" if new_pct >= 90 else "MEDIUM",
                    }
                )

        # Rule 3: Context parameter position
        ctx_first = self.profile.context_patterns.get("ctx_first_param", 0)
        ctx_not_first = self.profile.context_patterns.get("ctx_not_first", 0)
        if ctx_first + ctx_not_first > 0:
            ctx_first_pct = (ctx_first / (ctx_first + ctx_not_first)) * 100
            if ctx_first_pct >= 85:
                rules.append(
                    {
                        "category": "function_signature",
                        "rule": "context.Context must be the first parameter",
                        "evidence": f"{ctx_first_pct:.0f}% consistency across {ctx_first + ctx_not_first} functions",
                        "confidence": "HIGH",
                    }
                )

        # Rule 4: Guard clauses vs else blocks
        if self.profile.guard_clause_usage > self.profile.else_block_usage * 2:
            ratio = self.profile.guard_clause_usage / max(self.profile.else_block_usage, 1)
            rules.append(
                {
                    "category": "control_flow",
                    "rule": "Prefer guard clauses (early returns) over else blocks",
                    "evidence": f"{ratio:.1f}x more guard clauses than else blocks",
                    "confidence": "HIGH",
                }
            )

        # Rule 5: Error variable naming
        err_var_total = sum(self.profile.error_var_names.values())
        if err_var_total > 0:
            err_pct = (self.profile.error_var_names.get("err", 0) / err_var_total) * 100
            if err_pct >= 90:
                rules.append(
                    {
                        "category": "naming",
                        "rule": "Error variables must be named 'err', not 'e' or 'error'",
                        "evidence": f"{err_pct:.0f}% consistency across {err_var_total} error variables",
                        "confidence": "HIGH",
                    }
                )

        return rules


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Code Cartographer: Statistical analysis for rule extraction")
    parser.add_argument("repo_path", help="Path to Go repository")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--name", help="Repository name (defaults to directory name)")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    if not repo_path.exists():
        print(f"Error: Path not found: {repo_path}")
        sys.exit(1)

    cartographer = CodeCartographer(repo_path, args.name)
    profile = cartographer.scan()

    # Generate output path
    if args.output:
        output_path = Path(args.output)
    else:
        skill_dir = Path(__file__).parent.parent
        output_path = skill_dir / "cartography_data" / f"{profile.repo_name}_cartography.json"

    report = cartographer.generate_report(output_path)

    # Print summary
    print("\n" + "=" * 80)
    print("CODE CARTOGRAPHY SUMMARY")
    print("=" * 80)
    print(f"\n📦 Repository: {profile.repo_name}")
    print(f"📄 Files analyzed: {profile.total_go_files}")
    print(f"📏 Total lines: {profile.total_lines:,}")

    if report["derived_rules"]:
        print(f"\n🎯 Derived Rules: {len(report['derived_rules'])}")
        for rule in report["derived_rules"]:
            print(f"\n  [{rule['confidence']}] {rule['rule']}")
            print(f"  Evidence: {rule['evidence']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
