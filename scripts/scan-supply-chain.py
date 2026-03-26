#!/usr/bin/env python3
"""
Supply-Chain Auditor — Phase 3 of the security-threat-model skill.

Scans installed hooks, skills, and agents for:
- Zero-width and bidirectional Unicode characters (CRITICAL)
- HTML comments and hidden payload blocks (CRITICAL)
- ANTHROPIC_BASE_URL override patterns (CRITICAL)
- Outbound network commands: curl, wget, nc, ssh (WARNING)
- enableAllProjectMcpServers setting (WARNING)
- Broad unscoped permission grants (WARNING)
- Instruction-override and role-hijacking phrases (CRITICAL)

Output: security/supply-chain-findings.json

Usage:
    python3 scripts/scan-supply-chain.py --scan-dirs hooks/ skills/ agents/ --output security/supply-chain-findings.json
    python3 scripts/scan-supply-chain.py --scan-dirs hooks/ --exclude hooks/pretool-prompt-injection-scanner.py
    python3 scripts/scan-supply-chain.py --help
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ─── Detection Patterns ────────────────────────────────────────

# Invisible Unicode codepoints (same set as pretool-prompt-injection-scanner.py)
_INVISIBLE_CODEPOINTS: frozenset[int] = frozenset(
    [
        0x200B,
        0x200C,
        0x200D,
        0x200E,
        0x200F,
        0x00AD,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0xFEFF,
        0x2060,
        0x2061,
        0x2062,
        0x2063,
        0x2064,
    ]
)

_INVISIBLE_NAMES: dict[int, str] = {
    0x200B: "zero-width space",
    0x200C: "zero-width non-joiner",
    0x200D: "zero-width joiner",
    0x200E: "left-to-right mark",
    0x200F: "right-to-left mark",
    0x00AD: "soft hyphen",
    0x202A: "LTR embedding",
    0x202B: "RTL embedding",
    0x202C: "pop directional formatting",
    0x202D: "LTR override",
    0x202E: "RTL override",
    0xFEFF: "BOM mid-text",
    0x2060: "word joiner",
    0x2061: "function application",
    0x2062: "invisible times",
    0x2063: "invisible separator",
    0x2064: "invisible plus",
}

# Regex-based patterns: (compiled_regex, severity, category, description)
_REGEX_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    # CRITICAL: ANTHROPIC_BASE_URL override
    (
        re.compile(r"ANTHROPIC_BASE_URL", re.IGNORECASE),
        "CRITICAL",
        "base-url-override",
        "ANTHROPIC_BASE_URL found — potential API interception",
    ),
    (
        re.compile(r"<script", re.IGNORECASE),
        "CRITICAL",
        "script-tag",
        "Script tag in non-HTML file",
    ),
    (
        re.compile(r"data:text/html", re.IGNORECASE),
        "CRITICAL",
        "data-uri",
        "data: URI — potential payload carrier",
    ),
    (
        re.compile(r"base64,[A-Za-z0-9+/]{40,}"),
        "CRITICAL",
        "base64-blob",
        "Inline base64 blob — may conceal payload",
    ),
    # CRITICAL: instruction-override phrases (described without literal phrases to avoid self-flagging)
    (
        re.compile(r"\bdisregard\s+(all\s+)?(previous|above|prior)\b", re.IGNORECASE),
        "CRITICAL",
        "instruction-override",
        "Instruction disregard phrase detected",
    ),
    (
        re.compile(r"\bforget\s+(all\s+)?your\s+instructions\b", re.IGNORECASE),
        "CRITICAL",
        "instruction-override",
        "Instruction-clearing phrase detected",
    ),
    (
        re.compile(r"\byou\s+are\s+now\s+a\b", re.IGNORECASE),
        "CRITICAL",
        "role-hijacking",
        "Role-reassignment phrase detected",
    ),
    (
        re.compile(r"\b(admin|developer|jailbreak)\s+mode\b", re.IGNORECASE),
        "CRITICAL",
        "role-hijacking",
        "Privileged mode activation phrase",
    ),
    # WARNING: outbound network commands
    (
        re.compile(r"\bcurl\b"),
        "WARNING",
        "outbound-network",
        "curl command — potential outbound data exfiltration",
    ),
    (
        re.compile(r"\bwget\b"),
        "WARNING",
        "outbound-network",
        "wget command — potential outbound data exfiltration",
    ),
    (
        re.compile(r"\bnc\s+"),
        "WARNING",
        "outbound-network",
        "netcat (nc) command — potential reverse shell",
    ),
    (
        re.compile(r"\bssh\s+"),
        "WARNING",
        "outbound-network",
        "ssh command in hook/skill",
    ),
    # WARNING: MCP auto-approval
    (
        re.compile(r"enableAllProjectMcpServers", re.IGNORECASE),
        "WARNING",
        "mcp-auto-approval",
        "enableAllProjectMcpServers — auto-approves all MCP servers",
    ),
    # WARNING: broad unscoped permissions
    (
        re.compile(r"\b(Read|Write)\(\s*\*\s*\)"),
        "WARNING",
        "unscoped-permission",
        "Unscoped Read(*) or Write(*) — no path constraint",
    ),
]

# File extensions to scan
_SCAN_EXTENSIONS: frozenset[str] = frozenset([".py", ".md", ".json", ".yaml", ".yml", ".sh"])


# ─── Scanning ──────────────────────────────────────────────────


def _scan_file(fpath: Path, excludes: set[str]) -> list[dict]:
    """Scan a single file for all detection patterns. Returns list of findings."""
    if str(fpath) in excludes or fpath.name in excludes:
        return []

    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    findings: list[dict] = []
    lines = text.splitlines()
    seen_categories: set[str] = set()

    # Regex patterns
    for pattern, severity, category, description in _REGEX_PATTERNS:
        for lineno, line in enumerate(lines, 1):
            if pattern.search(line):
                findings.append(
                    {
                        "file": str(fpath),
                        "line": lineno,
                        "severity": severity,
                        "category": category,
                        "pattern": description,
                        "excerpt": line.strip()[:120],
                    }
                )
                seen_categories.add(category)
                break  # one finding per pattern per file

    # HTML comment detection: WARNING for .md files, CRITICAL elsewhere
    _html_comment_pattern = re.compile(r"<!--")
    html_comment_severity = "WARNING" if fpath.suffix == ".md" else "CRITICAL"
    for lineno, line in enumerate(lines, 1):
        if _html_comment_pattern.search(line):
            findings.append(
                {
                    "file": str(fpath),
                    "line": lineno,
                    "severity": html_comment_severity,
                    "category": "hidden-html-comment",
                    "pattern": "HTML comment — may conceal hidden instructions",
                    "excerpt": line.strip()[:120],
                }
            )
            break  # one finding per file

    # Invisible Unicode scan
    for lineno, line in enumerate(lines, 1):
        for char in line:
            cp = ord(char)
            if cp in _INVISIBLE_CODEPOINTS:
                name = _INVISIBLE_NAMES.get(cp, f"U+{cp:04X}")
                findings.append(
                    {
                        "file": str(fpath),
                        "line": lineno,
                        "severity": "CRITICAL",
                        "category": "invisible-unicode",
                        "pattern": f"Invisible Unicode: {name} (U+{cp:04X})",
                        "excerpt": repr(line[:80]),
                    }
                )
                break  # one invisible-unicode finding per file

    return findings


def scan_dirs(
    scan_dirs: list[Path],
    excludes: set[str],
    verbose: bool,
) -> list[dict]:
    """Scan all files across directories. Returns all findings."""
    all_findings: list[dict] = []

    for base_dir in scan_dirs:
        if not base_dir.exists():
            if verbose:
                print(f"  [supply-chain] Directory not found, skipping: {base_dir}", file=sys.stderr)
            continue

        for fpath in sorted(base_dir.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.suffix not in _SCAN_EXTENSIONS:
                continue
            file_findings = _scan_file(fpath, excludes)
            all_findings.extend(file_findings)
            if verbose and file_findings:
                print(
                    f"  [supply-chain] {fpath}: {len(file_findings)} finding(s)",
                    file=sys.stderr,
                )

    return all_findings


# ─── Main ──────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan hooks/skills/agents for supply-chain injection patterns.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--scan-dirs",
        nargs="+",
        default=["hooks", "skills", "agents"],
        help="Directories to scan (default: hooks/ skills/ agents/)",
    )
    parser.add_argument(
        "--output",
        default="security/supply-chain-findings.json",
        help="Output path (default: security/supply-chain-findings.json)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="File paths or names to exclude from scanning",
    )
    parser.add_argument("--verbose", action="store_true", help="Print per-file progress to stderr")
    args = parser.parse_args()

    dirs = [Path(d) for d in args.scan_dirs]
    excludes = set(args.exclude)

    if args.verbose:
        print(f"[supply-chain] Scanning: {[str(d) for d in dirs]}", file=sys.stderr)

    findings = scan_dirs(dirs, excludes, args.verbose)

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]

    result = {
        "scan_dirs": [str(d) for d in dirs],
        "excludes": list(excludes),
        "findings": findings,
        "summary": {
            "total": len(findings),
            "critical": len(critical),
            "warning": len(warnings),
            "files_with_findings": len({f["file"] for f in findings}),
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        f"[supply-chain] CRITICAL={len(critical)} WARNING={len(warnings)} "
        f"total={len(findings)} files_flagged={result['summary']['files_with_findings']}",
        file=sys.stderr,
    )
    print(f"[supply-chain] Written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[supply-chain] FATAL: {e}", file=sys.stderr)
        sys.exit(1)
