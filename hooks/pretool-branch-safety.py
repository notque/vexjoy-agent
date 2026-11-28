#!/usr/bin/env python3
# hook-version: 1.0.2
"""
PreToolUse:Bash Hook: Branch Safety Gate

Blocks git commit commands when the current working branch is main or master.
Forces agents to create a feature branch before committing.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Bash tool.

Detection logic:
- Tool is Bash
- Command contains 'git commit'
- Current branch is 'main' or 'master' (checked via git branch --show-current)

Allow-through conditions:
- Tool is not Bash
- Command does not contain 'git commit'
- Current branch is NOT main or master
- BRANCH_SAFETY_BYPASS=1 env var
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
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from git_cmd import GIT_COMMIT_RE, normalize_bash_path, repo_allows_direct_main, split_shell_tokens
from hook_utils import deny_tool_use, get_tool_input, hook_error, record_governance
from stdin_timeout import read_stdin

_BYPASS_ENV = "BRANCH_SAFETY_BYPASS"
_PROTECTED_BRANCHES = {"main", "master"}
_GIT_VALUE_OPTS = frozenset({"-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"})


def _split_shell_segments(command: str) -> list[str]:
    """Split *command* on unquoted shell separators (&&, ||, ;, |, &, newline)."""
    segments: list[str] = []
    buf: list[str] = []
    in_single = in_double = False
    i = 0
    while i < len(command):
        ch = command[i]
        if ch == "\\" and not in_single and i + 1 < len(command):
            buf.append(ch)
            buf.append(command[i + 1])
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
        elif not in_single and not in_double and ch in ";|&\n":
            seg = "".join(buf).strip()
            if seg:
                segments.append(seg)
            buf = []
            if i + 1 < len(command) and command[i + 1] == ch and ch in "|&":
                i += 1
        else:
            buf.append(ch)
        i += 1
    seg = "".join(buf).strip()
    if seg:
        segments.append(seg)
    return segments


def _resolve_dir(base: str | None, target: str) -> str | None:
    """Resolve *target* against *base*, preserving absolute/Windows drive paths."""
    if not target or "$" in target or "`" in target:
        return base
    expanded = normalize_bash_path(os.path.expanduser(target))
    if os.path.isabs(expanded) or re.match(r"^[A-Za-z]:[/\\]", expanded):
        return expanded
    if base:
        return os.path.normpath(os.path.join(base, expanded))
    return expanded


def _extract_effective_cwd(command: str, default_cwd: str | None) -> str | None:
    """Extract the effective working directory for the `git commit` segment.

    Walks chained shell segments with `split_shell_tokens` up to the `git commit`
    segment, resolving relative/absolute `cd` (unquoted, single-quoted, or
    double-quoted) and `git -C <dir>` against `default_cwd`.
    """
    current_cwd = normalize_bash_path(default_cwd) if default_cwd else default_cwd

    for seg in _split_shell_segments(command):
        toks = split_shell_tokens(seg)
        idx = 0
        while idx < len(toks) and "=" in toks[idx] and not toks[idx].startswith(("=", "-")):
            key = toks[idx].split("=", 1)[0]
            if key and key.replace("_", "").isalnum():
                idx += 1
                continue
            break
        toks = toks[idx:]
        if not toks:
            continue

        exe = toks[0].replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
        if exe == "cd" and len(toks) >= 2:
            arg_i = 1
            while arg_i < len(toks) and toks[arg_i].startswith("-") and toks[arg_i] != "-":
                if toks[arg_i] == "--":
                    arg_i += 1
                    break
                arg_i += 1
            if arg_i < len(toks) and toks[arg_i] != "-":
                current_cwd = _resolve_dir(current_cwd, toks[arg_i])
            continue

        if exe == "git":
            git_cwd = current_cwd
            j = 1
            while j < len(toks):
                tok = toks[j]
                if tok == "--":
                    j += 1
                    break
                if tok == "-C" and j + 1 < len(toks):
                    git_cwd = _resolve_dir(git_cwd, toks[j + 1])
                    j += 2
                    continue
                if tok.startswith("-C") and len(tok) > 2:
                    git_cwd = _resolve_dir(git_cwd, tok[2:])
                    j += 1
                    continue
                if tok in _GIT_VALUE_OPTS and j + 1 < len(toks):
                    j += 2
                    continue
                if tok.startswith("-") and tok != "-":
                    j += 1
                    continue
                break
            if j < len(toks) and toks[j].lower() == "commit":
                return git_cwd

    return current_cwd


def _current_branch(cwd: str | None) -> str | None:
    """Return the current git branch name, or None on error."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            cwd=cwd or None,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _repo_toplevel(cwd: str | None) -> str | None:
    """Return the git repository top-level directory, or None on error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            cwd=cwd or None,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Bash" in settings.json prevents
    # this hook from spawning for non-Bash tools.

    command = get_tool_input(event).get("command", "")
    if not GIT_COMMIT_RE.search(command):
        sys.exit(0)

    # Bypass env var — set when an explicit override is needed.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[branch-safety] Bypassed via BRANCH_SAFETY_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = _extract_effective_cwd(command, default_cwd)
    if repo_allows_direct_main(_repo_toplevel(cwd)):
        if debug:
            print("[branch-safety] Direct main commits explicitly enabled for repo — allowing through", file=sys.stderr)
        sys.exit(0)
    branch = _current_branch(cwd)

    if debug:
        print(f"[branch-safety] git commit detected, branch={branch!r}", file=sys.stderr)

    if branch is None:
        # Cannot determine branch — fail open rather than block valid work.
        if debug:
            print("[branch-safety] Could not determine branch — allowing through", file=sys.stderr)
        sys.exit(0)

    if branch in _PROTECTED_BRANCHES:
        print(
            f"[branch-safety] BLOCKED: Cannot commit directly to {branch}. Create a feature branch first.",
            file=sys.stderr,
        )
        print("[fix-with-skill] pr-workflow", file=sys.stderr)
        record_governance(
            "policy_violation",
            hook_name="pretool-branch-safety",
            tool_name="Bash",
            hook_phase="pre",
            severity="high",
            blocked=True,
            event=event,
            command=command,
        )
        deny_tool_use(
            "PreToolUse",
            f"Cannot commit directly to {branch}. Create a feature branch first. "
            "[fix-with-skill] pr-workflow\nCall the Skill tool with `pr-workflow`.",
        )
        sys.exit(0)

    if debug:
        print(f"[branch-safety] Branch {branch!r} is not protected — allowing through", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-branch-safety", e)
    finally:
        sys.exit(0)
