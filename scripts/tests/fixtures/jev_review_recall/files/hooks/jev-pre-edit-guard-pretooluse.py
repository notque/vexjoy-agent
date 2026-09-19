#!/usr/bin/env python3
# hook-version: 1.2.0
"""
PreToolUse Hook: Jev Pre-Edit Guard

Runs Jev safety checks before Write/Edit/Bash tool calls:

- Write/Edit: three ordered gates.
  1. Protected path (``.env``, ``*.pem``, ``.ssh/``, ... per
     ``jev_redact.is_protected_path``): skip Jev, emit the manual-review context,
     name only the path.
  2. Local deterministic scan (``jev_redact.redact_text``): any hit is a
     high-severity secret. Deny with types + last4 only. Jev is NOT called.
  3. Only when the local scan is clean, run jev-secret-scan.py on the content
     (``call_jev`` redacts the payload again before send). High-severity real
     secrets (severity >= 4, not a false positive) block the tool call via
     permissionDecision:deny. Lower-severity detections inject a warning as
     additionalContext.

- Bash: local scan of the command first. A secret in the command warns
  (additionalContext, types + last4 only) and the command is NOT sent to Jev.
  Otherwise runs jev-rollback-risk.py on the command. Irreversible commands
  that need a backup inject a warning as additionalContext. Never blocks Bash
  (commands are too varied to safely gate).

Shadow mode: set JEV_GATE_MODE=shadow to compute verdicts without acting.
Records what would have happened to ~/.claude/state/gate-shadow.sqlite.

Fail-open: every error path (missing script, subprocess timeout, JSON parse
failure, empty input) exits 0 with no output, allowing the tool through.

Performance: Jev subprocess calls have an 8-second timeout. The hook itself
adds negligible overhead beyond the Jev call.

ADR: adr/jev-pre-edit-guard-pretooluse.md
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import jev_redact
from gate_shadow import record_shadow
from hook_utils import context_output, deny_tool_use, empty_output, get_tool_input, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "PreToolUse"
HOOK_NAME = "jev-pre-edit-guard"

# Module-level session_id, set in main() from the event JSON.
_session_id: str = "unknown"
# ---------------------------------------------------------------------------
# Read-only command classification (Task 1: program-first gate)
# ---------------------------------------------------------------------------

# Programs that are always read-only (no file-mutating side effects).
_READONLY_PROGRAMS = frozenset(
    {
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        "rg",
        "awk",
        "sort",
        "uniq",
        "cut",
        "tr",
        "echo",
        "printf",
        "pwd",
        "stat",
        "file",
        "which",
        "date",
        "diff",
        "jq",
    }
)

# Read-only git subcommands.
_GIT_READONLY_SUBCMDS = frozenset(
    {
        "status",
        "log",
        "diff",
        "show",
        "branch",
        "rev-parse",
        "ls-files",
    }
)

# Programs that are never read-only regardless of arguments.
_DANGEROUS_PROGRAMS_RE = re.compile(r"\b(rm|mv|cp|chmod|chown|kill|curl|wget|pip|npm|sudo)\b")

# Dangerous git subcommands (as two-token sequences).
_DANGEROUS_GIT_RE = re.compile(r"\bgit\s+(commit|push|reset|checkout|clean|stash|rebase)\b")

# SQL mutation keywords.
_SQL_MUTATE_RE = re.compile(r"\b(DELETE|UPDATE|INSERT|DROP|VACUUM)\b", re.IGNORECASE)

# Shell operators that split commands into segments. Match || before |.
_SEGMENT_SPLIT_RE = re.compile(r"\|\||&&|;|\||\n")

# Environment variable assignment at segment start.
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s*")

# Leading cd <path> that can be stripped.
_CD_PREFIX_RE = re.compile(r"^cd\s+\S+\s*$|^cd\s+\S+\s+")


def _is_read_only_command(command: str) -> bool:
    """Return True when every segment of command is provably read-only.

    When unsure, returns False so Jev judges the command. See the Task 1
    spec for the full classification algorithm.
    """
    if not command or not command.strip():
        return False

    # Global checks that immediately disqualify the entire command.
    # Command substitution anywhere.
    if "$(" in command or "`" in command:
        return False
    # Heredocs.
    if "<<" in command:
        return False
    # Redirects to file.
    if re.search(r"(?<![12])>|>>", command):
        return False

    segments = _SEGMENT_SPLIT_RE.split(command)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        # Check for dangerous programs anywhere in the segment.
        if _DANGEROUS_PROGRAMS_RE.search(segment):
            return False
        if _DANGEROUS_GIT_RE.search(segment):
            return False
        if _SQL_MUTATE_RE.search(segment):
            return False

        # Strip leading env assignments.
        stripped = segment
        while _ENV_ASSIGN_RE.match(stripped):
            stripped = _ENV_ASSIGN_RE.sub("", stripped, count=1).lstrip()

        # Strip leading cd <path>.
        cd_match = _CD_PREFIX_RE.match(stripped)
        if cd_match:
            rest = stripped[cd_match.end() :].strip()
            if not rest:
                # Bare cd /path is read-only.
                continue
            stripped = rest

        if not stripped:
            continue

        # Tokenize the remaining command.
        tokens = stripped.split()
        if not tokens:
            continue

        program = tokens[0]

        # Simple read-only programs.
        if program in _READONLY_PROGRAMS:
            continue

        # find: read-only unless -delete or -exec present.
        if program == "find":
            lower_tokens = [t.lower() for t in tokens]
            if "-delete" in lower_tokens or "-exec" in lower_tokens:
                return False
            continue

        # sed: read-only only without -i.
        if program == "sed":
            if "-i" in tokens:
                return False
            # Check that no flag token contains 'i' (e.g. -ni is modifying).
            for t in tokens[1:]:
                if t.startswith("-") and "i" in t and t != "-n":
                    return False
            continue

        # python3: only python3 -m pytest is read-only.
        if program == "python3":
            if len(tokens) >= 3 and tokens[1] == "-m" and tokens[2] == "pytest":
                continue
            return False

        # Ruff linter: only ``ruff check`` or ``ruff format --check``.
        if program == "ruff":
            if len(tokens) >= 2 and tokens[1] == "check":
                continue
            if len(tokens) >= 3 and tokens[1] == "format" and "--check" in tokens:
                continue
            return False

        # git: only read-only subcommands.
        if program == "git":
            if len(tokens) >= 2 and tokens[1] in _GIT_READONLY_SUBCMDS:
                continue
            return False

        # sqlite3: read-only when SQL does not contain mutation keywords.
        if program == "sqlite3":
            sql_parts = " ".join(tokens[1:])
            if _SQL_MUTATE_RE.search(sql_parts):
                return False
            continue

        # tee is a write program.
        if program == "tee":
            return False

        # Unknown program: not provably read-only.
        return False

    return True


def _is_shadow_mode() -> bool:
    """Return True when JEV_GATE_MODE=shadow (compute verdicts, take no action)."""
    return os.environ.get("JEV_GATE_MODE", "enforce").lower() == "shadow"


def _shadow_record(would_action: str, top_probability: float | None = None) -> None:
    """Record a shadow verdict and emit empty_output. Never raises."""
    import time

    record_shadow(HOOK_NAME, _session_id, time.time(), would_action, top_probability)
    empty_output(EVENT_NAME).print_and_exit()


JEV_TIMEOUT = 8  # seconds — single Jev call per script
MAX_CONTENT_LENGTH = 4000  # truncate before passing to Jev

# Severity threshold for blocking Write/Edit (>= this value blocks).
SECRET_BLOCK_SEVERITY = 4.0

# Tools that trigger secret scanning.
WRITE_TOOLS = frozenset({"Write", "Edit"})


def _scripts_dir() -> Path:
    """Resolve the scripts directory relative to this hook file."""
    return Path(__file__).resolve().parent.parent / "scripts"


def _run_jev_script(script_name: str, content: str) -> dict | None:
    """Run a Jev script via --request-file to avoid shell quoting issues.

    Writes content to a temp file (request-file pattern), invokes the script
    as a subprocess, parses JSON stdout. Returns the parsed dict or None on
    any failure (fail open).
    """
    script = _scripts_dir() / script_name
    if not script.is_file():
        return None

    # Truncate content to limit Jev token usage.
    truncated = content[:MAX_CONTENT_LENGTH] if len(content) > MAX_CONTENT_LENGTH else content

    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="jev-guard-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None  # os.fdopen took ownership
            f.write(truncated)

        child_env = os.environ.copy()
        child_env["JEV_SESSION_ID"] = _session_id
        proc = subprocess.run(
            [sys.executable, str(script), "--request-file", tmp_path, "--json-compact"],
            capture_output=True,
            text=True,
            timeout=JEV_TIMEOUT,
            check=False,
            env=child_env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if proc.returncode != 0:
        return None
    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return result if isinstance(result, dict) else None


def _local_hit_summary(types: list[str], redacted: str) -> str:
    """Describe local hits as ``type:last4`` pairs. Never includes the value."""
    tokens = re.findall(r"<redacted:([a-z-]+)(?::([^>]{4}))?>", redacted)
    labels = sorted({f"{kind}:{last4}" if last4 else kind for kind, last4 in tokens})
    if not labels:
        labels = sorted(set(types))
    return ", ".join(labels)


# ---------------------------------------------------------------------------
# Credential-adjacent path detection (Task 6: skip Jev for non-sensitive files)
# ---------------------------------------------------------------------------

# Extensions that suggest the file may contain secrets even when the
# deterministic scan comes up clean.
_CREDENTIAL_EXTS = frozenset({".env", ".pem", ".key", ".p12", ".pfx", ".cfg", ".ini", ".conf"})

# Basename patterns for config/settings files that may hold secrets.
_CREDENTIAL_BASENAME_RE = re.compile(
    r"^(config|settings|secrets|credentials" + r"|" + r"\.env(\..+)?)\.(py|js|ts|sh)$"
    r"|^secrets\.",
    re.IGNORECASE,
)

# Path segments that indicate a credential-adjacent directory.
_CREDENTIAL_PATH_SEGMENTS = frozenset({".ssh", ".gnupg", ".aws", ".config", "credentials", "secrets", "certs"})


def _is_credential_adjacent_path(file_path: str) -> bool:
    """Return True when a file path is close enough to credentials that
    the deterministic scan alone is insufficient -- Jev should double-check.

    Protected paths (Gate 1) are already caught upstream; this covers the
    broader class of config/settings/secrets files where an embedded token
    might slip past regex alone.
    """
    if not file_path or file_path == "unknown":
        return False
    p = Path(file_path)

    # Extension check.
    suffix = p.suffix.lower()
    if suffix in _CREDENTIAL_EXTS:
        return True
    # .env.* compound extensions (e.g. .env.production).
    if ".env." in p.name.lower() or p.name.lower() == ".env":
        return True

    # Basename pattern.
    if _CREDENTIAL_BASENAME_RE.match(p.name):
        return True

    # Path segment check.
    segments = [s.lower() for s in file_path.replace("\\", "/").split("/") if s]
    if any(seg in _CREDENTIAL_PATH_SEGMENTS for seg in segments):
        return True

    return False


def _handle_write_edit(tool_name: str, tool_input: dict) -> None:
    """Gate Write/Edit content: protected path -> local scan -> Jev scan.

    Blocks on protected paths and on any local deterministic hit without
    calling Jev. Otherwise runs jev-secret-scan: blocks on high-severity real
    secrets, warns on lower severity, allows on no secrets, false positives,
    or any failure.
    """
    file_path = tool_input.get("file_path", "unknown")

    shadow = _is_shadow_mode()

    # Gate 1: protected path. Never send the content anywhere; name only the path.
    if file_path != "unknown" and jev_redact.is_protected_path(file_path):
        if shadow:
            _shadow_record("warn")
            return
        context_output(
            EVENT_NAME,
            f"[{HOOK_NAME}] Protected path — Jev secret-scan skipped, manual review required for {file_path}.",
        ).print_and_exit()
        return

    # Extract the content being written.
    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        content = tool_input.get("new_string", "")
    else:
        empty_output(EVENT_NAME).print_and_exit()
        return

    # Skip short or empty content.
    if not content or len(content) < 10:
        empty_output(EVENT_NAME).print_and_exit()
        return

    # Gate 2: local deterministic scan. Any hit is high severity; Jev is not called.
    redacted, types = jev_redact.redact_text(content)
    if types:
        if shadow:
            _shadow_record("block")
            return
        deny_tool_use(
            EVENT_NAME,
            f"[{HOOK_NAME}] BLOCKED: local secret scan found {len(types)} value(s) "
            f"in content for {file_path} ({_local_hit_summary(types, redacted)}). "
            "Remove the secret before writing. Content was not sent to Jev.",
        )
        sys.exit(0)

    # Gate 2b: skip Jev for non-credential-adjacent paths whose local scan
    # was clean. The deterministic scanner catches all high-confidence patterns;
    # Jev adds value only on files where a missed token matters (config, env,
    # credential dirs). Task 6: 67 Jev calls observed, only 2 hits (both
    # "placeholder"), so the vast majority of calls were wasted.
    if not _is_credential_adjacent_path(file_path):
        if shadow:
            _shadow_record("pass")
            return
        empty_output(EVENT_NAME).print_and_exit()
        return

    # Gate 3: Jev scan (call_jev redacts the payload again before send).
    # Only reached for credential-adjacent paths with a clean local scan.
    result = _run_jev_script("jev-secret-scan.py", content)
    if result is None:
        if shadow:
            _shadow_record("pass")
            return
        # Safety check unavailable: warn instead of silently allowing.
        context_output(
            EVENT_NAME,
            f"[{HOOK_NAME}] Jev secret-scan unavailable — manual review recommended for {file_path}.",
        ).print_and_exit()
        return

    has_secrets = result.get("has_secrets", False)
    is_false_positive = result.get("is_false_positive", False)
    severity = float(result.get("severity", 0.0))

    if not has_secrets:
        if shadow:
            _shadow_record("pass", severity)
            return
        empty_output(EVENT_NAME).print_and_exit()
        return

    if is_false_positive:
        if shadow:
            _shadow_record("pass", severity)
            return
        # False positive: allow silently.
        empty_output(EVENT_NAME).print_and_exit()
        return

    if severity >= SECRET_BLOCK_SEVERITY:
        if shadow:
            _shadow_record("block", severity)
            return
        # High severity real secret: BLOCK.
        deny_tool_use(
            EVENT_NAME,
            f"[{HOOK_NAME}] BLOCKED: Jev secret-scan detected a high-severity "
            f"secret in content for {file_path}. Severity: {severity:.0f}/5. "
            "Remove the secret before writing.",
        )
        sys.exit(0)

    # Lower severity, not a false positive: warn but allow.
    if shadow:
        _shadow_record("warn", severity)
        return
    warning = (
        f"[{HOOK_NAME}] WARNING: Jev secret-scan detected a possible secret "
        f"in content for {file_path}. Severity: {severity:.0f}/5. "
        "Review the content for accidental credential exposure."
    )
    context_output(EVENT_NAME, warning).print_and_exit()


def _handle_bash(tool_input: dict) -> None:
    """Run jev-rollback-risk on the Bash command.

    Warns on irreversible commands that need backup. Never blocks.
    """
    command = tool_input.get("command", "")
    if not command or not command.strip():
        empty_output(EVENT_NAME).print_and_exit()
        return

    shadow = _is_shadow_mode()

    # Local scan first: a secret in the command warns and is never sent to Jev.
    redacted, types = jev_redact.redact_text(command)
    if types:
        if shadow:
            _shadow_record("warn")
            return
        warning = (
            f"[{HOOK_NAME}] WARNING: local secret scan found {len(types)} value(s) "
            f"in the Bash command ({_local_hit_summary(types, redacted)}). "
            "Do not put credentials on the command line; command was not sent to Jev."
        )
        context_output(EVENT_NAME, warning).print_and_exit()
        return

    # Program-first gate: skip Jev for provably read-only commands.
    if _is_read_only_command(command):
        if shadow:
            _shadow_record("skip-readonly")
            return
        print(f"[{HOOK_NAME}] read-only command, Jev skipped", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    result = _run_jev_script("jev-rollback-risk.py", command)
    if result is None:
        # Fail open.
        empty_output(EVENT_NAME).print_and_exit()
        return

    is_reversible = result.get("is_reversible", True)
    needs_backup = result.get("needs_backup", False)
    rollback_complexity = result.get("rollback_complexity", "trivial-git-revert")

    if not is_reversible and needs_backup and rollback_complexity in ("irreversible", "needs-manual-steps"):
        if shadow:
            _shadow_record("warn")
            return
        warning = (
            f"[{HOOK_NAME}] WARNING: Jev rollback-risk assessment — command may be "
            f"irreversible and needs backup. Complexity: {rollback_complexity}. "
            "Consider taking a snapshot before proceeding."
        )
        context_output(EVENT_NAME, warning).print_and_exit()
        return

    if shadow:
        _shadow_record("pass")
        return
    empty_output(EVENT_NAME).print_and_exit()


def main() -> None:
    global _session_id

    raw = read_stdin(timeout=2)
    if not raw or not raw.strip():
        empty_output(EVENT_NAME).print_and_exit()
        return

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        empty_output(EVENT_NAME).print_and_exit()
        return

    _session_id = event.get("session_id", "unknown") or "unknown"
    tool_name = event.get("tool_name") or event.get("tool", "")
    tool_input = get_tool_input(event)

    if tool_name in WRITE_TOOLS:
        _handle_write_edit(tool_name, tool_input)
        return

    if tool_name == "Bash":
        _handle_bash(tool_input)
        return

    # Non-target tool: allow.
    empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        hook_error(HOOK_NAME, exc)
    finally:
        sys.exit(0)
