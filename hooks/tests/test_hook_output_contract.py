"""Every hook registered in .claude/settings.json emits only output Claude Code accepts (B-16).

Claude Code 2.1.319 validates a hook's JSON stdout against one schema per
event. A field outside it is rejected or ignored (a top-level
``permissionDecision`` on SubagentStop never blocks), a mismatched
``hookSpecificOutput.hookEventName`` raises "Hook returned incorrect event
name", and two JSON documents on stdout are read as plain text, which loses a
deny. This test runs each registered hook in a sandbox HOME with
representative payloads for its event and checks any JSON it prints against
that schema. Plain-text output is outside this contract and is not checked.

The validator has its own negative controls at the end of the file.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks"
SETTINGS = ROOT / ".claude" / "settings.json"
RUN_TIMEOUT_SECONDS = 60

# --- The 2.1.319 output schema ------------------------------------------------

_TOP_LEVEL = {
    "continue",
    "suppressOutput",
    "stopReason",
    "decision",
    "systemMessage",
    "terminalSequence",
    "reason",
    "hookSpecificOutput",
}
_TOP_LEVEL_TYPES = {
    "continue": bool,
    "suppressOutput": bool,
    "stopReason": str,
    "systemMessage": str,
    "terminalSequence": str,
    "reason": str,
    "hookSpecificOutput": dict,
}
_DECISIONS = {"approve", "block"}
# hookSpecificOutput keys besides hookEventName; an event missing here has none.
_SPECIFIC = {
    "PreToolUse": {
        "permissionDecision",
        "permissionDecisionReason",
        "updatedInput",
        "additionalContext",
        "permissionDisplay",
    },
    "UserPromptSubmit": {"additionalContext", "sessionTitle", "suppressOriginalPrompt"},
    "UserPromptExpansion": {"additionalContext", "suppressOriginalPrompt"},
    "SessionStart": {"additionalContext", "initialUserMessage", "sessionTitle", "watchPaths", "reloadSkills"},
    "Setup": {"additionalContext"},
    "PreModelSwitch": {"permissionDecision", "permissionDecisionReason"},
    "PostModelSwitch": {"additionalContext"},
    "SubagentStart": {"additionalContext"},
    "PostToolUse": {"additionalContext", "classifierContext", "updatedToolOutput", "updatedMCPToolOutput"},
    "PostToolUseFailure": {"additionalContext"},
    "PostToolBatch": {"additionalContext"},
    "Stop": {"additionalContext"},
    "SubagentStop": {"additionalContext"},
    "PermissionDenied": {"retry"},
    "Notification": {"additionalContext"},
    "PermissionRequest": {"decision"},
    "Elicitation": {"action", "content"},
    "ElicitationResult": {"action", "content"},
    "CwdChanged": {"watchPaths"},
    "FileChanged": {"watchPaths"},
    "WorktreeCreate": {"worktreePath"},
    "MessageDisplay": {"displayContent"},
}
_PERMISSION_DECISIONS = {"allow", "deny", "ask", "defer"}


def contract_violations(event: str, stdout: str) -> list[str]:
    """Why *stdout* is not output Claude Code accepts for *event*; [] when it is
    valid or is not JSON at all."""
    text = stdout.strip()
    if not text.startswith("{"):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        if exc.msg == "Extra data":
            return ["several JSON documents on stdout: Claude Code reads them as plain text"]
        return [f"stdout starts like JSON but does not parse: {exc.msg}"]
    if not isinstance(data, dict):
        return ["JSON output is not an object"]
    if "async" in data:
        extra = set(data) - {"async", "asyncTimeout"}
        problems = [f"async output carries other keys: {sorted(extra)}"] if extra else []
        if data["async"] is not True:
            problems.append("async must be true")
        return problems

    problems = [f"unknown top-level key {key!r}" for key in sorted(set(data) - _TOP_LEVEL)]
    for key, expected in _TOP_LEVEL_TYPES.items():
        if key in data and not isinstance(data[key], expected):
            problems.append(f"{key} must be {expected.__name__}")
    if "decision" in data and data["decision"] not in _DECISIONS:
        problems.append(f"decision must be one of {sorted(_DECISIONS)}, got {data['decision']!r}")

    specific = data.get("hookSpecificOutput")
    if isinstance(specific, dict):
        allowed = _SPECIFIC.get(event)
        if allowed is None:
            problems.append(f"{event} accepts no hookSpecificOutput")
        else:
            if specific.get("hookEventName") != event:
                problems.append(f"hookSpecificOutput.hookEventName is {specific.get('hookEventName')!r}, not {event!r}")
            for key in sorted(set(specific) - allowed - {"hookEventName"}):
                problems.append(f"hookSpecificOutput.{key} is not valid for {event}")
            if "additionalContext" in specific and not isinstance(specific["additionalContext"], str):
                problems.append("additionalContext must be a string")
            if event == "PreToolUse" and "permissionDecision" in specific:
                if specific["permissionDecision"] not in _PERMISSION_DECISIONS:
                    problems.append(f"permissionDecision {specific['permissionDecision']!r} is not valid")
    return problems


# --- Registrations ----------------------------------------------------------------

_HOOK_SCRIPT_RE = re.compile(r"\$HOME/\.claude/hooks/([A-Za-z0-9_.-]+\.py)\"")

# Registrations this test does not run, and why.
_NOT_RUN = {
    "session-bootstrap.sh": "cloud bootstrap shell script: it installs the toolkit, so it never runs in a test",
    "sync-to-user-claude.py": (
        "syncs the toolkit into ~/.claude and is never run outside its installer sandbox; "
        "scripts/tests/test_codex_hooks_runtime_compat.py covers its runtime"
    ),
}

# Known violations owned by other findings. Non-strict, so the fix landing in
# another PR does not turn this suite red.
_KNOWN = {
    ("SubagentStop", "subagent-completion-guard.py"): (
        "B-01: the guard prints a top-level permissionDecision, which SubagentStop ignores"
    ),
}


def _registrations() -> list:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    params = []
    for event, groups in settings["hooks"].items():
        for group in groups:
            matcher = group.get("matcher", "")
            for handler in group.get("hooks", []):
                command = handler.get("command", "")
                match = _HOOK_SCRIPT_RE.search(command)
                script = match.group(1) if match else Path(command.split()[-1].strip('"')).name
                case_id = f"{event}:{script}" + (f"[{matcher}]" if matcher else "")
                marks = []
                if script in _NOT_RUN:
                    marks.append(pytest.mark.skip(reason=_NOT_RUN[script]))
                elif not match:
                    raise AssertionError(f"unrecognized hook command shape: {command}")
                if (event, script) in _KNOWN:
                    marks.append(pytest.mark.xfail(strict=False, reason=_KNOWN[(event, script)]))
                params.append(pytest.param(event, matcher, script, id=case_id, marks=marks))
    return params


REGISTRATIONS = _registrations()


def test_every_settings_registration_is_covered() -> None:
    """The parametrization tracks settings.json; a new hook is checked without edits here."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    handlers = sum(len(g.get("hooks", [])) for groups in settings["hooks"].values() for g in groups)
    assert len(REGISTRATIONS) == handlers


