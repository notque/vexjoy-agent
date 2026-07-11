#!/usr/bin/env python3
"""Run a VexJoy Claude hook against the current Codex hook protocol.

The adapter keeps harness-specific conversion in one process boundary. It is
deliberately limited to Codex tool paths that hooks can intercept; patch mode
covers ``apply_patch`` only.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVENTS = (
    "SessionStart",
    "SubagentStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStop",
    "Stop",
)
MODES = ("native", "prompt", "patch", "precompact", "subagent-stop", "stop")
FAILURE_POLICIES = ("open", "closed")
_CONTEXT_EVENTS = {"SessionStart", "SubagentStart", "UserPromptSubmit", "PostToolUse"}
_MAX_CHILD_OUTPUT = 1_048_576


class AdapterError(RuntimeError):
    """A conversion or child-hook result cannot be represented safely."""


class PatchParseError(AdapterError):
    """An apply_patch command is incomplete or ambiguous."""


class OutputNormalizationError(AdapterError):
    """A child hook emitted output Codex cannot consume safely."""


@dataclass(frozen=True)
class PatchEdit:
    """One Claude-style file event derived from an apply_patch operation."""

    tool_name: str
    file_path: str
    tool_input: dict[str, str]


def _path_after(line: str, marker: str) -> str:
    path = line[len(marker) :].strip()
    if not path:
        raise PatchParseError(f"missing path after {marker.strip()}")
    if "\x00" in path or "\n" in path or "\r" in path:
        raise PatchParseError("patch path contains an invalid character")
    return path


def _hunk_strings(lines: list[str]) -> tuple[str, str]:
    old: list[str] = []
    new: list[str] = []
    for line in lines:
        if line.startswith("@@"):
            continue
        if line.startswith("+"):
            new.append(line[1:])
        elif line.startswith("-"):
            old.append(line[1:])
        elif line.startswith(" "):
            old.append(line[1:])
            new.append(line[1:])
        else:
            raise PatchParseError(f"invalid update line: {line!r}")
    old_string = "\n".join(old) + ("\n" if old else "")
    new_string = "\n".join(new) + ("\n" if new else "")
    return old_string, new_string


def parse_apply_patch(command: str) -> list[PatchEdit]:
    """Parse Add, Update, Move, and Delete operations in Codex patch order."""
    if not isinstance(command, str):
        raise PatchParseError("apply_patch command is not a string")
    lines = command.splitlines()
    if len(lines) < 2 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise PatchParseError("apply_patch command lacks complete Begin/End markers")

    edits: list[PatchEdit] = []
    index = 1
    while index < len(lines) - 1:
        header = lines[index]
        if header.startswith("*** Add File:"):
            kind = "add"
            path = _path_after(header, "*** Add File:")
        elif header.startswith("*** Update File:"):
            kind = "update"
            path = _path_after(header, "*** Update File:")
        elif header.startswith("*** Delete File:"):
            kind = "delete"
            path = _path_after(header, "*** Delete File:")
        else:
            raise PatchParseError(f"unknown patch operation: {header!r}")

        index += 1
        body: list[str] = []
        while index < len(lines) - 1 and not lines[index].startswith(
            ("*** Add File:", "*** Update File:", "*** Delete File:")
        ):
            body.append(lines[index])
            index += 1

        if kind == "add":
            if any(not line.startswith("+") for line in body):
                raise PatchParseError(f"add operation for {path!r} contains a non-add line")
            content_lines = [line[1:] for line in body]
            content = "\n".join(content_lines) + ("\n" if content_lines else "")
            edits.append(PatchEdit("Write", path, {"file_path": path, "content": content}))
            continue

        if kind == "delete":
            if body:
                raise PatchParseError(f"delete operation for {path!r} has unexpected content")
            edits.append(
                PatchEdit(
                    "Edit",
                    path,
                    {"file_path": path, "old_string": "", "new_string": ""},
                )
            )
            continue

        move_targets = [line for line in body if line.startswith("*** Move to:")]
        if len(move_targets) > 1:
            raise PatchParseError(f"update operation for {path!r} has multiple move targets")
        move_path = _path_after(move_targets[0], "*** Move to:") if move_targets else None
        end_markers = [index for index, line in enumerate(body) if line == "*** End of File"]
        if len(end_markers) > 1 or (end_markers and end_markers[0] != len(body) - 1):
            raise PatchParseError(f"update operation for {path!r} has a misplaced End of File marker")
        hunk_lines = [line for line in body if not line.startswith("*** Move to:") and line != "*** End of File"]
        if any(line.startswith("*** ") for line in hunk_lines):
            raise PatchParseError(f"update operation for {path!r} contains an unknown marker")
        if not hunk_lines and not move_path:
            raise PatchParseError(f"update operation for {path!r} has no changes")
        old_string, new_string = _hunk_strings(hunk_lines)
        edits.append(
            PatchEdit(
                "Edit",
                path,
                {"file_path": path, "old_string": old_string, "new_string": new_string},
            )
        )
        if move_path:
            edits.append(
                PatchEdit(
                    "Write",
                    move_path,
                    {"file_path": move_path, "content": new_string},
                )
            )

    if not edits:
        raise PatchParseError("apply_patch command contains no file operations")
    return edits


def normalize_event(event: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Add Claude-compatible fields while retaining the Codex payload."""
    normalized = copy.deepcopy(event)
    tool_input = normalized.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
        normalized["tool_input"] = tool_input

    if mode == "prompt":
        prompt = normalized.get("prompt")
        if not isinstance(prompt, str):
            candidate = normalized.get("userMessage")
            prompt = candidate if isinstance(candidate, str) else ""
        normalized["prompt"] = prompt
        normalized["userMessage"] = prompt
        tool_input["prompt"] = prompt
    elif mode == "subagent-stop":
        if "agent_transcript_path" in normalized:
            normalized["transcript_path"] = normalized.get("agent_transcript_path")
    elif mode == "precompact":
        normalized.setdefault("conversation_history", [])
    elif mode == "stop":
        normalized.setdefault("session_data", {})
    return normalized


