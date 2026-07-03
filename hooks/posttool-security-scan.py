#!/usr/bin/env python3
# hook-version: 2.0.0
"""
PostToolUse:Write,Edit Hook: Unified Security Pattern Scanner

Scans edited/written code files for common security vulnerability patterns
after each modification. Outputs informational warnings — never blocks.

Detection is delegated to the CANONICAL rule engine,
``scripts/security-review-scan.py`` (the single source of detection rules,
shared with hooks/security-review-hook.py). This hook used to hand-maintain
its own ``_build_patterns`` regex list; that fork has been retired. Importing
the canonical engine means this hook automatically inherits:

  - the engine's full rule set (a strict superset of the old inline list —
    parity proven by scripts/tests/test_security_review_scan.py),
  - the 13 test-skip guards (``skip_test`` rules + ``_is_test_file``) so
    project test-fixture files no longer false-positive, and
  - doc-aware filtering (``_DOC_EXTS`` / ``_rule_applies_to_file``) so prose in
    markdown/JSON does not trip code-pattern rules, while anchored secret
    signatures (AKIA/PEM) still fire in docs,
  - custom rules from ``.claude/security-patterns.{yaml,json}``.

Design:
- PostToolUse (informational only, never blocks — always exit 0)
- Only scans files the engine supports (SUPPORTED_EXTENSIONS)
- Reads file content from disk (tool_result may be truncated)
- Fail-open: any error is swallowed and the hook exits 0

ADR: adr/018-post-edit-security-scan.md
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

# Max findings to print before collapsing to a count (avoid noise).
_MAX_FINDINGS = 5


def _scanner_path() -> Path | None:
    """Locate scripts/security-review-scan.py from known deploy layouts.

    Mirrors hooks/security-review-hook.py so this hook works from any cwd
    (deployed copies live under ~/.claude/hooks/ alongside ~/.claude/scripts/).
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "scripts" / "security-review-scan.py",  # repo: hooks/ -> scripts/
        here.parent / "scripts" / "security-review-scan.py",
        Path(os.path.expanduser("~/.claude/scripts/security-review-scan.py")),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _load_scanner_module():
    """Load scripts/security-review-scan.py as a module (single source of rules).

    Returns the module or None on any failure (callers fail open / silent).
    """
    scanner = _scanner_path()
    if scanner is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("security_review_scan", scanner)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        event = json.loads(raw)

        # tool_name/event_type filters are unnecessary — the matcher "Write|Edit"
        # in settings.json prevents this hook from spawning for other tools.
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        if not file_path:
            return

        scanner = _load_scanner_module()
        if scanner is None:
            return

        # Only scan files the engine supports; everything else is skipped.
        if scanner._ext(file_path) not in scanner.SUPPORTED_EXTENSIONS:
            return

        # Resolve relative tool paths against the session cwd.
        cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
        abs_path = file_path if os.path.isabs(file_path) else os.path.join(cwd or os.getcwd(), file_path)
        if not os.path.isfile(abs_path):
            return

        # Build the canonical rule set (+ any project custom rules) and scan.
        # _scan_file applies the engine's test-skip + doc-aware filtering.
        rules = scanner._build_rules()
        rules.extend(scanner._load_custom_rules(cwd or os.getcwd()))
        findings = scanner._scan_file(abs_path, rules)
        if not findings:
            return

        name = Path(file_path).name
        for f in findings[:_MAX_FINDINGS]:
            print(
                f"[SECURITY-HINT] Potential {f.get('rule', '?')} "
                f"({f.get('severity', '?')}) at {name}:{f.get('line', '?')}\n"
                f"  Match: {f.get('match', '')}"
            )
        if len(findings) > _MAX_FINDINGS:
            print(f"  ... and {len(findings) - _MAX_FINDINGS} more security hints")

    except Exception as e:
        hook_error("posttool-security-scan", e)
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code.
        sys.exit(0)


if __name__ == "__main__":
    main()
