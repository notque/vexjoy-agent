#!/usr/bin/env python3
"""
Security Review Scanner — deterministic regex-based security scan.

Scans source files for hardcoded secrets, injection vulnerabilities, unsafe
deserialization, XSS sinks, weak crypto, disabled TLS, and dangerous function
calls using pattern matching. Detection parity with Anthropic's
``security-guidance`` plugin deterministic layer, plus our own secret/SQLi/IP
rules. Stdlib-only (PyYAML optional, used only if importable for custom rules).

Best effort, not a guarantee: the rules catch known shapes only. A clean result
means no rule matched, not that the files hold no secret or flaw.

Usage:
    python3 scripts/security-review-scan.py --files file1.py file2.go
    python3 scripts/security-review-scan.py --files src/*.py --format json
    python3 scripts/security-review-scan.py --staged --format json
    python3 scripts/security-review-scan.py --help

What gets scanned:
    - Files with an extension in SUPPORTED_EXTENSIONS get every rule for their type.
    - Every other text file (.env, .sh, .toml, .tf, .pem, Dockerfile, files with no
      extension) gets the secret rules: anchored token signatures, plus
      credential-key assignments outside documentation files.
    - Binary files get the anchored token signatures only.
    - --staged reads each staged blob from the index, which is what the commit
      will hold, not the working tree. It covers added, copied, modified, renamed
      and type-changed paths, named relative to the repository top level, and
      works from any subdirectory.
    - Each rule scans a line in windows of _WINDOW_CHARS characters, so a long
      minified line costs time in proportion to its length.

Secrets in output:
    A secret finding prints only <redacted:TYPE:last4>, and the last four
    characters only when the value has at least _LAST4_MIN_LEN. Other findings
    print their match with every secret span replaced the same way, cut to
    _MATCH_DISPLAY_CHARS characters.

Custom rules (optional, additive — built-ins always run):
    Drop a ``security-patterns.{yaml,json}`` file in one of, in precedence order:
      ~/.claude/security-patterns.*
      <cwd>/.claude/security-patterns.*
      <cwd>/.claude/security-patterns.local.*
    Shape: {"patterns": [{"rule_name", "reminder"/"severity", "regex"|"substrings",
            "paths"?, "exclude_paths"?}]}. ReDoS-prone or invalid rules, and files
    of any other shape, are skipped with a stderr warning. Capped at 50 rules.
    Custom rules run on SUPPORTED_EXTENSIONS files only.

Suppression (two escape hatches so commits stop being gated on code you don't own):
    1. Inline marker — a line containing ``nosec`` or ``security-review: ignore``
       (also ``security_review ignore``) drops every finding on THAT line. For
       deliberate, auditable, single-line exceptions in your own code.
    2. Wholesale path ignore — drop a ``security-review-ignore`` file (no ext,
       one path glob per line, ``#`` comments) in, lowest precedence first:
         ~/.claude/security-review-ignore
         <cwd>/.claude/security-review-ignore
         <cwd>/.claude/security-review-ignore.local
       Globs match repo-relative path AND basename (``core/*``, ``*/vendor/*``).
       Intended for vendored / third-party code the repo owner does not maintain.
    Both are additive and OFF by default — no file and no marker == prior behavior.
    With --staged, <cwd> in both lists is the repository top level.

Exit codes:
    0  The scan completed with no HIGH or CRITICAL finding
    1  At least one HIGH or CRITICAL finding, even when the scan is incomplete
    2  The scan did not complete and found nothing blocking in what it did read:
       an internal error, a git failure, a file over _MAX_SCAN_BYTES, or the
       --time-budget ran out. The JSON summary's "incomplete" list says why.
       Command-line usage errors also exit 2.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ─── File-extension groups (mirrors Anthropic patterns.py) ────────

_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte")
_PY_EXTS = (".py", ".pyi", ".ipynb")
# Documentation/data files where prose mentioning eval/exec/etc. is not code.
# yaml/yml are intentionally NOT skipped — the GitHub-Actions rule needs them.
_DOC_EXTS = (".md", ".mdx", ".txt", ".rst", ".json")

# Inline per-line suppression: a finding on a line containing one of these markers
# is dropped. Mirrors bandit `# nosec` / semgrep `// nosemgrep`. Intended for
# deliberate, auditable, single-line exceptions (e.g. a vetted vendored sink).
# `nosec` must be a standalone token so it doesn't fire on unrelated identifiers.
_INLINE_SUPPRESS_RE = re.compile(r"(?:\bnosec\b|security[-_ ]?review\s*:?\s*ignore)", re.IGNORECASE)

# Project/user file listing path globs to skip wholesale (one glob per line,
# `#` comments, blank lines ignored). For vendored / third-party code we don't
# own and shouldn't gate on. Discovered like the custom-patterns config.
_IGNORE_FILE_STEM = "security-review-ignore"

# Files that get the full rule set: the superset of every code rule's accepted
# extensions. Every other file still gets the secret rules (see
# _rule_applies_to_file); the edit-time hooks scan only files in this set.
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

# Files whose syntax takes unquoted values (KEY=value, key: value), so the
# credential-assignment rule also accepts an unquoted value there.
_CONFIG_EXTS = frozenset(
    [".env", ".sh", ".bash", ".zsh", ".ksh", ".properties", ".ini", ".cfg", ".conf", ".cnf", ".yml", ".yaml", ".toml"]
)
_CONFIG_NAMES = frozenset([".npmrc", ".netrc", ".pypirc", ".pgpass"])

# Every rule scans a line in windows of at most this many characters, so one
# rule's cost on a minified or generated line grows with the line's length and
# no faster (D-02).
_WINDOW_CHARS = 4096
# Neighbouring windows overlap by this much, longer than any built-in rule's
# match plus lookahead, so a match that crosses a window edge is still seen whole.
_WINDOW_OVERLAP = 1280
# A file larger than this is not read; the scan reports it as incomplete.
_MAX_SCAN_BYTES = 16 * 1024 * 1024
# A NUL byte in this many leading bytes marks a file as binary (git's test).
_BINARY_SNIFF_BYTES = 8000
# Displayed match text is cut to this many characters.
_MATCH_DISPLAY_CHARS = 160
# A redacted value shows its last four characters only when at least this long.
_LAST4_MIN_LEN = 12
# Longest quoted literal the SQL rules look inside.
_SQL_SPAN = 1000

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


def _config_syntax(filepath: str) -> bool:
    """True for .env, shell, YAML, INI-style and similar files, where a value may be unquoted."""
    base = os.path.basename(_norm_path(filepath)).lower()
    return base.startswith((".env", "dockerfile")) or base in _CONFIG_NAMES or _ext(filepath) in _CONFIG_EXTS


# ─── Detection Rules ─────────────────────────────────────────

# Anchored token formats: a fixed prefix, alphabet and length, so a match is
# almost never anything but the credential. (secret type, regex)
_SECRET_SIGNATURES = (
    ("aws-access-key-id", r"AKIA[0-9A-Z]{16}"),
    ("private-key", r"-----BEGIN (?:[A-Z0-9]{1,20} ){0,3}PRIVATE KEY(?: BLOCK)?-----"),
    ("aws-access-key-id", r"(?<![A-Za-z0-9])ASIA[0-9A-Z]{16}(?![A-Za-z0-9])"),
    ("github-token", r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,251}(?![A-Za-z0-9_])"),
    ("github-token", r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{50,251}(?![A-Za-z0-9_])"),
    ("slack-token", r"(?<![A-Za-z0-9])xox[abeoprs]-[A-Za-z0-9-]{10,250}"),
    ("slack-webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]{6,20}/B[A-Z0-9]{6,20}/[A-Za-z0-9]{20,40}"),
    ("google-api-key", r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![A-Za-z0-9_-])"),
    ("anthropic-api-key", r"(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_-]{32,250}"),
    (
        "openai-api-key",
        r"(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{16,200}T3BlbkFJ[A-Za-z0-9_-]{16,200}",
    ),
    ("npm-token", r"(?<![A-Za-z0-9_])npm_[A-Za-z0-9]{36}(?![A-Za-z0-9_])"),
    ("stripe-live-key", r"(?<![A-Za-z0-9_])[rs]k_live_[A-Za-z0-9]{20,250}"),
    ("gitlab-token", r"(?<![A-Za-z0-9_-])glpat-[A-Za-z0-9_-]{20,250}"),
)

# Credential-like key names, as the last part of an identifier or quoted key:
# token, GITHUB_TOKEN, apiKey, aws_secret_access_key, "password", client_secret.
_SECRET_KEY = (
    r"(?P<key>pass(?:word|wd|phrase)|secret|token|credentials?"
    r"|api[_.-]?(?:key|secret)|(?:access|secret|private|client|signing|encryption|master)[_.-]?key"
    r"|client[_.-]?secret)"
)


def _build_rules() -> list[dict]:
    """Build the ordered list of detection rules.

    Each rule dict contains:
      - name: rule identifier
      - severity: CRITICAL | HIGH | MEDIUM
      - pattern: compiled regex (matched per line, in windows of _WINDOW_CHARS)
      - skip_test: whether to skip this rule in test files (default False)
      - secret_type: for secret rules, the TYPE in the <redacted:TYPE:last4>
                     that replaces the match in output; a str, or a callable(match)
                     -> str. None (default) for every other rule.
      - show_last4: secret rules only; False hides the last four characters too
      - scope: which files the rule runs on (see _rule_applies_to_file):
               "code" (default) SUPPORTED_EXTENSIONS files, documentation files
               excluded unless an explicit path_filter accepts them;
               "text" every file except documentation files;
               "any" every file, binary included. Reserved for anchored,
               near-zero-false-positive secret signatures.
      - path_filter: optional callable(path) -> bool; True means the rule applies
                     to that file, within its scope.
      - filter_fn: optional callable(match, line, filepath) -> bool;
                   True means *keep* the finding (proximity/context suppression).
                   On a line longer than _WINDOW_CHARS, `line` is the window the
                   match was found in.
    """
    rules: list[dict] = []

    def add(
        name,
        severity,
        pattern,
        *,
        flags=0,
        skip_test=False,
        secret_type=None,
        show_last4=True,
        scope="code",
        path_filter=None,
        filter_fn=None,
    ):
        rules.append(
            {
                "name": name,
                "severity": severity,
                "pattern": re.compile(pattern, flags) if isinstance(pattern, str) else pattern,
                "skip_test": skip_test,
                "secret_type": secret_type,
                "show_last4": show_last4,
                "scope": scope,
                "path_filter": path_filter,
                "filter_fn": filter_fn,
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
    #
    # A secret rule sets secret_type, and its findings never show the matched
    # text: the match field is <redacted:TYPE:last4>, built from the named group
    # "secret" or else the whole match. The same rules redact secret spans in
    # every other finding's match (_redact_text): this table is the scanner's
    # only redaction set.

    # Credential assignments in code (ours, kept): any quoted value fires.
    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""(?:password|passwd|pwd)\s{0,50}=\s{0,50}["'](?P<secret>[^"'\n]{1,1000})["']""",
        flags=re.IGNORECASE,
        secret_type="password",
    )
    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""(?:api_key|apikey|api_secret)\s{0,50}=\s{0,50}["'](?P<secret>[^"'\n]{0,1000})""",
        flags=re.IGNORECASE,
        secret_type="api-key",
    )
    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""(?:secret|secret_key|auth_token|access_token)\s{0,50}=\s{0,50}["'](?P<secret>[^"'\n]{0,1000})""",
        flags=re.IGNORECASE,
        secret_type="secret",
    )
    # Anchored token formats (AWS key ids, private-key headers, GitHub, Slack,
    # Google, Anthropic, OpenAI, npm, Stripe, GitLab) are near-zero
    # false-positive signatures, so they run on every scanned file: docs,
    # config, .env, .pem, files with no extension, binary blobs. The private-key
    # rule matches the BEGIN header alone, so a key stored on one line never
    # ends up in a match.
    for secret_type, pattern in _SECRET_SIGNATURES:
        add(
            "hardcoded-secret",
            "CRITICAL",
            pattern,
            secret_type=secret_type,
            show_last4=secret_type != "private-key",
            scope="any",
        )
    # A credential-named key given a literal, in every file but docs:
    # `token = "..."`, `"password": "..."`, `password := "..."`, `'api_key' => '...'`.
    # The value must look like a credential (_filter_secret_value), so
    # placeholders, templates, labels and empty strings stay quiet.
    add(
        "hardcoded-secret",
        "CRITICAL",
        _SECRET_KEY + r"""["']?\s{0,20}(?::=|=>|=|:)\s{0,20}(?P<q>["'])(?P<secret>[^"'\s]{4,250})(?P=q)""",
        flags=re.IGNORECASE,
        secret_type=_key_secret_type,
        scope="text",
        filter_fn=_filter_secret_value,
    )
    # The same with an unquoted value, in .env, shell, YAML and INI-style files,
    # where the key starts the line: `API_KEY=...`, `export TOKEN=...`,
    # `password: ...`, `- DB_PASSWORD=...`, `ENV API_KEY=...`.
    add(
        "hardcoded-secret",
        "CRITICAL",
        r"""^\s{0,40}(?:-\s{1,5})?(?:(?:export|env|arg)\s{1,5})?["']?[\w.-]{0,60}?"""
        + _SECRET_KEY
        + r"""["']?\s{0,20}[=:]\s{0,20}(?P<secret>[^\s"'#]{4,250})\s{0,20}(?:#[^\n]{0,500})?$""",
        flags=re.IGNORECASE,
        secret_type=_key_secret_type,
        scope="text",
        path_filter=_config_syntax,
        filter_fn=_filter_secret_value,
    )

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

    # eval()/exec() (ours, kept). Lookbehind skips method calls (model.eval()).  nosec: rule comment
    # Doc files skipped so prose/docstrings don't fire. Severity CRITICAL per
    # ADR (RCE). skip_test keeps noisy test code quiet.
    add("dangerous-eval", "CRITICAL", r"(?<![A-Za-z0-9_.])(?:eval|exec)\s*\(", skip_test=True, path_filter=not_doc)

    # JS new Function( — code injection (Anthropic new_function_injection).
    add("dangerous-eval", "CRITICAL", r"\bnew Function\s*\(", path_filter=js_only)

    # ==================================================================
    # HIGH — command/shell injection
    # ==================================================================

    # os.system (ours/Anthropic os_system_injection). Python only.  nosec: rule comment
    add("shell-injection", "HIGH", r"\bos\.system\s*\(", path_filter=py_only)
    add("shell-injection", "HIGH", r"\bfrom os import system\b", path_filter=py_only)
    # subprocess.call(...) (ours, broad — kept).  nosec: rule comment
    add("shell-injection", "HIGH", r"\bsubprocess\.call\s*\(", path_filter=py_only)
    # subprocess.* with shell=True (Anthropic python_subprocess_shell; ours had  nosec: rule comment
    # a bare shell=True too — this targeted form supersedes it).  nosec: rule comment
    add(
        "shell-injection",
        "HIGH",
        r"subprocess\.(?:run|call|Popen|check_output|check_call)\([^\n]{0,1000}?shell\s{0,20}=\s{0,20}True",
        path_filter=py_only,
    )
    # Bare `shell=True` anywhere (ours, kept as a catch for custom wrappers).  nosec: rule comment
    add("shell-injection", "HIGH", r"\bshell\s*=\s*True\b", path_filter=py_only)

    # JS child_process.exec / execSync / bare exec( (Anthropic child_process_exec).  nosec: rule comment
    add("shell-injection", "HIGH", r"\bchild_process\.exec\b", path_filter=js_only)
    add("shell-injection", "HIGH", r"\bexecSync\s*\(", path_filter=js_only)
    add("shell-injection", "HIGH", r"(?<![A-Za-z0-9_.])exec\s*\(", path_filter=js_only)

    # Go exec.Command("sh"|"bash"|...) shell wrapper (Anthropic go_exec_shell_injection).  nosec: rule comment
    add("shell-injection", "HIGH", r'exec\.Command\(\s*"(?:sh|bash|/bin/sh|/bin/bash)"')

    # ==================================================================
    # HIGH — SQL injection (ours, kept)
    # ==================================================================

    # Each SQL rule matches one quoted literal of at most _SQL_SPAN characters,
    # and lookaheads check what the literal must hold, in any order. A literal
    # costs a few passes over its own text, so a long or minified line scans in
    # linear time (the old `.*` forms took seconds to minutes on one long line).
    # nested=True (the three rules below, which used `.*`) lets a literal hold
    # the other quote character, so f"... = '{v}'" still fires; otherwise no
    # quote character may appear inside, as the inline scanner's rules required.
    def literal(needs, quotes="\"'", triple=False, close=True, nested=False):
        span = "{0," + str(_SQL_SPAN) + "}"
        if nested:
            forms = [(q, "[^" + q + "\\n]") for q in quotes]
        else:
            forms = [("[" + quotes + "]", "[^" + quotes + "\\n]")]
        alts = []
        for quote, body in forms:
            looks = "".join("(?=" + body + span + "?" + need + ")" for need in needs)
            alts.append(quote + ("{1,3}" if triple else "") + looks + body + span + (quote if close else ""))
        return "(?:" + "|".join(alts) + ")"

    # The lookaheads only check that each need occurs. Where the old form was
    # `keyword.*placeholder`, this filter keeps the order: the placeholder must
    # follow the first keyword, so prose such as f"{n} of {d.values()} rows"
    # (the brace before the keyword) stays quiet. Two plain searches, linear.
    def in_order(first, then):
        first_re = re.compile(first, re.IGNORECASE)
        then_re = re.compile(then, re.IGNORECASE)

        def keep(match, line, filepath):
            text = match.group(0)
            hit = first_re.search(text)
            return bool(hit and then_re.search(text, hit.end())) and _filter_sql_shape(match, line, filepath)

        return keep

    _SQL_KW4 = r"\b(?:SELECT|INSERT|UPDATE|DELETE)\b"
    add(
        "sql-injection",
        "HIGH",
        "f" + literal([_SQL_KW4, r"\{"], triple=True, close=False, nested=True),
        flags=re.IGNORECASE,
        filter_fn=in_order(_SQL_KW4, r"\{"),
    )
    add(
        "sql-injection",
        "HIGH",
        literal([_SQL_KW4], nested=True) + r"\s{0,20}\.format\s{0,20}\(",
        flags=re.IGNORECASE,
        filter_fn=_filter_sql_shape,
    )
    add(
        "sql-injection",
        "HIGH",
        literal([_SQL_KW4, "%s"], nested=True) + r"\s{0,20}%",
        flags=re.IGNORECASE,
        filter_fn=in_order(_SQL_KW4, "%s"),
    )

    # The following SQL-injection forms are consolidated from the retired inline
    # PostToolUse scanner (hooks/posttool-security-scan._build_patterns). They
    # extend the three rules above so the canonical engine is a strict superset
    # of the inline scanner's SQL coverage — no true positive is lost on retire.
    # `_SQL_KW` is the broader keyword set the inline scanner used for the
    # concat / sprintf-family / `+=` forms.
    _SQL_KW = r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|WHERE|FROM|JOIN|SET|VALUES)\b"
    # String concatenation: "...SQL..." + variable
    add(
        "sql-injection",
        "HIGH",
        literal([_SQL_KW]) + r"\s{0,20}\+",
        flags=re.IGNORECASE,
        filter_fn=_filter_sql_shape,
    )
    # variable + "...SQL..."
    add(
        "sql-injection",
        "HIGH",
        r"\+\s{0,20}" + literal([_SQL_KW]) + r"\s{0,20}(?:\+|$|;|\)|,)",
        flags=re.IGNORECASE,
        filter_fn=_filter_sql_shape,
    )
    # Go fmt.Sprintf with SQL percent placeholders
    add(
        "sql-injection",
        "HIGH",
        r"fmt\.Sprintf\s{0,20}\(\s{0,20}" + literal([_SQL_KW, "%[sdvfq]"], quotes="\"'`") + r"\s{0,20},",
        flags=re.IGNORECASE,
        filter_fn=in_order(_SQL_KW, "%[sdvfq]"),
    )
    # Java String.format with SQL percent placeholders
    add(
        "sql-injection",
        "HIGH",
        r"String\.format\s{0,20}\(\s{0,20}" + literal([_SQL_KW, "%[sdnf]"]) + r"\s{0,20},",
        flags=re.IGNORECASE,
        filter_fn=in_order(_SQL_KW, "%[sdnf]"),
    )
    # PHP sprintf with SQL percent placeholders (lookbehind skips fmt.Sprintf above)
    add(
        "sql-injection",
        "HIGH",
        r"(?<!\w)sprintf\s{0,20}\(\s{0,20}" + literal([_SQL_KW, "%[sduf]"]) + r"\s{0,20},",
        flags=re.IGNORECASE,
        filter_fn=in_order(_SQL_KW, "%[sduf]"),
    )
    # f-string with the extended keywords (WHERE/FROM/JOIN/SET/VALUES) the
    # SELECT/INSERT/... f-string rule above doesn't cover.
    _SQL_KW_EXT = r"\b(?:WHERE|FROM|JOIN|SET|VALUES)\b"
    add(
        "sql-injection",
        "HIGH",
        "f" + literal([_SQL_KW_EXT, r"\{"], close=False),
        flags=re.IGNORECASE,
        filter_fn=in_order(_SQL_KW_EXT, r"\{"),
    )
    # Multi-line SQL building via += concatenation
    add(
        "sql-injection",
        "HIGH",
        r"\b\w{1,100}\s{0,20}\+=\s{0,20}f?" + literal([_SQL_KW], close=False),
        flags=re.IGNORECASE,
        filter_fn=_filter_sql_shape,
    )

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
        r"""os\.path\.join\([^)\n]{0,500}\.\./""",
        path_filter=py_only,
        filter_fn=_filter_sanitized_path,
    )

    # ==================================================================
    # HIGH — unsafe deserialization (Anthropic; ADR bumps deser to HIGH)
    # ==================================================================

    # pickle.load/loads/Unpickler + pkl_load( (Anthropic pickle_deserialization).  nosec: rule comment
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
    # shelve.open (Anthropic shelve_open).  nosec: rule comment
    add("unsafe-deserialization", "HIGH", r"\bshelve\.open\s*\(", path_filter=py_only)
    # pickle wrappers: joblib.load, pandas.read_pickle, .cloudpickle_load,
    # numpy.load(..., allow_pickle=True) (Anthropic pickle_wrapper_load).  nosec: rule comment
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
    # yaml.unsafe_load (Anthropic yaml_unsafe_load_variants).  nosec: rule comment
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
        r"<script\s{1,50}(?![^>]{0,400}integrity\s*=)"
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
        r"pages|commits|head_commit|client_payload)\b[^}]{0,500}\}\}",
        path_filter=gha_workflow,
        filter_fn=_filter_gha_safe_context,
    )

    # Security TODOs (ours, kept).
    add("security-todo", "MEDIUM", r"(?:TODO[^\n]{0,200}?security|FIXME[^\n]{0,200}?auth|HACK:)", flags=re.IGNORECASE)

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


