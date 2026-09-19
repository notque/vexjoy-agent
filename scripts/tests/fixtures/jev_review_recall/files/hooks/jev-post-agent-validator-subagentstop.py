#!/usr/bin/env python3
# hook-version: 2.0.0
"""
SubagentStop Hook: Jev Post-Agent Validator

Validates subagent output against three dimensions in a single Jev call:

  1. Completion  (15 questions) -- did the output address the request?
  2. Confidence  (4 questions)  -- does output quality match expectations?
  3. Scope-creep (12 questions) -- did the agent expand beyond scope?

v2 (Task 11): merged the three separate scripts into one 31-question Jev
call. Same questions, same answer parsing, one HTTP round trip instead of
three. Question defs imported from the scripts; no wording changes.

Findings are written to stderr (debug-visible) and a per-session state file
so downstream hooks/turns can read them. SubagentStop does NOT support
hookSpecificOutput/additionalContext, so stdout emits ``{}`` only.

Design:
- Non-blocking: always exits 0 (fail-open on every error path).
- Single Jev call: 31 questions evaluated in one request.
- Sub-50ms overhead: the hook's own overhead is minimal; the Jev call
  is bounded by JEV_CALL_TIMEOUT.
- Truncates long text to 3000 chars before passing to Jev.
- Dedupe: (session_id, output_hash) prevents re-validating identical output.

Skip conditions (fail-open, no validation):
- No output text extractable from event
- No request text extractable from event
- Agent type starts with "reviewer-" (read-only agents; scope-creep N/A)
- Jev unavailable or call fails
- Duplicate (session_id, output_hash) already validated
"""

import hashlib
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import PIPE, Popen, TimeoutExpired

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from hook_utils import hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "SubagentStop"
HOOK_NAME = "jev-post-agent-validator"
JEV_TOOL_TIMEOUT = 10  # per-tool timeout in seconds (subprocess fallback)
JEV_CALL_TIMEOUT = 12.0  # merged call timeout in seconds
MAX_TEXT_LEN = 3000  # truncation limit for Jev input

# Jev scripts to run, keyed by short name (subprocess fallback).
_JEV_TOOLS = ("jev-completion-validator", "jev-agent-confidence", "jev-scope-creep")

# Read-only agents: skip scope-creep (and confidence is less meaningful).
_REVIEWER_PREFIX = "reviewer-"

# Session state directory for persisting findings.
_STATE_DIR = Path.home() / ".claude" / "state" / "jev-post-agent-validator"

# Dedupe directory: prevents re-validating the same (session, output) pair.
# SubagentStop fires per completed agent, including nested forks and parallel
# agents. A multi-agent session can fire 70+ events for ~6 top-level dispatches
# when each agent forks sub-agents. Dedupe keyed on (session_id, output_hash)
# ensures each unique output is validated exactly once per session.
_DEDUPE_DIR = _STATE_DIR / "dedupe"


def _output_hash(text: str) -> str:
    """SHA-256 of the output text, first 16 hex chars."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _is_duplicate(session_id: str, output_text: str) -> bool:
    """Return True if this (session, output) pair was already validated.

    Creates a marker file on first encounter. Best-effort: any filesystem
    error returns False (fail-open, may re-validate).
    """
    if not session_id or "/" in session_id or "\\" in session_id or session_id in (".", ".."):
        return False
    try:
        _DEDUPE_DIR.mkdir(parents=True, exist_ok=True)
        ohash = _output_hash(output_text)
        # Include session_id prefix (sanitized to first 12 chars) and hash.
        safe_sid = session_id[:12].replace("/", "_").replace("\\", "_")
        marker = _DEDUPE_DIR / f"{safe_sid}-{ohash}.seen"
        if marker.exists():
            return True
        marker.write_text("", encoding="utf-8")
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Event payload extraction
# ---------------------------------------------------------------------------


def extract_output_text(event: dict) -> str:
    """Extract the agent's output text from the SubagentStop event.

    Checks ``result`` first (task-notification summary, richest), then
    ``subagent_result``, then ``last_assistant_message`` (often just a
    short sign-off line). The fullest text wins.
    """
    candidates: list[str] = []

    # Direct fields — collect all non-empty ones, pick the longest.
    for key in ("result", "output", "last_assistant_message"):
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            candidates.append(val.strip())

    # Nested in subagent_result or tool_result.
    for container_key in ("subagent_result", "tool_result", "tool_response"):
        container = event.get(container_key)
        if isinstance(container, dict):
            for key in ("output", "text", "content", "message", "stdout"):
                val = container.get(key)
                if isinstance(val, str) and val.strip():
                    candidates.append(val.strip())
        if isinstance(container, str) and container.strip():
            candidates.append(container.strip())

    # Return the longest candidate — it carries the most context for grading.
    if candidates:
        return max(candidates, key=len)
    return ""


def _text_from_content(content: object) -> str:
    """Flatten a transcript message content field (str or block list) to text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return ""


