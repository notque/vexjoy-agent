#!/usr/bin/env python3
"""Probe Codex 0.144.1 hooks inside a disposable, isolated CODEX_HOME.

The probe copies authentication into a temporary Codex home, runs dedicated
Bash, apply_patch, and subagent attempts, and records only sanitized event
schemas and outcome metadata. It never writes normal Codex config or trust.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import re
import select
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_VERSION = "0.144.1"
REQUESTED_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "SubagentStart",
    "SubagentStop",
    "Stop",
)
CORE_REQUIRED_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop")
SENSITIVE_KEYS = {
    "command",
    "last_assistant_message",
    "prompt",
    "tool_input",
    "tool_response",
    "transcript_path",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/tests/fixtures/codex-hooks-0.144.1-events.json"),
        help="Sanitized fixture destination.",
    )
    parser.add_argument("--codex-bin", default="codex", help="Codex executable to probe.")
    parser.add_argument(
        "--auth-source",
        type=Path,
        default=Path.home() / ".codex" / "auth.json",
        help="Existing auth.json copied into the disposable Codex home.",
    )
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per live attempt.")
    parser.add_argument(
        "--patch-attempts",
        type=int,
        choices=range(1, 4),
        default=3,
        metavar="1..3",
        help="Number of dedicated apply_patch attempts.",
    )
    parser.add_argument(
        "--subagent-attempts",
        type=int,
        choices=range(1, 4),
        default=2,
        metavar="1..3",
        help="Number of dedicated subagent lifecycle attempts.",
    )
    parser.add_argument(
        "--allow-unverified-compaction",
        action="store_true",
        help="Permit exit 0 when the bounded interactive /compact probe remains unverified.",
    )
    return parser.parse_args()


def write_text(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def hook_blocks(recorder: Path, log: Path) -> dict[str, Any]:
    prefix = " ".join((shlex.quote(sys.executable), shlex.quote(str(recorder)), shlex.quote(str(log))))

    def command(event: str) -> dict[str, Any]:
        return {"type": "command", "command": f"{prefix} {shlex.quote(event)}", "timeout": 30}

    return {
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [command("SessionStart")]}],
            "UserPromptSubmit": [{"hooks": [command("UserPromptSubmit")]}],
            "PreToolUse": [{"matcher": ".*", "hooks": [command("PreToolUse")]}],
            "PostToolUse": [{"matcher": ".*", "hooks": [command("PostToolUse")]}],
            "PreCompact": [{"matcher": "manual|auto", "hooks": [command("PreCompact")]}],
            "PostCompact": [{"matcher": "manual|auto", "hooks": [command("PostCompact")]}],
            "SubagentStart": [{"matcher": ".*", "hooks": [command("SubagentStart")]}],
            "SubagentStop": [{"matcher": ".*", "hooks": [command("SubagentStop")]}],
            "Stop": [{"hooks": [command("Stop")]}],
        }
    }


RECORDER_SOURCE = r"""#!/usr/bin/env python3
import json
import os
import sys

log_path, configured_event = sys.argv[1:3]
try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError):
    payload = {"_invalid_json": True}
record = {
    "attempt": os.environ.get("CODEX_PROBE_ATTEMPT", "<missing>"),
    "configured_event": configured_event,
    "payload": payload,
}
line = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
try:
    os.write(fd, line)
finally:
    os.close(fd)

# Stop and SubagentStop explicitly require JSON on successful exit. The other
# observed events need no response, so emit no stdout and avoid influencing the
# tool or lifecycle action under test.
if configured_event in {"Stop", "SubagentStop"}:
    print("{}")