def compatibility_environment(event: dict[str, Any]) -> dict[str, str]:
    """Return the inherited environment plus Claude compatibility variables."""
    env = dict(os.environ)
    cwd = event.get("cwd")
    session_id = event.get("session_id")
    if isinstance(cwd, str) and cwd:
        env["CLAUDE_PROJECT_DIR"] = cwd
    if isinstance(session_id, str) and session_id:
        env["CLAUDE_SESSION_ID"] = session_id
    return env


def _matcher_matches(matcher: str, tool_name: str) -> bool:
    if matcher in {"", "*"}:
        return True
    try:
        return re.search(matcher, tool_name) is not None
    except re.error as exc:
        raise AdapterError(f"invalid original matcher {matcher!r}: {exc}") from exc


def build_invocations(event: dict[str, Any], *, mode: str, matcher: str) -> list[dict[str, Any]]:
    """Build the child events for one Codex hook event."""
    if mode != "patch":
        return [normalize_event(event, mode=mode)]
    if event.get("tool_name") != "apply_patch":
        raise PatchParseError("patch mode requires tool_name=apply_patch")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise PatchParseError("apply_patch tool_input is not an object")
    edits = parse_apply_patch(tool_input.get("command"))
    invocations: list[dict[str, Any]] = []
    for edit in edits:
        if not _matcher_matches(matcher, edit.tool_name):
            continue
        child = normalize_event(event, mode="native")
        child["codex_tool_name"] = event.get("tool_name")
        child["codex_tool_input"] = copy.deepcopy(tool_input)
        child["tool_name"] = edit.tool_name
        child["tool_input"] = copy.deepcopy(edit.tool_input)
        invocations.append(child)
    return invocations


def _context_output(event: str, text: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _plain_output(event: str, text: str) -> dict[str, Any]:
    if event in _CONTEXT_EVENTS:
        return _context_output(event, text)
    if event == "PreToolUse":
        raise OutputNormalizationError("plain text is invalid for PreToolUse")
    return {"systemMessage": text}


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _normalize_json_output(event: str, data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}
    inner_value = data.get("hookSpecificOutput")
    inner = inner_value if isinstance(inner_value, dict) else {}
    additional_context = _string(data.get("additionalContext")) or _string(inner.get("additionalContext"))
    user_message = _string(data.get("userMessage")) or _string(inner.get("userMessage"))
    system_message = _string(data.get("systemMessage"))
    permission = _string(data.get("permissionDecision")) or _string(inner.get("permissionDecision"))
    permission_reason = _string(data.get("permissionDecisionReason")) or _string(inner.get("permissionDecisionReason"))
    decision = _string(data.get("decision"))
    reason = _string(data.get("reason"))

    if event == "PermissionRequest":
        permission_request_decision = inner.get("decision")
        if isinstance(permission_request_decision, dict):
            return {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "decision": copy.deepcopy(permission_request_decision),
                }
            }

    if event in {"SubagentStop", "Stop"} and permission == "deny":
        return {"decision": "block", "reason": permission_reason or "Hook requested continuation."}

    output: dict[str, Any] = {}
    if system_message or user_message:
        output["systemMessage"] = system_message or user_message

    if event in {"PreToolUse", "PostToolUse", "SessionStart", "SubagentStart", "UserPromptSubmit"}:
        compatible_inner: dict[str, Any] = {"hookEventName": event}
        if additional_context:
            compatible_inner["additionalContext"] = additional_context
        if event == "PreToolUse" and permission in {"allow", "deny"}:
            compatible_inner["permissionDecision"] = permission
            if permission_reason:
                compatible_inner["permissionDecisionReason"] = permission_reason
            if permission == "allow" and isinstance(inner.get("updatedInput"), dict):
                compatible_inner["updatedInput"] = copy.deepcopy(inner["updatedInput"])
        if len(compatible_inner) > 1:
            output["hookSpecificOutput"] = compatible_inner
    elif additional_context:
        output["systemMessage"] = "\n".join(filter(None, [output.get("systemMessage", ""), additional_context]))

    if decision == "block" and event in {"PreToolUse", "PostToolUse", "UserPromptSubmit", "SubagentStop", "Stop"}:
        output["decision"] = "block"
        output["reason"] = reason or permission_reason or "Hook blocked this event."

    if event not in {"PreToolUse", "PermissionRequest"}:
        if data.get("continue") is False:
            output["continue"] = False
        stop_reason = _string(data.get("stopReason"))
        if stop_reason:
            output["stopReason"] = stop_reason

    if not output:
        known_empty = inner and set(inner) <= {"hookEventName"}
        if known_empty:
            return {}
        raise OutputNormalizationError(f"unsupported {event} JSON output")
    return output


