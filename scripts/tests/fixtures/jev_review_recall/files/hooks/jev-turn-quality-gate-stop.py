#!/usr/bin/env python3
# hook-version: 1.1.0
"""
Stop hook — done-check and advisory commit-readiness via jev-commit-readiness.py.

Fires on Stop (after the model finishes responding). Two checks, in order:

1. **Done-check**: when the reply claims "done/complete" (Noul >= 0.8) AND no
   test/build/lint probe result appears in the transcript, defers an advisory:
   "done claimed without a probe result; run the test/build and report its exit."
   The probe concedes (probe present = pass regardless of claim); the claim
   alone decides nothing.

2. **Commit-readiness**: detects code changes via working-tree diff, runs
   jev-commit-readiness.py. Non-"ready" verdicts surface a deferred advisory.

This is ADVISORY ONLY — it never blocks. Every failure path exits 0.

Skip conditions (all -> silent exit 0):
  - No working-tree diff (no code changes this turn)
  - Diff is trivial (< 20 chars)
  - Only non-code files changed (*.md, *.txt, *.json config)
  - jev-commit-readiness.py not found
  - Subprocess error/timeout
  - Verdict is "ready" (silence means clean)
  - Dedup: identical diff already checked
  - Recursion guard: stop_hook_active set (rewake in flight)
  - No last_assistant_message (done-check skipped, commit-readiness continues)

Kill switch:
  - VEXJOY_TURN_QUALITY_GATE_DISABLE=1 disables the hook entirely.

Module seams (patched by tests):
  - read_stdin(timeout=...)
  - _working_tree_diff(cwd) -> str
  - _run_commit_readiness(diff_text, cwd) -> dict | None
  - _estimate_done_claim(text) -> float
  - _has_probe_outcome(text) -> bool
  - _STATE_DIR, _STATE_FILE
  - main()
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from hook_utils import (
    DiffDedup,
    async_rewake,
    defer_advisory,
    hook_error,
    working_tree_diff,
)
from stdin_timeout import read_stdin

EVENT_NAME = "Stop"
HOOK_NAME = "jev-turn-quality-gate-stop"
_DISABLE_ENV = "VEXJOY_TURN_QUALITY_GATE_DISABLE"

_TRUSTED_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _TRUSTED_ROOT / "scripts" / "jev-commit-readiness.py"

JEV_TIMEOUT = 10
DIFF_TRUNCATE = 4000
TRIVIAL_THRESHOLD = 20

# Dedup state — own directory so this hook's dedup never collides with
# stop-drift-guard or other Stop hooks.
_STATE_DIR = Path.home() / ".claude" / "state" / "jev-turn-quality-gate"
_STATE_FILE = _STATE_DIR / "last-diff-hash.json"

# Extensions that do NOT count as code changes. If a diff touches ONLY
# these extensions, skip the check entirely.
_NON_CODE_EXTS = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".ini",
        ".csv",
        ".tsv",
        ".rst",
        ".adoc",
        ".lock",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    }
)


# =============================================================================
# Diff inspection
# =============================================================================


def _working_tree_diff(cwd: str | None) -> str:
    """Thin wrapper over hook_utils.working_tree_diff for test patching."""
    return working_tree_diff(cwd)


def _extract_extensions(diff: str) -> set[str]:
    """Extract the set of lowercased file extensions from a unified diff.

    Scans +++ lines (post-image paths). Returns the set of extensions
    found. Returns an empty set if no parseable paths are found.
    """
    exts: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("+++ "):
            continue
        path = line[4:].strip()
        if not path or path == "/dev/null":
            continue
        # Strip git's a/b/ prefix.
        if len(path) > 2 and path[1] == "/" and path[0] in "abciwo":
            path = path[2:]
        dot = path.rfind(".")
        slash = path.rfind("/")
        if dot != -1 and dot > slash:
            exts.add(path[dot:].lower())
    return exts


def _has_code_changes(diff: str) -> bool:
    """Return True if the diff contains at least one code file change.

    A diff that touches only non-code extensions (docs, config, images)
    does not warrant a commit-readiness check.
    """
    exts = _extract_extensions(diff)
    if not exts:
        # No extensions found — could be binary or unusual paths. Skip.
        return False
    # If ANY extension is NOT in the non-code set, there is code.
    return bool(exts - _NON_CODE_EXTS)


# =============================================================================
# Jev subprocess
# =============================================================================


def _run_commit_readiness(diff_text: str, cwd: str | None) -> dict | None:
    """Run jev-commit-readiness.py on the diff text via subprocess.

    Passes the diff via stdin (pipe) since it may be large.
    Returns parsed JSON dict, or None on any failure (fail open).
    """
    import subprocess

    if not _SCRIPT_PATH.is_file():
        return None

    truncated = diff_text[:DIFF_TRUNCATE]
    try:
        proc = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--json-compact"],
            input=truncated,
            capture_output=True,
            text=True,
            timeout=JEV_TIMEOUT,
            cwd=str(_TRUSTED_ROOT),
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    if proc.returncode != 0:
        return None

    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

    return result if isinstance(result, dict) else None


# =============================================================================
# Dedup
# =============================================================================


def _dedup() -> DiffDedup:
    """Build a DiffDedup bound to the current state paths."""
    return DiffDedup(_STATE_DIR, _STATE_FILE)


# =============================================================================
# Commit-intent detection
# =============================================================================

# Patterns in the assistant reply or user prompt that signal commit intent.
_COMMIT_INTENT_ASSISTANT = (
    "git commit",
    "git push",
    "pull request",
    " pr ",
    "create pr",
    "open pr",
    "created pr",
    "opened pr",
    "gh pr create",
)

_COMMIT_INTENT_USER = (
    "commit",
    "push",
    "pull request",
    "create pr",
    "open pr",
)


def _has_commit_intent(event: dict) -> bool:
    """Return True when the turn shows commit intent.

    Checks both the assistant's reply and the user's prompt for commit-related
    keywords. Without commit intent, the Jev commit-readiness check adds no
    value (evidence: 4 calls, 0 findings, "blocked" every turn).
    """
    message = event.get("last_assistant_message", "")
    if isinstance(message, str) and message:
        lower = message.lower()
        for pattern in _COMMIT_INTENT_ASSISTANT:
            if pattern in lower:
                return True

    # Check the user's prompt too.
    for key in ("prompt", "last_user_message"):
        prompt = event.get(key)
        if isinstance(prompt, str) and prompt:
            plower = prompt.lower()
            for pattern in _COMMIT_INTENT_USER:
                if pattern in plower:
                    return True

    return False


# =============================================================================
# Done-check: claim detection + probe-outcome grep
# =============================================================================

# Claim-detection threshold. A done-claim probability >= this value triggers
# the probe-outcome check. Below this, no advisory regardless of probes.
DONE_CLAIM_THRESHOLD = 0.8

# Patterns indicating the reply claims work is done or complete.
_DONE_CLAIM_PATTERNS = [
    re.compile(r"\ball\b.{0,20}\b(?:tasks?|work|changes?|items?)\b.{0,20}\b(?:done|complete|finished)\b", re.I),
    re.compile(r"\b(?:work|task|implementation|changes?) (?:is|are) (?:now )?(?:done|complete|finished)\b", re.I),
    re.compile(r"\b(?:everything|all) (?:is|has been) (?:done|completed|finished)\b", re.I),
    re.compile(r"\bI(?:'ve| have) (?:now )?(?:completed|finished|done)\b", re.I),
    re.compile(r"\b(?:this|that) (?:completes?|finishes?|wraps up)\b", re.I),
    re.compile(r"\btask (?:is )?complete\b", re.I),
    re.compile(r"\bimplementation is (?:now )?complete\b", re.I),
]

# Patterns indicating a test/build/lint/exit-code probe outcome in the text.
_PROBE_OUTCOME_PATTERNS = [
    re.compile(r"\b(?:pytest|py\.test)\b", re.I),
    re.compile(r"\bvitest\b", re.I),
    re.compile(r"\bgo test\b", re.I),
    re.compile(r"\bruff\b"),
    re.compile(r"\bexit code\b", re.I),
    re.compile(r"\b\d+ passed\b", re.I),
    re.compile(r"\btests? passed\b", re.I),
    re.compile(r"\btests? failed\b", re.I),
    re.compile(r"\bPASSED\b"),
    re.compile(r"\bFAILED\b"),
    re.compile(r"\bbuild succeeded\b", re.I),
    re.compile(r"\bbuild failed\b", re.I),
    re.compile(r"\blinting\b", re.I),
    re.compile(r"\bcheck passed\b", re.I),
    re.compile(r"\bcheck failed\b", re.I),
    re.compile(r"\bAll checks passed\b", re.I),
    re.compile(r"\bexited with\b", re.I),
]


def _estimate_done_claim(text: str) -> float:
    """Estimate probability that text claims work is done/complete.

    Deterministic heuristic (no API credits for Jev Noul). Returns 0.0 or 1.0.
    Injectable for tests via module-level patch.
    """
    if not text:
        return 0.0
    for pattern in _DONE_CLAIM_PATTERNS:
        if pattern.search(text):
            return 1.0
    return 0.0


def _has_probe_outcome(text: str) -> bool:
    """Return True if text contains a test/build/lint/exit-code outcome.

    Deterministic grep over known patterns. Injectable for tests via
    module-level patch.
    """
    if not text:
        return False
    for pattern in _PROBE_OUTCOME_PATTERNS:
        if pattern.search(text):
            return True
    return False


# =============================================================================
# Injection formatting
# =============================================================================


def _format_advisory(result: dict) -> str:
    """Format the advisory message from a commit-readiness result."""
    verdict = result.get("verdict", "unknown")
    has_debug = result.get("has_debug_artifacts", False)
    lint_score = result.get("lint_score", 3.0)
    is_partial = result.get("is_partial", False)

    lines = [
        f"[jev-turn-quality-gate] Commit readiness: {verdict}",
        f"  Debug artifacts: {'YES' if has_debug else 'no'}",
        f"  Lint confidence: {lint_score}/5",
        f"  Completeness: {'partial' if is_partial else 'complete'}",
    ]
    return "\n".join(lines)


# =============================================================================
# Stop handler
# =============================================================================


def handle_stop(event: dict) -> None:
    """Stop: run commit-readiness check and advisory rewake on non-ready."""
    session_id = event.get("session_id") if isinstance(event.get("session_id"), str) else None
    # Recursion guard: CC sets stop_hook_active while a rewake is in flight.
    if event.get("stop_hook_active"):
        sys.exit(0)

    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")

    diff = _working_tree_diff(cwd)

    # Front gate: no diff or trivial diff -> skip.
    stripped = diff.strip()
    if not stripped or len(stripped) < TRIVIAL_THRESHOLD:
        sys.exit(0)

    # Only-non-code gate: skip if all changed files are docs/config/images.
    if not _has_code_changes(diff):
        sys.exit(0)

    # Dedup: identical diff already checked -> skip.
    dedup = _dedup()
    is_dup, _last_iso = dedup.is_duplicate(cwd, diff)
    if is_dup:
        sys.exit(0)

    # Done-check: claim >= threshold AND no probe outcome -> advisory.
    message = event.get("last_assistant_message") or ""
    if message:
        claim = _estimate_done_claim(message)
        if claim >= DONE_CLAIM_THRESHOLD and not _has_probe_outcome(message):
            done_text = (
                "[jev-turn-quality-gate] done claimed without a probe result; run the test/build and report its exit."
            )
            done_summary = "done claimed without probe"
            if defer_advisory(session_id, "jev-turn-quality-gate-done", done_text, done_summary):
                print(
                    "[jev-turn-quality-gate] done-check: advisory queued for next prompt",
                    file=sys.stderr,
                )
                # Continue to commit-readiness — done-check does not short-circuit.

    # Commit-intent gate: skip the Jev commit-readiness call unless the turn
    # shows commit/push/PR intent. Evidence: 4/4 calls returned no findings.
    if not _has_commit_intent(event):
        dedup.record(cwd, diff)
        sys.exit(0)

    # Run commit-readiness check.
    result = _run_commit_readiness(diff, cwd)
    if result is None:
        # Script missing, timeout, or parse error -> fail open.
        sys.exit(0)

    verdict = result.get("verdict", "ready")
    if verdict == "ready":
        # Clean -> record dedup and stay silent.
        dedup.record(cwd, diff)
        sys.exit(0)

    # Non-ready verdict -> surface advisory. async_rewake raises
    # SystemExit(2) once the rewake is emitted; record the dedup marker only
    # then, so a rewake that fails before emitting is retried on the next Stop.
    advisory = _format_advisory(result)
    summary = f"Commit readiness: {verdict}"

    text = advisory + "\n\nThis is advisory — review the items above, then continue."
    # Deferred, not rewoken (see hook_utils.defer_advisory): same text, next
    # prompt, no extra generation.
    if defer_advisory(session_id, "jev-turn-quality-gate", text, summary):
        dedup.record(cwd, diff)
        print(f"[jev-turn-quality-gate] {verdict}: advisory queued for next prompt", file=sys.stderr)
        sys.exit(0)
    try:
        async_rewake(text, summary)
    except SystemExit as exc:
        if exc.code == 2:
            dedup.record(cwd, diff)
        raise


def main() -> None:
    # Kill switch.
    if os.environ.get(_DISABLE_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[{HOOK_NAME}] Disabled via {_DISABLE_ENV}=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)

    if event.get("hook_event_name") == "Stop":
        try:
            handle_stop(event)
        except SystemExit:
            raise
        except Exception as e:
            hook_error(HOOK_NAME, e)
    sys.exit(0)


if __name__ == "__main__":
    # No `finally: sys.exit(0)` here: it would swallow the SystemExit(2)
    # that async_rewake raises and the advisory would never fire.
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0/2) propagate.
    except Exception as e:
        hook_error(HOOK_NAME, e)
        sys.exit(0)
