#!/usr/bin/env python3
# hook-version: 1.0.0
"""
MCP Health Check Hook (ADR-116)

Monitors MCP server health with exponential backoff and JSON state persistence.
Handles two events via single-file dispatch on CLAUDE_HOOK_EVENT_NAME:

- PreToolUse:          Probe before MCP tool calls. Block (exit 2) if unhealthy
                       and within backoff window.
- PostToolUseFailure:  Detect failure patterns, mark server unhealthy. Exit 0
                       always (observing only).

State persisted to ~/.claude/mcp-health-cache.json.
Fail-open on any unexpected exception (exit 0).

Bypass:
  MCP_HEALTH_CHECK_BYPASS=1    — disable for a single invocation
  MCP_HEALTH_FAIL_OPEN=1       — suppress blocking, emit warning instead

Reconnect (optional):
  MCP_HEALTH_RECONNECT_{SERVER}  — shell command to reconnect a named server
  MCP_HEALTH_RECONNECT_COMMAND   — fallback reconnect command (all servers)
"""

import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

STATE_FILE = Path.home() / ".claude" / "mcp-health-cache.json"

# TTL for healthy cache entries (ms). Override via MCP_HEALTH_TTL_MS.
DEFAULT_HEALTH_TTL_MS = 2 * 60 * 1000  # 2 minutes

# Backoff configuration
BACKOFF_BASE_MS = 30 * 1000  # 30 seconds base
BACKOFF_CAP_MS = 10 * 60 * 1000  # 10 minutes maximum

# Probe timeout (ms)
PROBE_TIMEOUT_S = 5

# MCP tool prefix — Claude Code names MCP tools mcp__{server}__{tool}
MCP_TOOL_PREFIX = "mcp__"

# ═══════════════════════════════════════════════════════════════
# FAILURE PATTERNS — detected in PostToolUseFailure output
# ═══════════════════════════════════════════════════════════════

_FAILURE_PATTERNS: list[re.Pattern[str]] = [
    # Auth failures
    re.compile(r"\b401\b"),
    re.compile(r"unauthorized", re.IGNORECASE),
    re.compile(r"auth\s*(failed|expired|invalid)", re.IGNORECASE),
    # Forbidden
    re.compile(r"\b403\b"),
    re.compile(r"forbidden", re.IGNORECASE),
    re.compile(r"permission\s+denied", re.IGNORECASE),
    # Rate limit
    re.compile(r"\b429\b"),
    re.compile(r"rate\s+limit", re.IGNORECASE),
    re.compile(r"too\s+many\s+requests", re.IGNORECASE),
    # Service unavailable
    re.compile(r"\b503\b"),
    re.compile(r"service\s+unavailable", re.IGNORECASE),
    re.compile(r"server\s+overloaded|overloaded\s+server", re.IGNORECASE),
    # Transport errors
    re.compile(r"ECONNREFUSED", re.IGNORECASE),
    re.compile(r"ENOTFOUND", re.IGNORECASE),
    re.compile(r"timed?\s*out", re.IGNORECASE),
    re.compile(r"socket\s+hang\s+up", re.IGNORECASE),
    re.compile(r"connection\s+(failed|lost|reset|closed)", re.IGNORECASE),
]


# ═══════════════════════════════════════════════════════════════
# STATE HELPERS
# ═══════════════════════════════════════════════════════════════


def _now_ms() -> int:
    """Current time as milliseconds since epoch."""
    return int(time.time() * 1000)


def _load_state() -> dict:
    """Load health state from disk. Falls back to empty state on any error."""
    empty: dict = {"version": 1, "servers": {}}
    if not STATE_FILE.exists():
        return empty
    try:
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "servers" not in data:
            return empty
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return empty