def normalize_output(event: str, stdout: str, stderr: str) -> dict[str, Any]:
    """Convert one successful child result to valid current Codex JSON."""
    text = stdout.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        lines = text.splitlines()
        parsed_line: dict[str, Any] | None = None
        parsed_index = -1
        for index in range(len(lines) - 1, -1, -1):
            try:
                candidate = json.loads(lines[index])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                parsed_line = candidate
                parsed_index = index
                break
        if parsed_line is not None:
            results: list[dict[str, Any]] = []
            prefix = "\n".join(lines[:parsed_index]).strip()
            if prefix:
                results.append(_plain_output(event, prefix))
            results.append(_normalize_json_output(event, parsed_line))
            return aggregate_outputs(event, results)
        return _plain_output(event, text)
    if not isinstance(parsed, dict):
        raise OutputNormalizationError("hook stdout JSON is not an object")
    return _normalize_json_output(event, parsed)


def result_from_exit(event: str, returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    """Interpret one child exit according to current Codex hook rules."""
    if returncode == 0:
        return normalize_output(event, stdout, stderr)
    if returncode != 2:
        detail = stderr.strip() or stdout.strip() or "no diagnostic"
        raise AdapterError(f"child hook exited {returncode}: {detail}")
    reason = stderr.strip() or stdout.strip() or "Hook exited with status 2."
    if event == "PreToolUse":
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    if event == "PermissionRequest":
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "decision": {"behavior": "deny", "message": reason},
            }
        }
    if event in {"PostToolUse", "UserPromptSubmit", "SubagentStop", "Stop"}:
        return {"decision": "block", "reason": reason}
    return {"continue": False, "stopReason": reason, "systemMessage": reason}


