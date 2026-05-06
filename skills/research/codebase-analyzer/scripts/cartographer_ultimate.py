#!/usr/bin/env python3
"""
Ultimate Code Cartographer: The DNA Sequencer for Go Codebases.
Combines Deep Pattern Analysis with Micro-Optimization Metrics.
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
    repo_name: str
    files_analyzed: int = 0
    total_lines: int = 0

    # --- 1. Data Structures & Performance ---
    struct_init: Counter = field(default_factory=Counter)  # Keyed vs Unkeyed
    slice_alloc: Counter = field(default_factory=Counter)  # Cap vs Len
    map_init: Counter = field(default_factory=Counter)  # make vs literal

    # --- 2. Concurrency & Safety ---
    goroutine_patterns: Counter = field(default_factory=Counter)
    channel_patterns: Counter = field(default_factory=Counter)
    sync_primitives: Counter = field(default_factory=Counter)  # Mutex vs RWMutex
    mutex_usage: Counter = field(default_factory=Counter)  # Embedded vs Field

    # --- 3. API Design & Architecture ---
    receiver_type: Counter = field(default_factory=Counter)  # Pointer vs Value
    interface_sizes: Counter = field(default_factory=Counter)
    context_usage: Counter = field(default_factory=Counter)
    option_pattern: int = 0

    # --- 4. Error Handling Dialect ---
    error_message_style: Counter = field(default_factory=Counter)  # "cannot" vs "failed"
    error_wrapping: Counter = field(default_factory=Counter)  # %w vs raw
    error_types: Counter = field(default_factory=Counter)  # Sentinel vs Custom

    # --- 5. Domain Specific ---
    http_patterns: Counter = field(default_factory=Counter)
    db_patterns: Counter = field(default_factory=Counter)

    # --- 6. Testing Strategy ---
    test_structure: Counter = field(default_factory=Counter)  # Table vs Helper


class UltimateCartographer:
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.profile = CodebaseProfile(repo_name=self.root.name)

        # Regex Patterns (Compiled for speed)
        self.REGEX = {
            # Structures
            "struct_keyed": re.compile(r"[A-Za-z0-9_]+\s*\{[A-Za-z0-9_]+\s*:"),
            "struct_unkeyed": re.compile(r'[A-Za-z0-9_]+\s*\{"[^"]+",'),
            "slice_cap": re.compile(r"make\(\[\][^,]+,\s*0,\s*[^)]+\)"),
            "slice_len": re.compile(r"make\(\[\][^,]+,\s*[0-9a-zA-Z_.]+\)"),
            # Concurrency
            "mutex_embed": re.compile(r"type\s+\w+\s+struct\s*\{[^}]*sync\.(RW)?Mutex"),
            "mutex_field": re.compile(r"\w+\s+sync\.(RW)?Mutex"),
            # Receivers (support both exported and unexported types)
            "recv_ptr": re.compile(r"func\s+\([a-zA-Z0-9_]+\s+\*[a-zA-Z]"),
            "recv_val": re.compile(r"func\s+\([a-zA-Z0-9_]+\s+[a-zA-Z][a-zA-Z0-9_]*\)"),
            # Errors
            "fmt_error": re.compile(r'fmt\.Errorf\("([^"]+)"'),
            "sentinel": re.compile(r"var\s+Err\w+\s*=\s*errors\.New"),
            # HTTP
            "json_enc": re.compile(r"json\.NewEncoder\("),
            "json_marsh": re.compile(r"json\.Marshal\("),
            # DB
            "tx_rollback": re.compile(r"defer\s+[a-zA-Z0-9_.]*Rollback\("),
        }

    def scan(self):
        print(f"🧬 Sequencing DNA of {self.profile.repo_name}...")
        go_files = [p for p in self.root.rglob("*.go") if "vendor" not in p.parts and ".git" not in p.parts]

        total = len(go_files)
        for idx, path in enumerate(go_files, 1):
            if idx % 50 == 0:
                print(f"   Analyzed {idx}/{total} files...")
            self._analyze_file(path)

        print(f"✓ Analysis complete: {self.profile.total_lines:,} lines analyzed")
        return self.generate_report()

    def _analyze_file(self, path: Path):
        try:
            content = path.read_text(errors="ignore")
        except:
            return

        self.profile.files_analyzed += 1
        self.profile.total_lines += len(content.splitlines())
        is_test = path.name.endswith("_test.go")

        # --- 1. Data Structures ---
        self.profile.struct_init["keyed"] += len(self.REGEX["struct_keyed"].findall(content))
        self.profile.struct_init["unkeyed"] += len(self.REGEX["struct_unkeyed"].findall(content))

        self.profile.slice_alloc["prealloc_cap"] += len(self.REGEX["slice_cap"].findall(content))
        self.profile.slice_alloc["len_only"] += len(self.REGEX["slice_len"].findall(content))

        # --- 2. Concurrency ---
        if "go func()" in content:
            self.profile.goroutine_patterns["anonymous"] += 1
        if re.search(r"go\s+\w+\(", content):
            self.profile.goroutine_patterns["named"] += len(re.findall(r"go\s+\w+\(", content))

        if "sync.RWMutex" in content:
            self.profile.sync_primitives["rwmutex"] += 1
        if "sync.Mutex" in content and "sync.RWMutex" not in content:
            self.profile.sync_primitives["mutex"] += 1

        self.profile.mutex_usage["embedded"] += len(self.REGEX["mutex_embed"].findall(content))
        self.profile.mutex_usage["field"] += len(self.REGEX["mutex_field"].findall(content))

        # --- 3. API Design ---
        self.profile.receiver_type["pointer"] += len(self.REGEX["recv_ptr"].findall(content))
        self.profile.receiver_type["value"] += len(self.REGEX["recv_val"].findall(content))

        if "With" in content and "Option" in content:
            if re.search(r"func\s+With\w+\(", content):
                self.profile.option_pattern += 1

        # --- 4. Error Dialect ---
        for match in self.REGEX["fmt_error"].finditer(content):
            msg = match.group(1)
            if msg.startswith("cannot"):
                self.profile.error_message_style["cannot_X"] += 1
            elif msg.startswith("failed"):
                self.profile.error_message_style["failed_to_X"] += 1
            elif "while" in msg:
                self.profile.error_message_style["while_X"] += 1

        self.profile.error_types["sentinel"] += len(self.REGEX["sentinel"].findall(content))

        # Error wrapping
        if "%w" in content:
            self.profile.error_wrapping["with_w"] += content.count("%w")
        if "return err" in content or "return nil, err" in content:
            self.profile.error_wrapping["raw_return"] += 1

        # --- 5. Domain Patterns ---
        if "net/http" in content:
            self.profile.http_patterns["json_marshal"] += len(self.REGEX["json_marsh"].findall(content))
            self.profile.http_patterns["json_encoder"] += len(self.REGEX["json_enc"].findall(content))

        if "database/sql" in content:
            if "Exec(" in content:
                self.profile.db_patterns["exec"] += 1
            if "Query(" in content:
                self.profile.db_patterns["query"] += 1
            self.profile.db_patterns["defer_rollback"] += len(self.REGEX["tx_rollback"].findall(content))

        # --- 6. Testing ---
        if is_test:
            if re.search(r"tests\s*:=\s*\[\]struct", content):
                self.profile.test_structure["table_driven"] += 1
            if "func test" in content.lower() or "func setup" in content.lower():
                self.profile.test_structure["helpers"] += 1

    def generate_report(self):
        # Manually serialize to avoid Counter -> tuple key conversion
        p = self.profile
        return {
            "metadata": {"repo": p.repo_name, "files": p.files_analyzed, "lines": f"{p.total_lines:,}"},
            "stats": {
                "repo_name": p.repo_name,
                "files_analyzed": p.files_analyzed,
                "total_lines": p.total_lines,
                "struct_init": dict(p.struct_init),
                "slice_alloc": dict(p.slice_alloc),
                "map_init": dict(p.map_init),
                "goroutine_patterns": dict(p.goroutine_patterns),
                "channel_patterns": dict(p.channel_patterns),
                "sync_primitives": dict(p.sync_primitives),
                "mutex_usage": dict(p.mutex_usage),
                "receiver_type": dict(p.receiver_type),
                "interface_sizes": dict(p.interface_sizes),
                "context_usage": dict(p.context_usage),
                "option_pattern": p.option_pattern,
                "error_message_style": dict(p.error_message_style),
                "error_wrapping": dict(p.error_wrapping),
                "error_types": dict(p.error_types),
                "http_patterns": dict(p.http_patterns),
                "db_patterns": dict(p.db_patterns),
                "test_structure": dict(p.test_structure),
            },
            "derived_rules": self._derive_rules(),
        }

    def _derive_rules(self) -> List[Dict]:
        rules = []
        p = self.profile

        def pct(counter, key, total_override=None):
            total = total_override or sum(counter.values())
            if total < 5:
                return 0
            return (counter[key] / total) * 100

        # 1. Struct Safety
        keyed_pct = pct(p.struct_init, "keyed")
        if keyed_pct > 90:
            rules.append(
                {
                    "rule": "Use keyed struct literals (User{ID: 1})",
                    "confidence": "HIGH",
                    "category": "maintainability",
                    "evidence": f"{keyed_pct:.0f}% of struct literals are keyed",
                }
            )

        # 2. Slice Performance
        prealloc_pct = pct(p.slice_alloc, "prealloc_cap")
        if prealloc_pct > 70:
            rules.append(
                {
                    "rule": "Preallocate slice capacity (make([]T, 0, cap))",
                    "confidence": "MEDIUM",
                    "category": "performance",
                    "evidence": f"{prealloc_pct:.0f}% of slices preallocate capacity",
                }
            )

        # 3. Receiver Semantics
        ptr_pct = pct(p.receiver_type, "pointer")
        if ptr_pct > 90:
            rules.append(
                {
                    "rule": "Use Pointer Receivers (*T) for all methods",
                    "confidence": "HIGH",
                    "category": "design",
                    "evidence": f"{ptr_pct:.0f}% of receivers are pointers",
                }
            )

        # 4. Mutex Safety
        if p.mutex_usage["embedded"] == 0 and p.mutex_usage["field"] > 0:
            rules.append(
                {
                    "rule": "Never embed sync.Mutex; use a named field",
                    "confidence": "HIGH",
                    "category": "safety",
                    "evidence": f"0 embedded mutexes, {p.mutex_usage['field']} as fields",
                }
            )

        # 5. Error Dialect
        cannot_pct = pct(p.error_message_style, "cannot_X")
        if cannot_pct > 60:
            total = sum(p.error_message_style.values())
            rules.append(
                {
                    "rule": 'Error messages should start with "cannot <verb>"',
                    "confidence": "HIGH",
                    "category": "style",
                    "evidence": f"{cannot_pct:.0f}% of {total} error messages use 'cannot'",
                }
            )

        # 6. HTTP Performance
        json_marshal_pct = pct(p.http_patterns, "json_marshal")
        if json_marshal_pct > 90:
            rules.append(
                {
                    "rule": "Use json.Marshal over json.NewEncoder for HTTP responses",
                    "confidence": "HIGH",
                    "category": "http",
                    "evidence": f"{json_marshal_pct:.0f}% use json.Marshal()",
                }
            )

        # 7. DB Safety
        if p.db_patterns.get("exec", 0) > 0 and p.db_patterns.get("defer_rollback", 0) > 0:
            rules.append(
                {
                    "rule": "Always defer transaction Rollback()",
                    "confidence": "HIGH",
                    "category": "database",
                    "evidence": f"{p.db_patterns['defer_rollback']} defer rollback patterns found",
                }
            )

        return rules


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cartographer_ultimate.py <path_to_repo> [--json] [--output FILE]")
        return

    path = sys.argv[1]
    cart = UltimateCartographer(path)
    report = cart.scan()

    # Handle output
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📊 Report saved to: {output_file}")

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)


def print_summary(report):
    print("\n" + "=" * 60)
    print(f"🧬 DNA REPORT: {report['metadata']['repo']}")
    print("=" * 60)

    print("\n📊 Repository Stats:")
    print(f"  Files: {report['metadata']['files']}")
    print(f"  Lines: {report['metadata']['lines']}")

    print("\n🔍 Granular Patterns:")
    stats = report["stats"]

    # Data Structures
    if stats["struct_init"]:
        print("\n  Data Structures:")
        print(
            f"    • Keyed Literals: {stats['struct_init'].get('keyed', 0)} | Unkeyed: {stats['struct_init'].get('unkeyed', 0)}"
        )
        if stats["slice_alloc"]:
            print(
                f"    • Prealloc Slices: {stats['slice_alloc'].get('prealloc_cap', 0)} | Len Only: {stats['slice_alloc'].get('len_only', 0)}"
            )

    # Concurrency
    if stats["sync_primitives"] or stats["goroutine_patterns"]:
        print("\n  Concurrency:")
        if stats["sync_primitives"]:
            print(
                f"    • RWMutex: {stats['sync_primitives'].get('rwmutex', 0)} | Mutex: {stats['sync_primitives'].get('mutex', 0)}"
            )
        if stats["mutex_usage"]:
            print(
                f"    • Embedded Mutexes: {stats['mutex_usage'].get('embedded', 0)} | Field: {stats['mutex_usage'].get('field', 0)}"
            )
        if stats["goroutine_patterns"]:
            print(
                f"    • Anonymous goroutines: {stats['goroutine_patterns'].get('anonymous', 0)} | Named: {stats['goroutine_patterns'].get('named', 0)}"
            )

    # API Design
    if stats["receiver_type"]:
        print("\n  API Design:")
        print(
            f"    • Pointer Receivers: {stats['receiver_type'].get('pointer', 0)} | Value: {stats['receiver_type'].get('value', 0)}"
        )
        if stats["option_pattern"]:
            print(f"    • Option Pattern (WithX): {stats['option_pattern']}")

    # Error Dialect
    if stats["error_message_style"]:
        print("\n  Error Dialect:")
        for style, count in sorted(stats["error_message_style"].items(), key=lambda x: x[1], reverse=True):
            print(f"    • {style}: {count}")

    # Domain Specific
    if stats["http_patterns"]:
        print("\n  HTTP Patterns:")
        print(
            f"    • json.Marshal: {stats['http_patterns'].get('json_marshal', 0)} | Encoder: {stats['http_patterns'].get('json_encoder', 0)}"
        )

    if stats["db_patterns"]:
        print("\n  Database:")
        print(f"    • Exec: {stats['db_patterns'].get('exec', 0)} | Query: {stats['db_patterns'].get('query', 0)}")
        print(f"    • Defer Rollback: {stats['db_patterns'].get('defer_rollback', 0)}")

    # Testing
    if stats["test_structure"]:
        print("\n  Testing:")
        print(f"    • Table-Driven: {stats['test_structure'].get('table_driven', 0)}")
        print(f"    • Test Helpers: {stats['test_structure'].get('helpers', 0)}")

    # Derived Rules
    print(f"\n🎯 Derived Rules ({len(report['derived_rules'])}):")
    if report["derived_rules"]:
        for r in report["derived_rules"]:
            print(f"\n  [{r['confidence']}] {r['rule']}")
            print(f"  Evidence: {r['evidence']}")
            print(f"  Category: {r['category']}")
    else:
        print("  No high-confidence rules derived (need more code or clearer patterns)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