# Real SQL shape: keyword pairs a query needs, not one lone keyword. English
# prose in an f-string ("omitted from {label}", "reply from {model}") has a
# lone FROM and must stay quiet; a query fragment has a pair or an operator.
# Quantifiers are bounded so the check stays linear on a long line.
_IDENT = r"""[\w.`"\[\]{}]{1,200}"""
_SQL_SHAPE_RE = re.compile(
    r"\bSELECT\s[^;]{0,1000}?\bFROM\s{1,20}"
    + _IDENT
    + r"|\bINSERT\s{1,20}(?:OR\s{1,20}\w{1,30}\s{1,20})?INTO\b"
    + r"|\bUPDATE\s{1,20}"
    + _IDENT
    + r"\s{1,20}SET\b"
    + r"|\bDELETE\s{1,20}FROM\b"
    + r"|\b(?:DROP|TRUNCATE|ALTER|CREATE)\s{1,20}(?:TABLE|DATABASE|INDEX|VIEW|SCHEMA)\b"
    + r"|\bWHERE\s{1,20}"
    + _IDENT
    + r"\s{0,20}(?:=|<|>|!=|\bLIKE\b|\bIN\b|\bIS\b|\bBETWEEN\b)"
    + r"|\bJOIN\s{1,20}"
    + _IDENT
    + r"(?:\s{1,20}(?:AS\s{1,20})?\w{1,100})?\s{1,20}(?:ON|USING)\b"
    + r"|\bVALUES\s{0,20}\("
    + r"|\bSET\s{1,20}"
    + _IDENT
    + r"\s{0,20}="
    + r"|\bFROM\s{1,20}"
    + _IDENT
    + r"\s{1,20}(?:WHERE|JOIN|INNER|LEFT|RIGHT|ORDER\s{1,20}BY|GROUP\s{1,20}BY|LIMIT)\b"
    + r"|\bORDER\s{1,20}BY\s{1,20}"
    + _IDENT
    + r"|\bGROUP\s{1,20}BY\s{1,20}"
    + _IDENT,
    re.IGNORECASE,
)
# A DB call on the same line is SQL context on its own.
_SQL_CALL_RE = re.compile(r"\b(?:execute|executemany|executescript|raw|query)\s{0,20}\(|\bcursor\b", re.IGNORECASE)
# The last line checked and its answer: several SQL rules ask about the same line.
_SQL_SHAPE_LAST: list = [None, False]


