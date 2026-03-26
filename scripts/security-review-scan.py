#!/usr/bin/env python3
"""
Security Review Scanner — deterministic regex-based security scan.

Scans source files for hardcoded secrets, injection vulnerabilities,
and dangerous function calls using pattern matching.

Usage:
    python3 scripts/security-review-scan.py --files file1.py file2.go
    python3 scripts/security-review-scan.py --files src/*.py --format json
    python3 scripts/security-review-scan.py --help

Exit codes:
    0  No HIGH or CRITICAL findings
    1  At least one HIGH or CRITICAL finding
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = frozenset([".py", ".go", ".js", ".ts", ".rb", ".java", ".php", ".kt", ".swift"])

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

# ─── Detection Rules ─────────────────────────────────────────


def _build_rules() -> list[dict]:
    """Build the ordered list of detection rules.

    Each rule dict contains:
      - name: rule identifier
      - severity: CRITICAL | HIGH | MEDIUM
      - pattern: compiled regex
      - skip_test: whether to skip this rule in test files
      - redact: whether to redact matched values (for secrets)
      - filter_fn: optional callable(match, line, filepath) -> bool
                   returning True means *keep* the finding
    """
    rules: list[dict] = []

    # ── CRITICAL ──────────────────────────────────────────

    # Hardcoded secrets: password = '...'
    rules.append(
        {
            "name": "hardcoded-secret",
            "severity": "CRITICAL",
            "pattern": re.compile(
                r"""(?:password|passwd|pwd)\s*=\s*["'][^"']+["']""",
                re.IGNORECASE,
            ),
            "skip_test": False,
            "redact": True,
        }
    )

    # Hardcoded secrets: api_key = '...'
    rules.append(
        {
            "name": "hardcoded-secret",
            "severity": "CRITICAL",
            "pattern": re.compile(
                r"""(?:api_key|apikey|api_secret)\s*=\s*["']""",
                re.IGNORECASE,
            ),
            "skip_test": False,
            "redact": True,
        }
    )

    # Hardcoded secrets: secret = '...'
    rules.append(
        {
            "name": "hardcoded-secret",
            "severity": "CRITICAL",
            "pattern": re.compile(
                r"""(?:secret|secret_key|auth_token|access_token)\s*=\s*["']""",
                re.IGNORECASE,
            ),
            "skip_test": False,
            "redact": True,
        }
    )

    # AWS access key IDs
    rules.append(
        {
            "name": "hardcoded-secret",
            "severity": "CRITICAL",
            "pattern": re.compile(r"AKIA[0-9A-Z]{16}"),
            "skip_test": False,
            "redact": True,
        }
    )

    # PEM private key headers
    rules.append(
        {
            "name": "hardcoded-secret",
            "severity": "CRITICAL",
            "pattern": re.compile(r"-----BEGIN.*PRIVATE KEY-----"),
            "skip_test": False,
            "redact": True,
        }
    )

    # Hardcoded IP addresses (non-private, non-test)
    rules.append(
        {
            "name": "hardcoded-ip",
            "severity": "CRITICAL",
            "pattern": re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"),
            "skip_test": True,
            "redact": False,
            "filter_fn": _filter_private_ip,
        }
    )

    # ── HIGH ──────────────────────────────────────────────

    # Dangerous eval/exec
    rules.append(
        {
            "name": "dangerous-eval",
            "severity": "HIGH",
            "pattern": re.compile(r"\b(?:eval|exec)\s*\("),
            "skip_test": True,
            "redact": False,
        }
    )

    # SQL injection via f-string
    rules.append(
        {
            "name": "sql-injection",
            "severity": "HIGH",
            "pattern": re.compile(
                r"""f["'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*\{""",
                re.IGNORECASE,
            ),
            "skip_test": False,
            "redact": False,
        }
    )

    # SQL injection via .format()
    rules.append(
        {
            "name": "sql-injection",
            "severity": "HIGH",
            "pattern": re.compile(
                r"""["'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*["']\s*\.format\s*\(""",
                re.IGNORECASE,
            ),
            "skip_test": False,
            "redact": False,
        }
    )

    # SQL injection via % formatting
    rules.append(
        {
            "name": "sql-injection",
            "severity": "HIGH",
            "pattern": re.compile(
                r"""["'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*%s.*["']\s*%""",
                re.IGNORECASE,
            ),
            "skip_test": False,
            "redact": False,
        }
    )

    # Shell injection: os.system()
    rules.append(
        {
            "name": "shell-injection",
            "severity": "HIGH",
            "pattern": re.compile(r"\bos\.system\s*\("),
            "skip_test": False,
            "redact": False,
        }
    )

    # Shell injection: subprocess.call with string arg
    rules.append(
        {
            "name": "shell-injection",
            "severity": "HIGH",
            "pattern": re.compile(r"\bsubprocess\.call\s*\("),
            "skip_test": False,
            "redact": False,
        }
    )

    # Shell injection: shell=True with variable
    rules.append(
        {
            "name": "shell-injection",
            "severity": "HIGH",
            "pattern": re.compile(r"shell\s*=\s*True"),
            "skip_test": False,
            "redact": False,
        }
    )

    # ── MEDIUM ────────────────────────────────────────────

    # Security TODOs
    rules.append(
        {
            "name": "security-todo",
            "severity": "MEDIUM",
            "pattern": re.compile(r"(?:TODO.*security|FIXME.*auth|HACK:)", re.IGNORECASE),
            "skip_test": False,
            "redact": False,
        }
    )

    # Unsafe deserialization
    rules.append(
        {
            "name": "unsafe-deserialization",
            "severity": "MEDIUM",
            "pattern": re.compile(r"\bpickle\.loads\s*\("),
            "skip_test": False,
            "redact": False,
        }
    )

    # Unsafe YAML: yaml.load without Loader=
    rules.append(
        {
            "name": "unsafe-yaml",
            "severity": "MEDIUM",
            "pattern": re.compile(r"\byaml\.load\s*\("),
            "skip_test": False,
            "redact": False,
            "filter_fn": _filter_safe_yaml_load,
        }
    )

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
    # Validate all octets are 0-255
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
    """Return True to keep finding (unsafe yaml.load without Loader=)."""
    if "Loader=" in line:
        return False
    return True


