#!/usr/bin/env python3
"""
Omni-Cartographer: Full-Spectrum Go Codebase DNA Analyzer.

Extracts architectural, stylistic, and operational habits from Go codebases.
Focuses on "Habits" (Good, Bad, Ugly) and "The Shadow Constitution" (what rules they ignore).

Generates 20-50+ actionable, measurable, LLM-ready coding rules.
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class OmniProfile:
    repo_name: str
    files_analyzed: int = 0
    total_lines: int = 0

    # --- 1. Shadow Constitution (What Rules They Ignore) ---
    linter_suppressions: Counter = field(default_factory=Counter)  # //nolint:xxx
    todo_markers: Counter = field(default_factory=Counter)  # TODO vs FIXME vs HACK

    # --- 2. Context Hygiene (The Nervous System) ---
    context_creation: Counter = field(default_factory=Counter)  # Background/TODO usage by location
    context_patterns: Counter = field(default_factory=Counter)  # WithCancel/Timeout/Deadline

    # --- 3. Time Management & Testability ---
    time_patterns: Counter = field(default_factory=Counter)  # time.Now vs Clock interface
    random_patterns: Counter = field(default_factory=Counter)  # Determinism check

    # --- 4. Dangerous Functions & Safety ---
    dangerous_funcs: Counter = field(default_factory=Counter)  # panic, fatal, init
    global_state: Counter = field(default_factory=Counter)  # Global vars/mutability

    # --- 5. Modern Go Adoption (Granular) ---
    go_version_signals: Counter = field(default_factory=Counter)  # any vs interface{}
    slices_functions: Counter = field(default_factory=Counter)  # Per-function tracking
    maps_functions: Counter = field(default_factory=Counter)  # Per-function tracking
    cmp_usage: Counter = field(default_factory=Counter)  # cmp.Compare/Or/Less
    builtin_minmax: Counter = field(default_factory=Counter)  # min/max builtins

    # --- 6. Anti-patterns (What They Avoid) ---
    anti_patterns: Counter = field(default_factory=Counter)  # Manual loops, float conversions

    # --- 7. Project Architecture ---
    project_layout: Counter = field(default_factory=Counter)  # cmd/internal/pkg structure
    package_organization: Counter = field(default_factory=Counter)  # Files per package

    # --- 8. Constructor & Builder Patterns ---
    constructor_patterns: Counter = field(default_factory=Counter)  # New vs Create vs Must
    constructor_sigs: Counter = field(default_factory=Counter)  # Return types
    builder_patterns: Counter = field(default_factory=Counter)  # Builder detection

    # --- 9. Error Handling Deep Dive ---
    error_wrapping: Counter = field(default_factory=Counter)  # %w vs %v vs raw
    error_messages: Counter = field(default_factory=Counter)  # cannot vs failed vs while
    error_types: Counter = field(default_factory=Counter)  # Sentinel vs custom
    error_checking: Counter = field(default_factory=Counter)  # errors.Is/As usage

    # --- 10. Logging & Observability ---
    log_libraries: Counter = field(default_factory=Counter)  # logrus vs zap vs slog
    log_levels: Counter = field(default_factory=Counter)  # Debug/Info/Warn/Error
    log_patterns: Counter = field(default_factory=Counter)  # Structured vs string

    # --- 11. Testing Patterns ---
    test_frameworks: Counter = field(default_factory=Counter)  # standard vs testify vs ginkgo
    test_patterns: Counter = field(default_factory=Counter)  # table-driven, subtests
    test_coverage: Counter = field(default_factory=Counter)  # Example/benchmark tests

    # --- 12. Naming Conventions ---
    variable_abbreviations: Counter = field(default_factory=Counter)  # ctx, cfg, db, etc.
    receiver_naming: Counter = field(default_factory=Counter)  # Single vs multi-letter
    function_prefixes: Counter = field(default_factory=Counter)  # Get/Set/Handle/Process
    boolean_naming: Counter = field(default_factory=Counter)  # is/has/can/should

    # --- 13. Core Patterns (From Ultimate) ---
    struct_init: Counter = field(default_factory=Counter)  # Keyed vs unkeyed
    slice_alloc: Counter = field(default_factory=Counter)  # Prealloc vs len-only
    receiver_type: Counter = field(default_factory=Counter)  # Pointer vs value
    mutex_usage: Counter = field(default_factory=Counter)  # Embedded vs field
    goroutine_patterns: Counter = field(default_factory=Counter)  # Anonymous vs named

    # --- 14. Documentation Quality ---
    documentation: Counter = field(default_factory=Counter)  # Godoc coverage
    comment_patterns: Counter = field(default_factory=Counter)  # Quality indicators

    # --- 15. HTTP & API Patterns ---
    http_patterns: Counter = field(default_factory=Counter)  # Marshal vs Encoder
    api_patterns: Counter = field(default_factory=Counter)  # Handler patterns

    # --- PHASE 1 ENHANCEMENTS: 100 METRICS ---

    # --- 16. Naming Dialects (Extended) ---
    getter_style: Counter = field(default_factory=Counter)  # GetName() vs Name()
    id_convention: Counter = field(default_factory=Counter)  # ID vs Id vs UUID
    acronym_casing: Counter = field(default_factory=Counter)  # URL vs Url, HTTP vs Http
    constant_style: Counter = field(default_factory=Counter)  # CamelCase vs SCREAMING_SNAKE
    error_var_naming: Counter = field(default_factory=Counter)  # err vs error vs e
    boolean_extended: Counter = field(default_factory=Counter)  # should/will/enable prefixes
    type_suffix_usage: Counter = field(default_factory=Counter)  # TypeUser vs UserType

    # --- 17. Control Flow Flavor ---
    guard_clauses: Counter = field(default_factory=Counter)  # Guard vs nested if
    switch_vs_if: Counter = field(default_factory=Counter)  # Switch vs if-else chains
    loop_styles: Counter = field(default_factory=Counter)  # for-range vs classic for
    flow_control: Counter = field(default_factory=Counter)  # break/continue vs flags
    defer_patterns: Counter = field(default_factory=Counter)  # defer placement
    return_style: Counter = field(default_factory=Counter)  # early return vs single exit

    # --- 18. API & Interface Design ---
    string_concat_methods: Counter = field(default_factory=Counter)  # + vs Sprintf vs Builder
    zero_value_usage: Counter = field(default_factory=Counter)  # Explicit vs implicit zero
    enum_styles: Counter = field(default_factory=Counter)  # iota vs map vs string
    optional_params: Counter = field(default_factory=Counter)  # Functional opts vs variadic

    # --- 19. Observability Extended ---
    log_structure_style: Counter = field(default_factory=Counter)  # JSON vs key=value vs plain
    http_status_style: Counter = field(default_factory=Counter)  # Named constants vs magic numbers
    metric_naming: Counter = field(default_factory=Counter)  # Metric name conventions
    error_codes: Counter = field(default_factory=Counter)  # Numeric vs string codes

    # --- PHASE 2 ENHANCEMENTS: ARCHITECTURAL PATTERNS ---

    # --- 20. Interface Topology ---
    interface_sizes: Counter = field(default_factory=Counter)  # small/medium/large interfaces
    interface_composition: Counter = field(default_factory=Counter)  # Embedded interfaces
    interface_params: Counter = field(default_factory=Counter)  # Interface-typed parameters

    # --- 21. Configuration Strategy ---
    config_sources: Counter = field(default_factory=Counter)  # env/flags/files
    env_var_patterns: Counter = field(default_factory=Counter)  # os.Getenv usage
    flag_patterns: Counter = field(default_factory=Counter)  # flag package usage
    config_structs: Counter = field(default_factory=Counter)  # Config struct patterns

    # --- 22. Dependency Injection ---
    constructor_deps: Counter = field(default_factory=Counter)  # Constructor DI patterns
    interface_deps: Counter = field(default_factory=Counter)  # Interface parameters
    factory_patterns: Counter = field(default_factory=Counter)  # Factory functions

    # --- 23. Lifecycle Management ---
    lifecycle_methods: Counter = field(default_factory=Counter)  # Start/Stop/Close
    shutdown_patterns: Counter = field(default_factory=Counter)  # Context-aware shutdown
    cleanup_patterns: Counter = field(default_factory=Counter)  # Resource cleanup
    health_checks: Counter = field(default_factory=Counter)  # Health/readiness patterns

    # --- 24. Package Organization ---
    package_naming: Counter = field(default_factory=Counter)  # Singular vs plural
    package_patterns: Counter = field(default_factory=Counter)  # Package structure

    # --- 25. Architectural Patterns ---
    arch_patterns: Counter = field(default_factory=Counter)  # Repository/Service/Handler
    middleware_patterns: Counter = field(default_factory=Counter)  # Middleware detection
    layer_separation: Counter = field(default_factory=Counter)  # Domain/Infra separation

    # --- PHASE 3: STYLE VECTOR (Composite Scores 0-100) ---

    # Style vector: Multi-dimensional coding style fingerprint
    # Each score is 0-100, computed from existing metrics
    style_vector: Dict[str, float] = field(default_factory=dict)  # Composite scores


class OmniCartographer:
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.profile = OmniProfile(repo_name=self.root.name)
        self._compile_regex()
        self._detect_layout()

    def _compile_regex(self):
        """Pre-compile all regex patterns for performance."""
        self.R = {
            # --- Shadow Constitution ---
            "nolint": re.compile(r"//\s*nolint:([a-z0-9_,]+)"),
            "todo_markers": re.compile(r"//\s*(TODO|FIXME|HACK|XXX|NOTE)"),
            "todo_with_issue": re.compile(r"//\s*TODO\(#\d+\)"),
            "todo_with_author": re.compile(r"//\s*TODO\([a-zA-Z]+\)"),
            # --- Context Hygiene ---
            "ctx_background": re.compile(r"context\.Background\("),
            "ctx_todo": re.compile(r"context\.TODO\("),
            "ctx_with_cancel": re.compile(r"context\.WithCancel"),
            "ctx_with_timeout": re.compile(r"context\.WithTimeout"),
            "ctx_with_deadline": re.compile(r"context\.WithDeadline"),
            "ctx_with_value": re.compile(r"context\.WithValue"),
            "ctx_param": re.compile(r"func\s+\w+\(\s*ctx\s+context\.Context"),
            "context_param": re.compile(r"func\s+\w+\(\s*context\s+context\.Context"),
            # --- Time Management ---
            "time_now": re.compile(r"time\.Now\("),
            "clock_interface": re.compile(r"type\s+Clock\s+interface"),
            "time_constants": re.compile(r"time\.(Second|Minute|Hour|Millisecond|Microsecond|Nanosecond)"),
            # --- Dangerous Functions ---
            "panic_call": re.compile(r"\bpanic\("),
            "log_fatal": re.compile(r"log\.Fatal|logger\.Fatal"),
            "os_exit": re.compile(r"os\.Exit\("),
            "init_func": re.compile(r"func\s+init\(\)"),
            "global_var": re.compile(r"^var\s+[A-Z]\w+\s*="),
            # --- Modern Go ---
            "interface_empty": re.compile(r"interface\{\}"),
            "any_keyword": re.compile(r"\bany\b"),
            "generic_func": re.compile(r"func\s+\w+\[[A-Z]\w*\s+any\]"),
            "generic_type": re.compile(r"type\s+\w+\[[A-Z]\w*\s+any\]"),
            # Slices package
            "slices_sort": re.compile(r"slices\.Sort"),
            "slices_compact": re.compile(r"slices\.Compact"),
            "slices_contains": re.compile(r"slices\.Contains"),
            "slices_equal": re.compile(r"slices\.Equal"),
            "slices_clone": re.compile(r"slices\.Clone"),
            "slices_index": re.compile(r"slices\.Index"),
            "slices_delete": re.compile(r"slices\.Delete"),
            "slices_reverse": re.compile(r"slices\.Reverse"),
            # Maps package
            "maps_clone": re.compile(r"maps\.Clone"),
            "maps_equal": re.compile(r"maps\.Equal"),
            "maps_copy": re.compile(r"maps\.Copy"),
            # CMP package
            "cmp_compare": re.compile(r"cmp\.Compare"),
            "cmp_or": re.compile(r"cmp\.Or"),
            "cmp_less": re.compile(r"cmp\.Less"),
            # Builtins
            "min_builtin": re.compile(r"\bmin\("),
            "max_builtin": re.compile(r"\bmax\("),
            "clear_builtin": re.compile(r"\bclear\("),
            # --- Anti-patterns ---
            "manual_contains": re.compile(r"for\s+_,\s*\w+\s*:=\s*range\s+\w+\s*\{[^}]*if\s+\w+\s*=="),
            "manual_dedup": re.compile(r"seen\s*:=\s*make\(map\["),
            "math_min_int": re.compile(r"int\(math\.Min\(float64\("),
            "manual_map_copy": re.compile(r"for\s+\w+,\s*\w+\s*:=\s*range\s+\w+\s*\{[^}]*\w+\[\w+\]\s*="),
            # --- Constructors ---
            "new_constructor": re.compile(r"func\s+New[A-Z]\w*\("),
            "create_constructor": re.compile(r"func\s+Create[A-Z]\w*\("),
            "must_constructor": re.compile(r"func\s+Must\w*\("),
            "constructor_error": re.compile(r"func\s+\w+\([^)]*\)\s*\(\*\w+,\s*error\)"),
            "functional_option": re.compile(r"func\s+With[A-Z]\w*\("),
            # --- Error Handling ---
            "fmt_errorf_w": re.compile(r"fmt\.Errorf\([^)]*%w"),
            "fmt_errorf_v": re.compile(r"fmt\.Errorf\([^)]*%v"),
            "error_msg": re.compile(r'fmt\.Errorf\("([^"]+)"'),
            "sentinel_error": re.compile(r"var\s+Err\w+\s*=\s*errors\.New"),
            "custom_error_type": re.compile(r"type\s+\w+Error\s+struct"),
            "errors_is": re.compile(r"errors\.Is\("),
            "errors_as": re.compile(r"errors\.As\("),
            # --- Logging ---
            "logrus_import": re.compile(r'"github\.com/sirupsen/logrus"'),
            "zap_import": re.compile(r'"go\.uber\.org/zap"'),
            "slog_import": re.compile(r'"log/slog"'),
            "log_debug": re.compile(r"\.Debug\(|log\.Debug"),
            "log_info": re.compile(r"\.Info\(|log\.Info"),
            "log_warn": re.compile(r"\.Warn\(|log\.Warn"),
            "log_error": re.compile(r"\.Error\(|log\.Error"),
            "log_with_fields": re.compile(r"\.WithFields\(|\.With\("),
            # --- Testing ---
            "testify_import": re.compile(r'"github\.com/stretchr/testify'),
            "ginkgo_import": re.compile(r'"github\.com/onsi/ginkgo'),
            "table_driven": re.compile(r"tests\s*:=\s*\[\]struct"),
            "t_run": re.compile(r"t\.Run\("),
            "t_helper": re.compile(r"t\.Helper\("),
            "t_parallel": re.compile(r"t\.Parallel\("),
            "example_test": re.compile(r"func\s+Example"),
            "benchmark_test": re.compile(r"func\s+Benchmark"),
            # --- Naming Conventions ---
            "var_ctx": re.compile(r"\bctx\s*:?="),
            "var_context": re.compile(r"\bcontext\s*:?=\s*context\."),
            "var_cfg": re.compile(r"\bcfg\s*:?="),
            "var_db": re.compile(r"\bdb\s*:?="),
            "var_tx": re.compile(r"\btx\s*:?="),
            "bool_is": re.compile(r"func\s+is[A-Z]\w*\("),
            "bool_has": re.compile(r"func\s+has[A-Z]\w*\("),
            "bool_can": re.compile(r"func\s+can[A-Z]\w*\("),
            "func_get": re.compile(r"func\s+Get[A-Z]\w*\("),
            "func_set": re.compile(r"func\s+Set[A-Z]\w*\("),
            "func_handle": re.compile(r"func\s+Handle[A-Z]\w*\("),
            # --- Core Patterns ---
            "struct_keyed": re.compile(r"[A-Za-z0-9_]+\s*\{[A-Za-z0-9_]+\s*:"),
            "struct_unkeyed": re.compile(r'[A-Za-z0-9_]+\s*\{"[^"]+",'),
            "slice_prealloc": re.compile(r"make\(\[\][^,]+,\s*0,\s*[^)]+\)"),
            "slice_len_only": re.compile(r"make\(\[\][^,]+,\s*[^,)]+\)"),
            "recv_ptr": re.compile(r"func\s+\([a-zA-Z0-9_]+\s+\*[a-zA-Z]"),
            "recv_val": re.compile(r"func\s+\([a-zA-Z0-9_]+\s+[a-zA-Z][a-zA-Z0-9_]*\)"),
            "recv_single": re.compile(r"func\s+\(([a-z])\s+[\*]?[A-Z]"),
            "mutex_embed": re.compile(r"type\s+\w+\s+struct\s*\{[^}]*sync\.(RW)?Mutex"),
            "mutex_field": re.compile(r"\s+\w+\s+sync\.(RW)?Mutex"),
            "go_func_anon": re.compile(r"go\s+func\("),
            "go_func_named": re.compile(r"go\s+[a-zA-Z]\w*\("),
            # --- Documentation ---
            "godoc_exported": re.compile(r"//\s*[A-Z]\w+\s+\w+"),
            "package_doc": re.compile(r"//\s*Package\s+\w+"),
            # --- HTTP Patterns ---
            "json_marshal": re.compile(r"json\.Marshal"),
            "json_encoder": re.compile(r"json\.NewEncoder"),
            # --- PHASE 1: Extended Naming Dialects ---
            # Getter style detection
            "getter_with_get": re.compile(r"func\s+\([^)]+\)\s+Get([A-Z]\w*)\("),
            "getter_without_get": re.compile(r"func\s+\([^)]+\)\s+([A-Z]\w*)\(\)\s+\w"),
            # ID conventions
            "id_upper": re.compile(r"\bID\b"),
            "id_capitalized": re.compile(r"\bId\b"),
            "uuid_upper": re.compile(r"\bUUID\b"),
            "uuid_capitalized": re.compile(r"\bUuid\b"),
            # Acronym casing
            "url_upper": re.compile(r"\bURL\b"),
            "url_capitalized": re.compile(r"\bUrl\b"),
            "http_upper": re.compile(r"\bHTTP\b"),
            "http_capitalized": re.compile(r"\bHttp\b"),
            "json_upper": re.compile(r"\bJSON\b"),
            "json_capitalized": re.compile(r"\bJson\b"),
            "api_upper": re.compile(r"\bAPI\b"),
            "api_capitalized": re.compile(r"\bApi\b"),
            # Constant styles
            "const_screaming": re.compile(r"const\s+[A-Z][A-Z0-9_]+\s*="),
            "const_camel": re.compile(r"const\s+[A-Z][a-z]\w+\s*="),
            # Error variable naming
            "err_var": re.compile(r"\berr\s*[:=]"),
            "error_var": re.compile(r"\berror\s*[:=]"),
            "e_var": re.compile(r"\be\s*[:=]"),
            # Extended boolean prefixes
            "bool_should": re.compile(r"func\s+should[A-Z]\w*\("),
            "bool_will": re.compile(r"func\s+will[A-Z]\w*\("),
            "bool_enable": re.compile(r"func\s+enable[A-Z]\w*\("),
            # Type suffix patterns
            "type_suffix": re.compile(r"type\s+(\w+Type)\s+"),
            "prefix_type": re.compile(r"type\s+(Type\w+)\s+"),
            # --- PHASE 1: Control Flow ---
            # Guard clauses (early return on error)
            "guard_clause": re.compile(r"if\s+err\s*!=\s*nil\s*\{\s*return"),
            "nested_if": re.compile(r"if\s+[^{]+\{\s*if\s+"),
            # Switch vs if-else
            "switch_statement": re.compile(r"\bswitch\s+"),
            "if_else_chain": re.compile(r"if\s+[^{]+\{[^}]*\}\s*else\s+if"),
            # Loop styles
            "for_range": re.compile(r"for\s+\w*,?\s*\w*\s*:=\s*range\s+"),
            "for_classic": re.compile(r"for\s+\w+\s*:=\s*\d+;\s*\w+\s*<"),
            "for_infinite": re.compile(r"for\s*\{"),
            "for_condition": re.compile(r"for\s+[^{;]+\s*\{"),
            # Flow control
            "break_statement": re.compile(r"\bbreak\b"),
            "continue_statement": re.compile(r"\bcontinue\b"),
            "goto_statement": re.compile(r"\bgoto\s+\w+"),
            # Defer patterns
            "defer_immediate": re.compile(r"defer\s+func\("),
            "defer_named": re.compile(r"defer\s+\w+\("),
            "defer_cleanup": re.compile(r"defer\s+.*\.Close\("),
            # Return patterns
            "return_naked": re.compile(r"return\s*$", re.MULTILINE),
            "return_values": re.compile(r"return\s+\w"),
            # --- PHASE 1: API Design ---
            # String concatenation methods
            "string_plus": re.compile(r'"\s*\+\s*"'),
            "fmt_sprintf": re.compile(r"fmt\.Sprintf\("),
            "strings_builder": re.compile(r"strings\.Builder"),
            "strings_join": re.compile(r"strings\.Join\("),
            # Zero value usage
            "explicit_zero_string": re.compile(r'=\s*""'),
            "explicit_zero_int": re.compile(r"=\s*0\b"),
            "explicit_zero_bool": re.compile(r"=\s*false\b"),
            "explicit_zero_nil": re.compile(r"=\s*nil\b"),
            # Enum styles
            "iota_enum": re.compile(r"const\s*\([^)]*iota"),
            "string_enum": re.compile(r'const\s+\w+\s+string\s*=\s*"'),
            # Optional parameters (already have functional_option, add variadic)
            "variadic_param": re.compile(r"func\s+\w+\([^)]*\.\.\.\w+\)"),
            # --- PHASE 1: Observability ---
            # Log structure styles
            "log_json": re.compile(r"json\.Marshal\(.*log|log.*json\.Marshal"),
            "log_keyvalue": re.compile(r"log\.[A-Z]\w*\([^)]*\w+\s*:\s*\w+"),
            # HTTP status codes
            "http_status_const": re.compile(r"http\.Status\w+"),
            "http_status_magic": re.compile(r"\b[2-5]\d\d\b"),
            # Metric naming (prometheus-style)
            "metric_snake_case": re.compile(r"[a-z][a-z0-9_]+_total|[a-z][a-z0-9_]+_count"),
            "metric_camel_case": re.compile(r"[A-Z][a-z]+[A-Z]"),
            # Error codes
            "error_code_const": re.compile(r"const\s+Err\w+Code"),
            "error_code_string": re.compile(r"const\s+Err\w+\s+string"),
            # --- PHASE 2: Interface Topology ---
            "interface_def": re.compile(r"type\s+\w+\s+interface\s*\{"),
            "interface_embed": re.compile(r"^\s+\w+\s*$", re.MULTILINE),
            "interface_method": re.compile(r"^\s+\w+\([^)]*\)", re.MULTILINE),
            "interface_param": re.compile(r"func\s+\w+\([^)]*\s+\w+\s+interface\{"),
            # --- PHASE 2: Configuration Strategy ---
            "os_getenv": re.compile(r"os\.Getenv\("),
            "os_lookupenv": re.compile(r"os\.LookupEnv\("),
            "flag_string": re.compile(r"flag\.String\(|flag\.Int\(|flag\.Bool\("),
            "viper_import": re.compile(r'"github\.com/spf13/viper"'),
            "config_struct": re.compile(r"type\s+Config\s+struct"),
            "default_value": re.compile(r'=\s*getenv\w*\([^,]+,\s*"[^"]+"\)'),
            # --- PHASE 2: Dependency Injection ---
            "constructor_interface_param": re.compile(r"func\s+New\w+\([^)]*\w+\s+interface\{"),
            "interface_field": re.compile(r"^\s+\w+\s+interface\{", re.MULTILINE),
            "factory_func": re.compile(r"func\s+\w+Factory\("),
            # --- PHASE 2: Lifecycle Management ---
            "start_method": re.compile(r"func\s+\([^)]+\)\s+Start\("),
            "stop_method": re.compile(r"func\s+\([^)]+\)\s+Stop\("),
            "close_method": re.compile(r"func\s+\([^)]+\)\s+Close\("),
            "run_method": re.compile(r"func\s+\([^)]+\)\s+Run\("),
            "shutdown_method": re.compile(r"func\s+\([^)]+\)\s+Shutdown\("),
            "graceful_shutdown": re.compile(r"ctx,\s*cancel\s*:=\s*context\.WithTimeout"),
            "signal_notify": re.compile(r"signal\.Notify\("),
            "health_check": re.compile(r"func\s+\w*Health\w*\(|func\s+\w*Readiness\w*\("),
            # --- PHASE 2: Package Naming ---
            "package_stmt": re.compile(r"^package\s+(\w+)", re.MULTILINE),
            # --- PHASE 2: Architectural Patterns ---
            "repository_pattern": re.compile(r"type\s+\w+Repository\s+(interface|struct)"),
            "service_pattern": re.compile(r"type\s+\w+Service\s+(interface|struct)"),
            "handler_pattern": re.compile(r"type\s+\w+Handler\s+struct|func\s+\w+Handler\("),
            "controller_pattern": re.compile(r"type\s+\w+Controller\s+struct"),
            "middleware_func": re.compile(r"func\s+\w+Middleware\("),
            "middleware_chain": re.compile(r"http\.Handler\)\s+http\.Handler"),
            "domain_entity": re.compile(r"type\s+\w+\s+struct.*//.*entity|//.*domain"),
            "dto_pattern": re.compile(r"type\s+\w+DTO\s+struct|type\s+\w+Request\s+struct|type\s+\w+Response\s+struct"),
        }

    def _detect_layout(self):
        """Detect project layout structure."""
        p = self.profile
        if (self.root / "cmd").exists():
            p.project_layout["has_cmd"] = 1
        if (self.root / "internal").exists():
            p.project_layout["has_internal"] = 1
        if (self.root / "pkg").exists():
            p.project_layout["has_pkg"] = 1
        if (self.root / "api").exists():
            p.project_layout["has_api"] = 1

    def scan(self):
        """Scan repository and analyze all Go files."""
        print(f"🔭 Scanning {self.profile.repo_name} with Omni-Cartographer...")
        go_files = [p for p in self.root.rglob("*.go") if "vendor" not in p.parts]

        for i, path in enumerate(go_files):
            if (i + 1) % 50 == 0:
                print(f"   Analyzed {i + 1}/{len(go_files)} files...")
            self._analyze_file(path)

        print(f"✓ Analysis complete: {self.profile.total_lines:,} lines analyzed\n")
        return self.generate_report()

    def _analyze_file(self, path: Path):
        """Analyze a single Go file for all patterns."""
        try:
            content = path.read_text(errors="ignore")
        except:
            return

        p = self.profile
        p.files_analyzed += 1
        p.total_lines += len(content.splitlines())

        is_test = "_test.go" in path.name
        is_cmd = "cmd/" in str(path)
        is_internal = "internal/" in str(path)
        is_pkg = "pkg/" in str(path)

        # --- 1. Shadow Constitution ---
        for match in self.R["nolint"].findall(content):
            for rule in match.split(","):
                p.linter_suppressions[rule.strip()] += 1

        for match in self.R["todo_markers"].findall(content):
            p.todo_markers[match] += 1

        if self.R["todo_with_issue"].search(content):
            p.todo_markers["with_issue"] += 1
        if self.R["todo_with_author"].search(content):
            p.todo_markers["with_author"] += 1

        # --- 2. Context Hygiene ---
        bg_count = len(self.R["ctx_background"].findall(content))
        if is_cmd or is_test:
            p.context_creation["safe_background"] += bg_count
        else:
            p.context_creation["suspicious_background"] += bg_count

        p.context_creation["todo"] += len(self.R["ctx_todo"].findall(content))
        p.context_patterns["with_cancel"] += len(self.R["ctx_with_cancel"].findall(content))
        p.context_patterns["with_timeout"] += len(self.R["ctx_with_timeout"].findall(content))
        p.context_patterns["with_deadline"] += len(self.R["ctx_with_deadline"].findall(content))
        p.context_patterns["with_value"] += len(self.R["ctx_with_value"].findall(content))

        p.variable_abbreviations["ctx"] += len(self.R["ctx_param"].findall(content))
        p.variable_abbreviations["context"] += len(self.R["context_param"].findall(content))

        # --- 3. Time Management ---
        p.time_patterns["time_now"] += len(self.R["time_now"].findall(content))
        if self.R["clock_interface"].search(content):
            p.time_patterns["clock_interface"] += 1
        p.time_patterns["constants"] += len(self.R["time_constants"].findall(content))

        # --- 4. Dangerous Functions ---
        panic_count = len(self.R["panic_call"].findall(content))
        if is_test:
            p.dangerous_funcs["panic_in_test"] += panic_count
        else:
            p.dangerous_funcs["panic_in_production"] += panic_count

        p.dangerous_funcs["log_fatal"] += len(self.R["log_fatal"].findall(content))
        p.dangerous_funcs["os_exit"] += len(self.R["os_exit"].findall(content))
        p.dangerous_funcs["init_functions"] += len(self.R["init_func"].findall(content))
        p.global_state["global_vars"] += len(self.R["global_var"].findall(content))

        # --- 5. Modern Go ---
        p.go_version_signals["interface{}"] += len(self.R["interface_empty"].findall(content))
        p.go_version_signals["any"] += len(self.R["any_keyword"].findall(content))
        p.go_version_signals["generic_func"] += len(self.R["generic_func"].findall(content))
        p.go_version_signals["generic_type"] += len(self.R["generic_type"].findall(content))

        # Slices functions
        p.slices_functions["Sort"] += len(self.R["slices_sort"].findall(content))
        p.slices_functions["Compact"] += len(self.R["slices_compact"].findall(content))
        p.slices_functions["Contains"] += len(self.R["slices_contains"].findall(content))
        p.slices_functions["Equal"] += len(self.R["slices_equal"].findall(content))
        p.slices_functions["Clone"] += len(self.R["slices_clone"].findall(content))
        p.slices_functions["Index"] += len(self.R["slices_index"].findall(content))
        p.slices_functions["Delete"] += len(self.R["slices_delete"].findall(content))
        p.slices_functions["Reverse"] += len(self.R["slices_reverse"].findall(content))

        # Maps functions
        p.maps_functions["Clone"] += len(self.R["maps_clone"].findall(content))
        p.maps_functions["Equal"] += len(self.R["maps_equal"].findall(content))
        p.maps_functions["Copy"] += len(self.R["maps_copy"].findall(content))

        # CMP package
        p.cmp_usage["Compare"] += len(self.R["cmp_compare"].findall(content))
        p.cmp_usage["Or"] += len(self.R["cmp_or"].findall(content))
        p.cmp_usage["Less"] += len(self.R["cmp_less"].findall(content))

        # Builtins
        p.builtin_minmax["min"] += len(self.R["min_builtin"].findall(content))
        p.builtin_minmax["max"] += len(self.R["max_builtin"].findall(content))
        p.builtin_minmax["clear"] += len(self.R["clear_builtin"].findall(content))

        # --- 6. Anti-patterns ---
        p.anti_patterns["manual_contains"] += len(self.R["manual_contains"].findall(content))
        p.anti_patterns["manual_dedup"] += len(self.R["manual_dedup"].findall(content))
        p.anti_patterns["math_min_int"] += len(self.R["math_min_int"].findall(content))
        p.anti_patterns["manual_map_copy"] += len(self.R["manual_map_copy"].findall(content))

        # --- 7. Project Architecture ---
        if is_cmd:
            p.project_layout["cmd_files"] = p.project_layout.get("cmd_files", 0) + 1
        elif is_internal:
            p.project_layout["internal_files"] = p.project_layout.get("internal_files", 0) + 1
        elif is_pkg:
            p.project_layout["pkg_files"] = p.project_layout.get("pkg_files", 0) + 1

        # --- 8. Constructors ---
        p.constructor_patterns["New"] += len(self.R["new_constructor"].findall(content))
        p.constructor_patterns["Create"] += len(self.R["create_constructor"].findall(content))
        p.constructor_patterns["Must"] += len(self.R["must_constructor"].findall(content))
        p.constructor_sigs["error_return"] += len(self.R["constructor_error"].findall(content))
        p.builder_patterns["functional_options"] += len(self.R["functional_option"].findall(content))

        # --- 9. Error Handling ---
        p.error_wrapping["fmt_errorf_w"] += len(self.R["fmt_errorf_w"].findall(content))
        p.error_wrapping["fmt_errorf_v"] += len(self.R["fmt_errorf_v"].findall(content))

        for match in self.R["error_msg"].finditer(content):
            msg = match.group(1).lower()
            if msg.startswith("cannot"):
                p.error_messages["cannot"] += 1
            elif msg.startswith("failed"):
                p.error_messages["failed"] += 1
            elif "while" in msg:
                p.error_messages["while"] += 1

        p.error_types["sentinel"] += len(self.R["sentinel_error"].findall(content))
        p.error_types["custom"] += len(self.R["custom_error_type"].findall(content))
        p.error_checking["errors_is"] += len(self.R["errors_is"].findall(content))
        p.error_checking["errors_as"] += len(self.R["errors_as"].findall(content))

        # --- 10. Logging ---
        if self.R["logrus_import"].search(content):
            p.log_libraries["logrus"] += 1
        if self.R["zap_import"].search(content):
            p.log_libraries["zap"] += 1
        if self.R["slog_import"].search(content):
            p.log_libraries["slog"] += 1

        p.log_levels["Debug"] += len(self.R["log_debug"].findall(content))
        p.log_levels["Info"] += len(self.R["log_info"].findall(content))
        p.log_levels["Warn"] += len(self.R["log_warn"].findall(content))
        p.log_levels["Error"] += len(self.R["log_error"].findall(content))
        p.log_patterns["structured"] += len(self.R["log_with_fields"].findall(content))

        # --- 11. Testing ---
        if is_test:
            if self.R["testify_import"].search(content):
                p.test_frameworks["testify"] += 1
            if self.R["ginkgo_import"].search(content):
                p.test_frameworks["ginkgo"] += 1
            else:
                p.test_frameworks["standard"] += 1

            p.test_patterns["table_driven"] += len(self.R["table_driven"].findall(content))
            p.test_patterns["t_run"] += len(self.R["t_run"].findall(content))
            p.test_patterns["t_helper"] += len(self.R["t_helper"].findall(content))
            p.test_patterns["t_parallel"] += len(self.R["t_parallel"].findall(content))
            p.test_coverage["example"] += len(self.R["example_test"].findall(content))
            p.test_coverage["benchmark"] += len(self.R["benchmark_test"].findall(content))

        # --- 12. Naming Conventions ---
        p.variable_abbreviations["cfg"] += len(self.R["var_cfg"].findall(content))
        p.variable_abbreviations["db"] += len(self.R["var_db"].findall(content))
        p.variable_abbreviations["tx"] += len(self.R["var_tx"].findall(content))

        p.boolean_naming["is"] += len(self.R["bool_is"].findall(content))
        p.boolean_naming["has"] += len(self.R["bool_has"].findall(content))
        p.boolean_naming["can"] += len(self.R["bool_can"].findall(content))

        p.function_prefixes["Get"] += len(self.R["func_get"].findall(content))
        p.function_prefixes["Set"] += len(self.R["func_set"].findall(content))
        p.function_prefixes["Handle"] += len(self.R["func_handle"].findall(content))

        # --- 13. Core Patterns ---
        p.struct_init["keyed"] += len(self.R["struct_keyed"].findall(content))
        p.struct_init["unkeyed"] += len(self.R["struct_unkeyed"].findall(content))
        p.slice_alloc["prealloc"] += len(self.R["slice_prealloc"].findall(content))
        p.slice_alloc["len_only"] += len(self.R["slice_len_only"].findall(content))
        p.receiver_type["pointer"] += len(self.R["recv_ptr"].findall(content))
        p.receiver_type["value"] += len(self.R["recv_val"].findall(content))
        p.receiver_naming["single_letter"] += len(self.R["recv_single"].findall(content))
        p.mutex_usage["embedded"] += len(self.R["mutex_embed"].findall(content))
        p.mutex_usage["field"] += len(self.R["mutex_field"].findall(content))
        p.goroutine_patterns["anonymous"] += len(self.R["go_func_anon"].findall(content))
        p.goroutine_patterns["named"] += len(self.R["go_func_named"].findall(content))

        # --- 14. Documentation ---
        if not is_test:
            p.documentation["godoc"] += len(self.R["godoc_exported"].findall(content))
            if self.R["package_doc"].search(content):
                p.documentation["package_doc"] += 1

        # --- 15. HTTP Patterns ---
        p.http_patterns["json_marshal"] += len(self.R["json_marshal"].findall(content))
        p.http_patterns["json_encoder"] += len(self.R["json_encoder"].findall(content))

        # --- PHASE 1: Extended Naming Dialects ---
        p.getter_style["with_get"] += len(self.R["getter_with_get"].findall(content))
        p.getter_style["without_get"] += len(self.R["getter_without_get"].findall(content))

        p.id_convention["ID"] += len(self.R["id_upper"].findall(content))
        p.id_convention["Id"] += len(self.R["id_capitalized"].findall(content))
        p.id_convention["UUID"] += len(self.R["uuid_upper"].findall(content))
        p.id_convention["Uuid"] += len(self.R["uuid_capitalized"].findall(content))

        p.acronym_casing["URL"] += len(self.R["url_upper"].findall(content))
        p.acronym_casing["Url"] += len(self.R["url_capitalized"].findall(content))
        p.acronym_casing["HTTP"] += len(self.R["http_upper"].findall(content))
        p.acronym_casing["Http"] += len(self.R["http_capitalized"].findall(content))
        p.acronym_casing["JSON"] += len(self.R["json_upper"].findall(content))
        p.acronym_casing["Json"] += len(self.R["json_capitalized"].findall(content))
        p.acronym_casing["API"] += len(self.R["api_upper"].findall(content))
        p.acronym_casing["Api"] += len(self.R["api_capitalized"].findall(content))

        p.constant_style["SCREAMING_SNAKE"] += len(self.R["const_screaming"].findall(content))
        p.constant_style["CamelCase"] += len(self.R["const_camel"].findall(content))

        p.error_var_naming["err"] += len(self.R["err_var"].findall(content))
        p.error_var_naming["error"] += len(self.R["error_var"].findall(content))
        p.error_var_naming["e"] += len(self.R["e_var"].findall(content))

        p.boolean_extended["should"] += len(self.R["bool_should"].findall(content))
        p.boolean_extended["will"] += len(self.R["bool_will"].findall(content))
        p.boolean_extended["enable"] += len(self.R["bool_enable"].findall(content))

        p.type_suffix_usage["TypeSuffix"] += len(self.R["type_suffix"].findall(content))
        p.type_suffix_usage["TypePrefix"] += len(self.R["prefix_type"].findall(content))

        # --- PHASE 1: Control Flow ---
        p.guard_clauses["guard"] += len(self.R["guard_clause"].findall(content))
        p.guard_clauses["nested"] += len(self.R["nested_if"].findall(content))

        p.switch_vs_if["switch"] += len(self.R["switch_statement"].findall(content))
        p.switch_vs_if["if_else_chain"] += len(self.R["if_else_chain"].findall(content))

        p.loop_styles["for_range"] += len(self.R["for_range"].findall(content))
        p.loop_styles["for_classic"] += len(self.R["for_classic"].findall(content))
        p.loop_styles["for_infinite"] += len(self.R["for_infinite"].findall(content))
        p.loop_styles["for_condition"] += len(self.R["for_condition"].findall(content))

        p.flow_control["break"] += len(self.R["break_statement"].findall(content))
        p.flow_control["continue"] += len(self.R["continue_statement"].findall(content))
        p.flow_control["goto"] += len(self.R["goto_statement"].findall(content))

        p.defer_patterns["immediate"] += len(self.R["defer_immediate"].findall(content))
        p.defer_patterns["named"] += len(self.R["defer_named"].findall(content))
        p.defer_patterns["cleanup"] += len(self.R["defer_cleanup"].findall(content))

        p.return_style["naked"] += len(self.R["return_naked"].findall(content))
        p.return_style["with_values"] += len(self.R["return_values"].findall(content))

        # --- PHASE 1: API Design ---
        p.string_concat_methods["plus"] += len(self.R["string_plus"].findall(content))
        p.string_concat_methods["sprintf"] += len(self.R["fmt_sprintf"].findall(content))
        p.string_concat_methods["builder"] += len(self.R["strings_builder"].findall(content))
        p.string_concat_methods["join"] += len(self.R["strings_join"].findall(content))

        p.zero_value_usage["string"] += len(self.R["explicit_zero_string"].findall(content))
        p.zero_value_usage["int"] += len(self.R["explicit_zero_int"].findall(content))
        p.zero_value_usage["bool"] += len(self.R["explicit_zero_bool"].findall(content))
        p.zero_value_usage["nil"] += len(self.R["explicit_zero_nil"].findall(content))

        p.enum_styles["iota"] += len(self.R["iota_enum"].findall(content))
        p.enum_styles["string_const"] += len(self.R["string_enum"].findall(content))

        p.optional_params["variadic"] += len(self.R["variadic_param"].findall(content))

        # --- PHASE 1: Observability ---
        p.log_structure_style["json"] += len(self.R["log_json"].findall(content))
        p.log_structure_style["keyvalue"] += len(self.R["log_keyvalue"].findall(content))

        p.http_status_style["const"] += len(self.R["http_status_const"].findall(content))
        p.http_status_style["magic_number"] += len(self.R["http_status_magic"].findall(content))

        p.metric_naming["snake_case"] += len(self.R["metric_snake_case"].findall(content))
        p.metric_naming["camel_case"] += len(self.R["metric_camel_case"].findall(content))

        p.error_codes["const"] += len(self.R["error_code_const"].findall(content))
        p.error_codes["string"] += len(self.R["error_code_string"].findall(content))

        # --- PHASE 2: Interface Topology ---
        # Detect interface definitions and count methods
        for interface_match in self.R["interface_def"].finditer(content):
            # Extract interface body
            start = interface_match.end()
            brace_count = 1
            end = start
            while end < len(content) and brace_count > 0:
                if content[end] == "{":
                    brace_count += 1
                elif content[end] == "}":
                    brace_count -= 1
                end += 1

            if brace_count == 0:
                interface_body = content[start : end - 1]
                method_count = len(self.R["interface_method"].findall(interface_body))
                embed_count = len(self.R["interface_embed"].findall(interface_body))

                if method_count < 3:
                    p.interface_sizes["small"] += 1
                elif method_count <= 7:
                    p.interface_sizes["medium"] += 1
                else:
                    p.interface_sizes["large"] += 1

                if embed_count > 0:
                    p.interface_composition["embedded"] += embed_count

        p.interface_params["interface_typed"] += len(self.R["interface_param"].findall(content))

        # --- PHASE 2: Configuration Strategy ---
        p.config_sources["env_vars"] += len(self.R["os_getenv"].findall(content))
        p.config_sources["env_lookup"] += len(self.R["os_lookupenv"].findall(content))
        p.config_sources["flags"] += len(self.R["flag_string"].findall(content))

        if self.R["viper_import"].search(content):
            p.config_sources["viper"] += 1

        p.config_structs["config_type"] += len(self.R["config_struct"].findall(content))
        p.env_var_patterns["with_default"] += len(self.R["default_value"].findall(content))

        # --- PHASE 2: Dependency Injection ---
        p.constructor_deps["interface_params"] += len(self.R["constructor_interface_param"].findall(content))
        p.interface_deps["fields"] += len(self.R["interface_field"].findall(content))
        p.factory_patterns["factory_funcs"] += len(self.R["factory_func"].findall(content))

        # --- PHASE 2: Lifecycle Management ---
        p.lifecycle_methods["Start"] += len(self.R["start_method"].findall(content))
        p.lifecycle_methods["Stop"] += len(self.R["stop_method"].findall(content))
        p.lifecycle_methods["Close"] += len(self.R["close_method"].findall(content))
        p.lifecycle_methods["Run"] += len(self.R["run_method"].findall(content))
        p.lifecycle_methods["Shutdown"] += len(self.R["shutdown_method"].findall(content))

        p.shutdown_patterns["graceful"] += len(self.R["graceful_shutdown"].findall(content))
        p.shutdown_patterns["signal_handling"] += len(self.R["signal_notify"].findall(content))
        p.health_checks["endpoints"] += len(self.R["health_check"].findall(content))

        # --- PHASE 2: Package Naming ---
        package_match = self.R["package_stmt"].search(content)
        if package_match:
            pkg_name = package_match.group(1)
            if pkg_name.endswith("s") and pkg_name != "strings":
                p.package_naming["plural"] += 1
            elif pkg_name not in ["main", "test"]:
                p.package_naming["singular"] += 1

        # --- PHASE 2: Architectural Patterns ---
        p.arch_patterns["repository"] += len(self.R["repository_pattern"].findall(content))
        p.arch_patterns["service"] += len(self.R["service_pattern"].findall(content))
        p.arch_patterns["handler"] += len(self.R["handler_pattern"].findall(content))
        p.arch_patterns["controller"] += len(self.R["controller_pattern"].findall(content))

        p.middleware_patterns["functions"] += len(self.R["middleware_func"].findall(content))
        p.middleware_patterns["chains"] += len(self.R["middleware_chain"].findall(content))

        p.layer_separation["domain"] += len(self.R["domain_entity"].findall(content))
        p.layer_separation["dto"] += len(self.R["dto_pattern"].findall(content))

    def generate_report(self):
        """Generate comprehensive report with all patterns."""
        p = self.profile

        # Phase 3: Compute style vector before generating report
        style_vector = self._compute_style_vector()
        p.style_vector = style_vector  # Store in profile

        return {
            "metadata": {"repo": p.repo_name, "files": p.files_analyzed, "lines": f"{p.total_lines:,}"},
            "style_vector": style_vector,  # Phase 3: Include style vector in report
            "stats": {
                "repo_name": p.repo_name,
                "files_analyzed": p.files_analyzed,
                "total_lines": p.total_lines,
                "linter_suppressions": dict(p.linter_suppressions),
                "todo_markers": dict(p.todo_markers),
                "context_creation": dict(p.context_creation),
                "context_patterns": dict(p.context_patterns),
                "time_patterns": dict(p.time_patterns),
                "dangerous_funcs": dict(p.dangerous_funcs),
                "global_state": dict(p.global_state),
                "go_version_signals": dict(p.go_version_signals),
                "slices_functions": dict(p.slices_functions),
                "maps_functions": dict(p.maps_functions),
                "cmp_usage": dict(p.cmp_usage),
                "builtin_minmax": dict(p.builtin_minmax),
                "anti_patterns": dict(p.anti_patterns),
                "project_layout": dict(p.project_layout),
                "constructor_patterns": dict(p.constructor_patterns),
                "constructor_sigs": dict(p.constructor_sigs),
                "builder_patterns": dict(p.builder_patterns),
                "error_wrapping": dict(p.error_wrapping),
                "error_messages": dict(p.error_messages),
                "error_types": dict(p.error_types),
                "error_checking": dict(p.error_checking),
                "log_libraries": dict(p.log_libraries),
                "log_levels": dict(p.log_levels),
                "log_patterns": dict(p.log_patterns),
                "test_frameworks": dict(p.test_frameworks),
                "test_patterns": dict(p.test_patterns),
                "test_coverage": dict(p.test_coverage),
                "variable_abbreviations": dict(p.variable_abbreviations),
                "receiver_naming": dict(p.receiver_naming),
                "function_prefixes": dict(p.function_prefixes),
                "boolean_naming": dict(p.boolean_naming),
                "struct_init": dict(p.struct_init),
                "slice_alloc": dict(p.slice_alloc),
                "receiver_type": dict(p.receiver_type),
                "mutex_usage": dict(p.mutex_usage),
                "goroutine_patterns": dict(p.goroutine_patterns),
                "documentation": dict(p.documentation),
                "http_patterns": dict(p.http_patterns),
                # Phase 1 metrics
                "getter_style": dict(p.getter_style),
                "id_convention": dict(p.id_convention),
                "acronym_casing": dict(p.acronym_casing),
                "constant_style": dict(p.constant_style),
                "error_var_naming": dict(p.error_var_naming),
                "boolean_extended": dict(p.boolean_extended),
                "type_suffix_usage": dict(p.type_suffix_usage),
                "guard_clauses": dict(p.guard_clauses),
                "switch_vs_if": dict(p.switch_vs_if),
                "loop_styles": dict(p.loop_styles),
                "flow_control": dict(p.flow_control),
                "defer_patterns": dict(p.defer_patterns),
                "return_style": dict(p.return_style),
                "string_concat_methods": dict(p.string_concat_methods),
                "zero_value_usage": dict(p.zero_value_usage),
                "enum_styles": dict(p.enum_styles),
                "optional_params": dict(p.optional_params),
                "log_structure_style": dict(p.log_structure_style),
                "http_status_style": dict(p.http_status_style),
                "metric_naming": dict(p.metric_naming),
                "error_codes": dict(p.error_codes),
                # Phase 2 metrics
                "interface_sizes": dict(p.interface_sizes),
                "interface_composition": dict(p.interface_composition),
                "interface_params": dict(p.interface_params),
                "config_sources": dict(p.config_sources),
                "env_var_patterns": dict(p.env_var_patterns),
                "flag_patterns": dict(p.flag_patterns),
                "config_structs": dict(p.config_structs),
                "constructor_deps": dict(p.constructor_deps),
                "interface_deps": dict(p.interface_deps),
                "factory_patterns": dict(p.factory_patterns),
                "lifecycle_methods": dict(p.lifecycle_methods),
                "shutdown_patterns": dict(p.shutdown_patterns),
                "cleanup_patterns": dict(p.cleanup_patterns),
                "health_checks": dict(p.health_checks),
                "package_naming": dict(p.package_naming),
                "package_patterns": dict(p.package_patterns),
                "arch_patterns": dict(p.arch_patterns),
                "middleware_patterns": dict(p.middleware_patterns),
                "layer_separation": dict(p.layer_separation),
            },
            "derived_rules": self._derive_rules(),
        }

    def _derive_rules(self) -> List[Dict]:
        """Multi-tier rule derivation: HIGH/MEDIUM/EMERGING/ANTI/SHADOW."""
        rules = []
        p = self.profile

        def pct(counter, key, total_override=None):
            """Calculate percentage with minimum threshold."""
            total = total_override or sum(counter.values())
            if total < 5:
                return 0
            return (counter[key] / total) * 100

        # --- HIGH CONFIDENCE RULES (>85% consistency) ---

        # Struct literals
        keyed_pct = pct(p.struct_init, "keyed")
        if keyed_pct > 85:
            rules.append(
                {
                    "category": "style",
                    "confidence": "HIGH",
                    "rule": "Use keyed struct literals (Foo{Bar: 1})",
                    "evidence": f"{keyed_pct:.0f}% of {sum(p.struct_init.values())} struct literals are keyed",
                    "adoption_rate": f"{p.struct_init['keyed']}/{sum(p.struct_init.values())}",
                }
            )

        # Pointer receivers
        ptr_pct = pct(p.receiver_type, "pointer")
        if ptr_pct > 85:
            rules.append(
                {
                    "category": "design",
                    "confidence": "HIGH",
                    "rule": "Use pointer receivers (*T) for methods",
                    "evidence": f"{ptr_pct:.0f}% of {sum(p.receiver_type.values())} receivers are pointers",
                    "adoption_rate": f"{p.receiver_type['pointer']}/{sum(p.receiver_type.values())}",
                }
            )

        # Error messages dialect
        if sum(p.error_messages.values()) >= 10:
            cannot_pct = pct(p.error_messages, "cannot")
            failed_pct = pct(p.error_messages, "failed")

            if cannot_pct > 70:
                rules.append(
                    {
                        "category": "style",
                        "confidence": "HIGH",
                        "rule": 'Error messages should use "cannot <verb>" format',
                        "evidence": f'{cannot_pct:.0f}% of {sum(p.error_messages.values())} error messages use "cannot"',
                        "adoption_rate": f"{p.error_messages['cannot']}/{sum(p.error_messages.values())}",
                    }
                )
            elif failed_pct > 70:
                rules.append(
                    {
                        "category": "style",
                        "confidence": "HIGH",
                        "rule": 'Error messages should use "failed to <verb>" format',
                        "evidence": f'{failed_pct:.0f}% of {sum(p.error_messages.values())} error messages use "failed"',
                        "adoption_rate": f"{p.error_messages['failed']}/{sum(p.error_messages.values())}",
                    }
                )

        # Context variable naming
        if p.variable_abbreviations["ctx"] > 0 or p.variable_abbreviations["context"] > 0:
            ctx_total = p.variable_abbreviations["ctx"] + p.variable_abbreviations["context"]
            ctx_pct = (p.variable_abbreviations["ctx"] / ctx_total * 100) if ctx_total > 0 else 0
            if ctx_pct > 85:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": 'Use "ctx" not "context" for context.Context variables',
                        "evidence": f"{ctx_pct:.0f}% use 'ctx' ({p.variable_abbreviations['ctx']}/{ctx_total})",
                    }
                )

        # --- SAFETY RULES ---

        # Panic usage
        if p.dangerous_funcs["panic_in_production"] == 0 and p.files_analyzed > 20:
            rules.append(
                {
                    "category": "safety",
                    "confidence": "HIGH",
                    "rule": "Do not use panic() in production code; return errors",
                    "evidence": f"0 panics in {p.files_analyzed} production files",
                }
            )
        elif p.dangerous_funcs["panic_in_production"] > 0:
            rules.append(
                {
                    "category": "safety",
                    "confidence": "MEDIUM",
                    "type": "violation",
                    "rule": f"VIOLATION: Found {p.dangerous_funcs['panic_in_production']} panic() calls in production code",
                    "evidence": "panic() should be avoided; use error returns instead",
                }
            )

        # Init functions
        if p.dangerous_funcs["init_functions"] == 0 and p.files_analyzed > 20:
            rules.append(
                {
                    "category": "architecture",
                    "confidence": "HIGH",
                    "rule": "Do not use init() functions",
                    "evidence": f"0 init() functions found in {p.files_analyzed} files",
                }
            )
        elif p.dangerous_funcs["init_functions"] > 0 and p.dangerous_funcs["init_functions"] < 5:
            rules.append(
                {
                    "category": "architecture",
                    "confidence": "MEDIUM",
                    "rule": "Minimize init() function usage",
                    "evidence": f"{p.dangerous_funcs['init_functions']} init() functions found (use sparingly)",
                }
            )

        # Log.Fatal usage
        if p.dangerous_funcs["log_fatal"] > 0:
            rules.append(
                {
                    "category": "safety",
                    "confidence": "MEDIUM",
                    "type": "anti_pattern",
                    "rule": f"ANTI-PATTERN: Found {p.dangerous_funcs['log_fatal']} log.Fatal() calls",
                    "evidence": "log.Fatal() prevents defer cleanup; return errors to main()",
                }
            )

        # Embedded mutexes
        if p.mutex_usage["embedded"] == 0 and p.mutex_usage["field"] > 0:
            rules.append(
                {
                    "category": "safety",
                    "confidence": "HIGH",
                    "rule": "Never embed sync.Mutex; use named field",
                    "evidence": f"0 embedded mutexes, {p.mutex_usage['field']} as fields",
                }
            )
        elif p.mutex_usage["embedded"] > 0:
            rules.append(
                {
                    "category": "safety",
                    "confidence": "HIGH",
                    "type": "violation",
                    "rule": f"VIOLATION: Found {p.mutex_usage['embedded']} embedded mutexes",
                    "evidence": "Embedded mutexes can be accidentally copied; use named fields",
                }
            )

        # --- CONTEXT HYGIENE RULES ---

        if p.context_creation["suspicious_background"] > 0:
            severity = "HIGH" if p.context_creation["suspicious_background"] < 5 else "MEDIUM"
            rules.append(
                {
                    "category": "context",
                    "confidence": severity,
                    "type": "violation",
                    "rule": f"VIOLATION: Found {p.context_creation['suspicious_background']} context.Background() in business logic",
                    "evidence": "Use context.Background() only in main() or tests; propagate ctx parameter",
                    "safe_usage": f"Found {p.context_creation['safe_background']} safe uses in cmd/tests",
                }
            )
        elif p.context_creation["safe_background"] > 5 and p.context_creation["suspicious_background"] == 0:
            rules.append(
                {
                    "category": "context",
                    "confidence": "HIGH",
                    "rule": "Use context.Background() only in main() or tests",
                    "evidence": f"{p.context_creation['safe_background']} safe uses, 0 violations",
                }
            )

        if p.context_creation["todo"] > 0:
            rules.append(
                {
                    "category": "context",
                    "confidence": "MEDIUM",
                    "type": "anti_pattern",
                    "rule": f"ANTI-PATTERN: Found {p.context_creation['todo']} context.TODO() calls",
                    "evidence": "context.TODO() should be replaced with proper context propagation",
                }
            )

        # --- SHADOW CONSTITUTION (What They Ignore) ---

        top_suppressions = p.linter_suppressions.most_common(5)
        for linter_rule, count in top_suppressions:
            if count >= 5:
                rules.append(
                    {
                        "category": "linter_config",
                        "confidence": "HIGH",
                        "type": "shadow_rule",
                        "rule": f"TEAM STANDARD: Suppress linter rule '{linter_rule}'",
                        "evidence": f"Explicitly suppressed {count} times via //nolint:{linter_rule}",
                        "interpretation": f"Team has decided to ignore {linter_rule} warnings",
                    }
                )

        # --- MODERN GO ADOPTION ---

        # any vs interface{}
        if sum(p.go_version_signals.values()) > 10:
            any_pct = pct(p.go_version_signals, "any")
            if any_pct > 80:
                rules.append(
                    {
                        "category": "modern_go",
                        "confidence": "HIGH",
                        "rule": 'Use "any" instead of "interface{}"',
                        "evidence": f"{any_pct:.0f}% adoption ({p.go_version_signals['any']} vs {p.go_version_signals['interface{}']})",
                    }
                )
            elif any_pct < 20 and p.go_version_signals["interface{}"] > 20:
                rules.append(
                    {
                        "category": "modern_go",
                        "confidence": "HIGH",
                        "rule": 'Use "interface{}" (legacy Go 1.17 style)',
                        "evidence": f"Pre-Go 1.18 codebase ({p.go_version_signals['interface{}']} vs {p.go_version_signals['any']})",
                    }
                )
            else:
                rules.append(
                    {
                        "category": "modern_go",
                        "confidence": "EMERGING",
                        "rule": f"INCONSISTENT: Mixed any ({p.go_version_signals['any']}) and interface{{}} ({p.go_version_signals['interface{}']})",
                        "evidence": "Consider standardizing on one syntax",
                    }
                )

        # Slices package adoption
        slices_total = sum(p.slices_functions.values())
        if slices_total > 10:
            if p.slices_functions.get("Contains", 0) > 0 and p.anti_patterns.get("manual_contains", 0) > 0:
                adopt_pct = (
                    p.slices_functions["Contains"]
                    / (p.slices_functions["Contains"] + p.anti_patterns["manual_contains"])
                    * 100
                )
                if adopt_pct > 80:
                    rules.append(
                        {
                            "category": "modern_go",
                            "confidence": "HIGH",
                            "rule": "Use slices.Contains() for membership checks",
                            "evidence": f"{adopt_pct:.0f}% adoption ({p.slices_functions['Contains']} uses, {p.anti_patterns['manual_contains']} manual loops)",
                        }
                    )

            top_slices = sorted(p.slices_functions.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_slices:
                rules.append(
                    {
                        "category": "modern_go",
                        "confidence": "MEDIUM",
                        "rule": f"Slices package adoption: {', '.join(f'slices.{k}() ({v} uses)' for k, v in top_slices)}",
                        "evidence": "Go 1.21+ features in use",
                    }
                )

        # --- CONSTRUCTOR PATTERNS ---

        if sum(p.constructor_patterns.values()) > 5:
            new_pct = pct(p.constructor_patterns, "New")
            if new_pct > 85:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Constructors use New<Type> naming pattern",
                        "evidence": f"{new_pct:.0f}% of {sum(p.constructor_patterns.values())} constructors",
                    }
                )

            if p.constructor_patterns.get("Must", 0) == 0:
                rules.append(
                    {
                        "category": "safety",
                        "confidence": "HIGH",
                        "rule": "Do not use Must*() constructors that panic",
                        "evidence": f"0 Must* constructors in {sum(p.constructor_patterns.values())} constructors",
                    }
                )
            elif p.constructor_patterns.get("Must", 0) > 0:
                rules.append(
                    {
                        "category": "safety",
                        "confidence": "MEDIUM",
                        "type": "anti_pattern",
                        "rule": f"ANTI-PATTERN: Found {p.constructor_patterns['Must']} Must*() constructors",
                        "evidence": "Must*() constructors panic on error; prefer New*() with error return",
                    }
                )

        # --- ERROR WRAPPING ---

        if sum(p.error_wrapping.values()) > 10:
            wrap_pct = pct(p.error_wrapping, "fmt_errorf_w")
            if wrap_pct > 70:
                rules.append(
                    {
                        "category": "error_handling",
                        "confidence": "HIGH",
                        "rule": 'Wrap errors with fmt.Errorf("...: %w", err)',
                        "evidence": f"{wrap_pct:.0f}% of {sum(p.error_wrapping.values())} error formats use %w",
                    }
                )
            elif wrap_pct < 30:
                rules.append(
                    {
                        "category": "error_handling",
                        "confidence": "MEDIUM",
                        "rule": "Consider adopting error wrapping with %w",
                        "evidence": f"Only {wrap_pct:.0f}% use %w ({p.error_wrapping.get('fmt_errorf_w', 0)}/{sum(p.error_wrapping.values())})",
                    }
                )

        # --- TIME MANAGEMENT ---

        if p.time_patterns.get("time_now", 0) > 10:
            if p.time_patterns.get("clock_interface", 0) == 0:
                rules.append(
                    {
                        "category": "testability",
                        "confidence": "MEDIUM",
                        "rule": f"OBSERVATION: Direct time.Now() usage ({p.time_patterns['time_now']} instances, no Clock interface)",
                        "evidence": "Consider Clock interface for testable time-dependent code",
                    }
                )
            else:
                rules.append(
                    {
                        "category": "testability",
                        "confidence": "HIGH",
                        "rule": "Use Clock interface for testable time operations",
                        "evidence": f"Clock interface detected with {p.time_patterns['time_now']} time.Now() calls",
                    }
                )

        # --- TESTING PATTERNS ---

        if sum(p.test_frameworks.values()) > 5:
            if pct(p.test_frameworks, "standard") > 70:
                rules.append(
                    {
                        "category": "testing",
                        "confidence": "HIGH",
                        "rule": "Use standard library testing package",
                        "evidence": f"{pct(p.test_frameworks, 'standard'):.0f}% of test files use standard testing",
                    }
                )
            elif p.test_frameworks.get("testify", 0) > 0:
                rules.append(
                    {
                        "category": "testing",
                        "confidence": "MEDIUM",
                        "rule": "Use testify for assertions",
                        "evidence": f"{p.test_frameworks['testify']} test files use testify",
                    }
                )

        if p.test_patterns.get("table_driven", 0) > 0:
            rules.append(
                {
                    "category": "testing",
                    "confidence": "MEDIUM",
                    "rule": "Use table-driven tests",
                    "evidence": f"{p.test_patterns['table_driven']} table-driven test instances found",
                }
            )

        # --- HTTP PATTERNS ---

        if sum(p.http_patterns.values()) > 5:
            marshal_pct = pct(p.http_patterns, "json_marshal")
            if marshal_pct > 85:
                rules.append(
                    {
                        "category": "http",
                        "confidence": "HIGH",
                        "rule": "Use json.Marshal() over json.NewEncoder() for HTTP responses",
                        "evidence": f"{marshal_pct:.0f}% use json.Marshal() ({p.http_patterns['json_marshal']}/{sum(p.http_patterns.values())})",
                    }
                )

        # --- PHASE 1: EXTENDED NAMING DIALECTS ---

        # Getter style preference
        if sum(p.getter_style.values()) >= 5:
            get_pct = pct(p.getter_style, "with_get")
            if get_pct > 80:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Getter methods use Get<Name>() prefix",
                        "evidence": f"{get_pct:.0f}% of {sum(p.getter_style.values())} getters use Get prefix",
                    }
                )
            elif get_pct < 20:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Getter methods use <Name>() without Get prefix (Go idiomatic)",
                        "evidence": f"{100 - get_pct:.0f}% of {sum(p.getter_style.values())} getters omit Get prefix",
                    }
                )

        # ID convention
        id_total = p.id_convention.get("ID", 0) + p.id_convention.get("Id", 0)
        if id_total >= 10:
            id_upper_pct = p.id_convention["ID"] / id_total * 100
            if id_upper_pct > 85:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": 'Use "ID" not "Id" for identifiers',
                        "evidence": f"{id_upper_pct:.0f}% use ID ({p.id_convention['ID']}/{id_total})",
                    }
                )
            elif id_upper_pct < 15:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": 'Use "Id" not "ID" for identifiers',
                        "evidence": f"{100 - id_upper_pct:.0f}% use Id ({p.id_convention['Id']}/{id_total})",
                    }
                )

        # Acronym casing patterns
        acronyms = {}
        for acronym in ["URL", "HTTP", "JSON", "API"]:
            upper = p.acronym_casing.get(acronym, 0)
            lower = p.acronym_casing.get(f"{acronym[0]}{acronym[1:].lower()}", 0)
            if upper + lower >= 5:
                acronyms[acronym] = (upper, lower, upper / (upper + lower) * 100 if upper + lower > 0 else 0)

        if acronyms:
            all_upper = all(pct > 80 for _, _, pct in acronyms.values())
            all_camel = all(pct < 20 for _, _, pct in acronyms.values())

            if all_upper:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Use ALL_CAPS for acronyms (URL, HTTP, JSON, API)",
                        "evidence": f"Consistent ALL_CAPS usage across {len(acronyms)} acronym types",
                    }
                )
            elif all_camel:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Use CamelCase for acronyms (Url, Http, Json, Api)",
                        "evidence": f"Consistent CamelCase usage across {len(acronyms)} acronym types",
                    }
                )

        # Constant style
        if sum(p.constant_style.values()) >= 5:
            screaming_pct = pct(p.constant_style, "SCREAMING_SNAKE")
            if screaming_pct > 70:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Use SCREAMING_SNAKE_CASE for constants",
                        "evidence": f"{screaming_pct:.0f}% of {sum(p.constant_style.values())} constants use SCREAMING_SNAKE",
                    }
                )
            elif screaming_pct < 30:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Use CamelCase for constants (Go idiomatic)",
                        "evidence": f"{100 - screaming_pct:.0f}% of {sum(p.constant_style.values())} constants use CamelCase",
                    }
                )

        # Error variable naming
        if sum(p.error_var_naming.values()) >= 20:
            err_pct = pct(p.error_var_naming, "err")
            if err_pct > 90:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": 'Use "err" for error variables',
                        "evidence": f'{err_pct:.0f}% of {sum(p.error_var_naming.values())} error variables use "err"',
                    }
                )

        # --- PHASE 1: CONTROL FLOW FLAVOR ---

        # Guard clauses vs nested ifs
        if sum(p.guard_clauses.values()) >= 10:
            guard_pct = pct(p.guard_clauses, "guard")
            if guard_pct > 70:
                rules.append(
                    {
                        "category": "control_flow",
                        "confidence": "HIGH",
                        "rule": "Prefer guard clauses (early returns) over nested ifs",
                        "evidence": f"{guard_pct:.0f}% use guard clauses ({p.guard_clauses['guard']} guard vs {p.guard_clauses['nested']} nested)",
                    }
                )

        # Switch vs if-else chains
        if sum(p.switch_vs_if.values()) >= 10:
            switch_pct = pct(p.switch_vs_if, "switch")
            if switch_pct > 60:
                rules.append(
                    {
                        "category": "control_flow",
                        "confidence": "MEDIUM",
                        "rule": "Prefer switch statements over if-else chains",
                        "evidence": f"{switch_pct:.0f}% use switch ({p.switch_vs_if['switch']} switch vs {p.switch_vs_if['if_else_chain']} if-else)",
                    }
                )

        # Loop style preference
        if sum(p.loop_styles.values()) >= 10:
            range_pct = pct(p.loop_styles, "for_range")
            if range_pct > 70:
                rules.append(
                    {
                        "category": "control_flow",
                        "confidence": "HIGH",
                        "rule": "Prefer for-range loops over classic for loops",
                        "evidence": f"{range_pct:.0f}% of {sum(p.loop_styles.values())} loops use range",
                    }
                )

        # Goto usage (flag if present)
        if p.flow_control.get("goto", 0) > 0:
            rules.append(
                {
                    "category": "control_flow",
                    "confidence": "MEDIUM",
                    "type": "observation",
                    "rule": f"OBSERVATION: Found {p.flow_control['goto']} goto statements",
                    "evidence": "Goto is rare in Go; verify if necessary for error handling",
                }
            )

        # Defer patterns
        if sum(p.defer_patterns.values()) >= 5:
            cleanup_total = sum(p.defer_patterns.values())
            cleanup_pct = p.defer_patterns.get("cleanup", 0) / cleanup_total * 100
            if cleanup_pct > 50:
                rules.append(
                    {
                        "category": "resource_management",
                        "confidence": "HIGH",
                        "rule": "Use defer for resource cleanup (Close, Unlock, etc.)",
                        "evidence": f"{cleanup_pct:.0f}% of {cleanup_total} defer calls are for cleanup",
                    }
                )

        # --- PHASE 1: API DESIGN ---

        # String concatenation methods
        if sum(p.string_concat_methods.values()) >= 10:
            concat_total = sum(p.string_concat_methods.values())
            plus_pct = pct(p.string_concat_methods, "plus")
            sprintf_pct = pct(p.string_concat_methods, "sprintf")
            builder_pct = pct(p.string_concat_methods, "builder")

            if plus_pct > 60:
                rules.append(
                    {
                        "category": "api_design",
                        "confidence": "MEDIUM",
                        "rule": "Prefer + operator for simple string concatenation",
                        "evidence": f"{plus_pct:.0f}% of {concat_total} string operations use +",
                    }
                )
            elif sprintf_pct > 50:
                rules.append(
                    {
                        "category": "api_design",
                        "confidence": "MEDIUM",
                        "rule": "Prefer fmt.Sprintf() for string formatting",
                        "evidence": f"{sprintf_pct:.0f}% of {concat_total} string operations use Sprintf",
                    }
                )

            if builder_pct > 0:
                rules.append(
                    {
                        "category": "performance",
                        "confidence": "MEDIUM",
                        "rule": f"strings.Builder used in {p.string_concat_methods['builder']} places for efficient concatenation",
                        "evidence": "Builder is preferred for loop-based string building",
                    }
                )

        # Enum styles
        if sum(p.enum_styles.values()) >= 3:
            iota_pct = pct(p.enum_styles, "iota")
            if iota_pct > 70:
                rules.append(
                    {
                        "category": "api_design",
                        "confidence": "HIGH",
                        "rule": "Use iota for enum-like constants",
                        "evidence": f"{iota_pct:.0f}% of {sum(p.enum_styles.values())} enum patterns use iota",
                    }
                )

        # --- PHASE 1: OBSERVABILITY ---

        # HTTP status code style
        if sum(p.http_status_style.values()) >= 10:
            const_pct = pct(p.http_status_style, "const")
            if const_pct > 70:
                rules.append(
                    {
                        "category": "http",
                        "confidence": "HIGH",
                        "rule": "Use http.Status* constants instead of magic numbers",
                        "evidence": f"{const_pct:.0f}% of {sum(p.http_status_style.values())} status codes use constants",
                    }
                )
            elif const_pct < 30:
                rules.append(
                    {
                        "category": "http",
                        "confidence": "MEDIUM",
                        "type": "anti_pattern",
                        "rule": "ANTI-PATTERN: Magic HTTP status numbers instead of constants",
                        "evidence": f"{100 - const_pct:.0f}% use magic numbers ({p.http_status_style['magic_number']} vs {p.http_status_style['const']} constants)",
                    }
                )

        # Metric naming conventions
        if sum(p.metric_naming.values()) >= 5:
            snake_pct = pct(p.metric_naming, "snake_case")
            if snake_pct > 70:
                rules.append(
                    {
                        "category": "observability",
                        "confidence": "HIGH",
                        "rule": "Use snake_case for Prometheus metric names",
                        "evidence": f"{snake_pct:.0f}% of {sum(p.metric_naming.values())} metrics use snake_case",
                    }
                )

        # --- PHASE 2: INTERFACE TOPOLOGY ---

        if sum(p.interface_sizes.values()) >= 5:
            small_pct = pct(p.interface_sizes, "small")
            if small_pct > 70:
                rules.append(
                    {
                        "category": "architecture",
                        "confidence": "HIGH",
                        "rule": "Prefer small interfaces (<3 methods) - Interface Segregation Principle",
                        "evidence": f"{small_pct:.0f}% of {sum(p.interface_sizes.values())} interfaces are small",
                    }
                )

            large_count = p.interface_sizes.get("large", 0)
            if large_count > 0:
                rules.append(
                    {
                        "category": "architecture",
                        "confidence": "MEDIUM",
                        "type": "observation",
                        "rule": f"OBSERVATION: Found {large_count} large interfaces (8+ methods)",
                        "evidence": "Consider splitting large interfaces for better testability",
                    }
                )

        # --- PHASE 2: CONFIGURATION STRATEGY ---

        if sum(p.config_sources.values()) >= 5:
            env_total = p.config_sources.get("env_vars", 0) + p.config_sources.get("env_lookup", 0)
            flag_total = p.config_sources.get("flags", 0)

            if env_total > flag_total * 2:
                rules.append(
                    {
                        "category": "configuration",
                        "confidence": "MEDIUM",
                        "rule": "Prefer environment variables over flags for configuration",
                        "evidence": f"{env_total} env var uses vs {flag_total} flag uses",
                    }
                )
            elif flag_total > env_total * 2:
                rules.append(
                    {
                        "category": "configuration",
                        "confidence": "MEDIUM",
                        "rule": "Prefer flags over environment variables for configuration",
                        "evidence": f"{flag_total} flag uses vs {env_total} env var uses",
                    }
                )

            if p.config_sources.get("viper", 0) > 0:
                rules.append(
                    {
                        "category": "configuration",
                        "confidence": "HIGH",
                        "rule": "Use Viper library for configuration management",
                        "evidence": "Viper library detected for config management",
                    }
                )

        # --- PHASE 2: DEPENDENCY INJECTION ---

        if p.constructor_deps.get("interface_params", 0) > 5:
            rules.append(
                {
                    "category": "architecture",
                    "confidence": "HIGH",
                    "rule": "Use constructor dependency injection with interface parameters",
                    "evidence": f"{p.constructor_deps['interface_params']} constructors accept interface dependencies",
                }
            )

        if p.interface_deps.get("fields", 0) > 10:
            rules.append(
                {
                    "category": "architecture",
                    "confidence": "MEDIUM",
                    "rule": "Store dependencies as interface-typed struct fields",
                    "evidence": f"{p.interface_deps['fields']} interface-typed fields for DI",
                }
            )

        # --- PHASE 2: LIFECYCLE MANAGEMENT ---

        lifecycle_total = sum(p.lifecycle_methods.values())
        if lifecycle_total >= 5:
            has_start = p.lifecycle_methods.get("Start", 0) > 0
            has_stop = p.lifecycle_methods.get("Stop", 0) > 0
            has_close = p.lifecycle_methods.get("Close", 0) > 0

            if has_start or has_stop:
                rules.append(
                    {
                        "category": "architecture",
                        "confidence": "HIGH",
                        "rule": "Implement explicit lifecycle methods (Start/Stop/Close)",
                        "evidence": f"{lifecycle_total} lifecycle methods: Start({p.lifecycle_methods.get('Start', 0)}), Stop({p.lifecycle_methods.get('Stop', 0)}), Close({p.lifecycle_methods.get('Close', 0)})",
                    }
                )

        if p.shutdown_patterns.get("graceful", 0) > 0:
            rules.append(
                {
                    "category": "reliability",
                    "confidence": "HIGH",
                    "rule": "Use graceful shutdown with context timeouts",
                    "evidence": f"{p.shutdown_patterns['graceful']} graceful shutdown patterns detected",
                }
            )

        if p.shutdown_patterns.get("signal_handling", 0) > 0:
            rules.append(
                {
                    "category": "reliability",
                    "confidence": "HIGH",
                    "rule": "Implement signal handling for graceful termination",
                    "evidence": f"{p.shutdown_patterns['signal_handling']} signal.Notify() usages",
                }
            )

        if p.health_checks.get("endpoints", 0) > 0:
            rules.append(
                {
                    "category": "observability",
                    "confidence": "HIGH",
                    "rule": "Implement health/readiness check endpoints",
                    "evidence": f"{p.health_checks['endpoints']} health check endpoints",
                }
            )

        # --- PHASE 2: PACKAGE NAMING ---

        if sum(p.package_naming.values()) >= 10:
            singular_pct = pct(p.package_naming, "singular")
            if singular_pct > 70:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "HIGH",
                        "rule": "Use singular package names (user not users)",
                        "evidence": f"{singular_pct:.0f}% of {sum(p.package_naming.values())} packages use singular names",
                    }
                )
            elif singular_pct < 30:
                rules.append(
                    {
                        "category": "naming",
                        "confidence": "MEDIUM",
                        "rule": "Use plural package names (users not user)",
                        "evidence": f"{100 - singular_pct:.0f}% of {sum(p.package_naming.values())} packages use plural names",
                    }
                )

        # --- PHASE 2: ARCHITECTURAL PATTERNS ---

        arch_total = sum(p.arch_patterns.values())
        if arch_total >= 5:
            patterns_found = []
            if p.arch_patterns.get("repository", 0) > 0:
                patterns_found.append(f"Repository({p.arch_patterns['repository']})")
            if p.arch_patterns.get("service", 0) > 0:
                patterns_found.append(f"Service({p.arch_patterns['service']})")
            if p.arch_patterns.get("handler", 0) > 0:
                patterns_found.append(f"Handler({p.arch_patterns['handler']})")

            if patterns_found:
                rules.append(
                    {
                        "category": "architecture",
                        "confidence": "HIGH",
                        "rule": f"Layered architecture: {', '.join(patterns_found)}",
                        "evidence": f"{arch_total} architectural pattern uses",
                    }
                )

        if p.middleware_patterns.get("functions", 0) > 0:
            rules.append(
                {
                    "category": "architecture",
                    "confidence": "MEDIUM",
                    "rule": "Use middleware pattern for cross-cutting concerns",
                    "evidence": f"{p.middleware_patterns['functions']} middleware functions",
                }
            )

        if p.layer_separation.get("dto", 0) > 0:
            rules.append(
                {
                    "category": "architecture",
                    "confidence": "MEDIUM",
                    "rule": "Separate DTOs/Request/Response types from domain entities",
                    "evidence": f"{p.layer_separation['dto']} DTO patterns detected",
                }
            )

        return rules

    def _compute_style_vector(self) -> Dict[str, float]:
        """
        Phase 3: Compute Style Vector - Multi-dimensional coding style fingerprint.

        Returns 10 composite scores (0-100) that capture the codebase's personality:
        1. Consistency Score: Pattern uniformity
        2. Modernization Score: Go 1.21+ adoption
        3. Safety Score: Avoidance of dangerous patterns
        4. Idiomaticity Score: Go conventions adherence
        5. Documentation Score: Godoc coverage
        6. Testing Maturity: Test quality and coverage
        7. Architecture Score: Layering and separation
        8. Performance Consciousness: Efficient patterns
        9. Observability Score: Logging and metrics
        10. Production Readiness: Lifecycle and health checks
        """
        p = self.profile
        vector = {}

        def safe_pct(counter, key):
            """Safe percentage calculation."""
            total = sum(counter.values())
            if total == 0:
                return 0
            return (counter.get(key, 0) / total) * 100

        def score_consistency(counter_name, preferred_key, min_samples=5):
            """Score consistency for a specific pattern (0-100)."""
            counter = getattr(p, counter_name)
            total = sum(counter.values())
            if total < min_samples:
                return 50  # Neutral score for insufficient data
            return safe_pct(counter, preferred_key)

        # 1. CONSISTENCY SCORE (0-100)
        # Measures how consistent the codebase is across naming and style patterns
        consistency_components = [
            score_consistency("struct_init", "keyed", 10),  # Keyed struct literals
            score_consistency("receiver_type", "pointer", 10),  # Pointer receivers
            score_consistency("error_var_naming", "err", 20),  # "err" for errors
            score_consistency("variable_abbreviations", "ctx", 10),  # "ctx" for context
            score_consistency("id_convention", "ID", 5),  # "ID" not "Id"
            score_consistency("guard_clauses", "guard", 10),  # Guard clauses
        ]
        vector["consistency"] = sum(c for c in consistency_components if c > 0) / max(
            1, len([c for c in consistency_components if c > 0])
        )

        # 2. MODERNIZATION SCORE (0-100)
        # Adoption of Go 1.21+ features (slices, maps, any, min/max, etc.)
        modern_signals = 0
        modern_total = 0

        # any vs interface{}
        any_count = p.go_version_signals.get("any", 0)
        interface_count = p.go_version_signals.get("interface{}", 0)
        if any_count + interface_count > 10:
            modern_signals += (any_count / (any_count + interface_count)) * 20
            modern_total += 20

        # slices package usage
        slices_usage = sum(p.slices_functions.values())
        if slices_usage > 0:
            modern_signals += min(slices_usage * 2, 20)  # Cap at 20 points
            modern_total += 20
        else:
            modern_total += 20

        # maps package usage
        maps_usage = sum(p.maps_functions.values())
        if maps_usage > 0:
            modern_signals += min(maps_usage * 5, 15)  # Cap at 15 points
            modern_total += 15
        else:
            modern_total += 15

        # builtin min/max/clear
        builtin_usage = sum(p.builtin_minmax.values())
        if builtin_usage > 0:
            modern_signals += min(builtin_usage * 5, 15)  # Cap at 15 points
            modern_total += 15
        else:
            modern_total += 15

        # generics usage
        generic_usage = p.go_version_signals.get("generic_func", 0) + p.go_version_signals.get("generic_type", 0)
        if generic_usage > 0:
            modern_signals += min(generic_usage * 5, 10)  # Cap at 10 points
            modern_total += 10
        else:
            modern_total += 10

        # Anti-patterns (subtract points)
        anti_total = sum(p.anti_patterns.values())
        if anti_total > 0:
            modern_signals -= min(anti_total * 2, 20)  # Max penalty 20 points

        vector["modernization"] = max(0, min(100, (modern_signals / max(1, modern_total)) * 100))

        # 3. SAFETY SCORE (0-100)
        # Inverse of dangerous patterns (panic, fatal, os.Exit, etc.)
        total_dangerous = (
            p.dangerous_funcs.get("panic_in_production", 0)
            + p.dangerous_funcs.get("log_fatal", 0)
            + p.dangerous_funcs.get("os_exit", 0)
            + p.mutex_usage.get("embedded", 0) * 2  # Embedded mutexes are more dangerous
            + p.context_creation.get("suspicious_background", 0)
        )

        # Normalize by lines of code (dangerous patterns per 1000 LOC)
        if p.total_lines > 0:
            dangerous_per_1k = (total_dangerous / p.total_lines) * 1000
            # Score: 100 - (dangerous_per_1k * 10), capped at 0-100
            vector["safety"] = max(0, min(100, 100 - (dangerous_per_1k * 10)))
        else:
            vector["safety"] = 50

        # 4. IDIOMATICITY SCORE (0-100)
        # How well the code follows Go idioms and conventions
        idiom_components = [
            score_consistency("error_var_naming", "err", 20),  # "err" for errors
            score_consistency("variable_abbreviations", "ctx", 10),  # "ctx" for context
            score_consistency("id_convention", "ID", 5),  # "ID" not "Id"
            score_consistency("package_naming", "singular", 10),  # Singular package names
            score_consistency("receiver_type", "pointer", 10),  # Pointer receivers
            score_consistency("guard_clauses", "guard", 10),  # Guard clauses
            score_consistency("error_wrapping", "fmt_errorf_w", 10),  # Error wrapping with %w
        ]
        vector["idiomaticity"] = sum(i for i in idiom_components if i > 0) / max(
            1, len([i for i in idiom_components if i > 0])
        )

        # 5. DOCUMENTATION SCORE (0-100)
        # Godoc coverage and documentation quality
        if p.files_analyzed > 0:
            godoc_count = p.documentation.get("godoc", 0)
            package_doc_count = p.documentation.get("package_doc", 0)

            # Estimate: ~5 exported symbols per file on average
            estimated_exports = p.files_analyzed * 5
            godoc_coverage = min(100, (godoc_count / max(1, estimated_exports)) * 100)

            # Package docs bonus
            pkg_doc_bonus = min(20, package_doc_count * 5)

            vector["documentation"] = min(100, godoc_coverage + pkg_doc_bonus)
        else:
            vector["documentation"] = 0

        # 6. TESTING MATURITY (0-100)
        # Quality and coverage of testing patterns
        test_score = 0

        # Test framework usage
        if sum(p.test_frameworks.values()) > 0:
            test_score += 20

        # Table-driven tests
        if p.test_patterns.get("table_driven", 0) > 0:
            test_score += 15

        # Subtests (t.Run)
        if p.test_patterns.get("t_run", 0) > 0:
            test_score += 15

        # Test helpers
        if p.test_patterns.get("t_helper", 0) > 0:
            test_score += 10

        # Parallel tests
        if p.test_patterns.get("t_parallel", 0) > 0:
            test_score += 10

        # Example tests
        if p.test_coverage.get("example", 0) > 0:
            test_score += 10

        # Benchmarks
        if p.test_coverage.get("benchmark", 0) > 0:
            test_score += 10

        # Testify or advanced framework
        if p.test_frameworks.get("testify", 0) > 0 or p.test_frameworks.get("ginkgo", 0) > 0:
            test_score += 10

        vector["testing_maturity"] = min(100, test_score)

        # 7. ARCHITECTURE SCORE (0-100)
        # Layering, separation of concerns, interface design
        arch_score = 0

        # Interface segregation (prefer small interfaces)
        if sum(p.interface_sizes.values()) > 0:
            small_pct = safe_pct(p.interface_sizes, "small")
            arch_score += min(30, small_pct * 0.3)  # Up to 30 points for small interfaces

        # Layered architecture patterns
        arch_total = sum(p.arch_patterns.values())
        if arch_total > 0:
            arch_score += min(20, arch_total * 5)  # Up to 20 points

        # Layer separation (DTOs vs domain)
        if p.layer_separation.get("dto", 0) > 0:
            arch_score += 10

        # Dependency injection patterns
        if p.constructor_deps.get("interface_params", 0) > 0:
            arch_score += 10

        # Middleware patterns
        if sum(p.middleware_patterns.values()) > 0:
            arch_score += 10

        # Project layout (cmd/internal structure)
        if p.project_layout.get("has_cmd", 0) > 0:
            arch_score += 10
        if p.project_layout.get("has_internal", 0) > 0:
            arch_score += 10

        vector["architecture"] = min(100, arch_score)

        # 8. PERFORMANCE CONSCIOUSNESS (0-100)
        # Use of efficient patterns (strings.Builder, preallocated slices, etc.)
        perf_score = 0

        # strings.Builder usage
        if p.string_concat_methods.get("builder", 0) > 0:
            perf_score += 20

        # Preallocated slices
        if p.slice_alloc.get("prealloc", 0) > 0:
            prealloc_pct = safe_pct(p.slice_alloc, "prealloc")
            perf_score += min(30, prealloc_pct * 0.3)

        # Use of sync.Pool (if detected)
        if p.goroutine_patterns.get("pool", 0) > 0:
            perf_score += 15

        # Avoid anti-patterns
        anti_total = sum(p.anti_patterns.values())
        if anti_total == 0:
            perf_score += 20
        else:
            perf_score += max(0, 20 - (anti_total * 2))

        # Proper mutex usage (named fields, not embedded)
        if p.mutex_usage.get("field", 0) > p.mutex_usage.get("embedded", 0):
            perf_score += 15

        vector["performance"] = min(100, perf_score)

        # 9. OBSERVABILITY SCORE (0-100)
        # Logging, metrics, structured logging, health checks
        obs_score = 0

        # Structured logging
        if p.log_patterns.get("structured", 0) > 0:
            obs_score += 25

        # Modern logging library (slog)
        if p.log_libraries.get("slog", 0) > 0:
            obs_score += 15

        # Logging levels usage
        if sum(p.log_levels.values()) > 0:
            obs_score += 15

        # Metric naming consistency
        if sum(p.metric_naming.values()) > 0:
            snake_pct = safe_pct(p.metric_naming, "snake_case")
            if snake_pct > 70:
                obs_score += 15

        # HTTP status constants over magic numbers
        if sum(p.http_status_style.values()) > 0:
            const_pct = safe_pct(p.http_status_style, "const")
            if const_pct > 50:
                obs_score += 10

        # Health check endpoints
        if p.health_checks.get("endpoints", 0) > 0:
            obs_score += 20

        vector["observability"] = min(100, obs_score)

        # 10. PRODUCTION READINESS (0-100)
        # Lifecycle management, graceful shutdown, health checks, configuration
        prod_score = 0

        # Graceful shutdown patterns
        if p.shutdown_patterns.get("graceful", 0) > 0:
            prod_score += 25

        # Signal handling
        if p.shutdown_patterns.get("signal_handling", 0) > 0:
            prod_score += 15

        # Health check endpoints
        if p.health_checks.get("endpoints", 0) > 0:
            prod_score += 20

        # Lifecycle methods (Start/Stop/Close)
        lifecycle_total = sum(p.lifecycle_methods.values())
        if lifecycle_total > 0:
            prod_score += min(20, lifecycle_total * 2)

        # Environment variable configuration (cloud-native)
        if p.config_sources.get("env_vars", 0) > 0:
            prod_score += 10

        # Error wrapping for observability
        if sum(p.error_wrapping.values()) > 0:
            wrap_pct = safe_pct(p.error_wrapping, "fmt_errorf_w")
            if wrap_pct > 80:
                prod_score += 10

        vector["production_readiness"] = min(100, prod_score)

        return vector


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 cartographer_omni.py <repo_path> [--json] [--output FILE]")
        print("\nOptions:")
        print("  --json          Output JSON only (no summary)")
        print("  --output FILE   Save report to file")
        return

    path = sys.argv[1]
    cart = OmniCartographer(path)
    report = cart.scan()

    # Handle output
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        output_file = sys.argv[idx + 1]
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"📊 Report saved to: {output_file}\n")

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)


def print_summary(report):
    """Print human-readable summary."""
    stats = report["stats"]

    print("=" * 70)
    print(f"🔭 OMNI-CARTOGRAPHER REPORT: {report['metadata']['repo']}")
    print("=" * 70)

    print("\n📊 Repository Stats:")
    print(f"  Files: {report['metadata']['files']}")
    print(f"  Lines: {report['metadata']['lines']}")

    # Phase 3: Style Vector Visualization
    if "style_vector" in report:
        print("\n🎨 Style Vector (Coding Style Fingerprint):")
        vector = report["style_vector"]

        # Define order and display names for scores
        score_order = [
            ("consistency", "Consistency"),
            ("modernization", "Modernization"),
            ("safety", "Safety"),
            ("idiomaticity", "Idiomaticity"),
            ("documentation", "Documentation"),
            ("testing_maturity", "Testing Maturity"),
            ("architecture", "Architecture"),
            ("performance", "Performance"),
            ("observability", "Observability"),
            ("production_readiness", "Production Readiness"),
        ]

        # Visual bar chart with Unicode blocks
        for key, label in score_order:
            score = vector.get(key, 0)
            bar_length = int(score / 5)  # 20 blocks = 100%
            bar = "█" * bar_length + "░" * (20 - bar_length)

            # Color coding (emoji indicators)
            if score >= 80:
                indicator = "🟢"
            elif score >= 60:
                indicator = "🟡"
            elif score >= 40:
                indicator = "🟠"
            else:
                indicator = "🔴"

            print(f"  {indicator} {label:20s} {bar} {score:5.1f}/100")

        # Overall Score
        overall = sum(vector.values()) / len(vector) if vector else 0
        print(f"\n  📈 Overall Code Quality Score: {overall:.1f}/100")

    # Shadow Constitution
    if stats["linter_suppressions"]:
        print("\n👻 Shadow Constitution (Suppressed Rules):")
        for rule, count in Counter(stats["linter_suppressions"]).most_common(5):
            print(f"  • {rule}: {count} suppressions")

    # Context Hygiene
    if stats["context_creation"]:
        print("\n🧠 Context Hygiene:")
        print(f"  • Safe Background (main/test): {stats['context_creation'].get('safe_background', 0)}")
        print(f"  • Suspicious Background (logic): {stats['context_creation'].get('suspicious_background', 0)}")
        print(f"  • context.TODO(): {stats['context_creation'].get('todo', 0)}")

    # Dangerous Functions
    if stats["dangerous_funcs"]:
        print("\n⚠️  Safety Violations:")
        print(f"  • panic() in production: {stats['dangerous_funcs'].get('panic_in_production', 0)}")
        print(f"  • log.Fatal(): {stats['dangerous_funcs'].get('log_fatal', 0)}")
        print(f"  • init() functions: {stats['dangerous_funcs'].get('init_functions', 0)}")

    # Modern Go
    if stats["go_version_signals"]:
        print("\n🆕 Modern Go Adoption:")
        print(
            f"  • 'any': {stats['go_version_signals'].get('any', 0)} | 'interface{{}}': {stats['go_version_signals'].get('interface{}', 0)}"
        )
        if stats["slices_functions"]:
            top_slices = sorted(stats["slices_functions"].items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"  • Slices: {', '.join(f'{k}({v})' for k, v in top_slices)}")

    # Error Handling
    if stats["error_messages"]:
        print("\n❌ Error Message Dialect:")
        for style, count in stats["error_messages"].items():
            print(f"  • {style}: {count}")

    # Core Patterns
    if stats["struct_init"]:
        print("\n🔧 Core Patterns:")
        print(
            f"  • Struct Literals: Keyed {stats['struct_init'].get('keyed', 0)} | Unkeyed {stats['struct_init'].get('unkeyed', 0)}"
        )
        print(
            f"  • Receivers: Pointer {stats['receiver_type'].get('pointer', 0)} | Value {stats['receiver_type'].get('value', 0)}"
        )
        print(
            f"  • Mutexes: Embedded {stats['mutex_usage'].get('embedded', 0)} | Field {stats['mutex_usage'].get('field', 0)}"
        )

    # Derived Rules
    print(f"\n🎯 Derived Rules ({len(report['derived_rules'])}):\n")

    # Group rules by type
    high_rules = [
        r
        for r in report["derived_rules"]
        if r.get("confidence") == "HIGH" and r.get("type") != "violation" and r.get("type") != "shadow_rule"
    ]
    violations = [r for r in report["derived_rules"] if r.get("type") == "violation"]
    shadow_rules = [r for r in report["derived_rules"] if r.get("type") == "shadow_rule"]
    other_rules = [
        r for r in report["derived_rules"] if r not in high_rules and r not in violations and r not in shadow_rules
    ]

    if high_rules:
        print("  ✅ HIGH CONFIDENCE STANDARDS:")
        for r in high_rules:
            print(f"    [{r['category']}] {r['rule']}")
            print(f"      Evidence: {r['evidence']}")

    if violations:
        print("\n  ⛔ VIOLATIONS DETECTED:")
        for r in violations:
            print(f"    [{r['category']}] {r['rule']}")
            print(f"      {r['evidence']}")

    if shadow_rules:
        print("\n  🙈 SHADOW CONSTITUTION (Team Accepts):")
        for r in shadow_rules:
            print(f"    {r['rule']}")
            print(f"      {r['evidence']}")

    if other_rules:
        print("\n  📋 OTHER PATTERNS:")
        for r in other_rules:
            print(f"    [{r['category']}] {r['rule']}")
            print(f"      {r['evidence']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