def first_user_message_from_transcript(transcript_path: str) -> str:
    """Return the first user message text from a JSONL transcript, or "".

    Each line is a JSON object; user rows carry ``type == "user"`` and a
    ``message`` dict with ``content`` (string or block list). Meta rows and
    rows whose content is only tool results are skipped.
    """
    if not transcript_path:
        return ""
    path = Path(transcript_path)
    try:
        if not path.is_file():
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "user" or entry.get("isMeta"):
                    continue
                message = entry.get("message")
                if not isinstance(message, dict):
                    continue
                text = _text_from_content(message.get("content"))
                if text:
                    return text
    except OSError:
        return ""
    return ""


def extract_request_text(event: dict) -> str:
    """Extract the original request text from the SubagentStop event.

    SubagentStop carries no prompt field; the request is the first user
    message of the subagent transcript (``agent_transcript_path``, then
    ``transcript_path``). The task_prompt/task/prompt/description keys stay
    as a fallback for synthetic events.
    """
    for key in ("agent_transcript_path", "transcript_path"):
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            text = first_user_message_from_transcript(val.strip())
            if text:
                return text
    for key in ("task_prompt", "task", "prompt", "description"):
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def is_reviewer_agent(agent_type: str) -> bool:
    """Return True if agent_type starts with 'reviewer-' prefix."""
    return bool(agent_type) and agent_type.startswith(_REVIEWER_PREFIX)


def truncate(text: str, max_len: int = MAX_TEXT_LEN) -> str:
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... [truncated]"


# ---------------------------------------------------------------------------
# Jev tool execution
# ---------------------------------------------------------------------------


def _scripts_dir() -> Path:
    """Return the scripts directory path."""
    return Path(__file__).resolve().parent.parent / "scripts"


def _write_private_tempfile(content: str, prefix: str) -> str:
    """Write content to a fresh 0600 temp file and return its path."""
    fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix=prefix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    os.chmod(tmp_path, 0o600)
    return tmp_path