# An expression that is the whole value of an ALL_CAPS env-var key (GitHub's
# documented mitigation: pass untrusted input through env, then quote "$VAR"
# in the script) or that reads a numeric field (.number, .id) cannot inject
# shell. Free-text fields inlined into run:/script: still fire.
_GHA_ENV_VALUE_RE = re.compile(r"""^\s*[A-Z][A-Z0-9_]*\s*:\s*["']?\$\{\{[^}]*\}\}["']?\s*(?:#.*)?$""")
_GHA_NUMERIC_FIELD_RE = re.compile(r"\.(?:number|id|run_id|run_number)\s*\}\}$")


def _filter_gha_safe_context(match: re.Match, line: str, filepath: str) -> bool:
    """Return True to keep a github-actions-injection finding."""
    if _GHA_NUMERIC_FIELD_RE.search(match.group(0)):
        return False
    return not _GHA_ENV_VALUE_RE.match(line)


def _filter_sql_shape(match: re.Match, line: str, filepath: str) -> bool:
    """Return True to keep a sql-injection finding: the line holds real SQL
    shape (keyword pair or operator) or a DB call. A lone FROM/SET/SELECT
    word in prose is suppressed."""
    if _SQL_SHAPE_LAST[0] is not line:
        _SQL_SHAPE_LAST[:] = [line, bool(_SQL_SHAPE_RE.search(line) or _SQL_CALL_RE.search(line))]
    return _SQL_SHAPE_LAST[1]


