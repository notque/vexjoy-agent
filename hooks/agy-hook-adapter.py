#!/usr/bin/env python3
"""Run a VexJoy Claude hook against the Antigravity CLI (agy) hooks.json protocol.

Translates Antigravity's camelCase hook stdin payloads (`conversationId`,
`workspacePaths`, `toolCall`, `lastUserInput`, `transcriptPath`, `modelName`)
into VexJoy's Claude-compatible hook input contract (`session_id`, `cwd`,
`tool_name`, `tool_input`, `prompt`, `transcript_path`), executes the target
VexJoy hook script, and converts its exit code and stdout into Antigravity's
per-event JSON output schema:

  - SessionStart / PreInvocation: `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}` or `{}`
  - PostInvocation: `{"injectSteps": [...], "terminationBehavior": "force_continue"|"terminate"}` or `{}`
  - PreToolUse: `{"decision": "allow"|"deny"|"ask"|"force_ask", "reason": "...", "overwrite": {...}}`
  - PostToolUse: `{}` (advisory outputs are queued per conversationId and drained on PreInvocation)
  - Stop: `{"decision": "continue"|"allow", "reason": "..."}`
"""

from __future__ import annotations

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard adapter
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
    _a = sys.argv[sys.argv.index("--failure-policy") + 1 :] if "--failure-policy" in sys.argv else []
    sys.exit(2 if _a[:1] == ["closed"] else 0)

import argparse
import copy
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

AGY_EVENTS = (
    "SessionStart",
    "PreInvocation",
    "PostInvocation",
    "PreToolUse",
    "PostToolUse",
    "Stop",
)
CLAUDE_EVENT_FOR_AGY = {
    "SessionStart": "SessionStart",
    "PreInvocation": "UserPromptSubmit",
    "PostInvocation": "Stop",
    "PreToolUse": "PreToolUse",
    "PostToolUse": "PostToolUse",
    "Stop": "Stop",
}
FAILURE_POLICIES = ("open", "closed")
_MAX_CHILD_OUTPUT = 1_048_576
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


class AdapterError(RuntimeError):
    """A conversion or child-hook result cannot be represented safely."""