def run_jev_tool(
    tool_name: str, request_text: str, output_text: str, context: str = "", session_id: str = "", agent_id: str = ""
) -> dict | None:
    """Run a single Jev tool script as a subprocess.

    Request and output go through 0600 temp files (``--request-file`` /
    ``--output-file``) so they never appear on argv. Temp files are removed
    in ``finally``. Returns the parsed JSON result, or None on any failure
    (fail-open).
    """
    script = _scripts_dir() / f"{tool_name}.py"
    if not script.is_file():
        return None

    req_path = out_path = None
    proc = None
    try:
        req_path = _write_private_tempfile(request_text, "jev-validator-req-")
        out_path = _write_private_tempfile(output_text, "jev-validator-out-")
        cmd = [
            sys.executable,
            str(script),
            "--request-file",
            req_path,
            "--output-file",
            out_path,
            "--json-compact",
        ]
        if context:
            cmd.extend(["--context", context])
        child_env = os.environ.copy()
        if session_id:
            child_env["JEV_SESSION_ID"] = session_id
        if agent_id:
            child_env["JEV_AGENT_ID"] = agent_id
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True, env=child_env)
        stdout, _ = proc.communicate(timeout=JEV_TOOL_TIMEOUT)
    except (OSError, TimeoutExpired, ValueError):
        if proc is not None:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
        return None
    finally:
        for path in (req_path, out_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    if proc.returncode != 0 or not stdout.strip():
        return None

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    return result if isinstance(result, dict) else None


def _summarize_completion(cv_result: dict | None) -> str:
    """Extract a brief summary from completion-validator results for threading."""
    if not cv_result:
        return ""
    verdict = cv_result.get("verdict", "unknown")
    depth = cv_result.get("completeness_depth", "?")
    addressed = cv_result.get("addressed_primary_intent", "?")
    return f"Prior assessment: verdict={verdict}, completeness={depth}/5, addressed={addressed}"


def run_jev_tool_with_context(
    tool_name: str, request_text: str, output_text: str, context: str = "", session_id: str = "", agent_id: str = ""
) -> dict | None:
    """Run a Jev tool with optional --context for prior assessment threading."""
    return run_jev_tool(tool_name, request_text, output_text, context, session_id=session_id, agent_id=agent_id)


def run_all_tools(
    request_text: str, output_text: str, session_id: str = "", agent_id: str = ""
) -> dict[str, dict | None]:
    """Run Jev tools with prior-assessment threading.

    Completion-validator runs first (primary assessment). Its findings are
    threaded into scope-creep and agent-confidence as --context, so they
    have temporal awareness of what completion already judged.

    Reviewer agents are skipped entirely before this function is called,
    so all 3 tools always run when this is reached.
    """
    results: dict[str, dict | None] = {}

    # Phase 1: run completion-validator first (primary assessment).
    results["jev-completion-validator"] = run_jev_tool(
        "jev-completion-validator", request_text, output_text, session_id=session_id, agent_id=agent_id
    )

    # Extract completion summary for threading.
    completion_context = _summarize_completion(results["jev-completion-validator"])

    # Phase 2: run scope-creep and agent-confidence in parallel, with completion context.
    secondary_tools = ["jev-agent-confidence", "jev-scope-creep"]

    with ThreadPoolExecutor(max_workers=len(secondary_tools)) as executor:
        futures = {
            executor.submit(
                run_jev_tool_with_context, tool, request_text, output_text, completion_context, session_id, agent_id
            ): tool
            for tool in secondary_tools
        }
        for future in as_completed(futures):
            tool = futures[future]
            try:
                results[tool] = future.result()
            except Exception:
                results[tool] = None

    return results


# ---------------------------------------------------------------------------
# Findings formatting
# ---------------------------------------------------------------------------


def format_findings(results: dict[str, dict | None], agent_type: str) -> str:
    """Format Jev tool results into a structured findings string."""
    parts = [f"[{HOOK_NAME}] Jev validated subagent output (agent_type={agent_type}):"]

    # Completion validator
    cv = results.get("jev-completion-validator")
    if cv:
        verdict = cv.get("verdict", "unknown")
        completeness = cv.get("completeness_depth", "?")
        addressed = cv.get("addressed_primary_intent", "?")
        parts.append(f"  COMPLETION: {verdict} (completeness: {completeness}/5, addressed: {addressed})")
    else:
        parts.append("  COMPLETION: unavailable")

    # Agent confidence
    ac = results.get("jev-agent-confidence")
    if ac:
        quality = ac.get("output_quality", "?")
        matches = ac.get("matches_intent", "?")
        reroute = ac.get("should_reroute", "?")
        parts.append(f"  CONFIDENCE: output_quality={quality}/5 (matches_intent: {matches}, should_reroute: {reroute})")
    else:
        parts.append("  CONFIDENCE: unavailable")

    # Scope creep
    sc = results.get("jev-scope-creep")
    if sc:
        expansion = sc.get("scope_expansion", "?")
        outside = sc.get("files_outside_scope", "?")
        justified = sc.get("is_justified", "?")
        parts.append(f"  SCOPE: {expansion} (files_outside_scope: {outside}, justified: {justified})")
    elif "jev-scope-creep" not in results:
        parts.append("  SCOPE: skipped (reviewer agent)")
    else:
        parts.append("  SCOPE: unavailable")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def save_findings(session_id: str, findings: str, results: dict[str, dict | None]) -> None:
    """Persist findings to a per-session state file (best-effort).

    State file: consumed by jev-route-injector on next prompt (feedback loop).
    Uses atomic write-to-temp-then-rename to prevent corruption.
    """
    if not session_id:
        return

    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file = _STATE_DIR / f"{session_id}.json"
        state = {
            "findings": findings,
            "results": {k: v for k, v in results.items() if v is not None},
        }

        fd, tmp = tempfile.mkstemp(dir=str(_STATE_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp, str(state_file))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    raw = read_stdin(timeout=2)
    if not raw or not raw.strip():
        return

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return

    # Verify event type when present.
    event_type = event.get("hook_event_name") or event.get("type", "")
    if event_type and event_type != EVENT_NAME:
        return

    agent_type = event.get("agent_type", "")
    session_id = event.get("session_id", "")

    # Skip reviewer agents entirely (read-only; scope-creep doesn't apply,
    # completion/confidence less meaningful).
    if is_reviewer_agent(agent_type):
        print(f"[{HOOK_NAME}] Skipping reviewer agent: {agent_type}", file=sys.stderr)
        return

    # Extract request and output text.
    request_text = extract_request_text(event)
    output_text = extract_output_text(event)

    if not request_text:
        print(f"[{HOOK_NAME}] No request text extractable; skipping validation", file=sys.stderr)
        return

    if not output_text:
        print(f"[{HOOK_NAME}] No output text extractable; skipping validation", file=sys.stderr)
        return

    # Dedupe: skip if this (session, output) pair was already validated.
    if _is_duplicate(session_id, output_text):
        print(
            f"[{HOOK_NAME}] Duplicate output for session {session_id[:8] if session_id else '?'}; skipping",
            file=sys.stderr,
        )
        return

    # Truncate for Jev.
    request_text = truncate(request_text)
    output_text = truncate(output_text)

    # Run all Jev tools in parallel.
    # Extract agent identifier for telemetry.
    agent_id = event.get("agent_id") or event.get("agent_type") or event.get("subagent_type") or ""

    results = run_all_tools(request_text, output_text, session_id=session_id, agent_id=agent_id)

    # Check if ALL tools failed.
    if all(v is None for v in results.values()):
        print(f"[{HOOK_NAME}] All Jev tools failed; skipping findings", file=sys.stderr)
        return

    # Format and emit findings.
    findings = format_findings(results, agent_type)
    print(findings, file=sys.stderr)

    # Persist to session state file for downstream consumption.
    save_findings(session_id, findings, results)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        hook_error(HOOK_NAME, exc)
    finally:
        sys.exit(0)