# Values that are references, templates or placeholders, not literal secrets.
_PLACEHOLDER_VALUE_RE = re.compile(
    r"^[$%{<\[(!&*@~]|\$\{|\$\(|\{\{|[<>|]|://"
    r"|example|placeholder|change_?me|redacted|dummy|sample|your[_-]|xxxx|\*\*\*|\.\.\.",
    re.IGNORECASE,
)


def _key_secret_type(match: re.Match) -> str:
    """The <redacted:TYPE> for a credential-key rule, from the key name that matched."""
    key = re.sub(r"[_.-]", "", match.group("key").lower())
    if key.startswith("pass"):
        return "password"
    named = {"apikey": "api-key", "apisecret": "api-key", "clientsecret": "client-secret", "credentials": "credential"}
    if key in named:
        return named[key]
    return key[:-3] + "-key" if key.endswith("key") else key


def _filter_secret_value(match: re.Match, line: str, filepath: str) -> bool:
    """Return True to keep a credential-key finding: the value looks like a real
    credential. A password needs 6+ characters with a digit or symbol (so labels
    such as "Required" stay quiet); any other key needs 12+ characters drawn
    from at least two of upper case, lower case and digits (so env-var names,
    paths and words stay quiet). References, templates and placeholders never fire."""
    value = match.group("secret")
    if _PLACEHOLDER_VALUE_RE.search(value):
        return False
    if _key_secret_type(match) == "password":
        return len(value) >= 6 and not value.isalpha()
    classes = sum(1 for test in (str.isupper, str.islower, str.isdigit) if any(test(c) for c in value))
    return len(value) >= 12 and classes >= 2


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

    regex = entry.get("regex") or ""
    if not isinstance(regex, str):
        print(f"  [warn] security-patterns: skipping {name}: regex must be a string", file=sys.stderr)
        return None
    regex = regex.strip()
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
        "secret_type": None,
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


