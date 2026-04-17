"""
Shared utilities for Claude Code hooks.

Provides common functionality used across multiple hooks:
- JSON output formatting with proper escaping
- User message support
- Cascading fallback patterns
- Error handling with degraded modes

Inspired by shared/lib patterns.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


# =============================================================================
# JSON Utilities
# =============================================================================


def json_escape(text: str) -> str:
    """
    Escape a string for safe JSON embedding.

    RFC 8259 compliant - handles all control characters.

    Args:
        text: The string to escape

    Returns:
        JSON-safe escaped string (without surrounding quotes)
    """
    # json.dumps adds quotes, we strip them
    return json.dumps(text)[1:-1]


# =============================================================================
# Hook Output Formatting
# =============================================================================


@dataclass
class HookOutput:
    """
    Structured hook output with user message support.

    Attributes:
        event_name: The hook event name (SessionStart, UserPromptSubmit, etc.)
        additional_context: System context for Claude (not shown to user)
        user_message: User-facing message that MUST be shown verbatim
        metadata: Additional key-value pairs for the output
    """

    event_name: str
    additional_context: Optional[str] = None
    user_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Events that support hookSpecificOutput per Claude Code's schema.
    # All other events must emit top-level fields or an empty object.
    # Source: https://code.claude.com/docs/en/hooks (2026-03-26)
    _HOOK_SPECIFIC_OUTPUT_EVENTS = frozenset(
        {
            "PreToolUse",
            "PostToolUse",
            "PostToolUseFailure",
            "UserPromptSubmit",
            "SessionStart",
            "SubagentStart",
            "Notification",
            "CwdChanged",
            "FileChanged",
            "Elicitation",
            "ElicitationResult",
            "WorktreeCreate",
            "PermissionRequest",
        }
    )

    def to_json(self) -> str:
        """Convert to JSON string for hook output.

        Events in ``_HOOK_SPECIFIC_OUTPUT_EVENTS`` support the
        ``hookSpecificOutput`` wrapper (PreToolUse, PostToolUse,
        PostToolUseFailure, UserPromptSubmit, SessionStart, SubagentStart,
        Notification, CwdChanged, FileChanged, Elicitation,
        ElicitationResult, WorktreeCreate, PermissionRequest).

        All other events (Stop, SubagentStop, StopFailure, PreCompact,
        PostCompact, TaskCreated, TaskCompleted, TeammateIdle, ConfigChange,
        WorktreeRemove, SessionEnd, InstructionsLoaded) must emit top-level
        fields or ``{}`` — wrapping them causes a JSON validation error in
        Claude Code.
        """
        if self.event_name in self._HOOK_SPECIFIC_OUTPUT_EVENTS:
            inner: dict[str, Any] = {"hookEventName": self.event_name}

            if self.user_message:
                inner["userMessage"] = self.user_message

            if self.additional_context:
                inner["additionalContext"] = self.additional_context

            inner.update(self.metadata)
            return json.dumps({"hookSpecificOutput": inner})

        # Non-supported events: emit top-level fields or empty object.
        output: dict[str, Any] = {}
        output.update(self.metadata)
        return json.dumps(output)

    def print_and_exit(self, exit_code: int = 0) -> None:
        """Print JSON output and exit."""
        print(self.to_json())
        sys.exit(exit_code)


def empty_output(event_name: str) -> HookOutput:
    """Create an empty hook output (no injection)."""
    return HookOutput(event_name=event_name)


def context_output(event_name: str, context: str) -> HookOutput:
    """Create hook output with additional context."""
    return HookOutput(event_name=event_name, additional_context=context)


def user_message_output(event_name: str, message: str, context: Optional[str] = None) -> HookOutput:
    """
    Create hook output with a mandatory user message.

    User messages MUST be displayed verbatim by Claude at the start
    of the response. They are used for critical notifications,
    warnings, and action-required messages.

    Args:
        event_name: Hook event name
        message: User-facing message (displayed verbatim)
        context: Optional additional context (not shown to user)

    Returns:
        HookOutput with user_message set
    """
    return HookOutput(event_name=event_name, user_message=message, additional_context=context)


# =============================================================================
# Cascading Fallback Pattern
# =============================================================================


def with_fallback(
    primary: Callable[[], T],
    fallback: Callable[[], T],
    error_message: Optional[str] = None,
) -> T:
    """
    Execute primary function, fall back on failure.

    Args:
        primary: Primary function to try
        fallback: Fallback function if primary fails
        error_message: Optional message to log on fallback

    Returns:
        Result from primary or fallback
    """
    try:
        return primary()
    except Exception as e:
        if error_message:
            print(f"Warning: {error_message}: {e}", file=sys.stderr)
        return fallback()


def cascading_fallback(
    *funcs: Callable[[], T],
    default: T,
    error_prefix: str = "Fallback",
) -> T:
    """
    Try multiple functions in sequence, return first success.

    This implements a cascading fallback architecture:
    Priority: func1 → func2 → ... → default

    Args:
        *funcs: Functions to try in order
        default: Value to return if all fail
        error_prefix: Prefix for error messages

    Returns:
        First successful result or default

    Example:
        result = cascading_fallback(
            try_with_yaml,
            try_with_regex,
            try_with_basic,
            default="",
            error_prefix="YAML parsing"
        )
    """
    for i, func in enumerate(funcs):
        try:
            return func()
        except Exception as e:
            print(f"Warning: {error_prefix} attempt {i + 1} failed: {e}", file=sys.stderr)

    return default


# =============================================================================
# Environment Utilities
# =============================================================================


def get_project_dir() -> Path:
    """Get the Claude project directory from environment."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def get_session_id() -> str:
    """Get session ID from environment or generate a unique fallback.

    Falls back to PPID + timestamp hash if CLAUDE_SESSION_ID is not set.
    This handles container scenarios where PPID might be 1 (init).
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID")
    if session_id:
        return session_id

    # Generate more unique fallback: PPID + process start time hash
    import hashlib
    import time

    ppid = os.getppid()
    # Use current time truncated to session start (rough approximation)
    time_component = str(int(time.time() // 3600))  # Hour-based bucket
    unique_str = f"{ppid}-{time_component}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:12]


def get_state_file(prefix: str) -> Path:
    """
    Get a session-specific state file path.

    Args:
        prefix: Prefix for the state file name

    Returns:
        Path to state file in /tmp
    """
    session_id = get_session_id()
    return Path(f"/tmp/claude-{prefix}-{session_id}.state")


# =============================================================================
# File Discovery
# =============================================================================


# Common directories to exclude when scanning
EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def discover_files(
    root: Path,
    pattern: str,
    exclude_dirs: Optional[set[str]] = None,
) -> list[Path]:
    """
    Discover files matching a pattern, excluding common directories.

    Args:
        root: Root directory to search
        pattern: Glob pattern (e.g., "CLAUDE.md", "*.py")
        exclude_dirs: Additional directories to exclude

    Returns:
        List of matching file paths
    """
    excludes = EXCLUDE_DIRS | (exclude_dirs or set())
    found = []

    try:
        for path in root.rglob(pattern):
            # Skip if in excluded directory
            if any(part in excludes for part in path.parts):
                continue
            # Skip symlinks for security
            if path.is_symlink():
                continue
            if path.is_file():
                found.append(path)
    except OSError:
        # Best-effort discovery: if we hit a filesystem error while walking
        # (e.g., permission denied), return any files found so far rather
        # than failing the entire hook.
        pass

    return found


# =============================================================================
# YAML Frontmatter Parsing (with fallback)
# =============================================================================

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def parse_frontmatter(content: str) -> Optional[dict[str, Any]]:
    """
    Parse YAML frontmatter from markdown content.

    Implements cascading fallback:
    1. Try PyYAML if available
    2. Fall back to regex parser

    Args:
        content: Markdown file content

    Returns:
        Parsed frontmatter dict or None
    """
    # Check for frontmatter markers
    if not content.startswith("---"):
        return None

    # Find end of frontmatter
    end_match = content.find("\n---", 3)
    if end_match == -1:
        return None

    frontmatter = content[4:end_match].strip()

    # Try YAML parser first
    if YAML_AVAILABLE:
        try:
            return yaml.safe_load(frontmatter)
        except yaml.YAMLError:
            pass

    # Fallback: simple regex parser for common fields
    return _parse_frontmatter_regex(frontmatter)


def _parse_frontmatter_regex(content: str) -> dict[str, Any]:
    """Simple regex-based frontmatter parser for common fields."""
    import re

    result: dict[str, Any] = {}

    # Match simple key: value patterns
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(r"^(\w+):\s*(.+)$", line)
        if match:
            key, value = match.groups()
            # Strip quotes if present
            value = value.strip().strip("\"'")
            result[key] = value

    return result


# =============================================================================
# Logging Utilities
# =============================================================================


def log_info(message: str) -> None:
    """Log info message to stderr (won't interfere with JSON output)."""
    print(f"[info] {message}", file=sys.stderr)


def log_warning(message: str) -> None:
    """Log warning message to stderr."""
    print(f"[warn] {message}", file=sys.stderr)


def log_error(message: str) -> None:
    """Log error message to stderr."""
    print(f"[error] {message}", file=sys.stderr)


def deny_tool_use(event_name: str, reason: str) -> None:
    """Output a structured deny decision for PreToolUse/SubagentStop hooks.

    Public utility for simpler hooks that only need a deny decision without
    the governance recording and stderr logging that pretool-unified-gate's
    ``_block()`` provides.

    Prints the JSON permissionDecision format that Claude Code expects to stdout,
    then returns. The caller is responsible for calling sys.exit(0) afterwards.

    The reason is surfaced to the model so it can adapt its approach.

    Args:
        event_name: Hook event name (e.g. "PreToolUse", "SubagentStop").
        reason: Human-readable explanation shown to the model.
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))
