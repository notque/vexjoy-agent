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

# Git commit shapes this hook acts on (quick prefilter before shlex parsing).
_GIT_COMMIT_RE = re.compile(
    r"\bgit(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)|--?[A-Za-z][\w-]*(?:=\S+)?))*\s+commit\b"
)

# Pass-through subjects (fixup!, squash!, Merge, Revert).
_PASSTHROUGH_SUBJECTS = re.compile(r"^(?:fixup!|squash!|Merge |Revert )")

# Global git options (before subcommand) that consume a separate argument token.
_GIT_GLOBAL_OPTS_WITH_ARG = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
)

# `git commit` long options that consume a separate argument token when not using `=`.
_COMMIT_LONG_OPTS_WITH_ARG = frozenset(
    {
        "--template",
        "--author",
        "--date",
        "--cleanup",
        "--trailer",
        "--pathspec-from-file",
        "--fixup",
        "--squash",
        "--reuse-message",
        "--reedit-message",
    }
)

# The trailer we look for.
_TRAILER_RE = re.compile(r"^Verified-By:\s+\S", re.MULTILINE)

# Heredoc form used by Claude Code: "$(cat <<'EOF'\n...\nEOF\n)"
_CAT_HEREDOC_RE = re.compile(r"\"\$\(cat\s+<<(['\"])([A-Za-z_]\w*)\1\n((?:.*\n)*?)\2\n\s*\)\"")
# Unquoted token form produced after shlex strips outer double quotes.
_HEREDOC_TOKEN_RE = re.compile(r"^\$\(cat\s+<<(['\"]?)([A-Za-z_]\w*)\1\n((?:.*\n)*?)\2\n?\s*\)$")

# State directory for observe and enforce logs.
_STATE_DIR_NAME = "commit-verify-gate"


def _get_mode() -> str:
    """Return the gate mode from the environment."""
    mode = os.environ.get(_MODE_ENV, "observe").lower().strip()
    return mode if mode in _VALID_MODES else "observe"


def _state_dir() -> Path:
    """~/.claude/state/commit-verify-gate/"""
    return Path.home() / ".claude" / "state" / _STATE_DIR_NAME