# --- Sandbox and payloads ------------------------------------------------------------


def _git(cwd: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, timeout=30)


def _sandbox(tmp_path: Path, session_id: str) -> tuple[Path, dict[str, str], Path]:
    home, project, state, temp, bin_dir = (tmp_path / n for n in ("home", "project", "state", "tmp", "bin"))
    for path in (home, project, state, temp, bin_dir):
        path.mkdir()
    # Stand-ins so nothing reaches a real CLI, model or the GitHub API.
    for name, code in (("codex", 0), ("gh", 1), ("claude", 1)):
        fake = bin_dir / name
        fake.write_text(f"#!/bin/sh\nexit {code}\n", encoding="utf-8")
        fake.chmod(0o755)
    # The sandbox does not rely on the root conftest: host integrations (herdr,
    # Jev), credentials and git overrides never reach a hook under test.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "HERDR_", "JEV_", "SSH_"))
        and not k.endswith(("_API_KEY", "_TOKEN"))
        and k not in ("PYTHONPATH", "TMUX", "STY")
    }
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "XDG_CACHE_HOME": str(state / "cache"),
            "XDG_CONFIG_HOME": str(state / "config"),
            "XDG_STATE_HOME": str(state / "xdg"),
            "TMPDIR": str(temp),
            "CLAUDE_LEARNING_DIR": str(state / "learning"),
            "CLAUDE_ROUTING_STATE_DIR": str(state / "routing"),
            "CLAUDE_PROJECT_DIR": str(project),
            "CLAUDE_SESSION_ID": session_id,
            "CLAUDE_KAIROS_ENABLED": "false",
            "PROTECTED_ORGS": "",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        }
    )
    for key in ("CLAUDE_HOOKS_DEBUG", "CLAUDE_HOOK_DEBUG", "GH_TOKEN", "GITHUB_TOKEN", "CLAUDE_AFK_MODE"):
        env.pop(key, None)

    _git(project, env, "init", "-q")
    _git(project, env, "symbolic-ref", "HEAD", "refs/heads/main")
    (project / "notes.txt").write_text("a\n", encoding="utf-8")
    skill = project / "skills" / "contract-probe"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("A skill file without frontmatter.\n", encoding="utf-8")
    (project / "decision.md").write_text("# Contract decision\n", encoding="utf-8")
    # Queued state that SessionStart and UserPromptSubmit hooks inject.
    claude_state = home / ".claude" / "state"
    (claude_state / "pending-advisories").mkdir(parents=True)
    (claude_state / "pending-advisories" / f"{session_id}.jsonl").write_text(
        json.dumps({"ts": time.time(), "source": "contract", "summary": "probe", "message": "queued advisory"}) + "\n",
        encoding="utf-8",
    )
    (claude_state / "task-registry.json").write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {
                        "id": "261107-001",
                        "agent": "python-general-engineer",
                        "skill": "",
                        "complexity": "simple",
                        "summary": "contract probe task",
                        "dispatched_at": datetime.now(timezone.utc).isoformat(),
                        "completed_at": None,
                        "status": "dispatched",
                        "session_id": "earlier-session",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # A reviewer that wrote a file: the subagent guard's READ-ONLY path (B-01).
    transcript = state / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": "x.py"}})
        + "\n"
        + json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "done"}})
        + "\n",
        encoding="utf-8",
    )
    return project, env, transcript


