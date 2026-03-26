#!/usr/bin/env python3
"""
Tests for the mcp-health-check hook (ADR-116).

Run with: python3 -m pytest hooks/tests/test_mcp_health_check.py -v
"""

import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "mcp-health-check.py"

spec = importlib.util.spec_from_file_location("mcp_health_check", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

extract_server_name = mod.extract_server_name
detect_failure_pattern = mod.detect_failure_pattern
handle_pretool = mod.handle_pretool
handle_posttool_failure = mod.handle_posttool_failure
probe_server = mod.probe_server
_load_state = mod._load_state
_save_state = mod._save_state
_mark_healthy = mod._mark_healthy
_mark_unhealthy = mod._mark_unhealthy
_now_ms = mod._now_ms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state_file(data: dict) -> str:
    """Write JSON to a temp file and return its path string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _event(tool_name: str, **extra) -> dict:
    """Build a minimal hook event dict."""
    return {"tool_name": tool_name, **extra}


# ---------------------------------------------------------------------------
# Tier 0: Server Name Extraction
# ---------------------------------------------------------------------------


class TestExtractServerName:
    """Unit tests for MCP tool-name parsing."""

    def test_mcp_tool_returns_server_name(self):
        assert extract_server_name("mcp__my-server__get_resource") == "my-server"

    def test_mcp_tool_single_segment(self):
        assert extract_server_name("mcp__toolonly") == "toolonly"

    def test_non_mcp_tool_returns_none(self):
        assert extract_server_name("Bash") is None
        assert extract_server_name("Read") is None
        assert extract_server_name("Write") is None
        assert extract_server_name("Edit") is None

    def test_empty_string_returns_none(self):
        assert extract_server_name("") is None

    def test_mcp_prefix_only_returns_none(self):
        # "mcp__" with nothing after the prefix segment
        assert extract_server_name("mcp__") is None

    def test_server_with_underscores(self):
        assert extract_server_name("mcp__my_cool_server__do_thing") == "my_cool_server"

    def test_server_with_hyphens(self):
        assert extract_server_name("mcp__context7__search") == "context7"

    def test_mcp_uppercase_not_matched(self):
        """Tool names starting with MCP__ (uppercase) are not MCP tools."""
        assert extract_server_name("MCP__server__tool") is None


# ---------------------------------------------------------------------------
# Tier 1: State Machine — _mark_healthy / _mark_unhealthy
# ---------------------------------------------------------------------------


class TestStateMachineTransitions:
    """Unit tests for healthy/unhealthy state transitions."""

    def _fresh_state(self) -> dict:
        return {"version": 1, "servers": {}}

    def test_mark_healthy_sets_status(self):
        state = self._fresh_state()
        _mark_healthy(state, "my-server")
        entry = state["servers"]["my-server"]
        assert entry["status"] == "healthy"
        assert entry["failureCount"] == 0
        assert entry["lastError"] is None

    def test_mark_healthy_sets_expires_at_in_future(self):
        state = self._fresh_state()
        before = _now_ms()
        _mark_healthy(state, "my-server")
        after = _now_ms()
        entry = state["servers"]["my-server"]
        assert entry["expiresAt"] > before
        assert entry["expiresAt"] <= after + mod.DEFAULT_HEALTH_TTL_MS + 1000

    def test_mark_unhealthy_sets_status(self):
        state = self._fresh_state()
        _mark_unhealthy(state, "my-server", "connection refused")
        entry = state["servers"]["my-server"]
        assert entry["status"] == "unhealthy"
        assert entry["failureCount"] == 1
        assert entry["lastError"] == "connection refused"

    def test_mark_unhealthy_increments_failure_count(self):
        state = self._fresh_state()
        # First failure
        _mark_unhealthy(state, "my-server", "err1")
        assert state["servers"]["my-server"]["failureCount"] == 1
        # Second failure
        _mark_unhealthy(state, "my-server", "err2")
        assert state["servers"]["my-server"]["failureCount"] == 2

    def test_mark_unhealthy_sets_next_retry_at_in_future(self):
        state = self._fresh_state()
        before = _now_ms()
        _mark_unhealthy(state, "my-server", "err")
        entry = state["servers"]["my-server"]
        assert entry["nextRetryAt"] > before

    def test_healthy_after_unhealthy_resets_failure_count(self):
        state = self._fresh_state()
        _mark_unhealthy(state, "my-server", "err")
        _mark_unhealthy(state, "my-server", "err2")
        _mark_healthy(state, "my-server")
        assert state["servers"]["my-server"]["failureCount"] == 0
        assert state["servers"]["my-server"]["status"] == "healthy"

    def test_mark_unhealthy_stores_code(self):
        state = self._fresh_state()
        _mark_unhealthy(state, "my-server", "rate limit hit", code="429")
        assert state["servers"]["my-server"]["lastFailureCode"] == "429"


# ---------------------------------------------------------------------------
# Tier 2: Backoff Calculation
# ---------------------------------------------------------------------------


class TestBackoffCalculation:
    """Unit tests for exponential backoff nextRetryAt values."""

    def _fresh_state(self) -> dict:
        return {"version": 1, "servers": {}}

    def test_first_failure_backoff_is_base(self):
        state = self._fresh_state()
        before = _now_ms()
        _mark_unhealthy(state, "srv", "err")
        entry = state["servers"]["srv"]
        backoff_ms = entry["nextRetryAt"] - entry["checkedAt"]
        assert backoff_ms == mod.BACKOFF_BASE_MS  # 30s

    def test_second_failure_backoff_doubles(self):
        state = self._fresh_state()
        _mark_unhealthy(state, "srv", "err1")  # failureCount -> 1
        _mark_unhealthy(state, "srv", "err2")  # failureCount -> 2
        entry = state["servers"]["srv"]
        backoff_ms = entry["nextRetryAt"] - entry["checkedAt"]
        expected = mod.BACKOFF_BASE_MS * (2 ** (2 - 1))  # 60s
        assert backoff_ms == expected

    def test_third_failure_backoff_quadruples(self):
        state = self._fresh_state()
        for i in range(3):
            _mark_unhealthy(state, "srv", f"err{i}")
        entry = state["servers"]["srv"]
        backoff_ms = entry["nextRetryAt"] - entry["checkedAt"]
        expected = mod.BACKOFF_BASE_MS * (2 ** (3 - 1))  # 120s
        assert backoff_ms == expected

    def test_backoff_caps_at_max(self):
        state = self._fresh_state()
        # Many failures should cap at BACKOFF_CAP_MS
        for i in range(20):
            _mark_unhealthy(state, "srv", f"err{i}")
        entry = state["servers"]["srv"]
        backoff_ms = entry["nextRetryAt"] - entry["checkedAt"]
        assert backoff_ms == mod.BACKOFF_CAP_MS

    def test_backoff_cap_is_ten_minutes(self):
        assert mod.BACKOFF_CAP_MS == 10 * 60 * 1000

    def test_backoff_base_is_thirty_seconds(self):
        assert mod.BACKOFF_BASE_MS == 30 * 1000


# ---------------------------------------------------------------------------
# Tier 3: Failure Pattern Detection
# ---------------------------------------------------------------------------


class TestFailurePatternDetection:
    """Unit tests for PostToolUseFailure text pattern matching."""

    def test_detects_401(self):
        assert detect_failure_pattern("Error: 401 Unauthorized") is not None

    def test_detects_unauthorized(self):
        assert detect_failure_pattern("auth failed: unauthorized access") is not None

    def test_detects_auth_expired(self):
        assert detect_failure_pattern("auth expired, please re-authenticate") is not None

    def test_detects_403(self):
        assert detect_failure_pattern("received 403 response") is not None

    def test_detects_forbidden(self):
        assert detect_failure_pattern("forbidden: access denied") is not None

    def test_detects_permission_denied(self):
        assert detect_failure_pattern("permission denied on resource") is not None

    def test_detects_429(self):
        assert detect_failure_pattern("HTTP 429 Too Many Requests") is not None

    def test_detects_rate_limit(self):
        assert detect_failure_pattern("rate limit exceeded, retry later") is not None

    def test_detects_503(self):
        assert detect_failure_pattern("upstream returned 503") is not None

    def test_detects_service_unavailable(self):
        assert detect_failure_pattern("service unavailable") is not None

    def test_detects_econnrefused(self):
        assert detect_failure_pattern("ECONNREFUSED 127.0.0.1:8080") is not None

    def test_detects_enotfound(self):
        assert detect_failure_pattern("getaddrinfo ENOTFOUND example.com") is not None

    def test_detects_timed_out(self):
        assert detect_failure_pattern("request timed out after 5s") is not None

    def test_detects_socket_hang_up(self):
        assert detect_failure_pattern("socket hang up") is not None

    def test_detects_connection_failed(self):
        assert detect_failure_pattern("connection failed") is not None

    def test_detects_connection_lost(self):
        assert detect_failure_pattern("connection lost") is not None

    def test_detects_connection_reset(self):
        assert detect_failure_pattern("connection reset by peer") is not None

    def test_detects_connection_closed(self):
        assert detect_failure_pattern("connection closed unexpectedly") is not None

    def test_no_match_returns_none(self):
        assert detect_failure_pattern("file not found") is None
        assert detect_failure_pattern("syntax error on line 5") is None
        assert detect_failure_pattern("") is None

    def test_case_insensitive_match(self):
        assert detect_failure_pattern("RATE LIMIT hit") is not None
        assert detect_failure_pattern("Service Unavailable") is not None


# ---------------------------------------------------------------------------
# Tier 4: State File I/O
# ---------------------------------------------------------------------------


class TestStateFileIO:
    """Tests for state persistence and corrupt-file handling."""

    def test_load_state_returns_empty_when_file_missing(self, tmp_path):
        with patch.object(mod, "STATE_FILE", tmp_path / "nonexistent.json"):
            state = _load_state()
        assert state == {"version": 1, "servers": {}}

    def test_load_state_reads_valid_file(self, tmp_path):
        data = {"version": 1, "servers": {"srv": {"status": "healthy"}}}
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps(data))
        with patch.object(mod, "STATE_FILE", state_file):
            state = _load_state()
        assert state["servers"]["srv"]["status"] == "healthy"

    def test_load_state_falls_back_on_corrupt_json(self, tmp_path):
        state_file = tmp_path / "health.json"
        state_file.write_text("not valid json {{{{")
        with patch.object(mod, "STATE_FILE", state_file):
            state = _load_state()
        assert state == {"version": 1, "servers": {}}

    def test_load_state_falls_back_on_missing_servers_key(self, tmp_path):
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1}))
        with patch.object(mod, "STATE_FILE", state_file):
            state = _load_state()
        assert state == {"version": 1, "servers": {}}

    def test_save_state_persists_data(self, tmp_path):
        state_file = tmp_path / "health.json"
        data = {"version": 1, "servers": {"srv": {"status": "healthy"}}}
        with patch.object(mod, "STATE_FILE", state_file):
            _save_state(data)
            loaded = json.loads(state_file.read_text())
        assert loaded["servers"]["srv"]["status"] == "healthy"

    def test_save_state_creates_parent_dirs(self, tmp_path):
        state_file = tmp_path / "nested" / "dir" / "health.json"
        with patch.object(mod, "STATE_FILE", state_file):
            _save_state({"version": 1, "servers": {}})
        assert state_file.exists()

    def test_corrupt_cache_never_blocks(self, tmp_path):
        """A corrupt state file must result in fail-open (exit 0), never exit 2."""
        state_file = tmp_path / "health.json"
        state_file.write_text("}{bad json")

        event = _event("mcp__my-server__tool")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "_discover_mcp_config", return_value=None),
        ):
            # probe_server returns healthy when no config (fail-open)
            handle_pretool(event)  # Must not raise SystemExit(2)


# ---------------------------------------------------------------------------
# Tier 5: PreToolUse Handler
# ---------------------------------------------------------------------------


class TestHandlePreTool:
    """Integration tests for the PreToolUse handler."""

    def _fresh_state(self) -> dict:
        return {"version": 1, "servers": {}}

    def test_non_mcp_tool_exits_0(self):
        """Non-MCP tool calls pass through without touching state."""
        event = _event("Bash", tool_input={"command": "ls"})
        with patch.object(mod, "_load_state") as mock_load:
            handle_pretool(event)  # Must not raise SystemExit
        mock_load.assert_not_called()

    def test_non_mcp_read_tool_exits_0(self):
        event = _event("Read", tool_input={"file_path": "/tmp/file"})
        with patch.object(mod, "_load_state") as mock_load:
            handle_pretool(event)
        mock_load.assert_not_called()

    def test_cached_healthy_passes_without_probing(self, tmp_path):
        """Healthy entry with TTL not expired — pass without probing."""
        state_file = tmp_path / "health.json"
        now = _now_ms()
        state = {
            "version": 1,
            "servers": {
                "my-server": {
                    "status": "healthy",
                    "expiresAt": now + 60_000,  # expires in 1 minute
                    "checkedAt": now - 1000,
                }
            },
        }
        state_file.write_text(json.dumps(state))

        event = _event("mcp__my-server__get_resource")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "probe_server") as mock_probe,
        ):
            handle_pretool(event)
        mock_probe.assert_not_called()

    def test_unhealthy_within_backoff_blocks(self, tmp_path):
        """Unhealthy server within backoff window exits 2."""
        state_file = tmp_path / "health.json"
        now = _now_ms()
        state = {
            "version": 1,
            "servers": {
                "my-server": {
                    "status": "unhealthy",
                    "failureCount": 1,
                    "lastError": "ECONNREFUSED",
                    "nextRetryAt": now + 20_000,  # 20 seconds in the future
                }
            },
        }
        state_file.write_text(json.dumps(state))

        event = _event("mcp__my-server__get_resource")
        with patch.object(mod, "STATE_FILE", state_file):
            try:
                handle_pretool(event)
                raise AssertionError("Should have raised SystemExit(2)")
            except SystemExit as e:
                assert e.code == 2

    def test_unhealthy_within_backoff_fail_open_passes(self, tmp_path):
        """Unhealthy server within backoff window passes when fail-open=1."""
        state_file = tmp_path / "health.json"
        now = _now_ms()
        state = {
            "version": 1,
            "servers": {
                "my-server": {
                    "status": "unhealthy",
                    "failureCount": 1,
                    "lastError": "ECONNREFUSED",
                    "nextRetryAt": now + 20_000,
                }
            },
        }
        state_file.write_text(json.dumps(state))

        event = _event("mcp__my-server__get_resource")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.dict(os.environ, {"MCP_HEALTH_FAIL_OPEN": "1"}),
        ):
            handle_pretool(event)  # Must not raise

    def test_unhealthy_past_retry_at_reprobes(self, tmp_path):
        """Unhealthy server past nextRetryAt triggers re-probe."""
        state_file = tmp_path / "health.json"
        now = _now_ms()
        state = {
            "version": 1,
            "servers": {
                "my-server": {
                    "status": "unhealthy",
                    "failureCount": 1,
                    "lastError": "old error",
                    "nextRetryAt": now - 5_000,  # 5 seconds in the past
                }
            },
        }
        state_file.write_text(json.dumps(state))

        event = _event("mcp__my-server__get_resource")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "_discover_mcp_config", return_value=None),
        ):
            # No config = fail-open (healthy)
            handle_pretool(event)  # Should pass

        # State should have been updated to healthy
        loaded = json.loads(state_file.read_text())
        assert loaded["servers"]["my-server"]["status"] == "healthy"

    def test_probe_fail_marks_unhealthy_and_blocks(self, tmp_path):
        """A fresh server that fails probe is marked unhealthy and blocks."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        event = _event("mcp__bad-server__tool")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "_discover_mcp_config", return_value={"url": "http://localhost:9999"}),
            patch.object(mod, "probe_server", return_value=(False, "connection refused")),
            patch.object(mod, "_attempt_reconnect", return_value=False),
        ):
            try:
                handle_pretool(event)
                raise AssertionError("Should have raised SystemExit(2)")
            except SystemExit as e:
                assert e.code == 2

        # State should be unhealthy
        loaded = json.loads(state_file.read_text())
        assert loaded["servers"]["bad-server"]["status"] == "unhealthy"

    def test_probe_fail_fail_open_passes(self, tmp_path):
        """Probe failure with MCP_HEALTH_FAIL_OPEN=1 passes instead of blocking."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        event = _event("mcp__bad-server__tool")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "_discover_mcp_config", return_value={"url": "http://localhost:9999"}),
            patch.object(mod, "probe_server", return_value=(False, "connection refused")),
            patch.object(mod, "_attempt_reconnect", return_value=False),
            patch.dict(os.environ, {"MCP_HEALTH_FAIL_OPEN": "1"}),
        ):
            handle_pretool(event)  # Must not raise

    def test_bypass_env_skips_all_checks(self, tmp_path):
        """MCP_HEALTH_CHECK_BYPASS=1 causes main() to return immediately."""
        state_file = tmp_path / "health.json"
        now = _now_ms()
        state = {
            "version": 1,
            "servers": {
                "my-server": {
                    "status": "unhealthy",
                    "failureCount": 5,
                    "lastError": "err",
                    "nextRetryAt": now + 999_000,
                }
            },
        }
        state_file.write_text(json.dumps(state))

        # Simulate main() with bypass — call main directly via module
        stdin_data = json.dumps({"tool_name": "mcp__my-server__tool"})
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.dict(os.environ, {"MCP_HEALTH_CHECK_BYPASS": "1", "CLAUDE_HOOK_EVENT_NAME": "PreToolUse"}),
            patch.object(mod, "read_stdin", return_value=stdin_data),
        ):
            mod.main()  # Must not raise

    def test_expired_healthy_cache_reprobes(self, tmp_path):
        """Healthy entry whose TTL has expired triggers a new probe."""
        state_file = tmp_path / "health.json"
        now = _now_ms()
        state = {
            "version": 1,
            "servers": {
                "my-server": {
                    "status": "healthy",
                    "expiresAt": now - 1000,  # Expired 1 second ago
                }
            },
        }
        state_file.write_text(json.dumps(state))

        event = _event("mcp__my-server__tool")
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "_discover_mcp_config", return_value=None),
        ):
            handle_pretool(event)  # Should probe and pass (no config = fail-open)


# ---------------------------------------------------------------------------
# Tier 6: PostToolUseFailure Handler
# ---------------------------------------------------------------------------


class TestHandlePostToolFailure:
    """Tests for the PostToolUseFailure path."""

    def test_non_mcp_tool_does_nothing(self, tmp_path):
        """Non-MCP tool failures don't touch state."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        event = _event("Bash", tool_response="connection failed badly")
        with patch.object(mod, "STATE_FILE", state_file):
            handle_posttool_failure(event)

        loaded = json.loads(state_file.read_text())
        assert loaded["servers"] == {}

    def test_mcp_tool_with_matching_pattern_marks_unhealthy(self, tmp_path):
        """MCP tool failure with ECONNREFUSED marks server unhealthy."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        event = _event(
            "mcp__my-server__tool",
            tool_response="ECONNREFUSED 127.0.0.1:8080",
        )
        with patch.object(mod, "STATE_FILE", state_file):
            handle_posttool_failure(event)

        loaded = json.loads(state_file.read_text())
        assert loaded["servers"]["my-server"]["status"] == "unhealthy"

    def test_mcp_tool_with_no_pattern_does_nothing(self, tmp_path):
        """MCP tool failure with unknown error — no state change."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        event = _event("mcp__my-server__tool", tool_response="resource not found at path /x")
        with patch.object(mod, "STATE_FILE", state_file):
            handle_posttool_failure(event)

        loaded = json.loads(state_file.read_text())
        assert loaded["servers"] == {}

    def test_posttool_always_exits_0(self, tmp_path):
        """PostToolUseFailure handler never calls sys.exit(2)."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        # Use a pattern that WILL match — should still exit 0 (no block)
        event = _event("mcp__my-server__tool", tool_response="503 service unavailable")
        with patch.object(mod, "STATE_FILE", state_file):
            handle_posttool_failure(event)  # Must not raise SystemExit

    def test_failure_text_extracted_from_tool_response(self, tmp_path):
        """Failure text is extracted from tool_response field."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        event = {
            "tool_name": "mcp__srv__action",
            "tool_response": {"output": "429 rate limit", "error": ""},
        }
        with patch.object(mod, "STATE_FILE", state_file):
            handle_posttool_failure(event)

        loaded = json.loads(state_file.read_text())
        assert loaded["servers"]["srv"]["status"] == "unhealthy"

    def test_main_dispatches_posttool_failure_event(self, tmp_path):
        """main() routes to PostToolUseFailure handler when event name matches."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"version": 1, "servers": {}}))

        stdin_data = json.dumps({"tool_name": "mcp__srv__tool", "tool_response": "ECONNREFUSED"})
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.dict(
                os.environ,
                {
                    "CLAUDE_HOOK_EVENT_NAME": "PostToolUseFailure",
                    "MCP_HEALTH_CHECK_BYPASS": "",
                },
            ),
            patch.object(mod, "read_stdin", return_value=stdin_data),
        ):
            mod.main()

        loaded = json.loads(state_file.read_text())
        assert loaded["servers"]["srv"]["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# Tier 7: Fail-Open Guarantees
# ---------------------------------------------------------------------------


class TestFailOpen:
    """Ensure the hook never exits 2 due to unexpected errors."""

    def test_empty_stdin_exits_0(self):
        """Empty stdin produces exit 0."""
        with patch.object(mod, "read_stdin", return_value=""):
            mod.main()  # Must not raise

    def test_non_json_stdin_exits_0(self):
        """Non-JSON stdin produces exit 0."""
        with patch.object(mod, "read_stdin", return_value="not json {{"):
            mod.main()  # Must not raise

    def test_empty_json_object_exits_0(self):
        """Minimal '{}' stdin — non-MCP tool, exits 0."""
        with patch.object(mod, "read_stdin", return_value="{}"):
            mod.main()  # Must not raise

    def test_exception_in_main_exits_0(self):
        """Any unexpected exception escaping main() is caught by __main__ guard (exit 0)."""
        # The outer try/except in the __main__ block catches exceptions from main()
        # and calls sys.exit(0). Simulate that behavior directly:
        with patch.object(mod, "read_stdin", side_effect=RuntimeError("unexpected")):
            try:
                try:
                    mod.main()
                except SystemExit:
                    raise
                except Exception:
                    sys.exit(0)
            except SystemExit as e:
                assert e.code == 0

    def test_corrupt_state_never_blocks(self, tmp_path):
        """Hook fails open when state file is corrupt, regardless of content."""
        state_file = tmp_path / "health.json"
        state_file.write_text("{corrupt")

        stdin_data = json.dumps({"tool_name": "mcp__srv__tool"})
        with (
            patch.object(mod, "STATE_FILE", state_file),
            patch.object(mod, "_discover_mcp_config", return_value=None),
            patch.dict(os.environ, {"CLAUDE_HOOK_EVENT_NAME": "PreToolUse", "MCP_HEALTH_CHECK_BYPASS": ""}),
            patch.object(mod, "read_stdin", return_value=stdin_data),
        ):
            mod.main()  # Must not raise SystemExit(2)