def _save_state(state: dict) -> None:
    """Persist health state to disk atomically (best-effort)."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        tmp.replace(STATE_FILE)
    except OSError:
        pass  # Best-effort; fail silently


def _get_server_entry(state: dict, server: str) -> dict:
    """Return the state entry for *server*, or a default empty entry."""
    return state["servers"].get(server, {})


def _mark_healthy(state: dict, server: str) -> None:
    try:
        ttl = int(os.environ.get("MCP_HEALTH_TTL_MS", DEFAULT_HEALTH_TTL_MS))
    except (ValueError, TypeError):
        ttl = DEFAULT_HEALTH_TTL_MS
    now = _now_ms()
    entry = state["servers"].get(server, {})
    entry.update(
        {
            "status": "healthy",
            "checkedAt": now,
            "expiresAt": now + ttl,
            "failureCount": 0,
            "lastError": None,
            "lastFailureCode": None,
            "nextRetryAt": now,
            "lastRestoredAt": now,
        }
    )
    state["servers"][server] = entry


def _mark_unhealthy(state: dict, server: str, error: str, code: str | None = None) -> None:
    now = _now_ms()
    entry = state["servers"].get(server, {})
    failure_count = entry.get("failureCount", 0) + 1
    # Exponential backoff: base * 2^(failureCount-1), capped at BACKOFF_CAP_MS
    backoff = min(BACKOFF_BASE_MS * (2 ** (failure_count - 1)), BACKOFF_CAP_MS)
    entry.update(
        {
            "status": "unhealthy",
            "checkedAt": now,
            "expiresAt": now,  # unhealthy entries don't cache positively
            "failureCount": failure_count,
            "lastError": error,
            "lastFailureCode": code,
            "nextRetryAt": now + backoff,
        }
    )
    state["servers"][server] = entry


# ═══════════════════════════════════════════════════════════════
# MCP CONFIG DISCOVERY
# ═══════════════════════════════════════════════════════════════


def _discover_mcp_config(server: str) -> dict | None:
    """
    Look for mcpServers config in the standard Claude Code config paths.
    Returns the server config dict for *server*, or None if not found.
    """
    home = Path.home()
    cwd = Path.cwd()
    search_paths = [
        cwd / ".claude.json",
        cwd / ".claude" / "settings.json",
        home / ".claude.json",
        home / ".claude" / "settings.json",
    ]
    for path in search_paths:
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            servers = data.get("mcpServers", {})
            if server in servers:
                return servers[server]
        except (json.JSONDecodeError, OSError):
            continue
    return None


# ═══════════════════════════════════════════════════════════════
# SERVER NAME EXTRACTION
# ═══════════════════════════════════════════════════════════════


def extract_server_name(tool_name: str) -> str | None:
    """
    Extract MCP server name from a Claude Code tool name.

    Claude Code names MCP tools: mcp__{server}__{tool}
    Returns the server name, or None if not an MCP tool.
    """
    if not tool_name.startswith(MCP_TOOL_PREFIX):
        return None
    # Strip leading "mcp__" and take the first segment
    rest = tool_name[len(MCP_TOOL_PREFIX) :]
    parts = rest.split("__", 1)
    if not parts or not parts[0]:
        return None
    return parts[0]


# ═══════════════════════════════════════════════════════════════
# PROBE STRATEGIES
# ═══════════════════════════════════════════════════════════════


def _probe_http(url: str) -> tuple[bool, str]:
    """
    Probe an HTTP/HTTPS MCP server.
    200-308 and 405 (method not allowed — server is alive) = healthy.
    Returns (is_healthy, message).
    """
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_S) as resp:
            status = resp.status
            if 200 <= status <= 308 or status == 405:
                return True, f"HTTP {status}"
            return False, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        if e.code == 405:
            return True, f"HTTP 405 (alive)"
        return False, f"HTTP error {e.code}"
    except Exception as e:
        return False, str(e)


def _probe_command(cmd: str) -> tuple[bool, str]:
    """
    Probe a command-based MCP server by spawning it and checking it accepts stdin.
    We wait PROBE_TIMEOUT_S seconds; if the process is still running (accepted stdio),
    we treat it as healthy.
    Returns (is_healthy, message).
    """
    try:
        proc = subprocess.Popen(
            shlex.split(cmd) if isinstance(cmd, str) else cmd,
            shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            proc.wait(timeout=PROBE_TIMEOUT_S)
            # Process exited — could be healthy (quick init) or failure
            if proc.returncode == 0:
                return True, "command exited 0"
            return False, f"command exited {proc.returncode}"
        except subprocess.TimeoutExpired:
            # Still running after timeout — server is accepting stdio, healthy
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            return True, "command accepted stdio (timeout=healthy)"
    except Exception as e:
        return False, str(e)


def probe_server(server: str, config: dict | None) -> tuple[bool, str]:
    """
    Probe the server using the best available strategy.
    Falls back to marking healthy if no config is available (fail-open for unknown servers).
    Returns (is_healthy, message).
    """
    if config is None:
        # No config discovered — fail-open: assume healthy, don't block
        return True, "no config found (fail-open)"

    # HTTP probe: config has a url field
    url = config.get("url") or config.get("baseUrl")
    if url:
        return _probe_http(url)

    # Command probe: config has a command field
    command = config.get("command")
    if command:
        args = config.get("args", [])
        if args:
            cmd_str = command + " " + " ".join(str(a) for a in args)
        else:
            cmd_str = command
        return _probe_command(cmd_str)

    # No probe strategy available — fail-open
    return True, "no probe strategy (fail-open)"


# ═══════════════════════════════════════════════════════════════
# RECONNECT SUPPORT (optional, deferred per ADR)
# ═══════════════════════════════════════════════════════════════


def _attempt_reconnect(server: str) -> bool:
    """
    Attempt reconnect via MCP_HEALTH_RECONNECT_{SERVER} or MCP_HEALTH_RECONNECT_COMMAND.
    Returns True if reconnect command exited 0.
    """
    server_upper = server.upper().replace("-", "_")
    cmd = os.environ.get(f"MCP_HEALTH_RECONNECT_{server_upper}") or os.environ.get("MCP_HEALTH_RECONNECT_COMMAND")
    if not cmd:
        return False
    try:
        result = subprocess.run(
            shlex.split(cmd) if isinstance(cmd, str) else cmd,
            shell=False,
            timeout=30,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# PRE-TOOL-USE HANDLER
# ═══════════════════════════════════════════════════════════════


def handle_pretool(event: dict) -> None:
    """
    PreToolUse handler: probe MCP server health and block if unhealthy.

    Exit codes:
      0 — allow (healthy, non-MCP tool, or fail-open)
      2 — block (unhealthy server within backoff window)
    """
    tool_name = event.get("tool_name") or event.get("tool", "")
    server = extract_server_name(tool_name)
    if server is None:
        # Not an MCP tool — pass through immediately
        return

    now = _now_ms()
    state = _load_state()
    entry = _get_server_entry(state, server)

    # Fast path: cached healthy and TTL not expired
    if entry.get("status") == "healthy" and entry.get("expiresAt", 0) > now:
        return  # exit 0

    # Unhealthy path: check backoff window
    if entry.get("status") == "unhealthy":
        next_retry = entry.get("nextRetryAt", 0)
        if now < next_retry:
            # Within backoff window — block or warn depending on fail-open mode
            fail_open = os.environ.get("MCP_HEALTH_FAIL_OPEN") == "1"
            failure_count = entry.get("failureCount", 0)
            last_error = entry.get("lastError", "unknown")
            retry_in_s = (next_retry - now) // 1000

            msg = (
                f"[mcp-health-check] MCP server '{server}' is unhealthy "
                f"(failures={failure_count}, last_error={last_error!r}, "
                f"retry_in={retry_in_s}s)"
            )
            if fail_open:
                print(f"[mcp-health-check] WARNING (fail-open): {msg}", file=sys.stderr)
                return  # exit 0
            else:
                print(msg, file=sys.stderr)
                sys.exit(2)
        # Past nextRetryAt — fall through to re-probe

    # Probe the server
    config = _discover_mcp_config(server)
    is_healthy, probe_msg = probe_server(server, config)

    if is_healthy:
        _mark_healthy(state, server)
        _save_state(state)
        return  # exit 0
    else:
        # Attempt reconnect before giving up
        if _attempt_reconnect(server):
            # Re-probe after reconnect
            is_healthy2, probe_msg2 = probe_server(server, config)
            if is_healthy2:
                _mark_healthy(state, server)
                _save_state(state)
                return  # exit 0
            probe_msg = f"{probe_msg} (reconnect attempted: {probe_msg2})"

        _mark_unhealthy(state, server, probe_msg)
        _save_state(state)

        fail_open = os.environ.get("MCP_HEALTH_FAIL_OPEN") == "1"
        failure_count = state["servers"][server].get("failureCount", 1)
        retry_in_s = BACKOFF_BASE_MS * (2 ** (failure_count - 1)) // 1000
        retry_in_s = min(retry_in_s, BACKOFF_CAP_MS // 1000)

        msg = f"[mcp-health-check] MCP server '{server}' probe failed: {probe_msg} (backoff={retry_in_s}s)"
        if fail_open:
            print(f"[mcp-health-check] WARNING (fail-open): {msg}", file=sys.stderr)
            return  # exit 0
        else:
            print(msg, file=sys.stderr)
            sys.exit(2)


# ═══════════════════════════════════════════════════════════════
# POST-TOOL-USE-FAILURE HANDLER
# ═══════════════════════════════════════════════════════════════


def _extract_failure_text(event: dict) -> str:
    """Extract all text from a PostToolUseFailure event for pattern matching."""
    parts: list[str] = []
    # tool_response / result fields
    for key in ("tool_response", "result", "error", "output"):
        val = event.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, dict):
            for subkey in ("output", "error", "stderr", "stdout", "content"):
                sub = val.get(subkey)
                if isinstance(sub, str):
                    parts.append(sub)
    # Also include raw string content blocks if present
    content = event.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content", "")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
    return "\n".join(parts)


def detect_failure_pattern(text: str) -> str | None:
    """Return the first matching failure pattern string, or None."""
    for pattern in _FAILURE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


def handle_posttool_failure(event: dict) -> None:
    """
    PostToolUseFailure handler: detect failure patterns and mark server unhealthy.
    Always exits 0 (observing only — never blocks).
    """
    tool_name = event.get("tool_name") or event.get("tool", "")
    server = extract_server_name(tool_name)
    if server is None:
        return  # Not an MCP tool — nothing to do

    failure_text = _extract_failure_text(event)
    matched = detect_failure_pattern(failure_text)
    if matched is None:
        return  # No known failure pattern — don't mark unhealthy

    state = _load_state()
    _mark_unhealthy(state, server, error=failure_text[:200], code=matched)
    _save_state(state)

    entry = state["servers"][server]
    failure_count = entry.get("failureCount", 1)
    next_retry = entry.get("nextRetryAt", 0)
    retry_in_s = max(0, (next_retry - _now_ms()) // 1000)

    print(
        f"[mcp-health-check] Marked '{server}' unhealthy "
        f"(pattern={matched!r}, failures={failure_count}, retry_in={retry_in_s}s)",
        file=sys.stderr,
    )


# ═══════════════════════════════════════════════════════════════
# MAIN DISPATCH
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    # Bypass: single-invocation disable
    if os.environ.get("MCP_HEALTH_CHECK_BYPASS") == "1":
        return

    raw = read_stdin(timeout=5)
    if not raw.strip():
        return

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return  # Fail-open: bad input is not our problem

    event_name = os.environ.get("CLAUDE_HOOK_EVENT_NAME", "PreToolUse")

    if event_name == "PostToolUseFailure":
        handle_posttool_failure(event)
    else:
        # Default to PreToolUse path
        handle_pretool(event)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(2) propagate for blocks
    except Exception:
        # Fail OPEN — a crashed hook must never exit 2.
        sys.exit(0)
