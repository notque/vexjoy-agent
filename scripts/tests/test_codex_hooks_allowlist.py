#!/usr/bin/env python3
"""
Allowlist guard tests for scripts/codex-hooks-allowlist.txt.

Purpose: Codex bug openai/codex#16732 means PreToolUse/PostToolUse hooks only
fire for the Bash tool. Any hook that guards Edit/Write/apply_patch would
register on Codex but silently never run. A registered-but-never-fires hook
is the worst failure mode: users assume protection that does not exist.

These tests ensure that Phase 2 hooks (Edit/Write interceptors) are never
accidentally promoted into the Phase 1 allowlist.

Run: python3 -m pytest scripts/tests/test_codex_hooks_allowlist.py -v
"""

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"
HOOKS_DIR = REPO_ROOT / "hooks"

# ---------------------------------------------------------------------------
# Phase 2 hooks: blocked from allowlist until openai/codex#16732 is fixed
# ---------------------------------------------------------------------------

PHASE_2_HOOKS = {
    "adr-enforcement.py",
    "pretool-config-protection.py",
    "creation-protocol-enforcer.py",
    "posttool-rename-sweep.py",
    "pretool-plan-gate.py",
    "pretool-unified-gate.py",
    "pretool-adr-creation-gate.py",
    "reference-loading-enforcer.py",
    "reference-loading-gate.py",
}

# Events that are NOT tool-tied (skip Edit/Write matcher checks for these)
NON_TOOL_EVENTS = {"SessionStart", "UserPromptSubmit", "Stop"}

# Tool-tied events where the matcher must be "Bash"
TOOL_EVENTS = {"PreToolUse", "PostToolUse"}

# Allowlist line format: EVENT:hook_filename[ matcher]
ALLOWLIST_LINE_RE = re.compile(r"^[A-Za-z]+:[a-zA-Z0-9_\-]+\.py( [A-Za-z]+)?$")

# Patterns in hook source that suggest Edit/Write interception (regex)
EDIT_WRITE_MATCHER_RE = re.compile(
    r"""tool_name\s*(?:==|in)\s*['"\[]{1,2}(?:Edit|Write|MultiEdit|NotebookEdit|apply_patch|WebSearch)"""
    r"""|matches.*(?:Edit|Write)|tool_name.*Edit|tool_name.*Write""",
    re.IGNORECASE,
)