def _unique_lines(values: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        for line in value.splitlines():
            if line and line not in seen:
                seen.add(line)
                ordered.append(line)
    return "\n".join(ordered)


def aggregate_outputs(event: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine per-file results in file order, with deny taking precedence."""
    if not results:
        return {}
    systems: list[str] = []
    contexts: list[str] = []
    deny_reasons: list[str] = []
    block_reasons: list[str] = []
    stop_reasons: list[str] = []
    permission_decisions: list[dict[str, Any]] = []
    updated_inputs: list[dict[str, Any]] = []
    continue_false = False

    for result in results:
        system = _string(result.get("systemMessage"))
        if system:
            systems.append(system)
        if result.get("continue") is False:
            continue_false = True
        stop_reason = _string(result.get("stopReason"))
        if stop_reason:
            stop_reasons.append(stop_reason)
        if result.get("decision") == "block":
            block_reasons.append(_string(result.get("reason")) or "Hook blocked this event.")
        inner_value = result.get("hookSpecificOutput")
        if not isinstance(inner_value, dict):
            continue
        context = _string(inner_value.get("additionalContext"))
        if context:
            contexts.append(context)
        if inner_value.get("permissionDecision") == "deny":
            deny_reasons.append(_string(inner_value.get("permissionDecisionReason")) or "Hook denied this event.")
        if inner_value.get("permissionDecision") == "allow" and isinstance(inner_value.get("updatedInput"), dict):
            updated_inputs.append(inner_value["updatedInput"])
        request_decision = inner_value.get("decision")
        if isinstance(request_decision, dict):
            permission_decisions.append(request_decision)

    output: dict[str, Any] = {}
    system_message = _unique_lines(systems)
    if system_message:
        output["systemMessage"] = system_message
    context = _unique_lines(contexts)

    if event == "PreToolUse":
        inner: dict[str, Any] = {"hookEventName": event}
        if deny_reasons:
            inner["permissionDecision"] = "deny"
            inner["permissionDecisionReason"] = _unique_lines(deny_reasons)
        elif len(updated_inputs) == 1:
            inner["permissionDecision"] = "allow"
            inner["updatedInput"] = updated_inputs[0]
        elif len(updated_inputs) > 1:
            raise OutputNormalizationError("multiple per-file updatedInput results cannot rewrite one patch")
        if context:
            inner["additionalContext"] = context
        if len(inner) > 1:
            output["hookSpecificOutput"] = inner
    elif event == "PermissionRequest" and permission_decisions:
        denied = [item for item in permission_decisions if item.get("behavior") == "deny"]
        chosen = denied[0] if denied else permission_decisions[0]
        output["hookSpecificOutput"] = {"hookEventName": event, "decision": chosen}
    elif event in {"SessionStart", "SubagentStart", "UserPromptSubmit", "PostToolUse"} and context:
        output["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": context}
    elif context:
        output["systemMessage"] = _unique_lines([output.get("systemMessage", ""), context])

    deny_wins = event == "PreToolUse" and bool(deny_reasons)
    stop_wins = event in {"SubagentStop", "Stop"} and continue_false
    if block_reasons and not deny_wins and not stop_wins:
        output["decision"] = "block"
        output["reason"] = _unique_lines(block_reasons)
    if continue_false:
        output["continue"] = False
    if stop_reasons:
        output["stopReason"] = _unique_lines(stop_reasons)
    return output


def failure_output(event: str, failure_policy: str, detail: str) -> dict[str, Any]:
    """Return a visible adapter failure under the declared policy."""
    message = f"[codex-hook-adapter] {detail}"
    if failure_policy == "open":
        return {"systemMessage": message}
    if event == "PreToolUse":
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    if event == "PermissionRequest":
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "decision": {"behavior": "deny", "message": message},
            }
        }
    if event in {"PostToolUse", "UserPromptSubmit", "SubagentStop", "Stop"}:
        return {"decision": "block", "reason": message}
    return {"continue": False, "stopReason": message, "systemMessage": message}


def _run_child(hook: Path, event: dict[str, Any], timeout: float) -> dict[str, Any]:
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else os.getcwd()
    completed = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=compatibility_environment(event),
        timeout=timeout,
        check=False,
    )
    if len(completed.stdout.encode()) > _MAX_CHILD_OUTPUT or len(completed.stderr.encode()) > _MAX_CHILD_OUTPUT:
        raise AdapterError("child hook output exceeded 1 MiB")
    if completed.stderr and completed.returncode == 0:
        print(completed.stderr, file=sys.stderr, end="")
    event_name = _string(event.get("hook_event_name"))
    return result_from_exit(event_name, completed.returncode, completed.stdout, completed.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hook", type=Path, required=True)
    parser.add_argument("--event", choices=EVENTS, required=True)
    parser.add_argument("--matcher", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--failure-policy", choices=FAILURE_POLICIES, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser


def run(args: argparse.Namespace, raw_input: str) -> dict[str, Any]:
    """Run the adapter once and return a Codex output object."""
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        return failure_output(args.event, args.failure_policy, f"invalid input JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return failure_output(args.event, args.failure_policy, "invalid input JSON: expected an object")
    if payload.get("hook_event_name") != args.event:
        return failure_output(
            args.event,
            args.failure_policy,
            f"event mismatch: expected {args.event}, got {payload.get('hook_event_name')!r}",
        )
    if args.timeout <= 0:
        return failure_output(args.event, args.failure_policy, "timeout must be positive")
    if not args.hook.is_file():
        return failure_output(args.event, args.failure_policy, f"hook not found: {args.hook}")

    try:
        invocations = build_invocations(payload, mode=args.mode, matcher=args.matcher)
        results = [_run_child(args.hook, event, args.timeout) for event in invocations]
        return aggregate_outputs(args.event, results)
    except subprocess.TimeoutExpired:
        return failure_output(args.event, args.failure_policy, f"child hook timed out after {args.timeout:g}s")
    except (AdapterError, OSError, ValueError) as exc:
        return failure_output(args.event, args.failure_policy, str(exc))


def main() -> int:
    args = _parser().parse_args()
    try:
        output = run(args, sys.stdin.read())
    except Exception as exc:  # Final containment: a hook adapter must not break Codex.
        output = failure_output(args.event, args.failure_policy, f"unexpected adapter error: {exc}")
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
