#!/usr/bin/env python3
"""
Security Review Scanner — deterministic regex-based security scan.

Scans source files for hardcoded secrets, injection vulnerabilities, unsafe
deserialization, XSS sinks, weak crypto, disabled TLS, and dangerous function
calls using pattern matching. Detection parity with Anthropic's
``security-guidance`` plugin deterministic layer, plus our own secret/SQLi/IP
rules. Stdlib-only (PyYAML optional, used only if importable for custom rules).

Usage:
    python3 scripts/security-review-scan.py --files file1.py file2.go
    python3 scripts/security-review-scan.py --files src/*.py --format json
    python3 scripts/security-review-scan.py --staged --format json
    python3 scripts/security-review-scan.py --help

Custom rules (optional, additive — built-ins always run):
    Drop a ``security-patterns.{yaml,json}`` file in one of, in precedence order:
      ~/.claude/security-patterns.*
      <cwd>/.claude/security-patterns.*
      <cwd>/.claude/security-patterns.local.*
    Shape: {"patterns": [{"rule_name", "reminder"/"severity", "regex"|"substrings",
            "paths"?, "exclude_paths"?}]}. ReDoS-prone or invalid rules are skipped
    with a stderr warning. Capped at 50 rules.

Exit codes:
    0  No HIGH or CRITICAL findings
    1  At least one HIGH or CRITICAL finding
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ─── File-extension groups (mirrors Anthropic patterns.py) ────────

_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte")
_PY_EXTS = (".py", ".pyi", ".ipynb")
# Documentation/data files where prose mentioning eval/exec/etc. is not code.
# yaml/yml are intentionally NOT skipped — the GitHub-Actions rule needs them.
_DOC_EXTS = (".md", ".mdx", ".txt", ".rst", ".json")

# Files we open and scan. A file is scannable if at least one rule's path_filter
# accepts it; this set is the superset of every rule's accepted extensions so
# main() can cheaply skip files no rule will ever look at.
SUPPORTED_EXTENSIONS = frozenset(
    [
        # Our original general-purpose languages
        ".py",
        ".go",
        ".js",
        ".ts",
        ".rb",
        ".java",
        ".php",
        ".kt",
        ".swift",
        # JS/TS family (parity)
        ".jsx",
        ".tsx",
        ".mjs",
        ".cjs",
        ".mts",
        ".cts",
        ".vue",
        ".svelte",
        # Python family (parity)
        ".pyi",
        ".ipynb",
        # Markup / config needed by SRI + GitHub-Actions rules
        ".html",
        ".htm",
        ".yml",
        ".yaml",
        # Documentation/data files. Opened so scan_docs secret rules (AKIA, PEM)
        # can fire on a real secret in a README/JSON. Every other rule stays
        # doc-skipped via _rule_applies_to_file, so prose mentioning eval/exec/
        # password= does not false-positive.
        ".md",
        ".mdx",
        ".txt",
        ".rst",
        ".json",
    ]
)

_TEST_FILE_PATTERNS = [
    re.compile(r"_test\.go$"),
    re.compile(r"test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    re.compile(r".*\.test\.[jt]s$"),
    re.compile(r".*\.spec\.[jt]s$"),
]

# ─── Private-range IPv4 exclusions ────────────────────────────

_PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\.0\.0\.1$"),
    re.compile(r"^0\.0\.0\.0$"),
    re.compile(r"^192\.168\."),
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[01])\."),
]


def _norm_path(filepath: str) -> str:
    """Path with forward slashes, for stable extension/glob checks on any OS."""
    return filepath.replace(os.sep, "/")


def _ext(filepath: str) -> str:
    return os.path.splitext(_norm_path(filepath))[1].lower()


# ─── Detection Rules ─────────────────────────────────────────


def _build_rules() -> list[dict]:
    """Build the ordered list of detection rules.

    Each rule dict contains:
      - name: rule identifier
      - severity: CRITICAL | HIGH | MEDIUM
      - pattern: compiled regex (matched per line)
      - skip_test: whether to skip this rule in test files (default False)
      - redact: whether to redact matched values (for secrets, default False)
      - path_filter: optional callable(path) -> bool; True means the rule applies
                     to that file. Default: applies to every supported file
                     except documentation files.
      - scan_docs: when True, the rule also scans documentation files
                   (_DOC_EXTS). Reserved for anchored, near-zero-false-positive
                   secret rules where a real secret in a README/JSON must fire.
                   Has no effect when an explicit path_filter is supplied.
      - filter_fn: optional callable(match, line, filepath) -> bool;
                   True means *keep* the finding (proximity/context suppression)
    """
    rules: list[dict] = []

    def add(
        name,
        severity,
        pattern,
        *,
        flags=0,
        skip_test=False,
        redact=False,
        path_filter=None,
        filter_fn=None,
        scan_docs=False,
    ):
        rules.append(
            {
                "name": name,
                "severity": severity,
                "pattern": re.compile(pattern, flags) if isinstance(pattern, str) else pattern,
                "skip_test": skip_test,
                "redact": redact,
                "path_filter": path_filter,
                "filter_fn": filter_fn,
                "scan_docs": scan_docs,
            }
        )

    # path_filter helpers
    def js_only(p):
        return _ext(p) in _JS_EXTS

    def py_only(p):
        return _ext(p) in _PY_EXTS

    def not_doc(p):
        return _ext(p) not in _DOC_EXTS

    def gha_workflow(p):
        np = _norm_path(p)
        return ".github/workflows/" in np and (np.endswith(".yml") or np.endswith(".yaml"))

    def html_only(p):
        return _ext(p) in (".html", ".htm")

    # ==================================================================
    # CRITICAL — hardcoded secrets (ours) + RCE map to CRITICAL via ADR
    # ==================================================================

    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""(?:password|passwd|pwd)\s*=\s*["'][^"']+["']""",
        flags=re.IGNORECASE,
        redact=True,
    )
    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""(?:api_key|apikey|api_secret)\s*=\s*["']""",
        flags=re.IGNORECASE,
        redact=True,
    )
    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""(?:secret|secret_key|auth_token|access_token)\s*=\s*["']""",
        flags=re.IGNORECASE,
        redact=True,
    )
    # AWS access key id and PEM private-key headers are anchored, near-zero
    # false-positive signatures. A real secret pasted into a README/JSON is a
    # genuine leak, so these two rules scan documentation too (scan_docs=True).
    # The loose assignment rules above stay doc-skipped — they false-positive in
    # prose. See `_rule_applies_to_file`.
    add("hardcoded-secret", "CRITICAL", r"AKIA[0-9A-Z]{16}", redact=True, scan_docs=True)
    add("hardcoded-secret", "CRITICAL", r"-----BEGIN.*PRIVATE KEY-----", redact=True, scan_docs=True)

    # Hardcoded public IP (ours). skip_test + private-range filter.
    add(
        "hardcoded-ip",
        "CRITICAL",
        r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b",
        skip_test=True,
        filter_fn=_filter_private_ip,
    )

    # ==================================================================
    # CRITICAL — RCE / code-execution sinks
    # ==================================================================

    # eval()/exec() (ours, kept). Lookbehind skips method calls (model.eval()).
    # Doc files skipped so prose/docstrings don't fire. Severity CRITICAL per
    # ADR (RCE). skip_test keeps noisy test code quiet.
    add("dangerous-eval", "CRITICAL", r"(?<![A-Za-z0-9_.])(?:eval|exec)\s*\(", skip_test=True, path_filter=not_doc)

    # JS new Function( — code injection (Anthropic new_function_injection).
    add("dangerous-eval", "CRITICAL", r"\bnew Function\s*\(", path_filter=js_only)

    # ==================================================================
    # HIGH — command/shell injection
    # ==================================================================

    # os.system (ours/Anthropic os_system_injection). Python only.
    add("shell-injection", "HIGH", r"\bos\.system\s*\(", path_filter=py_only)
    add("shell-injection", "HIGH", r"\bfrom os import system\b", path_filter=py_only)
    # subprocess.call(...) (ours, broad — kept).
    add("shell-injection", "HIGH", r"\bsubprocess\.call\s*\(", path_filter=py_only)
    # subprocess.* with shell=True (Anthropic python_subprocess_shell; ours had
    # a bare shell=True too — this targeted form supersedes it).
    add(
        "shell-injection",
        "HIGH",
        r"subprocess\.(?:run|call|Popen|check_output|check_call)\(.*shell\s*=\s*True",
        path_filter=py_only,
    )
    # Bare `shell=True` anywhere (ours, kept as a catch for custom wrappers).
    add("shell-injection", "HIGH", r"\bshell\s*=\s*True\b", path_filter=py_only)

    # JS child_process.exec / execSync / bare exec( (Anthropic child_process_exec).
    add("shell-injection", "HIGH", r"\bchild_process\.exec\b", path_filter=js_only)
    add("shell-injection", "HIGH", r"\bexecSync\s*\(", path_filter=js_only)
    add("shell-injection", "HIGH", r"(?<![A-Za-z0-9_.])exec\s*\(", path_filter=js_only)

    # Go exec.Command("sh"|"bash"|...) shell wrapper (Anthropic go_exec_shell_injection).
    add("shell-injection", "HIGH", r'exec\.Command\(\s*"(?:sh|bash|/bin/sh|/bin/bash)"')

    # ==================================================================
    # HIGH — SQL injection (ours, kept)
    # ==================================================================

    add("sql-injection", "HIGH", r"""f["'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*\{""", flags=re.IGNORECASE)
    add(
        "sql-injection",
        "HIGH",
        r"""["'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*["']\s*\.format\s*\(""",
        flags=re.IGNORECASE,
    )
    add("sql-injection", "HIGH", r"""["'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*%s.*["']\s*%""", flags=re.IGNORECASE)

    # The following SQL-injection forms are consolidated from the retired inline
    # PostToolUse scanner (hooks/posttool-security-scan._build_patterns). They
    # extend the three rules above so the canonical engine is a strict superset
    # of the inline scanner's SQL coverage — no true positive is lost on retire.
    # `_SQL_KW` is the broader keyword set the inline scanner used for the
    # concat / sprintf-family / `+=` forms.
    _SQL_KW = "SELECT|INSERT|UPDATE|DELETE|DROP|WHERE|FROM|JOIN|SET|VALUES"
    # String concatenation: "...SQL..." + variable
    add("sql-injection", "HIGH", rf"""["'](?:[^"']*\b(?:{_SQL_KW})\b[^"']*)["']\s*\+""", flags=re.IGNORECASE)
    # variable + "...SQL..."
    add(
        "sql-injection",
        "HIGH",
        rf"""\+\s*["'](?:[^"']*\b(?:{_SQL_KW})\b[^"']*)["']\s*(?:\+|$|;|\)|,)""",
        flags=re.IGNORECASE,
    )
    # Go fmt.Sprintf with SQL percent placeholders
    add(
        "sql-injection",
        "HIGH",
        rf"""fmt\.Sprintf\s*\(\s*['"`](?:[^'"`]*\b(?:{_SQL_KW})\b[^'"`]*%[sdvfq][^'"`]*)[`'"]\s*,""",
        flags=re.IGNORECASE,
    )
    # Java String.format with SQL percent placeholders
    add(
        "sql-injection",
        "HIGH",
        rf"""String\.format\s*\(\s*["'](?:[^"']*\b(?:{_SQL_KW})\b[^"']*%[sdnf][^"']*)['"]\s*,""",
        flags=re.IGNORECASE,
    )
    # PHP sprintf with SQL percent placeholders (lookbehind skips fmt.Sprintf above)
    add(
        "sql-injection",
        "HIGH",
        rf"""(?<!\w)sprintf\s*\(\s*["'](?:[^"']*\b(?:{_SQL_KW})\b[^"']*%[sduf][^"']*)['"]\s*,""",
        flags=re.IGNORECASE,
    )
    # f-string with the extended keywords (WHERE/FROM/JOIN/SET/VALUES) the
    # SELECT/INSERT/... f-string rule above doesn't cover.
    add(
        "sql-injection",
        "HIGH",
        r"""f["'](?:[^"']*\b(?:WHERE|FROM|JOIN|SET|VALUES)\b[^"']*)\{""",
        flags=re.IGNORECASE,
    )
    # Multi-line SQL building via += concatenation
    add("sql-injection", "HIGH", rf"""\b\w+\s*\+=\s*(?:f?["'][^"']*\b(?:{_SQL_KW})\b)""", flags=re.IGNORECASE)

    # ==================================================================
    # MEDIUM — path traversal (consolidated from the retired inline scanner)
    # ==================================================================

    # os.path.join(...) with a literal `../` component. Heuristic and
    # Python-specific; MEDIUM so it never blocks a commit (the inline scanner
    # was advisory-only). filter_fn keeps it quiet when a clear sanitizer
    # (Path.resolve / os.path.realpath) is already on the same line.
    add(
        "path-traversal",
        "MEDIUM",
        r"""os\.path\.join\([^)\n]*\.\./""",
        path_filter=py_only,
        filter_fn=_filter_sanitized_path,
    )

    # ==================================================================
    # HIGH — unsafe deserialization (Anthropic; ADR bumps deser to HIGH)
    # ==================================================================

    # pickle.load/loads/Unpickler + pkl_load( (Anthropic pickle_deserialization).
    add(
        "unsafe-deserialization",
        "HIGH",
        r"(?<![A-Za-z0-9_])pickle\.(?:loads?|Unpickler)\b|(?<![A-Za-z0-9_])pkl_load\(",
        path_filter=py_only,
    )
    # cPickle/cloudpickle/dill .load/.loads (Anthropic pickle_variants_load).
    add("unsafe-deserialization", "HIGH", r"\b(?:cPickle|cloudpickle|dill)\.(?:load|loads)\s*\(", path_filter=py_only)
    # marshal.load/loads (Anthropic marshal_loads).
    add("unsafe-deserialization", "HIGH", r"\bmarshal\.loads?\s*\(", path_filter=py_only)
    # shelve.open (Anthropic shelve_open).
    add("unsafe-deserialization", "HIGH", r"\bshelve\.open\s*\(", path_filter=py_only)
    # pickle wrappers: joblib.load, pandas.read_pickle, .cloudpickle_load,
    # numpy.load(..., allow_pickle=True) (Anthropic pickle_wrapper_load).
    add(
        "unsafe-deserialization",
        "HIGH",
        r"\bjoblib\.load\s*\(|\b(?:pd|pandas)\.read_pickle\s*\(|\.cloudpickle_load\s*\("
        r"|\b(?:np|numpy)\.load\s*\([^)\n]{0,200}allow_pickle\s*=\s*True",
        path_filter=py_only,
    )
    # torch.load without weights_only=True within 200 chars (Anthropic torch_unsafe_load).
    add(
        "unsafe-deserialization",
        "HIGH",
        r"(?:\btorch\.load|\.torch_load)\s*\((?![^)\n]{0,200}weights_only\s*=\s*True)",
        path_filter=py_only,
    )
    # yaml.load without Safe (ours had MEDIUM; Anthropic unsafe_yaml_load — bump HIGH).
    # Inline negative lookahead skips Safe within 80 chars; filter_fn keeps the
    # Loader=Safe... case suppressed for the line-level match too.
    add(
        "unsafe-yaml",
        "HIGH",
        r"\byaml\.load\s*\((?![^)\n]{0,80}\bSafe)",
        path_filter=py_only,
        filter_fn=_filter_safe_yaml_load,
    )
    # yaml.unsafe_load (Anthropic yaml_unsafe_load_variants).
    add("unsafe-yaml", "HIGH", r"(?:\byaml\.unsafe_load|\.yaml_unsafe_load)\s*\(", path_filter=py_only)

    # ==================================================================
    # HIGH — XSS sinks
    # ==================================================================

    # React dangerouslySetInnerHTML (Anthropic react_dangerously_set_html).
    add("xss-sink", "HIGH", r"\bdangerouslySetInnerHTML\b", path_filter=js_only)
    # .innerHTML= / .outerHTML= assignment (Anthropic innerHTML_xss/outerHTML_xss).
    add("xss-sink", "HIGH", r"\.(?:inner|outer)HTML\s*=", path_filter=js_only)
    # .insertAdjacentHTML( (Anthropic insertAdjacentHTML_xss).
    add("xss-sink", "HIGH", r"\.insertAdjacentHTML\s*\(", path_filter=js_only)

    # ==================================================================
    # HIGH — weak crypto
    # ==================================================================

    # Node createCipher/createDecipher (Anthropic node_createcipher_no_iv).
    add("weak-crypto", "HIGH", r"\bcrypto\.(?:createCipher|createDecipher)\b", path_filter=js_only)
    # AES-ECB mode (Anthropic aes_ecb_mode). Language-agnostic literal.
    add("weak-crypto", "HIGH", r"\bAES\.MODE_ECB\b|\bmodes\.ECB\s*\(|['\"]aes-\d+-ecb['\"]")

    # ==================================================================
    # HIGH — TLS verification disabled (Anthropic tls_verification_disabled)
    # ==================================================================

    add(
        "tls-disabled",
        "HIGH",
        r"\bverify\s*=\s*False\b|rejectUnauthorized\s*:\s*false"
        r"|InsecureSkipVerify\s*:\s*true|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0"
        r"|ssl\._create_unverified_context|check_hostname\s*=\s*False",
    )

    # ==================================================================
    # MEDIUM — XSS (document.write), SRI, XXE, security TODOs
    # ==================================================================

    # document.write (Anthropic document_write_xss; MEDIUM per ADR).
    add("xss-document-write", "MEDIUM", r"\bdocument\.write\b", path_filter=js_only)

    # External <script src=//...> without integrity= within 400 chars
    # (Anthropic script_src_without_sri). HTML files only.
    add(
        "missing-sri",
        "MEDIUM",
        r"<script\s+(?![^>]{0,400}integrity\s*=)"
        r"[^>]{0,200}src\s*=\s*['\"](?:https?:)?//"
        r"[^'\"]{1,300}['\"]"
        r"[^>]{0,100}>",
        path_filter=html_only,
    )

    # Unsafe XML parse — XXE (Anthropic xml_unsafe_parse). MEDIUM per ADR.
    add(
        "xxe-unsafe-xml",
        "MEDIUM",
        r"\b(?:xml\.etree\.ElementTree|ElementTree|ET)\.(?:parse|fromstring|XML)\s*\("
        r"|\bminidom\.(?:parse|parseString)\s*\("
        r"|\bxml\.sax\.(?:parse|make_parser)\b",
        path_filter=py_only,
    )

    # GitHub Actions injection: ${{ github.event.* }} into run: (workflow files).
    # MEDIUM-to-HIGH: ADR maps GHA injection HIGH. Workflow-file-gated.
    add(
        "github-actions-injection",
        "HIGH",
        r"\$\{\{\s*github\.event\.(?:issue|pull_request|comment|review|review_comment|"
        r"pages|commits|head_commit|client_payload)\b[^}]*\}\}",
        path_filter=gha_workflow,
    )

    # Security TODOs (ours, kept).
    add("security-todo", "MEDIUM", r"(?:TODO.*security|FIXME.*auth|HACK:)", flags=re.IGNORECASE)

    return rules