def _tool_payloads(project: Path) -> list[tuple[str, dict, dict]]:
    """(tool_name, tool_input, tool_response) cases, each picked to reach a hook's output path."""
    skill_md = str(project / "skills" / "contract-probe" / "SKILL.md")
    return [
        ("Bash", {"command": 'git commit -m "contract probe"'}, {"stdout": "", "stderr": "", "exit_code": 0}),
        ("Bash", {"command": "printf probe"}, {"stdout": "probe", "stderr": "", "exit_code": 0}),
        ("Read", {"file_path": str(project / ".env")}, {"type": "text", "file": {"content": ""}}),
        ("Read", {"file_path": str(project / "notes.txt")}, {"type": "text", "file": {"content": "a\n"}}),
        ("Write", {"file_path": skill_md, "content": "A skill file without frontmatter.\n"}, {"success": True}),
        (
            "Edit",
            {"file_path": str(project / "notes.txt"), "old_string": "a", "new_string": "b"},
            {"success": True},
        ),
        (
            "Agent",
            {
                "description": "create agent",
                "prompt": "[do-route] agent=python-general-engineer skill=-\nCreate a new agent for contract probes.",
                "subagent_type": "general-purpose",
            },
            {"content": [{"type": "text", "text": "done"}]},
        ),
        ("Skill", {"skill": "quick"}, {"success": True}),
    ]


def _matches(matcher: str, tool_name: str) -> bool:
    return matcher in ("", "*") or tool_name in matcher.split("|")


def _payloads(event: str, matcher: str, project: Path, transcript: Path, session_id: str) -> list[dict]:
    base = {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "cwd": str(project),
        "hook_event_name": event,
        "permission_mode": "default",
    }
    if event in ("PreToolUse", "PostToolUse"):
        cases = []
        for tool_name, tool_input, tool_response in _tool_payloads(project):
            if _matches(matcher, tool_name):
                payload = {**base, "tool_name": tool_name, "tool_input": tool_input, "tool_use_id": "toolu_contract"}
                if event == "PostToolUse":
                    payload["tool_response"] = tool_response
                cases.append(payload)
        return cases
    variants = {
        "SessionStart": [{"source": "startup"}, {"source": "compact"}],
        "UserPromptSubmit": [{"prompt": "create a pipeline for contract checks"}, {"prompt": "contract probe"}],
        "PreCompact": [{"trigger": "manual", "custom_instructions": ""}],
        "PostCompact": [{"trigger": "manual", "compact_summary": "contract probe"}],
        "SubagentStart": [{"agent_id": "agent-contract", "agent_type": "Explore"}],
        "SubagentStop": [
            {
                "agent_id": "agent-contract",
                "agent_type": agent_type,
                "agent_transcript_path": str(transcript),
                "stop_hook_active": False,
                "last_assistant_message": "done",
            }
            for agent_type in ("general-purpose", "reviewer-contract")
        ],
        "Stop": [{"stop_hook_active": False, "last_assistant_message": "done"}],
        "StopFailure": [{"error": "rate_limit", "error_details": "contract probe"}],
        "SessionEnd": [{"reason": "other"}],
    }
    assert event in variants, f"no contract payload for {event}: add one"
    return [{**base, **extra} for extra in variants[event]]


def _cleanup_global_state(session_id: str) -> None:
    """Hooks that key /tmp state on the session id; this run's id is unique."""
    shutil.rmtree(Path("/tmp/.claude-backups") / session_id, ignore_errors=True)
    for leftover in Path("/tmp").glob(f"claude-*{session_id}*"):
        if leftover.is_dir():
            shutil.rmtree(leftover, ignore_errors=True)
        else:
            leftover.unlink(missing_ok=True)


