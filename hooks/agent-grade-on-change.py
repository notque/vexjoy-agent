#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Claude Code hook: Grade agents when they are modified or created.

This hook runs as a PostToolUse hook after Edit/Write operations on agent files.
It automatically grades the agent using the eval harness and warns if quality drops.

Event: PostToolUse (Edit, Write)
Filters: agents/*.md files only
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin


def is_agent_file(file_path: str) -> bool:
    """Check if a file path is an agent markdown file."""
    path = Path(file_path)
    return path.suffix == ".md" and "agents" in path.parts and path.name != "INDEX.md" and path.name != "README.md"


def extract_file_path_from_tool_input(tool_input: str) -> str | None:
    """Extract file_path from tool input JSON."""
    try:
        data = json.loads(tool_input)
        return data.get("file_path")
    except (json.JSONDecodeError, TypeError):
        return None


def grade_agent(agent_path: str) -> tuple[dict | None, str | None]:
    """Run the eval harness to grade an agent.

    Returns:
        Tuple of (result_dict, error_message). If grading succeeds, error is None.
    """
    harness_path = Path(__file__).parent.parent / "evals" / "harness.py"

    if not harness_path.exists():
        return None, f"Harness not found at {harness_path}"

    try:
        result = subprocess.run(
            ["python3", str(harness_path), "grade-agent", agent_path, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout), None
        else:
            return None, f"Harness failed: {result.stderr[:200] if result.stderr else 'no output'}"
    except subprocess.TimeoutExpired:
        return None, "Grading timed out after 5s"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON from harness: {e}"
    except FileNotFoundError:
        return None, "python3 not found"


def main():
    """Main hook entry point."""
    # Read hook input - try stdin first, then fall back to temp file
    hook_input = None

    # Try reading from stdin with timeout protection
    try:
        if not sys.stdin.isatty():
            raw = read_stdin(timeout=2)
            if raw:
                hook_input = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to temp file (used by other hooks in the chain)
    if not hook_input:
        try:
            with open("/tmp/claude_hook_stdin.json") as f:
                hook_input = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

    if not hook_input:
        return

    # tool_name filter removed — matcher "Write|Edit" in settings.json prevents
    # this hook from spawning for non-matching tools.

    # Extract file path from tool input
    tool_input_data = hook_input.get("tool_input", {})
    if isinstance(tool_input_data, str):
        file_path = extract_file_path_from_tool_input(tool_input_data)
    else:
        file_path = tool_input_data.get("file_path")

    if not file_path or not is_agent_file(file_path):
        return

    # Check if the file exists (might be a new file)
    if not Path(file_path).exists():
        return

    # Grade the agent
    grade_result, error = grade_agent(file_path)

    if error:
        print(json.dumps({"message": f"[agent-grade] {Path(file_path).name}: grading failed - {error}"}))
        return

    if not grade_result:
        return

    score = grade_result.get("overall_score", 0)
    grade = grade_result.get("grade", "?")
    issues = grade_result.get("issues", [])

    # Output feedback
    output = {"message": f"[agent-grade] {Path(file_path).name}: {score}/100 ({grade})"}

    # Warn if grade is below B
    if score < 80:
        output["warning"] = True
        output["message"] += f"\n  Issues: {', '.join(issues[:3])}" if issues else ""
        output["message"] += "\n  Consider adding missing sections to improve quality."

    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[agent-grade] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