def _ignore_file_paths(cwd: str | None) -> list[str]:
    """security-review-ignore file locations, lowest precedence first:
    user (~/.claude) -> project (<cwd>/.claude) -> project-local. No extension."""
    home = os.path.expanduser(os.path.join("~", ".claude", _IGNORE_FILE_STEM))
    paths = [home]
    if cwd:
        paths.append(os.path.join(cwd, ".claude", _IGNORE_FILE_STEM))
        paths.append(os.path.join(cwd, ".claude", _IGNORE_FILE_STEM + ".local"))
    return paths


def _load_ignore_globs(cwd: str | None) -> tuple[str, ...]:
    """Load path globs from the security-review-ignore file(s). One glob per
    line; blank lines and `#` comments ignored. Non-fatal on missing/unreadable.
    These suppress ALL findings for matching paths — intended for vendored /
    third-party code the repo owner does not maintain."""
    globs: list[str] = []
    for path in _ignore_file_paths(cwd):
        try:
            with open(path, encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    globs.append(line)
        except OSError:
            continue
    return tuple(globs)


def _path_ignored(path: str, globs: tuple[str, ...]) -> bool:
    """True if `path` matches any ignore glob (full path or basename)."""
    if not globs:
        return False
    norm = _norm_path(path)
    base = os.path.basename(norm)
    return any(fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(base, g) for g in globs)


def _load_custom_rules(cwd: str | None) -> list[dict]:
    """Load additive custom rules from security-patterns.{yaml,json}. Failures
    are non-fatal: a file of the wrong shape is skipped with a warning and the
    built-in rules still run. Capped at PATTERN_MAX_RULES."""
    rules: list[dict] = []
    for stem in _custom_config_paths(cwd):
        for ext in (".yaml", ".yml", ".json"):
            data = _read_custom_config(stem + ext)
            if data is None:
                continue
            patterns = data.get("patterns") if isinstance(data, dict) else None
            if not isinstance(patterns, list):
                print(
                    f"  [warn] security-patterns: skipping {stem + ext}: expected a mapping with a 'patterns' list",
                    file=sys.stderr,
                )
                continue
            for entry in patterns:
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
    """Whether a rule runs on this file, from its scope and path_filter.

    - scope "any" (anchored secret signatures): every file, so a real secret in
      a README, JSON, .env, .pem or file with no extension fires.
    - scope "text" (credential-key assignments): every file except
      documentation, where prose that shows an example assignment would
      false-positive.
    - scope "code" (every other rule, custom rules too): SUPPORTED_EXTENSIONS
      files only, documentation excluded unless a path_filter accepts it.
    A path_filter narrows the "text" and "code" scopes.
    """
    scope = rule.get("scope", "code")
    if scope == "any":
        return True
    pf = rule.get("path_filter")
    if scope == "text":
        return _ext(filepath) not in _DOC_EXTS and (pf is None or bool(pf(filepath)))
    if _ext(filepath) not in SUPPORTED_EXTENSIONS:
        return False
    if pf is not None:
        return bool(pf(filepath))
    return _ext(filepath) not in _DOC_EXTS


# ─── Redaction ────────────────────────────────────────────────


def _placeholder(secret_type: str, value: str, show_last4: bool = True) -> str:
    """<redacted:TYPE:last4>, or <redacted:TYPE> when the value is short or hidden."""
    if show_last4 and len(value) >= _LAST4_MIN_LEN:
        return f"<redacted:{secret_type}:{value[-4:]}>"
    return f"<redacted:{secret_type}>"


def _secret_placeholder(rule: dict, match: re.Match) -> str:
    """The placeholder that stands in for a secret rule's match."""
    secret_type = rule["secret_type"]
    if callable(secret_type):
        secret_type = secret_type(match)
    value = match.group("secret") if "secret" in match.re.groupindex else match.group(0)
    return _placeholder(secret_type, value or "", rule.get("show_last4", True))


# Built-in secret rules, compiled once, for redacting text that is not a secret finding.
_SECRET_RULES: list[dict] = []
_PRIVATE_KEY_PLACEHOLDER = "<redacted:private-key>"


def _redact_text(text: str) -> str:
    """Replace every built-in secret rule's match in text with its placeholder."""
    if not _SECRET_RULES:
        _SECRET_RULES.extend(r for r in _build_rules() if r.get("secret_type"))
    for rule in _SECRET_RULES:
        text = rule["pattern"].sub(lambda m, rule=rule: _secret_placeholder(rule, m), text)
    # The private-key rule matches the header alone; the key body follows it
    # on the same line when a key is stored as one string, so drop the rest.
    cut = text.find(_PRIVATE_KEY_PLACEHOLDER)
    if cut >= 0:
        text = text[: cut + len(_PRIVATE_KEY_PLACEHOLDER)] + "..."
    return text


def _display_match(rule: dict, match: re.Match) -> str:
    """What a finding shows as its match: the placeholder for a secret rule;
    otherwise the matched text with secret spans redacted, cut to
    _MATCH_DISPLAY_CHARS characters."""
    if rule.get("secret_type"):
        return _secret_placeholder(rule, match)
    text = _redact_text(match.group(0))
    if len(text) > _MATCH_DISPLAY_CHARS:
        text = text[:_MATCH_DISPLAY_CHARS] + "..."
    return text


def _error_text(exc: BaseException) -> str:
    """An exception as one short line with any secret span redacted."""
    try:
        detail = _redact_text(str(exc))
    except Exception:
        detail = "(detail withheld: redaction failed)"
    return f"{type(exc).__name__}: {detail[:300]}"


# ─── Scanning ─────────────────────────────────────────────────


class _OutOfTime(Exception):
    """The --time-budget ran out."""


class _ScanError(Exception):
    """The scan cannot run as asked: no git work tree, or git failed."""


class _Deadline:
    """Raises _OutOfTime from check() once the time budget is spent (None: no budget)."""

    def __init__(self, seconds: float | None):
        self._at = None if seconds is None else time.monotonic() + seconds

    def check(self) -> None:
        if self._at is not None and time.monotonic() >= self._at:
            raise _OutOfTime


def _windows(length: int) -> list[tuple[int, int, int]]:
    """(lo, hi, accept) spans covering a line of this length. Each rule scans
    line[lo:hi] and keeps the matches that start before accept; neighbouring
    windows overlap by _WINDOW_OVERLAP, so a match is seen whole and reported once."""
    if length <= _WINDOW_CHARS:
        return [(0, length, length)]
    stride = _WINDOW_CHARS - _WINDOW_OVERLAP
    spans = []
    lo = 0
    while lo + _WINDOW_CHARS < length:
        spans.append((lo, lo + _WINDOW_CHARS, lo + stride))
        lo += stride
    spans.append((lo, length, length))
    return spans


def _scan_text(
    filepath: str,
    text: str,
    rules: list[dict],
    deadline: _Deadline | None = None,
    out: list[dict] | None = None,
) -> list[dict]:
    """Scan text (the content of filepath) against every rule that applies to it.

    Findings are appended to `out` when given, so a scan stopped by the deadline
    keeps what it already found.
    """
    findings: list[dict] = [] if out is None else out
    is_test = _is_test_file(filepath)
    applicable = [r for r in rules if _rule_applies_to_file(r, filepath) and not (is_test and r.get("skip_test"))]
    if not applicable:
        return findings

    for line_num, line in enumerate(text.splitlines(), start=1):
        if deadline is not None and (line_num % 256 == 0 or len(line) > _WINDOW_CHARS):
            deadline.check()
        # Inline per-line suppression (`# nosec`, `// security-review: ignore`).
        # A deliberate, auditable, single-line exception — skip every rule here.
        if _INLINE_SUPPRESS_RE.search(line):
            continue
        taken = [0] * len(applicable)  # per rule: where its last reported match ended
        secret_spans: list[tuple[int, int]] = []
        for lo, hi, accept in _windows(len(line)):
            if deadline is not None and lo:
                # One multi-megabyte line must not outrun the budget either.
                deadline.check()
            context = line if hi - lo == len(line) else line[lo:hi]
            for i, rule in enumerate(applicable):
                filter_fn = rule.get("filter_fn")
                for match in rule["pattern"].finditer(line, lo, hi):
                    start, end = match.span()
                    if start >= accept:
                        break
                    if start < taken[i]:
                        continue
                    taken[i] = max(end, start + 1)
                    if filter_fn and not filter_fn(match, context, filepath):
                        continue
                    if rule.get("secret_type"):
                        # Two secret rules on one span (a token assigned to a
                        # TOKEN key) report it once, under the first rule.
                        if any(s < end and start < e for s, e in secret_spans):
                            continue
                        secret_spans.append((start, end))
                    findings.append(
                        {
                            "file": filepath,
                            "line": line_num,
                            "severity": rule["severity"],
                            "rule": rule["name"],
                            "match": _display_match(rule, match),
                        }
                    )

    return findings


def _scan_bytes(
    filepath: str,
    data: bytes,
    rules: list[dict],
    deadline: _Deadline | None = None,
    out: list[dict] | None = None,
) -> list[dict]:
    """Scan raw file content. Binary content (a NUL byte near the start) gets
    the anchored signatures only; text gets every rule that applies to the path."""
    if b"\0" in data[:_BINARY_SNIFF_BYTES]:
        rules = [r for r in rules if r.get("scope") == "any"]
    return _scan_text(filepath, data.decode("utf-8", errors="replace"), rules, deadline, out)


def _scan_file(filepath: str, rules: list[dict]) -> list[dict]:
    """Scan a single file on disk against all applicable rules, returning findings."""
    if not any(_rule_applies_to_file(r, filepath) for r in rules):
        return []
    try:
        data = Path(filepath).read_bytes()
    except OSError as exc:
        print(f"  [warn] Cannot read {filepath}: {exc}", file=sys.stderr)
        return []
    return _scan_bytes(filepath, data, rules)


class _ScanResult:
    """Findings and counts so far, kept when a scan stops early."""

    def __init__(self) -> None:
        self.findings: list[dict] = []
        self.scanned = 0
        self.skipped = 0
        self.incomplete: list[str] = []

    def summary(self) -> dict:
        return {
            "files_scanned": self.scanned,
            "files_skipped": self.skipped,
            "total": len(self.findings),
            "critical": sum(1 for f in self.findings if f["severity"] == "CRITICAL"),
            "high": sum(1 for f in self.findings if f["severity"] == "HIGH"),
            "medium": sum(1 for f in self.findings if f["severity"] == "MEDIUM"),
            "incomplete": list(self.incomplete),
        }


def _too_large(path: str, size: int) -> str:
    return f"{path}: {size:,} bytes is over the {_MAX_SCAN_BYTES:,}-byte scan limit; not scanned"


def _scan_paths(
    files: list[str], rules: list[dict], ignore_globs: tuple[str, ...], deadline: _Deadline, result: _ScanResult
) -> None:
    """--files: scan each file as it is on disk."""
    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            print(f"  [warn] File not found, skipping: {filepath}", file=sys.stderr)
            result.skipped += 1
            continue
        # Wholesale path ignore (security-review-ignore globs) — vendored /
        # third-party code the repo owner doesn't maintain.
        if path.is_dir() or _path_ignored(str(path), ignore_globs):
            result.skipped += 1
            continue
        deadline.check()
        try:
            size = path.stat().st_size
            if size > _MAX_SCAN_BYTES:
                result.skipped += 1
                result.incomplete.append(_too_large(str(path), size))
                continue
            data = path.read_bytes()
        except OSError as exc:
            result.skipped += 1
            result.incomplete.append(f"{path}: cannot read: {exc.strerror or type(exc).__name__}")
            continue
        result.scanned += 1
        _scan_bytes(str(path), data, rules, deadline, result.findings)


# Staged entries the next commit adds or changes: added, copied, modified,
# renamed, type-changed. Deleted paths hold nothing to scan.
_STAGED_FILTER = "ACMRT"


def _git(cwd: str, *args: str, stdin: bytes | None = None) -> bytes:
    """Run git in cwd and return its stdout; raise _ScanError when it fails."""
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, input=stdin, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _ScanError(f"git {args[0]} could not run: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise _ScanError(f"git {args[0]} failed: {detail[0] if detail else f'exit {proc.returncode}'}")
    return proc.stdout


def _staged_entries(cwd: str) -> tuple[str, list[tuple[str, str]]]:
    """The repository top level, and its staged regular files as (path, blob id)
    with the path relative to the top level. Submodules and symlinks are left out."""
    top = os.fsdecode(_git(cwd, "rev-parse", "--show-toplevel").strip())
    raw = _git(top, "diff", "--cached", "--raw", "-z", "--no-abbrev", f"--diff-filter={_STAGED_FILTER}")
    fields = raw.split(b"\0")
    entries: list[tuple[str, str]] = []
    i = 0
    while i < len(fields):
        head = fields[i]
        i += 1
        if not head:
            continue
        # :<old mode> <new mode> <old id> <new id> <status>, then one path, or two for a rename or copy
        parts = head.lstrip(b":").split()
        if len(parts) != 5:
            raise _ScanError("git diff --raw printed a line this scanner does not understand")
        paths = 2 if parts[4][:1] in (b"R", b"C") else 1
        path = fields[i + paths - 1]
        i += paths
        if parts[1].startswith(b"100"):
            entries.append((path.decode("utf-8", "replace"), parts[3].decode("ascii")))
    return top, entries


def _blob_sizes(top: str, blobs: list[str]) -> dict[str, int]:
    """Blob id -> size in bytes for every blob git has."""
    out = _git(top, "cat-file", "--batch-check", stdin="".join(b + "\n" for b in blobs).encode("ascii"))
    sizes: dict[str, int] = {}
    for line in out.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])
    return sizes