# ─── Filter Functions ─────────────────────────────────────────


def _filter_private_ip(match: re.Match, line: str, filepath: str) -> bool:
    """Return True to keep the finding (i.e., it is a public/non-excluded IP)."""
    ip = match.group(1) if match.lastindex else match.group(0)
    if ip == "localhost":
        return False
    for pat in _PRIVATE_IP_PATTERNS:
        if pat.match(ip):
            return False
    octets = ip.split(".")
    if len(octets) != 4:
        return False
    for octet in octets:
        try:
            val = int(octet)
            if val < 0 or val > 255:
                return False
        except ValueError:
            return False
    return True


def _filter_safe_yaml_load(match: re.Match, line: str, filepath: str) -> bool:
    """Return True to keep finding (unsafe yaml.load). Suppress when the line
    pins a safe loader (Loader=SafeLoader / Loader=Safe...)."""
    if "Loader=" in line and "Safe" in line:
        return False
    return True


def _filter_sanitized_path(match: re.Match, line: str, filepath: str) -> bool:
    """Return True to keep finding (potential path traversal). Suppress when the
    same line already pins a resolver (Path.resolve / os.path.realpath /
    os.path.abspath) — those normalize away `../` before use."""
    if any(s in line for s in (".resolve(", "os.path.realpath", "os.path.abspath")):
        return False
    return True


