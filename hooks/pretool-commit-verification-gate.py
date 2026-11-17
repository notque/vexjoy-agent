#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreToolUse:Bash Hook: Commit Verification Gate

Checks that git commit messages carry a `Verified-By:` trailer naming the
verification method. Modes from COMMIT_VERIFY_GATE_MODE:
  off     — exit silently
  observe — (default) log missing trailers to observe.jsonl, never block
  enforce — deny twice per session, then allow the third to prevent deadlocks

Pass-through commits (amend, merge, revert, fixup, squash, -C/-c reuse) are
not checked because they carry or inherit their own verification history.

Source: "How the Claude Code team thinks about verification"
(https://claude.dev/blog/how-the-claude-code-team-thinks-about-verification/).

Bypass: COMMIT_VERIFY_GATE_BYPASS=1 env var. Always exits 0.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard gate
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(2)

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "COMMIT_VERIFY_GATE_BYPASS"
_MODE_ENV = "COMMIT_VERIFY_GATE_MODE"
_VALID_MODES = {"off", "observe", "enforce"}

# Git commit shapes this hook acts on.
_GIT_COMMIT_RE = re.compile(
    r"\bgit(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)|--?[A-Za-z][\w-]*(?:=\S+)?))*\s+commit\b"
)

# Pass-through: amend, fixup, squash, merge, revert, and -C/-c (reuse message).
_PASSTHROUGH_FLAGS = re.compile(r"(?:^|\s)(?:--amend|--fixup|--squash|-[Cc]\s)")
_PASSTHROUGH_SUBJECTS = re.compile(r"^(?:fixup!|squash!|Merge |Revert )")

# The trailer we look for.
_TRAILER_RE = re.compile(r"^Verified-By:\s+\S", re.MULTILINE)

# Heredoc form used by Claude Code: "$(cat <<'EOF'\n...\nEOF\n)"
_CAT_HEREDOC_RE = re.compile(r"\"\$\(cat\s+<<(['\"])([A-Za-z_]\w*)\1\n((?:.*\n)*?)\2\n\s*\)\"")

# State directory for observe and enforce logs.
_STATE_DIR_NAME = "commit-verify-gate"


def _get_mode() -> str:
    """Return the gate mode from the environment."""
    mode = os.environ.get(_MODE_ENV, "observe").lower().strip()
    return mode if mode in _VALID_MODES else "observe"


def _state_dir() -> Path:
    """~/.claude/state/commit-verify-gate/"""
    return Path.home() / ".claude" / "state" / _STATE_DIR_NAME


def _extract_messages(command: str) -> list[str]:
    """Extract commit message text from -m, --message, -F, and heredoc forms.

    Returns a list of message strings. An empty list means the message could
    not be read (e.g. editor commit, or unrecognizable form).
    """
    messages: list[str] = []

    # Heredoc form: "$(cat <<'EOF'\n...\nEOF\n)"
    for m in _CAT_HEREDOC_RE.finditer(command):
        messages.append(m.group(3))

    if messages:
        return messages

    # Tokenize for -m / --message / -F / --file flags.
    try:
        import shlex

        tokens = shlex.split(command)
    except ValueError:
        return []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("-m", "--message") and i + 1 < len(tokens):
            messages.append(tokens[i + 1])
            i += 2
            continue
        if token.startswith("--message="):
            messages.append(token[len("--message=") :])
            i += 1
            continue
        if token.startswith("-") and not token.startswith("--") and "m" in token[1:]:
            # Collapsed flags like -am "msg": -a + -m, message is next token.
            # Only if 'm' is the last flag char (the value follows).
            flag_chars = token[1:]
            if flag_chars.endswith("m") and i + 1 < len(tokens):
                messages.append(tokens[i + 1])
                i += 2
                continue
        if token in ("-F", "--file") and i + 1 < len(tokens):
            filepath = tokens[i + 1]
            if filepath == "-":
                # stdin: cannot read it, skip.
                i += 2
                continue
            try:
                messages.append(Path(filepath).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
            i += 2
            continue
        if token.startswith("--file="):
            filepath = token[len("--file=") :]
            if filepath != "-":
                try:
                    messages.append(Path(filepath).read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
            i += 1
            continue
        i += 1

    return messages


def _has_passthrough_flag(command: str) -> bool:
    """True when the commit is amend, fixup, squash, merge, revert, or -C/-c."""
    return bool(_PASSTHROUGH_FLAGS.search(command))


def _has_passthrough_subject(messages: list[str]) -> bool:
    """True when the message starts with fixup!, squash!, Merge, or Revert."""
    for msg in messages:
        first_line = msg.strip().split("\n", 1)[0]
        if _PASSTHROUGH_SUBJECTS.match(first_line):
            return True
    return False


def _has_trailer(messages: list[str]) -> bool:
    """True when any message contains a Verified-By: trailer."""
    return any(_TRAILER_RE.search(msg) for msg in messages)


def _session_block_count(session_id: str) -> int:
    """Read the block count for this session from the state file."""
    # Sanitize session_id for use as a filename component.
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:64]
    counter_file = _state_dir() / f"enforce-{safe_id}.count"
    try:
        return int(counter_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _increment_block_count(session_id: str) -> int:
    """Increment and return the new block count. Atomic write."""
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:64]
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    counter_file = state / f"enforce-{safe_id}.count"
    count = _session_block_count(session_id) + 1
    tmp = counter_file.with_suffix(f".{os.getpid()}.tmp")
    try:
        tmp.write_text(str(count), encoding="utf-8")
        os.replace(tmp, counter_file)
    except OSError:
        pass
    return count


def _log_observe(session_id: str, repo_dir: str, reason: str) -> None:
    """Append one JSON line to observe.jsonl. Never the message text."""
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repo": os.path.basename(repo_dir) if repo_dir else "",
        "session_id": session_id[:64] if session_id else "",
        "reason": reason,
    }
    try:
        with (state / "observe.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _deny(reason: str) -> None:
    """Print a PreToolUse deny decision to stdout."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.stdout.flush()


def main() -> None:
    mode = _get_mode()
    if mode == "off":
        return

    if os.environ.get(_BYPASS_ENV) == "1":
        print("[commit-verify-gate] BYPASSED", file=sys.stderr)
        return

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(event, dict):
        return

    command = event.get("tool_input", {}).get("command", "")
    if not command or not _GIT_COMMIT_RE.search(command):
        return

    # Pass-through commits are not checked.
    if _has_passthrough_flag(command):
        return

    messages = _extract_messages(command)

    # No readable message: the commit may use an editor or template. Pass.
    if not messages:
        return

    # Pass-through subjects (fixup!, squash!, Merge, Revert).
    if _has_passthrough_subject(messages):
        return

    if _has_trailer(messages):
        return

    # Missing trailer.
    session_id = event.get("session_id", "")
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", "")

    if mode == "observe":
        _log_observe(session_id, cwd, "missing Verified-By trailer")
        return

    # Enforce mode.
    count = _session_block_count(session_id)
    if count >= 2:
        # Allow the third attempt to prevent deadlocks.
        _log_observe(session_id, cwd, "enforce: allowed after 2 blocks")
        print("[commit-verify-gate] Allowed after 2 prior blocks in this session", file=sys.stderr)
        return

    _increment_block_count(session_id)
    _deny(
        "[commit-verify-gate] This commit is missing a Verified-By: trailer. "
        "Add one of these trailers at the end of the commit message:\n"
        "  Verified-By: tests\n"
        "  Verified-By: ci-local\n"
        "  Verified-By: e2e\n"
        "  Verified-By: review\n"
        "  Verified-By: manual\n"
        "  Verified-By: none (reason)\n"
        "The trailer goes on its own line after a blank line, before any Claude-Session: trailer."
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        pass
    finally:
        sys.exit(0)