class _BlobReader:
    """Reads blobs, one request at a time, from a single `git cat-file --batch`."""

    def __init__(self, top: str):
        try:
            self._proc = subprocess.Popen(
                ["git", "cat-file", "--batch"],
                cwd=top,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise _ScanError(f"git cat-file could not run: {exc}") from exc

    def read(self, blob: str) -> bytes:
        self._proc.stdin.write(blob.encode("ascii") + b"\n")
        self._proc.stdin.flush()
        header = self._proc.stdout.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise _ScanError(f"git cat-file could not read staged blob {blob[:12]}")
        data = self._proc.stdout.read(int(header[2]))
        self._proc.stdout.read(1)  # the newline git prints after each object
        return data

    def close(self) -> None:
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=10)
        except Exception:
            self._proc.kill()
            self._proc.wait()
        finally:
            self._proc.stdout.close()


def _scan_staged(
    top: str,
    entries: list[tuple[str, str]],
    rules: list[dict],
    ignore_globs: tuple[str, ...],
    deadline: _Deadline,
    result: _ScanResult,
) -> None:
    """--staged: scan each staged blob as the index holds it."""
    wanted = []
    for path, blob in entries:
        if _path_ignored(path, ignore_globs):
            result.skipped += 1
        else:
            wanted.append((path, blob))
    if not wanted:
        return
    sizes = _blob_sizes(top, [blob for _, blob in wanted])
    reader = _BlobReader(top)
    try:
        for path, blob in wanted:
            deadline.check()
            size = sizes.get(blob)
            if size is None:
                result.skipped += 1
                result.incomplete.append(f"{path}: git has no staged blob {blob[:12]}; not scanned")
                continue
            if size > _MAX_SCAN_BYTES:
                result.skipped += 1
                result.incomplete.append(_too_large(path, size))
                continue
            data = reader.read(blob)
            result.scanned += 1
            _scan_bytes(path, data, rules, deadline, result.findings)
    finally:
        reader.close()