"""


def sanitize_string(value: str, replacements: list[tuple[str, str]]) -> str:
    result = value
    for raw, token in replacements:
        if raw:
            result = result.replace(raw, token)
    result = re.sub(r"(?i)(bearer|token|api[_-]?key|secret)[=: ]+\S+", r"\1=<REDACTED>", result)
    result = re.sub(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b", "<ID>", result)
    return re.sub(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b", "<TIMESTAMP>", result)


def schema_sample(payload: dict[str, Any], replacements: list[tuple[str, str]]) -> dict[str, Any]:
    sample: dict[str, Any] = {"payload_keys": sorted(payload)}
    safe_values = ("hook_event_name", "source", "tool_name", "trigger", "agent_type", "stop_hook_active")
    for key in safe_values:
        if key in payload and key not in SENSITIVE_KEYS:
            value = payload[key]
            sample[key] = sanitize_string(value, replacements) if isinstance(value, str) else value
    if "cwd" in payload:
        sample["cwd"] = sanitize_string(str(payload["cwd"]), replacements)
    return sample


def read_records(log: Path) -> list[dict[str, Any]]:
    if not log.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {
                "attempt": "<invalid-record>",
                "configured_event": "<invalid-record>",
                "payload": {"_invalid_json": True},
            }
        if isinstance(value, dict):
            records.append(value)
    return records


def classify_error_text(text: str) -> list[str]:
    """Classify diagnostics without retaining their potentially sensitive text."""
    lines = text.lower().splitlines()
    patterns = {
        "hook_output_or_execution_error": ("hook", "failed"),
        "invalid_hook_output": ("hook", "invalid"),
        "apply_patch_error": ("apply_patch", "error"),
        "patch_rejected": ("patch", "failed"),
        "tool_error": ("tool", "error"),
        "sandbox_setup_failure": ("sandbox", "fail"),
        "sandbox_loopback_setup_failure": ("sandbox", "loopback"),
        "rate_limit": ("rate limit",),
    }
    return sorted(
        name for name, needles in patterns.items() if any(all(needle in line for needle in needles) for line in lines)
    )


def sanitize_diagnostic_lines(text: str, replacements: list[tuple[str, str]]) -> list[str]:
    keywords = ("error", "fail", "hook", "patch", "sandbox", "loopback")
    diagnostics: list[str] = []
    for raw_line in text.splitlines():
        if not any(keyword in raw_line.lower() for keyword in keywords):
            continue
        line = sanitize_string(raw_line.strip(), replacements)[:1000]
        if line and line not in diagnostics:
            diagnostics.append(line)
        if len(diagnostics) == 10:
            break
    return diagnostics


def summarize_codex_json(stdout: str, stderr: str, replacements: list[tuple[str, str]]) -> dict[str, Any]:
    event_types: Counter[str] = Counter()
    item_evidence: list[dict[str, Any]] = []
    error_messages: list[str] = []
    agent_message_diagnostics: list[str] = []
    parse_errors = 0
    error_text = stderr
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(value, dict):
            continue
        event_type = str(value.get("type", "<missing>"))
        event_types[event_type] += 1
        item = value.get("item")
        if isinstance(item, dict):
            evidence: dict[str, Any] = {
                "event_type": event_type,
                "item_keys": sorted(item),
                "item_type": str(item.get("type", "<missing>")),
            }
            for key in ("status", "exit_code"):
                if key in item and isinstance(item[key], (str, int, bool, type(None))):
                    evidence[key] = item[key]
            item_evidence.append(evidence)
            if item.get("type") == "error" and isinstance(item.get("message"), str):
                message = sanitize_string(item["message"], replacements)
                if message not in error_messages:
                    error_messages.append(message[:1000])
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                message = sanitize_string(item["text"], replacements)
                if message not in agent_message_diagnostics:
                    agent_message_diagnostics.append(message[:1000])
            for key in ("message", "text", "aggregated_output"):
                if isinstance(item.get(key), str):
                    error_text += "\n" + item[key]
        error = value.get("error")
        if isinstance(error, dict):
            for key in ("message", "code", "type"):
                if isinstance(error.get(key), str):
                    error_text += "\n" + error[key]
        elif isinstance(error, str):
            error_text += "\n" + error
    return {
        "json_line_count": sum(event_types.values()),
        "parse_error_count": parse_errors,
        "event_type_counts": dict(sorted(event_types.items())),
        "item_evidence": item_evidence,
        "sanitized_error_messages": error_messages,
        "sanitized_agent_message_diagnostics": agent_message_diagnostics,
        "stderr_nonempty": bool(stderr.strip()),
        "sanitized_stderr_diagnostics": sanitize_diagnostic_lines(stderr, replacements),
        "diagnostic_categories": classify_error_text(sanitize_string(error_text, replacements)),
    }


def run_attempt(
    *,
    name: str,
    prompt: str,
    codex_bin: str,
    codex_home: Path,
    isolated_home: Path,
    workspace: Path,
    timeout: int,
    sandbox_mode: str,
    ephemeral: bool = True,
) -> dict[str, Any]:
    command = [
        codex_bin,
        "exec",
        "--json",
        "--ignore-rules",
        "--sandbox",
        sandbox_mode,
        "--dangerously-bypass-hook-trust",
        prompt,
    ]
    if ephemeral:
        command.insert(2, "--ephemeral")
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home)
    environment["HOME"] = str(isolated_home)
    environment["CODEX_PROBE_ATTEMPT"] = name
    replacements = [
        (str(workspace), "<WORKSPACE>"),
        (str(codex_home.parent), "<PROBE_ROOT>"),
        (str(Path.home()), "<HOME>"),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "name": name,
            "sandbox_mode": sandbox_mode,
            "session_storage": "ephemeral" if ephemeral else "disposable_home_persisted",
            "returncode": completed.returncode,
            "timed_out": False,
            "codex_json_evidence": summarize_codex_json(completed.stdout, completed.stderr, replacements),
        }
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr or ""
        return {
            "name": name,
            "sandbox_mode": sandbox_mode,
            "session_storage": "ephemeral" if ephemeral else "disposable_home_persisted",
            "returncode": 124,
            "timed_out": True,
            "codex_json_evidence": summarize_codex_json(stdout, stderr, replacements),
        }


def run_compact_pty_attempt(
    *,
    codex_bin: str,
    codex_home: Path,
    isolated_home: Path,
    workspace: Path,
    log: Path,
) -> dict[str, Any]:
    """Make one bounded interactive /compact attempt without retaining TUI text."""
    command = [
        codex_bin,
        "--no-alt-screen",
        "--dangerously-bypass-hook-trust",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "--cd",
        str(workspace),
    ]
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home)
    environment["HOME"] = str(isolated_home)
    environment["CODEX_PROBE_ATTEMPT"] = "compact_interactive"
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    process = subprocess.Popen(
        command,
        cwd=workspace,
        env=environment,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        start_new_session=True,
    )
    os.close(slave)
    observed_bytes = 0

    def collect(seconds: float) -> None:
        nonlocal observed_bytes
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and process.poll() is None:
            timeout = max(0.0, min(0.25, deadline - time.monotonic()))
            readable, _, _ = select.select([master], [], [], timeout)
            if not readable:
                continue
            try:
                observed_bytes += len(os.read(master, 65536))
            except OSError:
                break

    prompt_sent = False
    prompt_hook_observed = False
    stop_hook_observed = False
    compact_sent = False
    compact_pre_observed = False
    compact_post_observed = False

    def hook_observed(event: str) -> bool:
        return any(
            record.get("attempt") == "compact_interactive" and record.get("configured_event") == event
            for record in read_records(log)
        )

    def collect_until(event: str, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and process.poll() is None:
            collect(min(0.5, deadline - time.monotonic()))
            if hook_observed(event):
                return True
        return hook_observed(event)

    try:
        collect(2.0)
        if process.poll() is None:
            os.write(master, b"Reply with exactly ready and do not use tools.\r")
            prompt_sent = True
        prompt_hook_observed = collect_until("UserPromptSubmit", 15.0)
        if not prompt_hook_observed and process.poll() is None:
            os.write(master, b"\x15Reply with exactly ready and do not use tools.\n")
            prompt_hook_observed = collect_until("UserPromptSubmit", 5.0)
        if prompt_hook_observed:
            stop_hook_observed = collect_until("Stop", 10.0)
        if process.poll() is None:
            os.write(master, b"\x15/compact\r")
            compact_sent = True
        compact_pre_observed = collect_until("PreCompact", 10.0)
        compact_post_observed = hook_observed("PostCompact")
        if process.poll() is None:
            os.write(master, b"\x15/quit\r")
        collect(3.0)
        if process.poll() is None:
            os.write(master, b"\x03")
        collect(2.0)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
    finally:
        os.close(master)
    return {
        "name": "compact_interactive",
        "kind": "compact",
        "sandbox_mode": "workspace-write",
        "session_storage": "disposable_home_persisted",
        "returncode": process.returncode,
        "timed_out": False,
        "pty_evidence": {
            "prompt_sent": prompt_sent,
            "prompt_hook_observed": prompt_hook_observed,
            "stop_hook_observed_before_compact": stop_hook_observed,
            "compact_slash_command_sent": compact_sent,
            "precompact_hook_observed_during_wait": compact_pre_observed,
            "postcompact_hook_observed_during_wait": compact_post_observed,
            "tui_output_bytes_observed": observed_bytes,
            "tui_text_retained": False,
            "bounded_seconds": 47,
        },
    }


def summarize_attempt_hooks(records: list[dict[str, Any]], replacements: list[tuple[str, str]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        event = str(record.get("configured_event", "<missing>"))
        payload = record.get("payload", {})
        grouped[event].append(payload if isinstance(payload, dict) else {"_non_object": True})
    result: dict[str, Any] = {}
    for event in REQUESTED_EVENTS:
        payloads = grouped.get(event, [])
        tool_counts = Counter(str(payload.get("tool_name", "<missing>")) for payload in payloads)
        result[event] = {
            "count": len(payloads),
            "tool_names": dict(sorted(tool_counts.items())),
            "samples": deduplicate_samples(payloads, replacements),
        }
    return result


def deduplicate_samples(payloads: list[dict[str, Any]], replacements: list[tuple[str, str]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        sample = schema_sample(payload, replacements)
        fingerprint = json.dumps(sample, sort_keys=True)
        if fingerprint not in seen:
            seen.add(fingerprint)
            samples.append(sample)
    return samples


def aggregate_observed_events(
    records: list[dict[str, Any]], replacements: list[tuple[str, str]]
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        event = str(record.get("configured_event", "<missing>"))
        payload = record.get("payload", {})
        grouped[event].append(payload if isinstance(payload, dict) else {"_non_object": True})
    observed: dict[str, Any] = {}
    for event in REQUESTED_EVENTS:
        payloads = grouped.get(event, [])
        observed[event] = {
            "observed": bool(payloads),
            "count": len(payloads),
            "samples": deduplicate_samples(payloads, replacements),
        }
    pre = Counter(str(payload.get("tool_name", "<missing>")) for payload in grouped["PreToolUse"])
    post = Counter(str(payload.get("tool_name", "<missing>")) for payload in grouped["PostToolUse"])
    names = sorted(pre.keys() | post.keys())
    return observed, {name: {"pre": pre[name], "post": post[name]} for name in names}


def event_count(attempt: dict[str, Any], event: str, tool_name: str | None = None) -> int:
    hook = attempt["hook_events"][event]
    if tool_name is None:
        return int(hook["count"])
    return int(hook["tool_names"].get(tool_name, 0))


def determine_exit_code(
    core_passed: bool, trigger_validation: dict[str, dict[str, Any]], allow_unverified_compaction: bool
) -> tuple[int, int]:
    trigger_passed = all(result["passed"] for result in trigger_validation.values())
    non_compaction_passed = all(
        result["passed"] for name, result in trigger_validation.items() if name != "compaction_lifecycle"
    )
    default = 1 if not core_passed else 0 if trigger_passed else 2 if non_compaction_passed else 1
    effective = (
        0
        if core_passed
        and allow_unverified_compaction
        and non_compaction_passed
        and not trigger_validation["compaction_lifecycle"]["passed"]
        else default
    )
    return default, effective


def validate_patch_inputs(records: list[dict[str, Any]], expected: str) -> dict[str, Any]:
    payloads = [
        record.get("payload", {})
        for record in records
        if record.get("configured_event") == "PreToolUse"
        and isinstance(record.get("payload"), dict)
        and record["payload"].get("tool_name") == "apply_patch"
    ]
    commands = [
        payload.get("tool_input", {}).get("command")
        for payload in payloads
        if isinstance(payload.get("tool_input"), dict)
    ]
    string_commands = [command for command in commands if isinstance(command, str)]
    return {
        "pretool_payload_count": len(payloads),
        "tool_input_object_count": len(commands),
        "command_string_count": len(string_commands),
        "exact_requested_patch_count": sum(command == expected for command in string_commands),
        "has_patch_markers_count": sum(
            command.startswith("*** Begin Patch") and command.endswith("*** End Patch") for command in string_commands
        ),
    }


def build_fixture(
    *,
    version: str,
    attempts: list[dict[str, Any]],
    records: list[dict[str, Any]],
    replacements: list[tuple[str, str]],
    normal_home_unchanged: bool,
    allow_unverified_compaction: bool,
) -> dict[str, Any]:
    records_by_attempt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_attempt[str(record.get("attempt", "<missing>"))].append(record)
    for attempt in attempts:
        attempt_records = records_by_attempt[attempt["name"]]
        attempt["hook_events"] = summarize_attempt_hooks(attempt_records, replacements)
        if attempt["kind"] == "apply_patch":
            expected = attempt.pop("_expected_patch_command")
            attempt["pretool_input_validation"] = validate_patch_inputs(attempt_records, expected)

    observed, tool_counts = aggregate_observed_events(records, replacements)
    patch_attempts = [attempt for attempt in attempts if attempt["kind"] == "apply_patch"]
    subagent_attempts = [attempt for attempt in attempts if attempt["kind"] == "subagent"]
    compact_attempt = next(attempt for attempt in attempts if attempt["kind"] == "compact")
    bash_attempt = next(attempt for attempt in attempts if attempt["kind"] == "bash")

    bash_pre = event_count(bash_attempt, "PreToolUse", "Bash")
    bash_post = event_count(bash_attempt, "PostToolUse", "Bash")
    patch_pre = sum(event_count(attempt, "PreToolUse", "apply_patch") for attempt in patch_attempts)
    patch_post = sum(event_count(attempt, "PostToolUse", "apply_patch") for attempt in patch_attempts)
    successful_patch_attempts = [
        attempt for attempt in patch_attempts if attempt["target_state"]["exact_expected_content"]
    ]
    patch_mutations = len(successful_patch_attempts)
    successful_patch_posts = sum(
        event_count(attempt, "PostToolUse", "apply_patch") > 0 for attempt in successful_patch_attempts
    )
    exact_patch_inputs = sum(
        attempt["pretool_input_validation"]["exact_requested_patch_count"] for attempt in patch_attempts
    )
    spawn_pre = sum(
        count
        for attempt in subagent_attempts
        for name, count in attempt["hook_events"]["PreToolUse"]["tool_names"].items()
        if "spawn_agent" in name
    )
    subagent_start = sum(event_count(attempt, "SubagentStart") for attempt in subagent_attempts)
    subagent_stop = sum(event_count(attempt, "SubagentStop") for attempt in subagent_attempts)
    completed_collab_items = sum(
        evidence.get("item_type") == "collab_tool_call" and evidence.get("status") == "completed"
        for attempt in subagent_attempts
        for evidence in attempt["codex_json_evidence"]["item_evidence"]
    )
    successful_subagent_lifecycles = sum(
        event_count(attempt, "SubagentStart") > 0 and event_count(attempt, "SubagentStop") > 0
        for attempt in subagent_attempts
    )

    core_required = {event: observed[event]["observed"] for event in CORE_REQUIRED_EVENTS}
    trigger_validation = {
        "bash_pre_post": {
            "pre_count": bash_pre,
            "post_count": bash_post,
            "passed": bash_pre > 0 and bash_post > 0,
        },
        "apply_patch_pre_post": {
            "attempt_count": len(patch_attempts),
            "pre_count": patch_pre,
            "post_count": patch_post,
            "exact_mutation_count": patch_mutations,
            "exact_requested_patch_input_count": exact_patch_inputs,
            "successful_mutations_with_post_count": successful_patch_posts,
            "passed": patch_mutations > 0 and successful_patch_posts == patch_mutations,
        },
        "subagent_lifecycle": {
            "attempt_count": len(subagent_attempts),
            "spawn_tool_pre_count": spawn_pre,
            "completed_collaboration_item_count": completed_collab_items,
            "start_count": subagent_start,
            "stop_count": subagent_stop,
            "successful_lifecycle_attempt_count": successful_subagent_lifecycles,
            "passed": successful_subagent_lifecycles > 0,
        },
        "compaction_lifecycle": {
            "noninteractive_trigger_available_in_codex_exec": False,
            "interactive_pty_attempted": compact_attempt["pty_evidence"]["compact_slash_command_sent"],
            "interactive_prompt_hook_observed": compact_attempt["pty_evidence"]["prompt_hook_observed"],
            "interactive_command_acceptance_demonstrated": compact_attempt["pty_evidence"]["prompt_hook_observed"],
            "pre_count": observed["PreCompact"]["count"],
            "post_count": observed["PostCompact"]["count"],
            "passed": observed["PreCompact"]["observed"] and observed["PostCompact"]["observed"],
        },
    }

    assessments: list[dict[str, str]] = [
        {
            "registration": "PreToolUse matcher=apply_patch|Edit|Write",
            "assessment": "supported_observed",
            "reason": f"observed {patch_pre} apply_patch PreToolUse events from {exact_patch_inputs} exact inputs",
        },
        {
            "registration": "PreToolUse/PostToolUse matcher=Bash",
            "assessment": "supported_observed",
            "reason": f"the Bash control emitted {bash_pre} pre-hook and {bash_post} post-hook",
        },
    ]
    if patch_mutations and successful_patch_posts < patch_mutations:
        assessments.append(
            {
                "registration": "PostToolUse matcher=apply_patch|Edit|Write",
                "assessment": "downgrade_to_unsupported_on_codex_0.144.1",
                "reason": (
                    f"{patch_mutations} exact mutations produced only {successful_patch_posts} PostToolUse events"
                ),
            }
        )
    elif patch_mutations:
        assessments.append(
            {
                "registration": "PostToolUse matcher=apply_patch|Edit|Write",
                "assessment": "supported_observed_after_successful_mutation",
                "reason": (
                    f"{patch_mutations} exact mutations produced {successful_patch_posts} corresponding "
                    "PostToolUse observations"
                ),
            }
        )
    else:
        assessments.append(
            {
                "registration": "PostToolUse matcher=apply_patch|Edit|Write",
                "assessment": "unverified_due_failed_tool_execution",
                "reason": (
                    f"{len(patch_attempts)} attempts reached PreToolUse but none mutated the target; "
                    "documented PostToolUse support is preserved"
                ),
            }
        )
    if successful_subagent_lifecycles:
        assessments.append(
            {
                "registration": "SubagentStart/SubagentStop",
                "assessment": "supported_observed_after_completed_subagent",
                "reason": (
                    f"{successful_subagent_lifecycles} dedicated attempt(s) emitted paired start/stop events "
                    f"and {completed_collab_items} completed collaboration item(s)"
                ),
            }
        )
    elif completed_collab_items:
        assessments.append(
            {
                "registration": "SubagentStart/SubagentStop",
                "assessment": "downgrade_to_unsupported_on_codex_0.144.1",
                "reason": (f"{completed_collab_items} collaboration item(s) completed without lifecycle hooks"),
            }
        )
    elif spawn_pre:
        assessments.append(
            {
                "registration": "SubagentStart/SubagentStop",
                "assessment": "unverified_due_incomplete_subagent_execution",
                "reason": "the spawn tool was selected but lifecycle completion was not demonstrated",
            }
        )
    for event in ("PreCompact", "PostCompact"):
        if not observed[event]["observed"]:
            assessments.append(
                {
                    "registration": event,
                    "assessment": (
                        "runtime_unverified_after_bounded_interactive_attempt"
                        if compact_attempt["pty_evidence"]["prompt_hook_observed"]
                        else "runtime_unverified_pty_input_not_accepted"
                    ),
                    "reason": (
                        "a disposable PTY sent /compact but no matching runtime event was observed"
                        if compact_attempt["pty_evidence"]["prompt_hook_observed"]
                        else "the PTY sent a prompt and /compact, but no UserPromptSubmit hook proved TUI acceptance"
                    ),
                }
            )

    trigger_passed = all(result["passed"] for result in trigger_validation.values())
    core_passed = all(core_required.values()) and all(not attempt["timed_out"] for attempt in attempts)
    default_exit_code, effective_exit_code = determine_exit_code(
        core_passed, trigger_validation, allow_unverified_compaction
    )
    return {
        "fixture_schema": 2,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "codex_version": version,
        "documentation": {
            "hook_reference": "https://learn.chatgpt.com/docs/hooks",
            "checked_on": datetime.now(UTC).date().isoformat(),
        },
        "probe": {
            "kind": "live_multi_attempt_disposable_codex_home",
            "expected_cli_version": EXPECTED_VERSION,
            "normal_config_hooks_auth_mutated": not normal_home_unchanged,
            "normal_persisted_hook_trust_written": False,
            "hook_trust": "documented_one_off_bypass_scoped_to_disposable_home",
            "attempt_count": len(attempts),
        },
        "validation": {
            "core_required_events": core_required,
            "core_passed": core_passed,
            "trigger_validation": trigger_validation,
            "overall_status": "passed" if trigger_passed else "partial_with_documented_limitations",
            "exit_semantics": {
                "default_exit_code": default_exit_code,
                "allow_unverified_compaction": allow_unverified_compaction,
                "effective_exit_code": effective_exit_code,
            },
            "requested_events": list(REQUESTED_EVENTS),
        },
        "attempts": attempts,
        "observed_events": observed,
        "observed_tool_names": tool_counts,
        "registration_assessments": assessments,
        "sanitization": {
            "raw_prompts_commands_tool_input_and_tool_output_omitted": True,
            "agent_messages_path_and_secret_sanitized_and_truncated": True,
            "authentication_material_omitted": True,
            "temporary_and_home_paths_tokenized": True,
            "codex_exec_json_reduced_to_schema_status_and_error_categories": True,
        },
    }


def file_fingerprint(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


def main() -> int:
    args = parse_args()
    version = subprocess.run([args.codex_bin, "--version"], check=True, capture_output=True, text=True).stdout.strip()
    if EXPECTED_VERSION not in version:
        raise SystemExit(f"Expected Codex {EXPECTED_VERSION}, got {version!r}")
    auth_source = args.auth_source.expanduser().resolve()
    if not auth_source.is_file():
        raise SystemExit(f"Authentication source does not exist: {auth_source}")

    normal_codex_home = auth_source.parent
    tracked_normal_files = (normal_codex_home / "config.toml", normal_codex_home / "hooks.json", auth_source)
    before = {str(path): file_fingerprint(path) for path in tracked_normal_files}

    with tempfile.TemporaryDirectory(prefix="codex-hook-probe-") as temporary:
        root = Path(temporary).resolve()
        codex_home = root / "codex-home"
        isolated_home = root / "home"
        workspace = root / "workspace"
        recorder = root / "record-hook.py"
        log = root / "events.jsonl"
        codex_home.mkdir(mode=0o700)
        isolated_home.mkdir(mode=0o700)
        workspace.mkdir(mode=0o700)
        if codex_home == normal_codex_home or normal_codex_home in codex_home.parents:
            raise SystemExit("Refusing to probe inside the normal Codex home")

        shutil.copyfile(auth_source, codex_home / "auth.json")
        (codex_home / "auth.json").chmod(0o600)
        write_text(codex_home / "config.toml", "[features]\nhooks = true\nmulti_agent = true\n")
        write_text(recorder, RECORDER_SOURCE, mode=0o700)
        write_text(codex_home / "hooks.json", json.dumps(hook_blocks(recorder, log), indent=2) + "\n")
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)

        attempts: list[dict[str, Any]] = []
        write_text(workspace / "probe-target.txt", "subagent-readable\n")
        bash = run_attempt(
            name="bash",
            prompt=(
                "Use the Bash/shell tool exactly once to run `printf codex-hook-probe`. "
                "Do not edit files, spawn agents, or use another tool. Then stop."
            ),
            codex_bin=args.codex_bin,
            codex_home=codex_home,
            isolated_home=isolated_home,
            workspace=workspace,
            timeout=args.timeout,
            sandbox_mode="workspace-write",
        )
        bash["kind"] = "bash"
        attempts.append(bash)

        for number in range(1, args.patch_attempts + 1):
            before_text = f"before-{number}\n"
            after_text = f"after-{number}\n"
            write_text(workspace / "probe-target.txt", before_text)
            patch = (
                "*** Begin Patch\n"
                "*** Update File: probe-target.txt\n"
                "@@\n"
                f"-{before_text.rstrip()}\n"
                f"+{after_text.rstrip()}\n"
                "*** End Patch"
            )
            attempt = run_attempt(
                name=f"apply_patch_{number}",
                prompt=(
                    "Use the apply_patch tool exactly once with the following exact patch. "
                    "Do not use Bash, shell redirection, Edit, Write, or any other tool. "
                    f"Stop immediately after the tool result.\n\n{patch}"
                ),
                codex_bin=args.codex_bin,
                codex_home=codex_home,
                isolated_home=isolated_home,
                workspace=workspace,
                timeout=args.timeout,
                sandbox_mode="workspace-write" if number == 1 else "danger-full-access",
            )
            actual = (workspace / "probe-target.txt").read_text(encoding="utf-8")
            attempt["kind"] = "apply_patch"
            attempt["_expected_patch_command"] = patch
            attempt["target_state"] = {
                "exact_expected_content": actual == after_text,
                "unchanged": actual == before_text,
                "changed_to_other_content": actual not in (before_text, after_text),
            }
            attempts.append(attempt)

        write_text(workspace / "probe-target.txt", "subagent-readable\n")
        for number in range(1, args.subagent_attempts + 1):
            subagent = run_attempt(
                name=f"subagent_{number}",
                prompt=(
                    "Spawn exactly one default subagent whose only task is to read probe-target.txt and report "
                    "whether it is non-empty. Wait for that subagent to finish. Do not use Bash or edit files. "
                    "Then stop."
                ),
                codex_bin=args.codex_bin,
                codex_home=codex_home,
                isolated_home=isolated_home,
                workspace=workspace,
                timeout=args.timeout,
                sandbox_mode="workspace-write",
                ephemeral=False,
            )
            subagent["kind"] = "subagent"
            attempts.append(subagent)

        attempts.append(
            run_compact_pty_attempt(
                codex_bin=args.codex_bin,
                codex_home=codex_home,
                isolated_home=isolated_home,
                workspace=workspace,
                log=log,
            )
        )

        records = read_records(log)
        replacements = [
            (str(workspace), "<WORKSPACE>"),
            (str(root), "<PROBE_ROOT>"),
            (str(Path.home()), "<HOME>"),
        ]
        after = {str(path): file_fingerprint(path) for path in tracked_normal_files}
        fixture = build_fixture(
            version=version,
            attempts=attempts,
            records=records,
            replacements=replacements,
            normal_home_unchanged=before == after,
            allow_unverified_compaction=args.allow_unverified_compaction,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(fixture["validation"], sort_keys=True))
    return int(fixture["validation"]["exit_semantics"]["effective_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