# ─── Custom-rule loading (extensibility) ──────────────────────

PATTERN_MAX_RULES = 50
_SEVERITY_NAMES = {"CRITICAL", "HIGH", "MEDIUM"}

# Catastrophic-backtracking heuristic (ported from Anthropic extensibility.py).
_REDOS_SHAPES = [
    re.compile(r"\([^()]*[+*][^()]*\)[+*?]"),  # nested quantifier: (a+)*  (a*b)*
    re.compile(r"\(\.\*[^()]*\)[+*]"),  # wildcard group: (.*)*
]
_ALT_UNDER_REP = re.compile(r"\(([^()]*)\|([^()|]*)(?:\|[^()]*)*\)[+*]")


def _has_redos_structure(regex: str) -> bool:
    """Heuristic catastrophic-backtracking check. Not a proof. Catches nested
    quantifiers, wildcard groups under repetition, and overlapping alternation
    under repetition. Non-overlapping alternation ((a|b)*) is safe."""
    if any(p.search(regex) for p in _REDOS_SHAPES):
        return True
    for m in _ALT_UNDER_REP.finditer(regex):
        branches = [b for b in m.group(0).strip("()*+").split("|") if b]
        for i, a in enumerate(branches):
            for b in branches[i + 1 :]:
                if a.startswith(b) or b.startswith(a):
                    return True
    return False