def _run_scan(args: argparse.Namespace, result: _ScanResult, deadline: _Deadline) -> None:
    """Load the rules and scan what args name. --staged reads the custom rules
    and the ignore file from the repository top level; --files from the cwd."""
    top, entries = _staged_entries(os.getcwd()) if args.staged else (None, [])
    base = top or os.getcwd()
    rules = _build_rules()
    rules.extend(_load_custom_rules(base))
    ignore_globs = _load_ignore_globs(base)
    if top is not None:
        _scan_staged(top, entries, rules, ignore_globs, deadline, result)
    else:
        _scan_paths(args.files, rules, ignore_globs, deadline, result)


# ─── Output Formatting ────────────────────────────────────────


def _format_text(findings: list[dict], summary: dict) -> str:
    """Format findings as a human-readable text table."""
    lines: list[str] = []
    incomplete = [f"  - {reason}" for reason in summary.get("incomplete", [])]
    if incomplete:
        incomplete.insert(0, "Scan incomplete; these were not fully scanned:")

    if not findings:
        lines.append("No security findings detected.")
        lines.append("")
        lines.append(f"Files scanned: {summary['files_scanned']}")
        lines.extend(incomplete)
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
    lines.extend(incomplete)

    return "\n".join(lines)


def _format_json(findings: list[dict], summary: dict) -> str:
    """Format findings as JSON."""
    return json.dumps(
        {"findings": findings, "summary": summary},
        indent=2,
    )