def _split_shell_segments(command: str) -> list[list[str]]:
    """Split a shell command into per-simple-command argv lists using shlex."""
    import shlex

    from git_cmd import _WIN_PATH_RE

    # Replace `"$(cat <<'EOF'\n...\nEOF\n)"` heredocs with opaque placeholders
    # before shlex tokenization so inner quotes and shell operators (`;&|\n`)
    # inside commit messages never split segments or cause unbalanced-quote errors.
    placeholders: list[tuple[str, str]] = []
    sentinel = "__VEXJOY_HEREDOC_"
    while sentinel in command:
        sentinel += "_"

    def _stash_heredoc(m: re.Match[str]) -> str:
        token = f"{sentinel}{len(placeholders)}__"
        placeholders.append((token, m.group(3)))
        return token

    stashed = _CAT_HEREDOC_RE.sub(_stash_heredoc, command)
    escaped = _WIN_PATH_RE.sub(lambda m: m.group(0).replace("\\", "\\\\"), stashed)
    lex = shlex.shlex(escaped, posix=True, punctuation_chars=";&|\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    segments: list[list[str]] = []
    current: list[str] = []
    for tok in lex:
        if tok and set(tok) <= set(";&|\n"):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    if placeholders:
        for seg in segments:
            for idx, tok in enumerate(seg):
                if sentinel in tok:
                    for ph, body in placeholders:
                        if ph in tok:
                            tok = tok.replace(ph, body)
                    seg[idx] = tok
    return segments


def _resolve_dir(base: Path | None, target: str) -> Path | None:
    """Resolve a cd / git -C target directory against *base*."""
    if not target or "$" in target or "`" in target:
        return base
    from git_cmd import normalize_bash_path

    norm = normalize_bash_path(os.path.expanduser(target))
    p = Path(norm)
    if p.is_absolute() or re.match(r"^[A-Za-z]:[/\\]", norm):
        return p
    return (base / p) if base is not None else p


def _strip_command_wrappers(seg: list[str]) -> list[str]:
    """Strip leading env assignments and trivial wrappers (`env`, `command`, `builtin`)."""
    i = 0
    while i < len(seg):
        tok = seg[i]
        if tok in ("command", "builtin"):
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                i += 1
            continue
        if tok == "env":
            i += 1
            while i < len(seg) and (seg[i].startswith("-") or ("=" in seg[i] and not seg[i].startswith("="))):
                i += 1
            continue
        if "=" in tok and not tok.startswith(("=", "-")):
            key = tok.split("=", 1)[0]
            if key.replace("_", "").isalnum():
                i += 1
                continue
        break
    return seg[i:]


def _parse_git_commits(command: str, base_cwd: str = "") -> list[tuple[list[str], Path | None]]:
    """Return `(commit_args, effective_repo_cwd)` for each `git ... commit` segment."""
    segments = _split_shell_segments(command)
    current_cwd: Path | None = _resolve_dir(None, base_cwd) if base_cwd else None
    commits: list[tuple[list[str], Path | None]] = []

    for raw_seg in segments:
        seg = _strip_command_wrappers(raw_seg)
        if not seg:
            continue
        cmd_name = seg[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        if cmd_name == "cd" and len(seg) >= 2:
            current_cwd = _resolve_dir(current_cwd, seg[1])
            continue
        if cmd_name not in ("git", "git.exe"):
            continue

        repo_cwd = current_cwd
        i = 1
        while i < len(seg):
            tok = seg[i]
            if tok == "--":
                break
            if tok == "-C" and i + 1 < len(seg):
                repo_cwd = _resolve_dir(repo_cwd, seg[i + 1])
                i += 2
                continue
            if tok.startswith("-C") and len(tok) > 2:
                repo_cwd = _resolve_dir(repo_cwd, tok[2:])
                i += 1
                continue
            if tok in _GIT_GLOBAL_OPTS_WITH_ARG and i + 1 < len(seg):
                i += 2
                continue
            if tok.startswith("-"):
                i += 1
                continue
            if tok == "commit":
                commits.append((seg[i + 1 :], repo_cwd))
            break

    return commits


def _unwrap_message_value(value: str) -> str:
    """If *value* is a `$(cat <<'EOF'...EOF)` heredoc expression, return its body."""
    m = _HEREDOC_TOKEN_RE.match(value)
    return m.group(3) if m else value


def _read_message_file(filepath: str, repo_cwd: Path | None) -> str | None:
    """Read a `-F` / `--file` message file, resolving relative paths against *repo_cwd*."""
    if not filepath or filepath == "-":
        return None
    from git_cmd import normalize_bash_path

    norm = normalize_bash_path(os.path.expanduser(filepath))
    path = Path(norm)
    if not path.is_absolute() and not re.match(r"^[A-Za-z]:[/\\]", norm) and repo_cwd is not None:
        path = repo_cwd / path
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _inspect_commit_args(commit_args: list[str], repo_cwd: Path | None = None) -> tuple[bool, list[str]]:
    """Parse arguments strictly AFTER the `commit` subcommand.

    Returns `(is_passthrough, messages)`. Option values (such as `-m` text) are
    never re-scanned as flags, so message text mentioning `--amend` or `-c`
    cannot trigger pass-through.
    """
    is_passthrough = False
    messages: list[str] = []

    i = 0
    while i < len(commit_args):
        tok = commit_args[i]
        if tok == "--":
            break

        # Pass-through long options.
        if tok == "--amend":
            is_passthrough = True
            i += 1
            continue
        if tok in ("--fixup", "--squash", "--reuse-message", "--reedit-message"):
            is_passthrough = True
            i += 2 if i + 1 < len(commit_args) else 1
            continue
        if tok.startswith(("--fixup=", "--squash=", "--reuse-message=", "--reedit-message=")):
            is_passthrough = True
            i += 1
            continue

        # Message long/short separate options.
        if tok in ("-m", "--message") and i + 1 < len(commit_args):
            messages.append(_unwrap_message_value(commit_args[i + 1]))
            i += 2
            continue
        if tok.startswith("--message="):
            messages.append(_unwrap_message_value(tok[len("--message=") :]))
            i += 1
            continue

        # Message file options.
        if tok in ("-F", "--file") and i + 1 < len(commit_args):
            content = _read_message_file(commit_args[i + 1], repo_cwd)
            if content is not None:
                messages.append(content)
            i += 2
            continue
        if tok.startswith("--file="):
            content = _read_message_file(tok[len("--file=") :], repo_cwd)
            if content is not None:
                messages.append(content)
            i += 1
            continue

        # Other long options that consume a separate argument token.
        if tok in _COMMIT_LONG_OPTS_WITH_ARG and i + 1 < len(commit_args):
            i += 2
            continue

        # Short flag clusters and attached short values (-m"msg", -am"msg", -am "msg", -Fpath, -C HEAD, -cHEAD).
        if tok.startswith("-") and not tok.startswith("--") and len(tok) >= 2:
            flag_chars = tok[1:]
            consumed_next = False
            for j, ch in enumerate(flag_chars):
                rest = flag_chars[j + 1 :]
                if ch == "m":
                    if rest:
                        messages.append(_unwrap_message_value(rest))
                    elif i + 1 < len(commit_args):
                        messages.append(_unwrap_message_value(commit_args[i + 1]))
                        consumed_next = True
                    break
                if ch == "F":
                    if rest:
                        content = _read_message_file(rest, repo_cwd)
                    elif i + 1 < len(commit_args):
                        content = _read_message_file(commit_args[i + 1], repo_cwd)
                        consumed_next = True
                    else:
                        content = None
                    if content is not None:
                        messages.append(content)
                    break
                if ch in ("C", "c"):
                    is_passthrough = True
                    if not rest and i + 1 < len(commit_args):
                        consumed_next = True
                    break
                if ch == "t":
                    if not rest and i + 1 < len(commit_args):
                        consumed_next = True
                    break
            i += 2 if consumed_next else 1
            continue

        i += 1

    return is_passthrough, messages


def _extract_messages(command: str, cwd: str = "") -> list[str]:
    """Extract commit message text from -m, --message, -F, and heredoc forms.

    Returns a list of message strings. An empty list means the message could
    not be read (e.g. editor commit, or unrecognizable form).
    """
    messages: list[str] = []

    try:
        commits = _parse_git_commits(command, base_cwd=cwd)
    except ValueError:
        # Unbalanced quotes: fall back to heredoc extraction only.
        return [m.group(3) for m in _CAT_HEREDOC_RE.finditer(command)]

    for commit_args, repo_cwd in commits:
        _, seg_messages = _inspect_commit_args(commit_args, repo_cwd)
        messages.extend(seg_messages)

    # Also capture any heredoc bodies not already extracted (e.g. non-standard wrapper).
    for m in _CAT_HEREDOC_RE.finditer(command):
        body = m.group(3)
        if body not in messages:
            messages.append(body)

    return messages


def _has_passthrough_flag(command: str) -> bool:
    """True when the commit is amend, fixup, squash, or -C/-c (after `commit`)."""
    try:
        commits = _parse_git_commits(command)
    except ValueError:
        return False
    return any(_inspect_commit_args(commit_args, repo_cwd)[0] for commit_args, repo_cwd in commits)


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
    if not session_id or not session_id.strip():
        return 0
    # Sanitize session_id for use as a filename component.
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id.strip())[:64]
    if not safe_id:
        return 0
    counter_file = _state_dir() / f"enforce-{safe_id}.count"
    try:
        return int(counter_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _increment_block_count(session_id: str) -> int:
    """Increment and return the new block count. Atomic write."""
    if not session_id or not session_id.strip():
        return 0
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id.strip())[:64]
    if not safe_id:
        return 0
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
    if not command or "git" not in command or "commit" not in command:
        return

    session_id = event.get("session_id") or ""
    if not isinstance(session_id, str):
        session_id = ""
    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", "")

    missing_trailer = False
    try:
        commits = _parse_git_commits(command, base_cwd=cwd)
    except ValueError:
        if not _GIT_COMMIT_RE.search(command):
            return
        messages = [m.group(3) for m in _CAT_HEREDOC_RE.finditer(command)]
        if messages and not _has_passthrough_subject(messages) and not _has_trailer(messages):
            missing_trailer = True
    else:
        if not commits:
            return
        for commit_args, repo_cwd in commits:
            is_passthrough, messages = _inspect_commit_args(commit_args, repo_cwd)
            if is_passthrough:
                continue
            # No readable message: the commit may use an editor or template. Pass.
            if not messages:
                continue
            # Pass-through subjects (fixup!, squash!, Merge, Revert).
            if _has_passthrough_subject(messages):
                continue
            if _has_trailer(messages):
                continue
            missing_trailer = True
            break

    if not missing_trailer:
        return

    if mode == "observe":
        _log_observe(session_id, cwd, "missing Verified-By trailer")
        return

    # Enforce mode. Guard empty session_id so missing IDs never share a counter.
    if session_id.strip():
        count = _session_block_count(session_id)
        if count >= 2:
            # Allow the third attempt to prevent deadlocks.
            _log_observe(session_id, cwd, "enforce: allowed after 2 blocks")
            print("[commit-verify-gate] Allowed after 2 prior blocks in this session", file=sys.stderr)
            return
        _increment_block_count(session_id)
    try:
        from hook_utils import record_governance

        record_governance(
            "policy_violation",
            hook_name="pretool-commit-verification-gate",
            tool_name="Bash",
            hook_phase="pre",
            severity="medium",
            blocked=True,
            event=event,
            command=command,
        )
    except Exception:
        pass
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