def _custom_config_paths(cwd: str | None) -> list[str]:
    """Existing config-file stems, lowest precedence first: user → project →
    project-local. Each stem gets each supported extension tried in turn."""
    home = os.path.expanduser(os.path.join("~", ".claude", "security-patterns"))
    stems = [home]
    if cwd:
        stems.append(os.path.join(cwd, ".claude", "security-patterns"))
        stems.append(os.path.join(cwd, ".claude", "security-patterns.local"))
    return stems


def _read_custom_config(path: str) -> dict | None:
    """Read a YAML or JSON config file. Returns None on missing/malformed
    (logged to stderr, never fatal). PyYAML is imported lazily — JSON works
    without it."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None
    if not raw.strip():
        return None
    if path.endswith(".json"):
        try:
            return json.loads(raw)
        except ValueError as exc:
            print(f"  [warn] security-patterns: invalid JSON in {path}: {exc}", file=sys.stderr)
            return None
    try:
        import yaml  # type: ignore
    except ImportError:
        print(
            f"  [warn] security-patterns: PyYAML not installed; skipping {path} (use .json)",
            file=sys.stderr,
        )
        return None
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:  # type: ignore
        print(f"  [warn] security-patterns: invalid YAML in {path}: {exc}", file=sys.stderr)
        return None


def _validate_custom_pattern(entry: object) -> dict | None:
    """Validate one user pattern entry into a rule dict in the same shape as the
    built-ins, or None if invalid (logged). regex/substrings, optional severity
    (default MEDIUM so it never silently blocks a commit), optional
    paths/exclude_paths globs."""
    if not isinstance(entry, dict):
        return None
    name = str(entry.get("rule_name", "")).strip()
    if not name:
        print("  [warn] security-patterns: skipping pattern without rule_name", file=sys.stderr)
        return None

    severity = str(entry.get("severity", "MEDIUM")).strip().upper()
    if severity not in _SEVERITY_NAMES:
        severity = "MEDIUM"

    regex = str(entry.get("regex", "")).strip()
    substrings = entry.get("substrings") or []
    if not isinstance(substrings, list) or not all(isinstance(s, str) for s in substrings):
        substrings = []
    if not regex and not substrings:
        print(f"  [warn] security-patterns: skipping {name}: no regex or substrings", file=sys.stderr)
        return None

    # Build one combined regex. Substrings become escaped alternatives.
    parts: list[str] = []
    if regex:
        if _has_redos_structure(regex):
            print(
                f"  [warn] security-patterns: skipping {name}: regex looks ReDoS-prone",
                file=sys.stderr,
            )
            return None
        parts.append(regex)
    parts.extend(re.escape(s) for s in substrings)
    combined = "|".join(parts)
    try:
        compiled = re.compile(combined)
    except re.error as exc:
        print(f"  [warn] security-patterns: skipping {name}: invalid regex: {exc}", file=sys.stderr)
        return None

    include = entry.get("paths") or []
    exclude = entry.get("exclude_paths") or []
    if not isinstance(include, list) or not isinstance(exclude, list):
        print(f"  [warn] security-patterns: skipping {name}: paths/exclude_paths must be lists", file=sys.stderr)
        return None
    path_filter = None
    if include or exclude:
        inc = tuple(str(g) for g in include)
        exc = tuple(str(g) for g in exclude)

        def path_filter(p, _inc=inc, _exc=exc):
            return _glob_match(p, _inc, _exc)

    return {
        "name": f"custom:{name}",
        "severity": severity,
        "pattern": compiled,
        "skip_test": False,
        "redact": False,
        "path_filter": path_filter,
        "filter_fn": None,
    }


def _glob_match(path: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    """Match a path against include/exclude globs. Matches on full path and
    basename so simple globs like ``*.py`` work without a directory prefix."""
    norm = _norm_path(path)
    base = os.path.basename(norm)

    def hit(globs):
        return any(fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(base, g) for g in globs)

    if include and not hit(include):
        return False
    if exclude and hit(exclude):
        return False
    return True


def _load_custom_rules(cwd: str | None) -> list[dict]:
    """Load additive custom rules from security-patterns.{yaml,json}. Failures
    are non-fatal. Capped at PATTERN_MAX_RULES."""
    rules: list[dict] = []
    for stem in _custom_config_paths(cwd):
        for ext in (".yaml", ".yml", ".json"):
            data = _read_custom_config(stem + ext)
            if data is None:
                continue
            for entry in (data or {}).get("patterns", []):
                rule = _validate_custom_pattern(entry)
                if rule:
                    rules.append(rule)
            break  # one extension per stem
        if len(rules) >= PATTERN_MAX_RULES:
            break
    if len(rules) > PATTERN_MAX_RULES:
        print(
            f"  [warn] security-patterns: {len(rules)} custom rules > cap {PATTERN_MAX_RULES}; truncating",
            file=sys.stderr,
        )
        rules = rules[:PATTERN_MAX_RULES]
    return rules


# ─── Helpers ──────────────────────────────────────────────────


def _is_test_file(filepath: str) -> bool:
    """Check if a file path matches test file naming conventions."""
    name = Path(filepath).name
    return any(pat.search(name) for pat in _TEST_FILE_PATTERNS)


def _rule_applies_to_file(rule: dict, filepath: str) -> bool:
    """Whether a rule's path_filter (if any) accepts this file. Rules without a
    path_filter apply to every supported file except documentation files —
    unless the rule sets scan_docs=True, which bypasses the _DOC_EXTS exclusion
    so anchored secret signatures fire in README/JSON too."""
    pf = rule.get("path_filter")
    if pf is not None:
        return bool(pf(filepath))
    if rule.get("scan_docs"):
        return True
    return _ext(filepath) not in _DOC_EXTS


def _staged_files(cwd: str | None = None) -> list[str]:
    """Return staged files (added/copied/modified) filtered to supported extensions."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd or None,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [f for f in files if _ext(f) in SUPPORTED_EXTENSIONS]