# ─── Main ─────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic security review scanner. Best effort: a clean result is not a guarantee."
    )
    parser.add_argument("--files", nargs="+", help="Files to scan, as they are on disk")
    parser.add_argument(
        "--staged",
        action="store_true",
        help=(
            "Scan what the next commit holds: every staged blob in the index (added, copied, modified, "
            "renamed or type-changed), named from the repository top level. Run before the command that "
            "commits; files staged by that same command, including by git commit -a or git commit <paths>, "
            "are not in the index yet."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        metavar="SECONDS",
        help="Stop after SECONDS and report the scan as incomplete (exit 2 unless a finding already blocks)",
    )
    args = parser.parse_args(argv)
    if not args.staged and not args.files:
        parser.error("one of --files or --staged is required")

    result = _ScanResult()
    try:
        _run_scan(args, result, _Deadline(args.time_budget))
    except _OutOfTime:
        result.incomplete.append(
            f"the time budget of {args.time_budget:g}s ran out after {result.scanned} file(s); the rest were not scanned"
        )
    except _ScanError as exc:
        result.incomplete.append(str(exc))
    except Exception as exc:
        # A crash is reported (exit 2), never a silent pass.
        result.incomplete.append(f"internal error: {_error_text(exc)}")
    for reason in result.incomplete:
        print(f"  [error] scan incomplete: {reason}", file=sys.stderr)

    summary = result.summary()
    if args.format == "json":
        print(_format_json(result.findings, summary))
    else:
        print(_format_text(result.findings, summary))

    if summary["critical"] > 0 or summary["high"] > 0:
        return 1
    return 2 if summary["incomplete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