def _set_adr_session(project: Path, active: bool) -> None:
    """An active ADR session wakes the ADR, synthesis and compaction hooks and
    silences others (creation-protocol-enforcer), so each hook runs both ways."""
    marker = project / ".adr-session.json"
    if not active:
        marker.unlink(missing_ok=True)
        return
    marker.write_text(
        json.dumps(
            {
                "adr_path": str(project / "decision.md"),
                "adr_hash": "contract-hash",
                "domain": "contract-probe",
                "registered_at": "2026-07-11T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def run_registration(tmp_path: Path, event: str, matcher: str, script: str) -> list[tuple[str, str]]:
    """Run one registered hook on every payload for its event, without and then
    with an ADR session; return (label, stdout) per run."""
    session_id = f"contract-{uuid.uuid4().hex[:12]}"
    project, env, transcript = _sandbox(tmp_path, session_id)
    hook = HOOKS / script
    assert hook.is_file(), f"settings.json registers a missing hook: {script}"
    outputs = []
    try:
        for adr_session in (False, True):
            _set_adr_session(project, adr_session)
            for payload in _payloads(event, matcher, project, transcript, session_id):
                result = subprocess.run(
                    [sys.executable, str(hook)],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    cwd=project,
                    env=env,
                    timeout=RUN_TIMEOUT_SECONDS,
                )
                label = payload.get("tool_name") or payload.get("source") or payload.get("agent_type") or event
                outputs.append((label + (" +adr-session" if adr_session else ""), result.stdout))
    finally:
        _cleanup_global_state(session_id)
    return outputs


@pytest.mark.parametrize(("event", "matcher", "script"), REGISTRATIONS)
def test_registered_hook_emits_only_valid_output(tmp_path: Path, event: str, matcher: str, script: str) -> None:
    problems = [
        f"{label}: {problem}"
        for label, stdout in run_registration(tmp_path, event, matcher, script)
        for problem in contract_violations(event, stdout)
    ]
    assert not problems, f"{script} on {event}:\n" + "\n".join(problems)


# --- Negative controls for the validator ----------------------------------------------


@pytest.mark.parametrize(
    ("event", "stdout"),
    [
        ("PreToolUse", ""),
        ("PreToolUse", "plain text advice\n"),
        (
            "PreToolUse",
            '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", '
            '"permissionDecisionReason": "no"}}',
        ),
        ("PostToolUse", '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "x"}}'),
        ("Stop", '{"decision": "block", "reason": "keep going"}'),
        ("SubagentStop", '{"decision": "block", "reason": "fix it"}'),
        ("PreCompact", '{"systemMessage": "archived"}'),
        ("SessionStart", '{"async": true, "asyncTimeout": 30}'),
        ("UserPromptSubmit", '{"continue": true, "suppressOutput": false}'),
    ],
)
def test_validator_accepts_valid_or_non_json_output(event: str, stdout: str) -> None:
    assert contract_violations(event, stdout) == []


@pytest.mark.parametrize(
    ("event", "stdout", "needle"),
    [
        ("SubagentStop", '{"permissionDecision": "deny", "reason": "x"}', "unknown top-level key 'permissionDecision'"),
        (
            "PreToolUse",
            '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "x"}}',
            "not 'PreToolUse'",
        ),
        (
            "PostToolUse",
            '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "deny"}}',
            "permissionDecision is not valid for PostToolUse",
        ),
        (
            "PreCompact",
            '{"hookSpecificOutput": {"hookEventName": "PreCompact", "additionalContext": "x"}}',
            "PreCompact accepts no hookSpecificOutput",
        ),
        (
            "PostCompact",
            '{"hookSpecificOutput": {"hookEventName": "PostCompact", "additionalContext": "x"}}',
            "PostCompact accepts no hookSpecificOutput",
        ),
        ("Stop", '{"decision": "deny"}', "decision must be one of"),
        (
            "PreToolUse",
            '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "block"}}',
            "permissionDecision 'block' is not valid",
        ),
        ("PreToolUse", '{"a": 1}\n{"b": 2}', "several JSON documents"),
        (
            "PreToolUse",
            '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ["x"]}}',
            "additionalContext must be a string",
        ),
        ("SessionStart", '{"async": true, "systemMessage": "x"}', "async output carries other keys"),
        ("Stop", '{"continue": "yes"}', "continue must be bool"),
        ("Stop", '{"decision": "block",', "starts like JSON but does not parse"),
    ],
)
def test_validator_rejects_invalid_output(event: str, stdout: str, needle: str) -> None:
    problems = contract_violations(event, stdout)
    assert any(needle in problem for problem in problems), problems