def _deferred_dir() -> Path:
    env_dir = os.environ.get("VEXJOY_AGY_DEFERRED_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(tempfile.gettempdir()) / "vexjoy-agy-deferred"


def _deferred_path(conversation_id: str) -> Path:
    safe_id = _SAFE_ID_RE.sub("_", conversation_id.strip() or "default")[:80]
    return _deferred_dir() / f"deferred-{safe_id}.json"


def queue_deferred_context(conversation_id: str, text: str) -> None:
    """Append PostToolUse advisory context for delivery on the next PreInvocation."""
    cleaned = text.strip()
    if not cleaned:
        return
    path = _deferred_path(conversation_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[str] = []
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = [str(item) for item in loaded if str(item).strip()]
        if cleaned not in existing:
            existing.append(cleaned)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def drain_deferred_context(conversation_id: str) -> list[str]:
    """Read and clear queued PostToolUse advisory messages for *conversation_id*."""
    path = _deferred_path(conversation_id)
    if not path.is_file():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        path.unlink(missing_ok=True)
        if isinstance(loaded, list):
            return [str(item).strip() for item in loaded if str(item).strip()]
    except (OSError, json.JSONDecodeError):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return []


def map_agy_tool_to_claude(tool_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map an Antigravity toolCall (name, args) pair to Claude (tool_name, tool_input)."""
    if tool_name == "run_command":
        return "Bash", {
            "command": str(args.get("CommandLine") or ""),
            "description": str(args.get("toolSummary") or ""),
        }
    if tool_name == "write_file":
        return "Write", {
            "file_path": str(args.get("Path") or ""),
            "content": str(args.get("Content") or ""),
        }
    if tool_name == "edit_file":
        return "Edit", {
            "file_path": str(args.get("Path") or ""),
            "old_string": str(args.get("Target") or ""),
            "new_string": str(args.get("Replacement") or ""),
        }
    if tool_name == "read_file":
        return "Read", {
            "file_path": str(args.get("Path") or ""),
        }
    if tool_name == "invoke_subagent":
        return "Agent", {
            "subagent_type": str(args.get("TypeName") or ""),
            "description": str(args.get("Role") or ""),
            "prompt": str(args.get("Prompt") or ""),
            "model": str(args.get("Model") or ""),
            "workspace": str(args.get("Workspace") or ""),
        }
    if tool_name == "run_workflow":
        return "Workflow", {
            "script": str(args.get("Script") or ""),
            "script_path": str(args.get("ScriptPath") or ""),
            "description": str(args.get("Description") or ""),
        }
    return tool_name, copy.deepcopy(args)


def map_claude_updated_input_to_agy(
    agy_tool_name: str,
    original_args: dict[str, Any],
    updated_input: dict[str, Any],
) -> dict[str, Any]:
    """Translate a Claude PreToolUse `updatedInput` dict back to Antigravity `overwrite` args."""
    merged = copy.deepcopy(original_args)
    if agy_tool_name == "run_command":
        if "command" in updated_input:
            merged["CommandLine"] = updated_input["command"]
        return merged
    if agy_tool_name == "write_file":
        if "file_path" in updated_input:
            merged["Path"] = updated_input["file_path"]
        if "content" in updated_input:
            merged["Content"] = updated_input["content"]
        return merged
    if agy_tool_name == "edit_file":
        if "file_path" in updated_input:
            merged["Path"] = updated_input["file_path"]
        if "old_string" in updated_input:
            merged["Target"] = updated_input["old_string"]
        if "new_string" in updated_input:
            merged["Replacement"] = updated_input["new_string"]
        return merged
    merged.update(updated_input)
    return merged


def normalize_agy_payload(payload: dict[str, Any], *, agy_event: str) -> dict[str, Any]:
    """Convert an Antigravity camelCase hook payload into a Claude-compatible event dict."""
    claude_event = CLAUDE_EVENT_FOR_AGY.get(agy_event, agy_event)
    normalized: dict[str, Any] = copy.deepcopy(payload)
    normalized["hook_event_name"] = claude_event
    normalized["agy_event_name"] = agy_event

    conv_id = str(payload.get("conversationId") or payload.get("session_id") or "")
    if conv_id:
        normalized["session_id"] = conv_id

    workspaces = payload.get("workspacePaths")
    cwd = ""
    if isinstance(workspaces, list) and workspaces and isinstance(workspaces[0], str):
        cwd = workspaces[0]
    elif isinstance(payload.get("cwd"), str):
        cwd = payload["cwd"]
    if cwd:
        normalized["cwd"] = cwd

    transcript = payload.get("transcriptPath") or payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        normalized["transcript_path"] = transcript

    model_name = payload.get("modelName") or payload.get("model")
    if isinstance(model_name, str) and model_name:
        normalized["model"] = model_name

    last_input = payload.get("lastUserInput")
    if not isinstance(last_input, str):
        last_input = str(payload.get("prompt") or "")
    if agy_event in ("PreInvocation", "SessionStart"):
        normalized["prompt"] = last_input
        normalized["userMessage"] = last_input

    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        agy_tool_name = str(tool_call.get("name") or "")
        agy_args = tool_call.get("args")
        if not isinstance(agy_args, dict):
            agy_args = tool_call.get("arguments")
        if not isinstance(agy_args, dict):
            agy_args = {}
        claude_tool, claude_input = map_agy_tool_to_claude(agy_tool_name, agy_args)
        normalized["agy_tool_name"] = agy_tool_name
        normalized["agy_tool_args"] = copy.deepcopy(agy_args)
        normalized["tool_name"] = claude_tool
        normalized["tool_input"] = claude_input
    else:
        normalized.setdefault("tool_input", {})

    if agy_event == "PostToolUse":
        err = payload.get("error")
        if isinstance(err, str) and err:
            normalized["tool_result"] = {"output": err, "is_error": True}
        elif "tool_result" not in normalized:
            normalized["tool_result"] = {"output": "", "is_error": False}

    if agy_event in ("Stop", "PostInvocation"):
        normalized.setdefault("stop_hook_active", False)
        normalized.setdefault("session_data", {})

    return normalized


def compatibility_environment(event: dict[str, Any]) -> dict[str, str]:
    """Return inherited environment plus VexJoy/Claude compatibility variables."""
    env = dict(os.environ)
    cwd = event.get("cwd")
    session_id = event.get("session_id")
    if isinstance(cwd, str) and cwd:
        env["CLAUDE_PROJECT_DIR"] = cwd
    if isinstance(session_id, str) and session_id:
        env["CLAUDE_SESSION_ID"] = session_id
        env["ANTIGRAVITY_SESSION_ID"] = session_id
    env["ANTIGRAVITY_AGENT"] = "1"
    env["VEXJOY_HOOK_RUNTIME"] = "antigravity"
    return env


def _extract_claude_fields(stdout: str) -> dict[str, Any]:
    """Extract normalized fields from a child hook's stdout (JSON or plain text)."""
    text = stdout.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"additional_context": text}
    if not isinstance(parsed, dict):
        return {"additional_context": text}

    inner = parsed.get("hookSpecificOutput")
    if not isinstance(inner, dict):
        inner = {}

    additional_context = str(parsed.get("additionalContext") or inner.get("additionalContext") or "").strip()
    system_message = str(parsed.get("systemMessage") or inner.get("userMessage") or "").strip()
    permission = str(parsed.get("permissionDecision") or inner.get("permissionDecision") or "").strip().lower()
    permission_reason = str(
        parsed.get("permissionDecisionReason") or inner.get("permissionDecisionReason") or ""
    ).strip()
    decision = str(parsed.get("decision") or "").strip().lower()
    reason = str(parsed.get("reason") or parsed.get("stopReason") or "").strip()
    updated_input = inner.get("updatedInput") if isinstance(inner.get("updatedInput"), dict) else None

    return {
        "additional_context": additional_context,
        "system_message": system_message,
        "permission": permission,
        "permission_reason": permission_reason,
        "decision": decision,
        "reason": reason,
        "updated_input": updated_input,
        "continue_flag": parsed.get("continue"),
    }


def translate_child_result(
    agy_event: str,
    returncode: int,
    stdout: str,
    stderr: str,
    *,
    normalized_event: dict[str, Any],
    drain_deferred: bool = False,
) -> dict[str, Any]:
    """Convert a VexJoy child hook result into Antigravity's exact stdout JSON contract."""
    conv_id = str(normalized_event.get("session_id") or "default")

    if returncode not in (0, 2):
        detail = stderr.strip() or stdout.strip() or f"child hook exited {returncode}"
        raise AdapterError(detail)

    fields = _extract_claude_fields(stdout) if returncode == 0 else {}
    exit2_reason = (
        stderr.strip()
        or fields.get("permission_reason")
        or fields.get("reason")
        or stdout.strip()
        or "Blocked by VexJoy hook."
    )

    if agy_event == "PreToolUse":
        if returncode == 2 or fields.get("permission") == "deny" or fields.get("decision") == "block":
            reason = fields.get("permission_reason") or fields.get("reason") or exit2_reason
            return {"decision": "deny", "reason": reason}
        if fields.get("permission") == "ask":
            reason = fields.get("permission_reason") or fields.get("reason") or "Confirmation required."
            return {"decision": "ask", "reason": reason}
        out: dict[str, Any] = {"decision": "allow"}
        updated = fields.get("updated_input")
        if isinstance(updated, dict):
            agy_tool = str(normalized_event.get("agy_tool_name") or "")
            orig_args = normalized_event.get("agy_tool_args")
            if not isinstance(orig_args, dict):
                orig_args = {}
            out["overwrite"] = map_claude_updated_input_to_agy(agy_tool, orig_args, updated)
        return out

    if agy_event == "PostToolUse":
        # Antigravity requires PostToolUse stdout to be `{}`. Queue any advisory text for PreInvocation.
        msg_parts = [
            p for p in (fields.get("system_message"), fields.get("additional_context")) if isinstance(p, str) and p
        ]
        if returncode == 2 and exit2_reason:
            msg_parts.append(exit2_reason)
        if msg_parts:
            queue_deferred_context(conv_id, "\n".join(msg_parts))
        return {}

    if agy_event in ("SessionStart", "PreInvocation"):
        messages: list[str] = []
        if drain_deferred:
            messages.extend(drain_deferred_context(conv_id))
        for key in ("system_message", "additional_context"):
            val = fields.get(key)
            if isinstance(val, str) and val and val not in messages:
                messages.append(val)
        if not messages:
            return {}
        combined = "\n\n".join(messages)
        return {"injectSteps": [{"systemMessage": {"systemMessage": combined}}]}

    if agy_event == "PostInvocation":
        messages = []
        if drain_deferred:
            messages.extend(drain_deferred_context(conv_id))
        for key in ("system_message", "additional_context"):
            val = fields.get(key)
            if isinstance(val, str) and val and val not in messages:
                messages.append(val)
        out = {}
        if messages:
            out["injectSteps"] = [{"systemMessage": {"systemMessage": "\n\n".join(messages)}}]
        if returncode == 2 or fields.get("decision") == "block" or fields.get("permission") == "deny":
            out["terminationBehavior"] = "force_continue"
        elif fields.get("continue_flag") is False:
            out["terminationBehavior"] = "terminate"
        return out

    if agy_event == "Stop":
        if returncode == 2 or fields.get("decision") == "block" or fields.get("permission") == "deny":
            reason = fields.get("reason") or fields.get("permission_reason") or exit2_reason
            return {"decision": "continue", "reason": reason}
        return {"decision": "allow"}

    return {}


def failure_output(agy_event: str, failure_policy: str, detail: str) -> dict[str, Any]:
    """Return a safe Antigravity JSON response when the adapter or child hook errors."""
    message = f"[agy-hook-adapter] {detail}"
    if failure_policy == "open":
        if agy_event == "PreToolUse":
            return {"decision": "allow"}
        if agy_event == "Stop":
            return {"decision": "allow"}
        return {}
    # closed policy
    if agy_event == "PreToolUse":
        return {"decision": "deny", "reason": message}
    if agy_event == "Stop":
        return {"decision": "continue", "reason": message}
    if agy_event == "PostInvocation":
        return {"terminationBehavior": "terminate"}
    return {}


def run_adapter(args: argparse.Namespace, raw_input: str) -> dict[str, Any]:
    """Execute the target VexJoy hook and return an Antigravity-compliant JSON dict."""
    if not raw_input.strip():
        raw_input = "{}"
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        return failure_output(args.event, args.failure_policy, f"invalid input JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return failure_output(args.event, args.failure_policy, "invalid input JSON: expected an object")
    if args.timeout <= 0:
        return failure_output(args.event, args.failure_policy, "timeout must be positive")
    if not args.hook.is_file():
        return failure_output(args.event, args.failure_policy, f"hook not found: {args.hook}")

    normalized = normalize_agy_payload(payload, agy_event=args.event)
    cwd = normalized.get("cwd") if isinstance(normalized.get("cwd"), str) and normalized.get("cwd") else os.getcwd()
    if not os.path.isdir(cwd):
        cwd = os.getcwd()

    try:
        completed = subprocess.run(
            [sys.executable, str(args.hook)],
            input=json.dumps(normalized),
            text=True,
            capture_output=True,
            cwd=cwd,
            env=compatibility_environment(normalized),
            timeout=args.timeout,
            check=False,
        )
        if len(completed.stdout.encode()) > _MAX_CHILD_OUTPUT or len(completed.stderr.encode()) > _MAX_CHILD_OUTPUT:
            raise AdapterError("child hook output exceeded 1 MiB")
        return translate_child_result(
            args.event,
            completed.returncode,
            completed.stdout,
            completed.stderr,
            normalized_event=normalized,
            drain_deferred=args.drain_deferred,
        )
    except subprocess.TimeoutExpired:
        return failure_output(args.event, args.failure_policy, f"child hook timed out after {args.timeout:g}s")
    except (AdapterError, OSError, ValueError) as exc:
        return failure_output(args.event, args.failure_policy, str(exc))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hook", type=Path, required=True)
    parser.add_argument("--event", choices=AGY_EVENTS, required=True)
    parser.add_argument("--matcher", default="*")
    parser.add_argument("--failure-policy", choices=FAILURE_POLICIES, default="open")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--drain-deferred",
        action="store_true",
        help="Drain queued PostToolUse advisory context into injectSteps (used on the first PreInvocation hook).",
    )
    return parser


_BYPASS_ENV = "AGY_HOOK_ADAPTER_BYPASS"


def main() -> int:
    if os.environ.get(_BYPASS_ENV) == "1":
        return 0
    args = _parser().parse_args()
    try:
        output = run_adapter(args, sys.stdin.read())
    except Exception as exc:
        output = failure_output(args.event, args.failure_policy, f"unexpected adapter error: {exc}")
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