def _redact_secret(matched_text: str) -> str:
    """Redact secret values in matched text, preserving key names."""
    redacted = re.sub(
        r"""((?:password|passwd|pwd|api_key|apikey|api_secret|secret|secret_key|auth_token|access_token)\s*=\s*)["'][^"']*["']""",
        r"\1[REDACTED]",
        matched_text,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA[REDACTED]", redacted)
    redacted = re.sub(r"(-----BEGIN.*PRIVATE KEY-----)", r"\1 [REDACTED]", redacted)
    return redacted


def _scan_file(filepath: str, rules: list[dict]) -> list[dict]:
    """Scan a single file against all applicable rules, returning findings."""
    findings: list[dict] = []
    is_test = _is_test_file(filepath)

    # Pre-filter rules to those that apply to this file's path/extension.
    applicable = [r for r in rules if _rule_applies_to_file(r, filepath)]
    if not applicable:
        return findings

    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  [warn] Cannot read {filepath}: {exc}", file=sys.stderr)
        return findings

    lines = text.splitlines()

    for line_num, line in enumerate(lines, start=1):
        for rule in applicable:
            if is_test and rule.get("skip_test", False):
                continue

            for match in rule["pattern"].finditer(line):
                matched_text = match.group(0)

                filter_fn = rule.get("filter_fn")
                if filter_fn and not filter_fn(match, line, filepath):
                    continue

                display_text = _redact_secret(matched_text) if rule.get("redact", False) else matched_text

                findings.append(
                    {
                        "file": filepath,
                        "line": line_num,
                        "severity": rule["severity"],
                        "rule": rule["name"],
                        "match": display_text,
                    }
                )

    return findings


# ─── Output Formatting ────────────────────────────────────────


def _format_text(findings: list[dict], summary: dict) -> str:
    """Format findings as a human-readable text table."""
    lines: list[str] = []

    if not findings:
        lines.append("No security findings detected.")
        lines.append("")
        lines.append(f"Files scanned: {summary['files_scanned']}")
        return "\n".join(lines)

    lines.append("=" * 80)
    lines.append("SECURITY SCAN RESULTS")
    lines.append("=" * 80)
    lines.append("")

    for severity in ("CRITICAL", "HIGH", "MEDIUM"):
        sev_findings = [f for f in findings if f["severity"] == severity]
        if not sev_findings:
            continue

        lines.append(f"── {severity} ({len(sev_findings)}) ──")
        lines.append("")

        for f in sev_findings:
            lines.append(f"  {f['file']}:{f['line']}")
            lines.append(f"    Rule:  {f['rule']}")
            lines.append(f"    Match: {f['match']}")
            lines.append("")

    lines.append("-" * 80)
    lines.append(
        f"Total: {summary['total']} findings "
        f"({summary['critical']} critical, {summary['high']} high, "
        f"{summary['medium']} medium)"
    )
    lines.append(f"Files scanned: {summary['files_scanned']}")
    lines.append(f"Files skipped: {summary['files_skipped']}")

    return "\n".join(lines)


def _format_json(findings: list[dict], summary: dict) -> str:
    """Format findings as JSON."""
    return json.dumps(
        {"findings": findings, "summary": summary},
        indent=2,
    )


# ─── Main ─────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic security review scanner")
    parser.add_argument("--files", nargs="+", help="Source files to scan")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan staged files (git diff --cached) instead of an explicit --files list",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    if args.staged:
        files = _staged_files()
    elif args.files:
        files = args.files
    else:
        parser.error("one of --files or --staged is required")

    rules = _build_rules()
    rules.extend(_load_custom_rules(os.getcwd()))

    all_findings: list[dict] = []
    files_scanned = 0
    files_skipped = 0

    for filepath in files:
        path = Path(filepath)

        if not path.exists():
            print(f"  [warn] File not found, skipping: {filepath}", file=sys.stderr)
            files_skipped += 1
            continue

        if _ext(str(path)) not in SUPPORTED_EXTENSIONS:
            files_skipped += 1
            continue

        files_scanned += 1
        all_findings.extend(_scan_file(str(path), rules))

    summary = {
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "total": len(all_findings),
        "critical": sum(1 for f in all_findings if f["severity"] == "CRITICAL"),
        "high": sum(1 for f in all_findings if f["severity"] == "HIGH"),
        "medium": sum(1 for f in all_findings if f["severity"] == "MEDIUM"),
    }

    if args.format == "json":
        print(_format_json(all_findings, summary))
    else:
        print(_format_text(all_findings, summary))

    if summary["critical"] > 0 or summary["high"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
