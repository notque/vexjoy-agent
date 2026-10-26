#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreToolUse:Bash,Edit,Write Hook: Routing Gate

Ensures Gemini models and other agents emit the 4-Phase Classification
and ROUTING banner before invoking execution or mutating tools.

Allows read-only inspection (Read, read-only bash) so agents can examine
the codebase to formulate their route. Subagent dispatches (invoke_subagent,
Workflow) immediately satisfy routing.
"""

from __future__ import annotations

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
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
    sys.exit(0)

import json
import os
import re
import shlex
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "PreToolUse"
_BYPASS_ENV = "ROUTING_GATE_BYPASS"

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Whitelist of read-only root binaries
_READ_ONLY_BINARIES = frozenset(
    {
        "cat",
        "head",
        "tail",
        "grep",
        "rg",
        "find",
        "ls",
        "pwd",
        "which",
        "echo",
        "file",
        "wc",
        "stat",
        "readlink",
        "basename",
        "dirname",
    }
)

_GIT_READ_SUBCOMMANDS = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "branch",
        "rev-parse",
        "config",
        "remote",
        "ls-files",
        "describe",
    }
)

_GIT_MUTATING_TOKENS = frozenset(
    {
        "commit",
        "push",
        "merge",
        "rebase",
        "cherry-pick",
        "reset",
        "checkout",
        "switch",
        "tag",
        "clean",
        "stash",
        "apply",
        "revert",
    }
)


def _state_dir() -> Path:
    env_dir = os.environ.get("VEXJOY_ROUTING_STATE_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(tempfile.gettempdir()) / "vexjoy-routing-state"


def _state_path(session_id: str) -> Path:
    safe_id = _SAFE_ID_RE.sub("_", session_id.strip() or "default")[:80]
    return _state_dir() / f"routing-state-{safe_id}.json"


def load_routing_state(session_id: str) -> dict:
    path = _state_path(session_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def mark_session_routed(session_id: str) -> None:
    path = _state_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = load_routing_state(session_id)
        data["routed"] = True
        data["timestamp"] = time.time()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def is_read_only_command(cmd_str: str) -> bool:
    """Return True if the command is purely inspection/read-only."""
    if not cmd_str or not cmd_str.strip():
        return True

    # Reject commands containing redirection operators that write files
    if re.search(r"(?:>|>>|\|\s*tee\b)", cmd_str):
        return False

    # Check command pipelines or chains
    sub_cmds = re.split(r"[;&|]+", cmd_str)
    for sub in sub_cmds:
        sub = sub.strip()
        if not sub:
            continue
        try:
            tokens = shlex.split(sub)
        except ValueError:
            # Unterminated quote or invalid syntax; treat as mutating
            return False

        if not tokens:
            continue

        bin_name = Path(tokens[0]).name

        if bin_name == "git":
            if len(tokens) < 2:
                continue
            subcmd = tokens[1]
            if subcmd in _GIT_MUTATING_TOKENS:
                return False
            if subcmd not in _GIT_READ_SUBCOMMANDS:
                return False
            continue

        if bin_name in _READ_ONLY_BINARIES:
            continue

        # Any non-whitelisted binary is considered modifying/execution
        return False

    return True


def check_transcript_for_routing(session_id: str) -> bool:
    """Check Antigravity conversation transcript for turn-1 routing banner."""
    if not session_id or session_id == "default":
        return False

    # Check both brain directory and env paths
    candidate_paths = [
        Path.home()
        / ".gemini"
        / "antigravity-cli"
        / "brain"
        / session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl",
    ]
    brain_env = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
    if brain_env:
        candidate_paths.append(Path(brain_env) / session_id / ".system_generated" / "logs" / "transcript.jsonl")

    transcript_file: Path | None = None
    for p in candidate_paths:
        if p.is_file():
            transcript_file = p
            break

    if not transcript_file:
        return False

    try:
        lines = transcript_file.read_text(encoding="utf-8").splitlines()
        # Scan backward from the end
        user_input_idx = -1
        for idx in range(len(lines) - 1, -1, -1):
            line = lines[idx].strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue
            if step.get("source") in ("USER_EXPLICIT", "USER") and step.get("type") == "USER_INPUT":
                user_input_idx = idx
                break

        # Check all MODEL steps after the last user input
        start_scan = user_input_idx if user_input_idx >= 0 else 0
        for idx in range(start_scan, len(lines)):
            line = lines[idx].strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue
            if step.get("source") == "MODEL":
                content = str(step.get("content") or "")
                if (
                    "ROUTING:" in content
                    or "===================================================================" in content
                    or "[do-route]" in content
                ):
                    return True
                # If tool calls include invoke_subagent or run_workflow
                tool_calls = step.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tc in tool_calls:
                        if isinstance(tc, dict) and tc.get("name") in ("invoke_subagent", "run_workflow"):
                            return True
    except OSError:
        pass

    return False


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        empty_output(EVENT_NAME)
        return

    raw = read_stdin()
    if not raw:
        empty_output(EVENT_NAME)
        return

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        hook_error(EVENT_NAME, f"invalid input JSON: {exc}")
        return

    session_id = str(event.get("session_id") or event.get("conversationId") or "default")
    tool_name = str(event.get("tool_name") or event.get("agy_tool_name") or "")
    tool_input = event.get("tool_input") or event.get("agy_tool_args") or {}

    # Agent dispatches always satisfy routing requirements
    if tool_name in ("Agent", "invoke_subagent", "Workflow", "run_workflow"):
        mark_session_routed(session_id)
        empty_output(EVENT_NAME)
        return

    # Read-only file inspection is always allowed
    if tool_name in ("Read", "read_file"):
        empty_output(EVENT_NAME)
        return

    # Bash / run_command inspection is allowed if read-only
    if tool_name in ("Bash", "run_command"):
        cmd = str(tool_input.get("command") or tool_input.get("CommandLine") or "")
        if is_read_only_command(cmd):
            empty_output(EVENT_NAME)
            return

    # Here we have a mutating tool (Edit, Write, or modifying Bash command)
    state = load_routing_state(session_id)

    # If state already marked routed or non-trivial is False, allow
    if state.get("routed") is True or state.get("non_trivial") is False:
        empty_output(EVENT_NAME)
        return

    # Check live transcript for turn-1 banner
    if check_transcript_for_routing(session_id):
        mark_session_routed(session_id)
        empty_output(EVENT_NAME)
        return

    # Block tool use
    reason = (
        "BLOCKED by VexJoy Routing Gate: Task is unrouted. "
        "You must output the /do CLASSIFY and ROUTING banner in Turn 1 before calling execution tools. "
        "Emit the routing decision first."
    )
    deny_tool_use(EVENT_NAME, reason)


if __name__ == "__main__":
    main()