# String literals that look like Edit/Write tool names used as matchers
EDIT_WRITE_LITERAL_RE = re.compile(r"""["'](Edit|Write|MultiEdit|apply_patch|NotebookEdit)["']""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_allowlist_lines() -> list[str]:
    """Return non-comment, non-blank lines from the allowlist file."""
    text = ALLOWLIST_PATH.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def _parse_entry(line: str) -> tuple[str, str, str | None]:
    """Parse an allowlist entry into (event, filename, matcher_or_None)."""
    parts = line.split(" ", 1)
    event_hook = parts[0]
    matcher = parts[1].strip() if len(parts) > 1 else None
    event, filename = event_hook.split(":", 1)
    return event, filename, matcher


def _lines_near_pattern(content: str, pattern: re.Pattern, context_lines: int = 5) -> list[str]:
    """Return source lines near any match, with surrounding context."""
    lines = content.splitlines()
    hits: list[str] = []
    for idx, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            snippet = lines[idx]
            # Include neighboring lines only if they contain matcher-related keywords
            context_keywords = re.compile(r"tool_name|matcher|if |elif ", re.IGNORECASE)
            neighbors = [lines[i] for i in range(start, end) if i != idx and context_keywords.search(lines[i])]
            hit = f"  line {idx + 1}: {snippet.strip()}"
            if neighbors:
                hit += " [nearby: " + " | ".join(n.strip() for n in neighbors[:3]) + "]"
            hits.append(hit)
    return hits


# ---------------------------------------------------------------------------
# Skip guard: skip all tests if allowlist not yet created
# ---------------------------------------------------------------------------


def _require_allowlist() -> None:
    if not ALLOWLIST_PATH.exists():
        pytest.skip("allowlist not yet created; guard will activate on next run")


# ---------------------------------------------------------------------------
# Test: allowlist format is valid
# ---------------------------------------------------------------------------


def test_allowlist_format_valid() -> None:
    """Each non-comment non-blank line must match EVENT:filename[ Matcher]."""
    _require_allowlist()
    lines = _load_allowlist_lines()
    bad: list[str] = []
    for line in lines:
        if not ALLOWLIST_LINE_RE.match(line):
            bad.append(line)
    assert not bad, "Allowlist lines with invalid format:\n" + "\n".join(f"  {b}" for b in bad)


# ---------------------------------------------------------------------------
# Test: all allowlisted hook files exist on disk
# ---------------------------------------------------------------------------


def test_allowlist_hooks_exist() -> None:
    """Every allowlisted hook file must exist in hooks/."""
    _require_allowlist()
    lines = _load_allowlist_lines()
    missing: list[str] = []
    for line in lines:
        _, filename, _ = _parse_entry(line)
        hook_path = HOOKS_DIR / filename
        if not hook_path.exists():
            missing.append(f"  {filename} (from entry: {line})")
    assert not missing, "Allowlisted hooks missing from hooks/ directory:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# Test: no duplicate entries
# ---------------------------------------------------------------------------


def test_no_duplicate_entries() -> None:
    """Each EVENT:filename pair must appear at most once."""
    _require_allowlist()
    lines = _load_allowlist_lines()
    seen: set[str] = set()
    duplicates: list[str] = []
    for line in lines:
        event, filename, _ = _parse_entry(line)
        key = f"{event}:{filename}"
        if key in seen:
            duplicates.append(f"  {key}")
        seen.add(key)
    assert not duplicates, "Duplicate allowlist entries:\n" + "\n".join(duplicates)


# ---------------------------------------------------------------------------
# Test: Phase 2 hooks are NOT in the allowlist (filename guard)
# ---------------------------------------------------------------------------


def test_phase2_hooks_are_NOT_in_allowlist() -> None:
    """Phase 2 hook filenames must not appear in the allowlist at all.

    These hooks intercept Edit/Write/apply_patch calls. Due to Codex bug
    openai/codex#16732, PreToolUse/PostToolUse only fires for Bash, so
    these hooks would register but never run. Silently broken is worse
    than absent.
    """
    _require_allowlist()
    lines = _load_allowlist_lines()
    violations: list[str] = []
    for line in lines:
        _, filename, _ = _parse_entry(line)
        if filename in PHASE_2_HOOKS:
            violations.append(f"  {line}")
    assert not violations, (
        "Phase 2 hooks (Edit/Write interceptors) found in allowlist.\n"
        "These hooks are blocked by openai/codex#16732 and must not be mirrored to Codex.\n"
        "Violations:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: tool-tied events must use Bash matcher only
# ---------------------------------------------------------------------------


def test_pretooluse_posttooluse_matcher_is_bash() -> None:
    """PreToolUse and PostToolUse entries must specify 'Bash' as the matcher.

    Any other matcher (Edit, Write, MultiEdit, or no matcher) would register
    a hook that silently never fires on Codex due to openai/codex#16732.
    """
    _require_allowlist()
    lines = _load_allowlist_lines()
    violations: list[str] = []
    for line in lines:
        event, filename, matcher = _parse_entry(line)
        if event not in TOOL_EVENTS:
            continue
        if matcher != "Bash":
            violations.append(f"  {line}" + (f" (matcher={matcher!r})" if matcher else " (no matcher specified)"))
    assert not violations, (
        "PreToolUse/PostToolUse entries without 'Bash' matcher.\n"
        "Non-Bash matchers silently never fire on Codex (openai/codex#16732).\n"
        "Violations:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Test: allowlisted hook source does not contain Edit/Write intercept patterns
# ---------------------------------------------------------------------------


def test_phase1_hooks_do_not_intercept_edit_write() -> None:
    """For each allowlisted PreToolUse/PostToolUse hook, scan its source for
    Edit/Write/apply_patch interception patterns.

    Failure modes guarded:
    - Pattern 1: tool_name == 'Edit' / tool_name in ['Write', ...] (direct comparison)
    - Pattern 2: string literals 'Edit', 'Write', 'MultiEdit', 'apply_patch' near
      conditional / matcher logic

    Reports ALL violations before failing so maintainers see the full list.
    Session-tied events (SessionStart, UserPromptSubmit, Stop) are skipped.
    Entries with matcher == 'Bash' are nominally safe but still scanned because
    a hook might check tool_name internally to handle both Bash and Edit paths.
    """
    _require_allowlist()
    lines = _load_allowlist_lines()
    warnings: list[str] = []

    for line in lines:
        event, filename, _ = _parse_entry(line)

        # Non-tool events cannot have Edit/Write matchers by design
        if event in NON_TOOL_EVENTS:
            continue

        hook_path = HOOKS_DIR / filename
        if not hook_path.exists():
            # Missing file is caught by test_allowlist_hooks_exist
            continue

        source = hook_path.read_text(encoding="utf-8")

        # Pattern 1: direct tool_name comparison with Edit/Write
        hits1 = _lines_near_pattern(source, EDIT_WRITE_MATCHER_RE)
        if hits1:
            warnings.append(f"\n[WARN] {filename}: tool_name == Edit/Write pattern detected\n" + "\n".join(hits1))

        # Pattern 2: string literals that look like tool-name matchers
        hits2 = _lines_near_pattern(source, EDIT_WRITE_LITERAL_RE)
        if hits2:
            # Filter out false positives: string literals that are clearly
            # comments, docstrings, or user-facing messages (not conditionals)
            real_hits = [h for h in hits2 if not re.search(r"#.*[Ee]dit|#.*[Ww]rite|\"\"\".*[Ee]dit|'{3}.*[Ee]dit", h)]
            if real_hits:
                warnings.append(
                    f"\n[WARN] {filename}: Edit/Write string literals near conditional logic\n" + "\n".join(real_hits)
                )

    assert not warnings, (
        "Phase 1 hooks contain patterns suggesting Edit/Write interception.\n"
        "These hooks would register on Codex but silently never fire (openai/codex#16732).\n"
        "Review each hook and move it to Phase 2 if it guards non-Bash tools.\n" + "".join(warnings)
    )
