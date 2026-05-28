#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Local Security Review Hook (ADR: adr/local-security-review.md)

Single-file hook that dispatches on the `hook_event_name` field of the JSON it
reads from stdin. Two paths, no Agent SDK, no API key, no network calls:

| Event       | Condition                       | Behavior                                            |
|-------------|---------------------------------|-----------------------------------------------------|
| PreToolUse  | Bash command contains git commit| Scan STAGED files via scripts/security-review-scan. |
|             |                                 | HIGH/CRITICAL -> JSON permissionDecision:deny.      |
| PostToolUse | Edit / Write / MultiEdit        | Scan the just-edited file via the same scanner rules|
|             |                                 | and inject findings as ADVISORY additionalContext.  |
|             |                                 | Never blocks (PostToolUse runs after the edit) —    |
|             |                                 | matches Anthropic's edit-time firing.               |
| Stop        | (always)                        | asyncRewake the session agent with the working-tree |
|             |                                 | diff + instruction to run the security-review skill.|

The commit gate (PreToolUse) is the ONLY blocking path. PostToolUse and Stop are
advisory — they inform but never deny, mirroring the ADR's "Stop is advisory" rule
and Anthropic's edit-time PostToolUse reminders.

The deterministic regex layer is `scripts/security-review-scan.py` (the single
source of detection rules — called as a subprocess with `--staged --format json`).
The LLM-depth layer is the CURRENT Claude session: the Stop hook injects the diff
as rewake context and the session agent performs the parallel-code-review Security
pass itself. There is no separate model call.