# ─── Helpers ──────────────────────────────────────────────────


def _is_test_file(filepath: str) -> bool:
    """Check if a file path matches test file naming conventions."""
    name = Path(filepath).name
    return any(pat.search(name) for pat in _TEST_FILE_PATTERNS)


def _redact_secret(matched_text: str) -> str:
    """Redact secret values in matched text, preserving key names."""
    # Handle key=value patterns: show key, redact value
    redacted = re.sub(
        r"""((?:password|passwd|pwd|api_key|apikey|api_secret|secret|secret_key|auth_token|access_token)\s*=\s*)["'][^"']*["']""",
        r"\1[REDACTED]",
        redacted if False else matched_text,
        flags=re.IGNORECASE,
    )
    # Handle AWS key patterns
    redacted = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA[REDACTED]", redacted)
    # Handle PEM headers (keep header, note redaction)
    redacted = re.sub(r"(-----BEGIN.*PRIVATE KEY-----)", r"\1 [REDACTED]", redacted)
    return redacted


def _scan_file(filepath: str, rules: list[dict]) -> list[dict]:
    """Scan a single file against all rules, returning findings."""
    findings: list[dict] = []
    is_test = _is_test_file(filepath)

    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  [warn] Cannot read {filepath}: {exc}", file=sys.stderr)
        return findings

    lines = text.splitlines()

    for line_num, line in enumerate(lines, start=1):
        for rule in rules:
            # Skip noisy rules in test files
            if is_test and rule.get("skip_test", False):
                continue

            for match in rule["pattern"].finditer(line):
                matched_text = match.group(0)

                # Apply optional filter function
                filter_fn = rule.get("filter_fn")
                if filter_fn and not filter_fn(match, line, filepath):
                    continue

                # Redact secrets
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

    # Header
    lines.append("=" * 80)
    lines.append("SECURITY SCAN RESULTS")
    lines.append("=" * 80)
    lines.append("")

    # Group by severity
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

    # Summary
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
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Source files to scan",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    rules = _build_rules()
    all_findings: list[dict] = []
    files_scanned = 0
    files_skipped = 0

    for filepath in args.files:
        path = Path(filepath)

        # Skip missing files with a warning
        if not path.exists():
            print(
                f"  [warn] File not found, skipping: {filepath}",
                file=sys.stderr,
            )
            files_skipped += 1
            continue

        # Skip unsupported extensions
        if path.suffix not in SUPPORTED_EXTENSIONS:
            files_skipped += 1
            continue

        files_scanned += 1
        all_findings.extend(_scan_file(str(path), rules))

    # Build summary
    summary = {
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "total": len(all_findings),
        "critical": sum(1 for f in all_findings if f["severity"] == "CRITICAL"),
        "high": sum(1 for f in all_findings if f["severity"] == "HIGH"),
        "medium": sum(1 for f in all_findings if f["severity"] == "MEDIUM"),
    }

    # Output
    if args.format == "json":
        print(_format_json(all_findings, summary))
    else:
        print(_format_text(all_findings, summary))

    # Exit 1 if any CRITICAL or HIGH findings
    if summary["critical"] > 0 or summary["high"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