Contracts:
- PreToolUse deny mirrors `hooks/pretool-branch-safety.py` /
  `hooks/pretool-config-protection.py`: stdout JSON
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "deny", "permissionDecisionReason": ...}}`, exit 0.
- Stop asyncRewake mirrors the official security-guidance plugin's
  security_reminder_hook.py: the rewake context is written to stderr, the hook
  exits 2 (the asyncRewake signal), and a stdout JSON line carries a per-run
  `rewakeSummary`. The `asyncRewake`/`rewakeMessage`/`rewakeSummary` config keys
  live in .claude/settings.json. Stop is ADVISORY — it never blocks a commit.

Bypass / kill switches:
- VEXJOY_SECURITY_REVIEW_SKIP=1     disables the commit BLOCK (deliberate override).
- VEXJOY_SECURITY_REVIEW_DISABLE=1  disables the hook entirely (both events).
- VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS=N  Stop dedup window (default 300s; <=0 disables).

Stop dedup: byte-identical working-tree diffs (under the same cwd) re-firing within
the TTL window short-circuit instead of triggering another rewake. State persists
to ~/.claude/state/security-review-hook/last-diff-hash.json via atomic write.

Fail-open: any internal error allows the commit / skips the rewake and prints a
warning to stderr. A crashed hook never blocks a tool and never stalls a session.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output
from stdin_timeout import read_stdin

_SKIP_ENV = "VEXJOY_SECURITY_REVIEW_SKIP"
_DISABLE_ENV = "VEXJOY_SECURITY_REVIEW_DISABLE"
_DEDUP_TTL_ENV = "VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS"
_DEDUP_TTL_DEFAULT = 300  # 5 minutes

# Stop-event dedup state. Absolute path so it works from any cwd the harness fires in.
_STATE_DIR = Path.home() / ".claude" / "state" / "security-review-hook"
_STATE_FILE = _STATE_DIR / "last-diff-hash.json"

# Matches a `git commit` invocation anywhere in the Bash command string.
_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit(?:\s|$)")


# Resolve the scanner relative to this file so the hook works from any cwd
# (deployed copies live under ~/.claude/hooks/ alongside scripts/).
def _scanner_path() -> Path | None:
    """Locate scripts/security-review-scan.py from known deploy layouts."""
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


def _extract_effective_cwd(command: str, default_cwd: str | None) -> str | None:
    """Extract the effective working directory from a command string.

    Mirrors hooks/pretool-branch-safety.py so `cd <path> && git commit` and
    `git -C <path> commit` scan the right repository.
    """
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p
    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)
    return default_cwd


def _run_scanner(cwd: str | None, staged: bool = True) -> dict | None:
    """Run the deterministic scanner over staged files; return parsed JSON.

    Returns None on any failure (scanner missing, subprocess error, malformed
    output) so callers fail open. The scanner exits 1 on HIGH/CRITICAL, which
    is expected — findings are read from the JSON, not the exit code.
    """
    scanner = _scanner_path()
    if scanner is None:
        return None
    args = [sys.executable, str(scanner), "--format", "json"]
    if staged:
        args.append("--staged")
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or None,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def _format_findings(findings: list[dict], cap: int = 20) -> str:
    """Render HIGH/CRITICAL findings as a compact, file:line list."""
    lines = []
    for f in findings[:cap]:
        lines.append(
            f"  [{f.get('severity', '?')}] {f.get('file', '?')}:{f.get('line', '?')}"
            f" — {f.get('rule', '?')}: {f.get('match', '')}"
        )
    if len(findings) > cap:
        lines.append(f"  ... and {len(findings) - cap} more")
    return "\n".join(lines)


def handle_pre_tool_use(event: dict) -> None:
    """PreToolUse: block `git commit` when staged files have HIGH/CRITICAL findings."""
    command = (event.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not _GIT_COMMIT_RE.search(command):
        sys.exit(0)

    # Deliberate per-commit override — let the commit through.
    if os.environ.get(_SKIP_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[security-review] Bypassed via {_SKIP_ENV}=1", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = _extract_effective_cwd(command, default_cwd)

    report = _run_scanner(cwd, staged=True)
    if report is None:
        # Fail open — the scanner is unavailable or crashed.
        print(
            "[security-review] WARNING: scanner unavailable — allowing commit (fail-open)",
            file=sys.stderr,
        )
        sys.exit(0)

    findings = report.get("findings", [])
    blocking = [f for f in findings if f.get("severity") in ("HIGH", "CRITICAL")]
    if not blocking:
        sys.exit(0)

    summary = report.get("summary", {})
    reason = (
        f"Security review BLOCKED this commit: "
        f"{summary.get('critical', 0)} critical, {summary.get('high', 0)} high finding(s) "
        f"in staged files.\n"
        f"{_format_findings(blocking)}\n"
        f"Fix the findings, or set {_SKIP_ENV}=1 to override deliberately."
    )
    print("[security-review] BLOCKED commit — HIGH/CRITICAL staged findings:", file=sys.stderr)
    print(_format_findings(blocking), file=sys.stderr)
    deny_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(deny_output))
    sys.exit(0)


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


def _edited_file_path(event: dict) -> str | None:
    """Extract the file path the Edit/Write/MultiEdit tool just wrote."""
    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    if isinstance(path, str) and path.strip():
        return path
    return None


def handle_post_tool_use(event: dict) -> None:
    """PostToolUse (Edit|Write|MultiEdit): advisory scan of the just-edited file.

    Mirrors Anthropic's edit-time firing so we surface the same findings at the
    same place. ADVISORY ONLY: PostToolUse runs after the tool, so it cannot block;
    it injects findings as additionalContext. The commit gate stays the only blocker.
    """
    tool_name = event.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        empty_output("PostToolUse").print_and_exit()

    path = _edited_file_path(event)
    if not path:
        empty_output("PostToolUse").print_and_exit()

    # Only scan supported source files; skip everything else silently.
    scanner = _load_scanner_module()
    if scanner is None:
        empty_output("PostToolUse").print_and_exit()

    if scanner._ext(path) not in scanner.SUPPORTED_EXTENSIONS:
        empty_output("PostToolUse").print_and_exit()

    # Resolve the file against the session cwd so relative tool paths scan correctly.
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    abs_path = path if os.path.isabs(path) else os.path.join(cwd or os.getcwd(), path)
    if not os.path.isfile(abs_path):
        empty_output("PostToolUse").print_and_exit()

    try:
        rules = scanner._build_rules()
        rules.extend(scanner._load_custom_rules(cwd or os.getcwd()))
        findings = scanner._scan_file(abs_path, rules)
    except Exception:
        # Fail open — never crash the session over an advisory scan.
        empty_output("PostToolUse").print_and_exit()

    if not findings:
        empty_output("PostToolUse").print_and_exit()

    header = (
        f"[security-review] {len(findings)} potential security finding(s) in {path} "
        f"(advisory — review or document; the commit gate blocks only HIGH/CRITICAL):"
    )
    body = _format_findings(findings)
    context_output("PostToolUse", header + "\n" + body).print_and_exit()


def _working_tree_diff(cwd: str | None) -> str:
    """Return the working-tree diff (tracked changes) for the Stop rewake context."""
    try:
        result = subprocess.run(
            ["git", "diff", "--no-color", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=cwd or None,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def _has_reviewable_content(diff: str) -> bool:
    """Return True if diff has actual added/removed lines (not just mode changes)."""
    for line in diff.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            return True
    return False


def _dedup_ttl_seconds() -> int:
    """Read TTL from env, fall back to default. Non-positive disables dedup."""
    raw = os.environ.get(_DEDUP_TTL_ENV)
    if not raw:
        return _DEDUP_TTL_DEFAULT
    try:
        return int(raw)
    except (ValueError, TypeError):
        return _DEDUP_TTL_DEFAULT


def _diff_signature(cwd: str | None, diff: str) -> str:
    """Hash (cwd, diff) so different repos with identical diffs don't collide."""
    h = hashlib.sha256()
    h.update((cwd or "").encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(diff.encode("utf-8", errors="replace"))
    return h.hexdigest()


def _load_dedup_state() -> dict:
    """Load last-diff-hash state. Empty dict on any failure."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return {}


def _save_dedup_state(state: dict) -> None:
    """Atomic write: tempfile in same dir + os.replace. Silent on failure (advisory path)."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(_STATE_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp, str(_STATE_FILE))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        # Failing to persist dedup state must never block a Stop hook — at worst we
        # double-review on the next event, which is the existing behavior.
        pass


def _is_duplicate_diff(cwd: str | None, diff: str) -> tuple[bool, str | None]:
    """Return (is_duplicate, last_seen_iso). Compares hash + freshness against state file."""
    ttl = _dedup_ttl_seconds()
    if ttl <= 0:
        return False, None
    state = _load_dedup_state()
    sig = _diff_signature(cwd, diff)
    if state.get("hash") != sig:
        return False, None
    try:
        last_ts = float(state.get("ts", 0))
    except (TypeError, ValueError):
        return False, None
    if (time.time() - last_ts) > ttl:
        return False, None
    last_iso = state.get("ts_iso")
    return True, last_iso


def _record_diff_seen(cwd: str | None, diff: str) -> None:
    """Persist the current diff signature so a byte-identical re-fire short-circuits."""
    now = time.time()
    _save_dedup_state(
        {
            "hash": _diff_signature(cwd, diff),
            "ts": now,
            "ts_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "cwd": cwd or "",
        }
    )


def handle_stop(event: dict) -> None:
    """Stop: asyncRewake the session agent to run the security-review pipeline.

    ADVISORY only. Re-wakes the session with the working-tree diff and an
    instruction to run the security-review skill. The session agent (not an SDK
    call) performs the LLM-depth review. Exit 2 is the asyncRewake signal that
    mirrors the official plugin; it does not block any tool or commit.
    """
    # Guard against the asyncRewake loop re-firing endlessly: CC sets
    # stop_hook_active while a rewake is in flight.
    if event.get("stop_hook_active"):
        sys.exit(0)

    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    diff = _working_tree_diff(cwd)
    if not diff.strip() or not _has_reviewable_content(diff):
        # Nothing reviewable (empty or mode-only changes) — skip.
        sys.exit(0)

    # Dedup: short-circuit if this exact diff (under this cwd) was already reviewed
    # within the TTL window. Prevents the rewake from re-firing on Stop events that
    # carry an unchanged working tree.
    is_dup, last_iso = _is_duplicate_diff(cwd, diff)
    if is_dup:
        ts_msg = f" since {last_iso}" if last_iso else ""
        print(
            f"[security-review] diff unchanged{ts_msg} — skipping",
            file=sys.stderr,
        )
        sys.exit(0)

    # Cap the injected diff so the rewake context stays bounded.
    max_chars = 60_000
    truncated = len(diff) > max_chars
    diff_excerpt = diff[:max_chars]

    instruction = (
        "Run the security-review pipeline on the working-tree changes below. "
        "Scope to the changed files, run the deterministic scanner "
        "(scripts/security-review-scan.py), compose the parallel-code-review "
        "Security reviewer over the diff, and report BLOCK/FIX/APPROVE. This "
        "review runs inside the current session — no API key, no SDK. "
        "This is supplementary feedback; after addressing or acknowledging it, "
        "continue with the user's original request."
    )
    if truncated:
        instruction += f"\n\n(diff truncated to {max_chars} chars)"

    # Per-run rewakeSummary (one-liner shown to the user). Mirrors the official
    # plugin's emit_metrics rewake_summary on a stdout JSON line.
    print(json.dumps({"rewakeSummary": "Local security review of session changes"}), flush=True)

    # Record the diff signature so a byte-identical re-fire within the TTL window
    # short-circuits cleanly. Recorded BEFORE exit 2 so the rewake itself won't loop.
    _record_diff_seen(cwd, diff)

    # The rewake context goes to stderr; exit 2 is the asyncRewake signal.
    sys.stderr.write(
        "[security-review] Session security review\n\n"
        + instruction
        + "\n\n=== working-tree diff ===\n"
        + diff_excerpt
        + "\n"
    )
    sys.exit(2)


def main() -> None:
    # Full kill switch — disables both events.
    if os.environ.get(_DISABLE_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[security-review] Disabled via {_DISABLE_ENV}=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)

    hook_event_name = event.get("hook_event_name", "")
    if hook_event_name == "PreToolUse":
        handle_pre_tool_use(event)
    elif hook_event_name == "PostToolUse":
        handle_post_tool_use(event)
    elif hook_event_name == "Stop":
        handle_stop(event)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0/2) propagate normally
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[security-review] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook fails OPEN — never block a commit, never stall a session.
        sys.exit(0)
