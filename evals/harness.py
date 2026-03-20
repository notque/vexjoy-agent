#!/usr/bin/env python3
"""
Eval Harness

Runs evaluation tasks against Claude Code agents and grades the results.
Uses the claude CLI to execute agents in isolated environments.

Security Note:
    Task YAML files are treated as trusted input. They may contain shell
    commands that execute with full privileges. Only run tasks from trusted
    sources.

Usage:
    python harness.py run tasks/routing/task-001.yaml
    python harness.py run tasks/routing/task-001.yaml --trials 3
    python harness.py suite tasks/routing/
    python harness.py calibrate string_contains
    python harness.py calibrate --all
"""

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import yaml

# Configure logging for the harness
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Security Helpers
# ============================================================================


def safe_path(work_dir: Path, relative_path: str) -> Path:
    """
    Safely resolve a path within work_dir, preventing path traversal attacks.

    Args:
        work_dir: The base working directory
        relative_path: A relative path that should stay within work_dir

    Returns:
        Resolved absolute path guaranteed to be within work_dir

    Raises:
        ValueError: If the path would escape work_dir
    """
    work_dir = work_dir.resolve()
    resolved = (work_dir / relative_path).resolve()
    if not str(resolved).startswith(str(work_dir)):
        raise ValueError(f"Path escapes work directory: {relative_path}")
    return resolved


def safe_regex_match(pattern: str, content: str, timeout_chars: int = 100000, multiline: bool = True) -> bool | None:
    """
    Execute regex match with protection against ReDoS attacks.

    Args:
        pattern: Regex pattern to match
        content: Content to search in
        timeout_chars: Maximum content length to search (prevents long-running matches)
        multiline: Whether to use MULTILINE mode (default: True) - ^ and $ match line boundaries

    Returns:
        True if pattern matches, False if not, None if content too long or pattern invalid
    """
    if len(content) > timeout_chars:
        logger.warning(f"Content too long for regex match: {len(content)} > {timeout_chars}")
        return None
    try:
        flags = re.MULTILINE if multiline else 0
        return re.search(pattern, content, flags) is not None
    except re.error as e:
        logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        return None


# ============================================================================
# Graders - Evaluate task outcomes
# ============================================================================


def grade_file_exists(transcript: str, env: dict, config: dict) -> dict:
    """
    Check if a file was created in the working directory.

    Config options:
        path: Path to the file relative to work_dir

    Returns:
        dict with passed (True if file exists), score (1.0 or 0.0), and details
    """
    try:
        path = safe_path(Path(env["work_dir"]), config["path"])
        exists = path.exists()
        return {
            "type": "file_exists",
            "passed": exists,
            "score": 1.0 if exists else 0.0,
            "details": f"File {'exists' if exists else 'not found'}: {config['path']}",
        }
    except ValueError as e:
        logger.error(f"Path traversal attempt in file_exists: {e}")
        return {
            "type": "file_exists",
            "passed": False,
            "score": 0.0,
            "details": f"Invalid path: {e}",
        }


def grade_string_contains(transcript: str, env: dict, config: dict) -> dict:
    """
    Check if target contains specified patterns.

    Config options:
        target: Where to search - "transcript" or "file:path/to/file"
        patterns: List of strings to search for
        match_all: If True (default), all patterns must match.
                   If False, any pattern matching passes.

    Returns:
        dict with passed, score (proportion matched if match_all, else 1.0/0.0),
        matched patterns list, and missing patterns list
    """
    target = config.get("target", "transcript")

    if target == "transcript":
        content = transcript
    elif target.startswith("file:"):
        try:
            file_path = safe_path(Path(env["work_dir"]), target[5:])
            if not file_path.exists():
                return {
                    "type": "string_contains",
                    "passed": False,
                    "score": 0.0,
                    "details": f"Target file not found: {target[5:]}",
                }
            content = file_path.read_text()
        except ValueError as e:
            logger.error(f"Path traversal attempt in string_contains: {e}")
            return {
                "type": "string_contains",
                "passed": False,
                "score": 0.0,
                "details": f"Invalid path: {e}",
            }
    else:
        content = transcript

    patterns = config.get("patterns", [])
    match_all = config.get("match_all", True)

    # Handle empty patterns case consistently
    if not patterns:
        return {
            "type": "string_contains",
            "passed": True,
            "score": 1.0,
            "details": "No patterns specified (auto-pass)",
            "matched": [],
            "missing": [],
        }

    matches = [p for p in patterns if p in content]
    if match_all:
        passed = len(matches) == len(patterns)
        score = len(matches) / len(patterns)
    else:
        passed = len(matches) > 0
        score = 1.0 if passed else 0.0

    return {
        "type": "string_contains",
        "passed": passed,
        "score": score,
        "details": f"Matched {len(matches)}/{len(patterns)} patterns",
        "matched": matches,
        "missing": [p for p in patterns if p not in matches],
    }


def grade_regex_match(transcript: str, env: dict, config: dict) -> dict:
    """
    Check if target matches a regex pattern.

    Config options:
        target: Where to search - "transcript" or "file:path/to/file"
        pattern: Regex pattern to match (uses re.MULTILINE flag)

    Returns:
        dict with passed (True if pattern matches), score (1.0 or 0.0), and details
    """
    target = config.get("target", "transcript")

    if target == "transcript":
        content = transcript
    elif target.startswith("file:"):
        try:
            file_path = safe_path(Path(env["work_dir"]), target[5:])
            if not file_path.exists():
                return {
                    "type": "regex_match",
                    "passed": False,
                    "score": 0.0,
                    "details": f"Target file not found: {target[5:]}",
                }
            content = file_path.read_text()
        except ValueError as e:
            logger.error(f"Path traversal attempt in regex_match: {e}")
            return {
                "type": "regex_match",
                "passed": False,
                "score": 0.0,
                "details": f"Invalid path: {e}",
            }
    else:
        content = transcript

    pattern = config.get("pattern", "")

    # Use safe_regex_match for ReDoS protection
    match_result = safe_regex_match(pattern, content)
    if match_result is None:
        return {
            "type": "regex_match",
            "passed": False,
            "score": 0.0,
            "details": f"Regex match failed (invalid pattern or content too long): {pattern[:50]}",
        }

    return {
        "type": "regex_match",
        "passed": match_result,
        "score": 1.0 if match_result else 0.0,
        "details": f"Pattern {'matched' if match_result else 'not found'}: {pattern[:50]}...",
    }


def grade_tests_pass(transcript: str, env: dict, config: dict) -> dict:
    """
    Run a test command and check if it passes.

    Config options:
        command: Shell command to execute (e.g., "pytest tests/")
        working_dir: Subdirectory to run command in (relative to work_dir)
        timeout: Command timeout in seconds (default: 60)

    Security Note:
        This grader uses shell=True which allows arbitrary command execution.
        Task YAML files are treated as trusted input (see module docstring).
        Only run eval tasks from trusted sources.

    Returns:
        dict with passed (True if exit code 0), score (1.0 or 0.0),
        truncated stdout/stderr (first 500 chars each)
    """
    command = config.get("command", "")
    timeout = config.get("timeout", 60)

    try:
        working_dir = safe_path(Path(env["work_dir"]), config.get("working_dir", "."))
    except ValueError as e:
        logger.error(f"Path traversal attempt in tests_pass: {e}")
        return {
            "type": "tests_pass",
            "passed": False,
            "score": 0.0,
            "details": f"Invalid working_dir: {e}",
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        passed = result.returncode == 0
        return {
            "type": "tests_pass",
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "details": f"Exit code: {result.returncode}",
            "stdout": result.stdout[:500] if result.stdout else "",
            "stderr": result.stderr[:500] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        logger.warning(f"Test command timed out after {timeout}s: {command[:50]}")
        return {
            "type": "tests_pass",
            "passed": False,
            "score": 0.0,
            "details": f"Test command timed out after {timeout}s",
        }
    except OSError as e:
        # OSError covers permission denied, command not found, etc.
        logger.error(f"OS error running test command: {e}")
        return {
            "type": "tests_pass",
            "passed": False,
            "score": 0.0,
            "details": f"Error running tests: {e}",
        }


def grade_yaml_valid(transcript: str, env: dict, config: dict) -> dict:
    """
    Check if a YAML file is valid and has required fields.

    Config options:
        path: Path to the YAML file relative to work_dir
        required_fields: List of field names that must be present in the YAML

    Supports YAML frontmatter in markdown files (content between --- delimiters).

    Returns:
        dict with passed, score (proportion of required fields present),
        and details about validation result
    """
    try:
        file_path = safe_path(Path(env["work_dir"]), config["path"])
    except ValueError as e:
        logger.error(f"Path traversal attempt in yaml_valid: {e}")
        return {
            "type": "yaml_valid",
            "passed": False,
            "score": 0.0,
            "details": f"Invalid path: {e}",
        }

    if not file_path.exists():
        return {
            "type": "yaml_valid",
            "passed": False,
            "score": 0.0,
            "details": f"File not found: {config['path']}",
        }

    try:
        with open(file_path) as f:
            content = f.read()

        # Handle YAML frontmatter in markdown files
        if file_path.suffix == ".md":
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    data = yaml.safe_load(parts[1])
                else:
                    return {
                        "type": "yaml_valid",
                        "passed": False,
                        "score": 0.0,
                        "details": "Invalid frontmatter format",
                    }
            else:
                return {
                    "type": "yaml_valid",
                    "passed": False,
                    "score": 0.0,
                    "details": "No YAML frontmatter found",
                }
        else:
            data = yaml.safe_load(content)

        if not isinstance(data, dict):
            return {
                "type": "yaml_valid",
                "passed": False,
                "score": 0.5,
                "details": "YAML is valid but not a dictionary",
            }

        # Check required fields
        required = config.get("required_fields", [])
        missing = [f for f in required if f not in data]

        if missing:
            return {
                "type": "yaml_valid",
                "passed": False,
                "score": (len(required) - len(missing)) / len(required),
                "details": f"Missing required fields: {missing}",
            }

        return {
            "type": "yaml_valid",
            "passed": True,
            "score": 1.0,
            "details": "Valid YAML with all required fields",
        }

    except yaml.YAMLError as e:
        return {
            "type": "yaml_valid",
            "passed": False,
            "score": 0.0,
            "details": f"Invalid YAML: {e}",
        }


def grade_llm_rubric(transcript: str, env: dict, config: dict) -> dict:
    """
    Use LLM-as-judge to evaluate against a rubric.

    Config options:
        rubric: Path to rubric file or inline rubric text
        assertions: List of specific assertions to check

    Calls the claude CLI to evaluate the transcript against the rubric.
    The LLM grades each assertion and returns an overall pass/fail with score.

    Returns:
        dict with passed, score (0.0-1.0), summary, and per-assertion results
    """
    rubric_path = config.get("rubric")
    assertions = config.get("assertions", [])

    # Build the rubric content
    rubric_content = ""
    if rubric_path:
        rubric_file = Path(__file__).parent / rubric_path
        if rubric_file.exists():
            rubric_content = rubric_file.read_text()

    # Build grading prompt
    prompt = f"""You are an evaluator grading an AI agent's output against specific criteria.

## Transcript to Evaluate
```
{transcript[:8000]}
```

## Rubric
{rubric_content}

## Assertions to Check
{chr(10).join(f"- {a}" for a in assertions)}

## Your Task
Evaluate each assertion as PASS or FAIL. Be strict but fair.

Output your evaluation as JSON:
{{
  "overall_pass": true/false,
  "score": 0.0-1.0,
  "assertions": [
    {{"assertion": "...", "passed": true/false, "reasoning": "..."}}
  ],
  "summary": "Brief overall assessment"
}}

Respond with ONLY the JSON, no other text.
"""

    try:
        # Call claude CLI for LLM grading
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return {
                "type": "llm_rubric",
                "passed": False,
                "score": 0.0,
                "details": f"LLM grading failed: {result.stderr[:200]}",
            }

        # Parse JSON response
        response = result.stdout.strip()
        # Handle potential markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        evaluation = json.loads(response)

        return {
            "type": "llm_rubric",
            "passed": evaluation.get("overall_pass", False),
            "score": evaluation.get("score", 0.0),
            "details": evaluation.get("summary", ""),
            "assertions": evaluation.get("assertions", []),
        }

    except subprocess.TimeoutExpired:
        return {
            "type": "llm_rubric",
            "passed": False,
            "score": 0.0,
            "details": "LLM grading timed out",
        }
    except json.JSONDecodeError as e:
        return {
            "type": "llm_rubric",
            "passed": False,
            "score": 0.0,
            "details": f"Failed to parse LLM response: {e}",
        }
    except Exception as e:
        return {
            "type": "llm_rubric",
            "passed": False,
            "score": 0.0,
            "details": f"LLM grading error: {e}",
        }


def grade_tool_calls(transcript: str, env: dict, config: dict) -> dict:
    """
    Verify which tools were called and with what parameters.

    This grader analyzes the raw JSON transcript to verify tool usage patterns.
    Essential for agentic evals where the action matters as much as the output.

    Config options:
        required_tools: List of tool names that MUST be called
        forbidden_tools: List of tool names that MUST NOT be called
        tool_params: Dict mapping tool names to required parameter patterns
        min_tool_calls: Minimum number of tool calls expected
        max_tool_calls: Maximum number of tool calls allowed

    Example config:
        required_tools: ["Read", "Edit"]
        forbidden_tools: ["Bash"]
        tool_params:
          Edit:
            file_path: ".*\\.py$"  # Regex pattern
        min_tool_calls: 2
    """
    required_tools = config.get("required_tools", [])
    forbidden_tools = config.get("forbidden_tools", [])
    tool_params = config.get("tool_params", {})
    min_calls = config.get("min_tool_calls", 0)
    max_calls = config.get("max_tool_calls", float("inf"))

    # Parse tool calls from the raw JSON transcript stored in env
    raw_json = env.get("raw_json_output", "")
    tool_calls = []

    try:
        # Try different JSON formats
        items = []
        raw_stripped = raw_json.strip()

        if raw_stripped.startswith("["):
            # JSON array
            items = json.loads(raw_stripped)
        elif raw_stripped.startswith("{"):
            # Could be single object or newline-delimited JSON
            try:
                # Try as single object first (handles multi-line JSON objects)
                item = json.loads(raw_stripped)
                items = [item]
            except json.JSONDecodeError:
                # Fall back to newline-delimited JSON
                items = [json.loads(line) for line in raw_stripped.split("\n") if line.strip()]

        for item in items:
            if item.get("type") == "assistant":
                message = item.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "name": block.get("name", ""),
                                "input": block.get("input", {}),
                            }
                        )
    except (json.JSONDecodeError, TypeError, KeyError):
        # Fallback: try to find tool patterns in transcript text
        tool_pattern = re.compile(r'<invoke name="(\w+)"')
        matches = tool_pattern.findall(transcript)
        tool_calls = [{"name": m, "input": {}} for m in matches]

    # Check results
    called_tools = {tc["name"] for tc in tool_calls}
    num_calls = len(tool_calls)

    issues = []
    score_deductions = 0.0

    # Check required tools
    missing_required = [t for t in required_tools if t not in called_tools]
    if missing_required:
        issues.append(f"Missing required tools: {missing_required}")
        score_deductions += 0.3 * (len(missing_required) / max(len(required_tools), 1))

    # Check forbidden tools
    called_forbidden = [t for t in forbidden_tools if t in called_tools]
    if called_forbidden:
        issues.append(f"Called forbidden tools: {called_forbidden}")
        score_deductions += 0.4

    # Check tool count bounds
    if num_calls < min_calls:
        issues.append(f"Too few tool calls: {num_calls} < {min_calls}")
        score_deductions += 0.2
    if num_calls > max_calls:
        issues.append(f"Too many tool calls: {num_calls} > {max_calls}")
        score_deductions += 0.1

    # Check tool parameters
    for tool_name, param_patterns in tool_params.items():
        matching_calls = [tc for tc in tool_calls if tc["name"] == tool_name]
        if not matching_calls:
            continue

        for param_name, pattern in param_patterns.items():
            for tc in matching_calls:
                param_value = tc["input"].get(param_name, "")
                if isinstance(param_value, str) and not re.search(pattern, param_value):
                    issues.append(f"{tool_name}.{param_name} doesn't match pattern: {pattern}")
                    score_deductions += 0.1

    score = max(0.0, 1.0 - score_deductions)
    passed = len(issues) == 0

    return {
        "type": "tool_calls",
        "passed": passed,
        "score": score,
        "details": "; ".join(issues) if issues else f"All tool call checks passed ({num_calls} calls)",
        "tool_calls_found": [tc["name"] for tc in tool_calls],
        "num_calls": num_calls,
        "issues": issues,
    }


def grade_state_check(transcript: str, env: dict, config: dict) -> dict:
    """
    Verify the environment state after agent execution.

    This grader inspects the filesystem or other state to verify the agent's
    actions produced the expected results. Essential for verifying that an
    agent actually accomplished its task, not just claimed to.

    Config options:
        files_exist: List of files that must exist
        files_not_exist: List of files that must NOT exist
        file_contains: Dict mapping file paths to required content patterns
        file_not_contains: Dict mapping file paths to forbidden content patterns
        git_status: Expected git status patterns
        env_vars: Environment variables to check

    Example config:
        files_exist:
          - "src/new_module.py"
          - "tests/test_new_module.py"
        file_contains:
          "src/new_module.py":
            - "def main"
            - "import logging"
        files_not_exist:
          - "src/old_module.py"  # Should have been deleted
    """
    work_dir = Path(env["work_dir"])
    issues = []
    checks_passed = 0
    total_checks = 0

    # Check files that must exist
    files_exist = config.get("files_exist", [])
    for file_path in files_exist:
        total_checks += 1
        full_path = work_dir / file_path
        if full_path.exists():
            checks_passed += 1
        else:
            issues.append(f"File not found: {file_path}")

    # Check files that must NOT exist
    files_not_exist = config.get("files_not_exist", [])
    for file_path in files_not_exist:
        total_checks += 1
        full_path = work_dir / file_path
        if not full_path.exists():
            checks_passed += 1
        else:
            issues.append(f"File should not exist: {file_path}")

    # Check file contents
    file_contains = config.get("file_contains", {})
    for file_path, patterns in file_contains.items():
        full_path = work_dir / file_path
        if not full_path.exists():
            for pattern in patterns:
                total_checks += 1
                issues.append(f"Cannot check pattern in missing file: {file_path}")
            continue

        content = full_path.read_text()
        for pattern in patterns:
            total_checks += 1
            if re.search(pattern, content):
                checks_passed += 1
            else:
                issues.append(f"Pattern not found in {file_path}: {pattern[:50]}")

    # Check file contents that should NOT be present
    file_not_contains = config.get("file_not_contains", {})
    for file_path, patterns in file_not_contains.items():
        full_path = work_dir / file_path
        if not full_path.exists():
            # File not existing means forbidden content can't be there
            for pattern in patterns:
                total_checks += 1
                checks_passed += 1
            continue

        content = full_path.read_text()
        for pattern in patterns:
            total_checks += 1
            if not re.search(pattern, content):
                checks_passed += 1
            else:
                issues.append(f"Forbidden pattern found in {file_path}: {pattern[:50]}")

    # Check git status if requested
    git_status = config.get("git_status", {})
    if git_status:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=10,
            )
            status_output = result.stdout

            for pattern in git_status.get("patterns", []):
                total_checks += 1
                if re.search(pattern, status_output):
                    checks_passed += 1
                else:
                    issues.append(f"Git status pattern not found: {pattern}")

        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            issues.append(f"Git status check failed: {e}")

    # Compute score
    if total_checks == 0:
        score = 1.0  # No checks configured
        passed = True
    else:
        score = checks_passed / total_checks
        passed = len(issues) == 0

    return {
        "type": "state_check",
        "passed": passed,
        "score": score,
        "details": "; ".join(issues) if issues else f"All {total_checks} state checks passed",
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "issues": issues,
    }


def grade_transcript_constraint(transcript: str, env: dict, config: dict) -> dict:
    """
    Verify transcript-level constraints (max turns, forbidden tools, etc.).

    This grader enforces behavioral constraints on the agent's execution,
    ensuring it operates within acceptable bounds.

    Config options:
        max_turns: Maximum number of conversational turns allowed
        max_tool_calls: Maximum number of tool invocations allowed
        max_tokens: Maximum tokens used (from env metrics)
        forbidden_patterns: Regex patterns that must NOT appear in transcript
        required_patterns: Regex patterns that MUST appear in transcript
        timeout_seconds: Execution should complete within this time

    Example config:
        max_turns: 5
        max_tool_calls: 10
        forbidden_patterns:
          - "I don't know"
          - "I cannot"
        required_patterns:
          - "completed successfully"
    """
    issues = []
    score_deductions = 0.0

    # Get metrics from env
    n_turns = env.get("n_turns", 0)
    n_tool_calls = env.get("n_tool_calls", 0)
    tokens_total = env.get("tokens_total", 0)
    elapsed_seconds = env.get("elapsed_seconds", 0)

    # Check max turns
    max_turns = config.get("max_turns")
    if max_turns is not None and n_turns > max_turns:
        issues.append(f"Too many turns: {n_turns} > {max_turns}")
        score_deductions += 0.3

    # Check max tool calls
    max_tool_calls = config.get("max_tool_calls")
    if max_tool_calls is not None and n_tool_calls > max_tool_calls:
        issues.append(f"Too many tool calls: {n_tool_calls} > {max_tool_calls}")
        score_deductions += 0.2

    # Check max tokens
    max_tokens = config.get("max_tokens")
    if max_tokens is not None and tokens_total > max_tokens:
        issues.append(f"Too many tokens: {tokens_total} > {max_tokens}")
        score_deductions += 0.2

    # Check timeout
    timeout_seconds = config.get("timeout_seconds")
    if timeout_seconds is not None and elapsed_seconds > timeout_seconds:
        issues.append(f"Exceeded timeout: {elapsed_seconds:.1f}s > {timeout_seconds}s")
        score_deductions += 0.2

    # Check forbidden patterns
    forbidden_patterns = config.get("forbidden_patterns", [])
    for pattern in forbidden_patterns:
        if re.search(pattern, transcript, re.IGNORECASE):
            issues.append(f"Forbidden pattern found: {pattern[:30]}")
            score_deductions += 0.15

    # Check required patterns
    required_patterns = config.get("required_patterns", [])
    for pattern in required_patterns:
        if not re.search(pattern, transcript, re.IGNORECASE):
            issues.append(f"Required pattern missing: {pattern[:30]}")
            score_deductions += 0.15

    score = max(0.0, 1.0 - score_deductions)
    passed = len(issues) == 0

    return {
        "type": "transcript_constraint",
        "passed": passed,
        "score": score,
        "details": "; ".join(issues) if issues else "All constraints satisfied",
        "metrics": {
            "n_turns": n_turns,
            "n_tool_calls": n_tool_calls,
            "tokens_total": tokens_total,
            "elapsed_seconds": elapsed_seconds,
        },
        "issues": issues,
    }


def grade_premature_action(transcript: str, env: dict, config: dict) -> dict:
    """
    Check if substantive tool calls occurred before the Skill tool was invoked.

    The ADR-008 principle: agents should load the appropriate skill before taking
    substantive actions (Write, Edit, Bash). Research tools (Read, Glob, Grep,
    TodoWrite) are allowed before the skill is loaded since they are planning/research.

    Config options:
        expected_skill: (optional) The skill name that should have been loaded.
                        If provided, the grader also verifies the Skill tool was
                        called with this specific skill.

    Parses the session output (JSON lines or raw text) for tool invocations,
    finds the first Skill tool invocation, and checks if any substantive tool
    calls (Write, Edit, Bash) precede it.

    Returns:
        dict with passed, score, details, and lists of premature/research tools found
    """
    expected_skill = config.get("expected_skill")

    # Research/planning tools that are allowed before skill loading
    RESEARCH_TOOLS = {"Read", "Glob", "Grep", "TodoWrite", "ToolSearch"}
    # Substantive tools that should NOT appear before the skill is loaded
    SUBSTANTIVE_TOOLS = {"Write", "Edit", "Bash"}

    # Parse tool calls from the raw JSON transcript stored in env
    raw_json = env.get("raw_json_output", "")
    tool_calls = []

    try:
        items = []
        raw_stripped = raw_json.strip()

        if raw_stripped.startswith("["):
            items = json.loads(raw_stripped)
        elif raw_stripped.startswith("{"):
            try:
                item = json.loads(raw_stripped)
                items = [item]
            except json.JSONDecodeError:
                items = [json.loads(line) for line in raw_stripped.split("\n") if line.strip()]

        for item in items:
            if item.get("type") == "assistant":
                message = item.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "name": block.get("name", ""),
                                "input": block.get("input", {}),
                            }
                        )
    except (json.JSONDecodeError, TypeError, KeyError):
        # Fallback: try to find tool patterns in transcript text
        tool_pattern = re.compile(r'<invoke name="(\w+)"')
        matches = tool_pattern.findall(transcript)
        tool_calls = [{"name": m, "input": {}} for m in matches]

    if not tool_calls:
        return {
            "type": "premature_action",
            "passed": False,
            "score": 0.0,
            "details": "No tool calls found in transcript",
            "premature_tools": [],
            "research_tools_before_skill": [],
            "skill_found": False,
        }

    # Walk through tool calls in order, looking for Skill invocation
    premature_tools = []
    research_tools_before_skill = []
    skill_index = None
    skill_name_used = None

    for i, tc in enumerate(tool_calls):
        name = tc["name"]

        if name == "Skill":
            skill_index = i
            skill_name_used = tc["input"].get("skill", "")
            break
        elif name in SUBSTANTIVE_TOOLS:
            premature_tools.append({"name": name, "index": i, "input_preview": str(tc["input"])[:100]})
        elif name in RESEARCH_TOOLS:
            research_tools_before_skill.append(name)
        # Other tools (e.g., Task, Agent) are ignored for this check

    # Build result
    skill_found = skill_index is not None
    has_premature = len(premature_tools) > 0

    issues = []

    if not skill_found:
        issues.append("Skill tool was never invoked")

    if has_premature:
        premature_names = [t["name"] for t in premature_tools]
        issues.append(f"Substantive tools called before Skill: {premature_names}")

    if expected_skill and skill_found and skill_name_used != expected_skill:
        issues.append(f"Expected skill '{expected_skill}', got '{skill_name_used}'")

    passed = skill_found and not has_premature
    if expected_skill and skill_found:
        passed = passed and (skill_name_used == expected_skill)

    # Score: 0.0 if premature action detected, partial credit for having skill but wrong one
    if passed:
        score = 1.0
    elif skill_found and not has_premature:
        # Skill was loaded first but wrong skill name
        score = 0.5
    elif skill_found and has_premature:
        # Skill was eventually loaded but substantive actions came first
        score = 0.2
    else:
        # No skill invocation at all
        score = 0.0

    return {
        "type": "premature_action",
        "passed": passed,
        "score": score,
        "details": "; ".join(issues) if issues else "Skill loaded before any substantive actions",
        "premature_tools": premature_tools,
        "research_tools_before_skill": research_tools_before_skill,
        "skill_found": skill_found,
        "skill_name_used": skill_name_used,
        "expected_skill": expected_skill,
    }


def grade_agent_evaluator(transcript: str, env: dict, config: dict) -> dict:
    """
    Use a specialized evaluator agent for grading.

    This grader is designed for use when running evals from within Claude Code,
    where we can invoke agents via the Task tool pattern. For CLI-based evals,
    use llm_rubric instead.

    The evaluator agent writes results to a JSON file that this grader reads.
    """
    rubric = config.get("rubric", "")
    assertions = config.get("assertions", [])
    output_file = Path(env["work_dir"]) / "eval_grade.json"

    # Build evaluation prompt for the agent
    eval_prompt = f"""You are an evaluation agent. Grade the following transcript.

## Transcript
```
{transcript[:10000]}
```

## Evaluation Criteria
{rubric}

## Assertions to Verify
{chr(10).join(f"- {a}" for a in assertions)}

## Instructions
1. Evaluate each assertion as PASS or FAIL
2. Provide reasoning for each judgment
3. Calculate an overall score (0.0-1.0)
4. Write your evaluation to: {output_file}

Write the evaluation as JSON with this structure:
{{
  "overall_pass": true/false,
  "score": 0.0-1.0,
  "assertions": [
    {{"assertion": "...", "passed": true/false, "reasoning": "..."}}
  ],
  "summary": "Brief assessment"
}}
"""

    # Note: This grader expects to be invoked from within Claude Code
    # where the Task tool can spawn an evaluator agent.
    # For standalone CLI usage, use llm_rubric instead.

    # Check if output file was created (by an agent in a parent session)
    if output_file.exists():
        try:
            with open(output_file) as f:
                evaluation = json.load(f)
            return {
                "type": "agent_evaluator",
                "passed": evaluation.get("overall_pass", False),
                "score": evaluation.get("score", 0.0),
                "details": evaluation.get("summary", ""),
                "assertions": evaluation.get("assertions", []),
            }
        except (json.JSONDecodeError, KeyError) as e:
            return {
                "type": "agent_evaluator",
                "passed": False,
                "score": 0.0,
                "details": f"Failed to parse evaluation: {e}",
            }

    # Fallback: If no agent output, return placeholder for manual/CLI grading
    return {
        "type": "agent_evaluator",
        "passed": False,
        "score": 0.0,
        "details": "Agent evaluation not available in CLI mode. Use llm_rubric for CLI evals.",
        "prompt_for_agent": eval_prompt,
    }


# Grader registry
GRADERS = {
    "file_exists": grade_file_exists,
    "string_contains": grade_string_contains,
    "regex_match": grade_regex_match,
    "tests_pass": grade_tests_pass,
    "yaml_valid": grade_yaml_valid,
    "llm_rubric": grade_llm_rubric,
    "agent_evaluator": grade_agent_evaluator,
    # V2 graders from Anthropic eval article
    "tool_calls": grade_tool_calls,
    "state_check": grade_state_check,
    "transcript_constraint": grade_transcript_constraint,
    # ADR-008: Skill discipline grader
    "premature_action": grade_premature_action,
}


# ============================================================================
# Grader Calibration
# ============================================================================


def load_calibration_examples(grader_type: str) -> list[dict]:
    """
    Load gold standard calibration examples for a grader type.

    Args:
        grader_type: The grader type (e.g., 'string_contains', 'llm_rubric')

    Returns:
        List of calibration examples with input/expected pairs

    Raises:
        FileNotFoundError: If calibration file doesn't exist
        yaml.YAMLError: If calibration file is invalid
    """
    calibration_dir = Path(__file__).parent / "calibration" / grader_type
    examples_file = calibration_dir / "examples.yaml"

    if not examples_file.exists():
        raise FileNotFoundError(f"No calibration data for grader: {grader_type}")

    with open(examples_file) as f:
        data = yaml.safe_load(f)

    return data.get("examples", [])


def run_calibration_example(grader_type: str, example: dict) -> dict:
    """
    Run a single calibration example against a grader.

    Args:
        grader_type: The grader type to calibrate
        example: Calibration example with input and expected values

    Returns:
        Dict with example_id, expected, actual, and alignment metrics
    """
    grader_fn = GRADERS.get(grader_type)
    if not grader_fn:
        return {
            "example_id": example.get("id", "unknown"),
            "error": f"Unknown grader type: {grader_type}",
            "aligned": False,
        }

    input_data = example.get("input", {})
    expected = example.get("expected", {})

    # Create minimal environment for graders that need it
    env = {"work_dir": tempfile.mkdtemp(prefix="calibration_")}

    try:
        # Run the grader
        actual = grader_fn(
            transcript=input_data.get("transcript", ""),
            env=env,
            config=input_data.get("config", {}),
        )

        # Compare results
        result = {
            "example_id": example.get("id", "unknown"),
            "description": example.get("description", ""),
            "expected": expected,
            "actual": {
                "passed": actual.get("passed"),
                "score": actual.get("score"),
            },
        }

        # Check alignment based on expected format
        if "score_min" in expected and "score_max" in expected:
            # Range-based comparison (for LLM graders with variance)
            score_aligned = expected["score_min"] <= actual["score"] <= expected["score_max"]
            passed_aligned = actual["passed"] == expected["passed"]
            result["aligned"] = passed_aligned and score_aligned
            result["score_deviation"] = (
                0.0
                if score_aligned
                else min(
                    abs(actual["score"] - expected["score_min"]),
                    abs(actual["score"] - expected["score_max"]),
                )
            )
        else:
            # Exact comparison (for deterministic graders)
            passed_aligned = actual["passed"] == expected.get("passed")
            score_deviation = abs(actual["score"] - expected.get("score", 0.0))
            result["aligned"] = passed_aligned and score_deviation < 0.01
            result["score_deviation"] = score_deviation

        return result

    finally:
        # Cleanup temp directory
        if Path(env["work_dir"]).exists():
            shutil.rmtree(env["work_dir"], ignore_errors=True)


def calibrate_grader(grader_type: str, verbose: bool = True) -> dict:
    """
    Calibrate a grader against gold standard examples.

    Runs all calibration examples for the specified grader type and
    reports alignment metrics including agreement rate and score deviation.

    Args:
        grader_type: The grader type to calibrate (e.g., 'string_contains')
        verbose: Whether to print progress and results

    Returns:
        Calibration report with metrics and per-example results
    """
    if grader_type not in GRADERS:
        return {
            "grader_type": grader_type,
            "error": f"Unknown grader type: {grader_type}",
            "calibrated": False,
        }

    try:
        examples = load_calibration_examples(grader_type)
    except FileNotFoundError as e:
        return {
            "grader_type": grader_type,
            "error": str(e),
            "calibrated": False,
        }

    if not examples:
        return {
            "grader_type": grader_type,
            "error": "No calibration examples found",
            "calibrated": False,
        }

    if verbose:
        print(f"\nCalibrating grader: {grader_type}")
        print(f"Running {len(examples)} calibration examples...")
        print("-" * 60)

    results = []
    for example in examples:
        result = run_calibration_example(grader_type, example)
        results.append(result)

        if verbose:
            status = "ALIGNED" if result.get("aligned") else "MISALIGNED"
            print(f"  [{status}] {result['example_id']}: {result.get('description', '')[:40]}")
            if not result.get("aligned"):
                exp = result["expected"]
                act = result["actual"]
                if "score_min" in exp:
                    print(
                        f"           Expected: passed={exp.get('passed')}, score={exp['score_min']}-{exp['score_max']}"
                    )
                else:
                    print(f"           Expected: passed={exp.get('passed')}, score={exp.get('score')}")
                print(f"           Actual:   passed={act['passed']}, score={act['score']:.3f}")

    # Compute aggregate metrics
    aligned_count = sum(1 for r in results if r.get("aligned", False))
    total_count = len(results)
    agreement_rate = aligned_count / total_count if total_count > 0 else 0.0

    score_deviations = [r.get("score_deviation", 0.0) for r in results if "score_deviation" in r]
    avg_deviation = sum(score_deviations) / len(score_deviations) if score_deviations else 0.0
    max_deviation = max(score_deviations) if score_deviations else 0.0

    report = {
        "grader_type": grader_type,
        "calibrated": True,
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_examples": total_count,
            "aligned_examples": aligned_count,
            "agreement_rate": agreement_rate,
            "avg_score_deviation": avg_deviation,
            "max_score_deviation": max_deviation,
        },
        "results": results,
    }

    if verbose:
        print("-" * 60)
        print(f"Agreement rate: {agreement_rate:.1%} ({aligned_count}/{total_count})")
        print(f"Avg score deviation: {avg_deviation:.4f}")
        print(f"Max score deviation: {max_deviation:.4f}")

        # Quality assessment
        if agreement_rate >= 0.95:
            print("Status: EXCELLENT - Grader is well-calibrated")
        elif agreement_rate >= 0.80:
            print("Status: GOOD - Minor calibration adjustments may be needed")
        elif agreement_rate >= 0.60:
            print("Status: FAIR - Review misaligned examples")
        else:
            print("Status: POOR - Grader needs significant calibration work")

    return report


def calibrate_all_graders(verbose: bool = True) -> dict:
    """
    Calibrate all graders that have calibration data.

    Args:
        verbose: Whether to print progress and results

    Returns:
        Dict with calibration reports for each grader
    """
    calibration_dir = Path(__file__).parent / "calibration"
    reports = {}

    if not calibration_dir.exists():
        if verbose:
            print("No calibration directory found")
        return {"error": "Calibration directory not found", "reports": {}}

    # Find all grader types with calibration data
    grader_dirs = [d for d in calibration_dir.iterdir() if d.is_dir()]

    if not grader_dirs:
        if verbose:
            print("No calibration data found for any graders")
        return {"error": "No calibration data", "reports": {}}

    if verbose:
        print(f"\n{'=' * 60}")
        print("GRADER CALIBRATION REPORT")
        print(f"{'=' * 60}")

    for grader_dir in sorted(grader_dirs):
        grader_type = grader_dir.name
        if grader_type in GRADERS:
            report = calibrate_grader(grader_type, verbose=verbose)
            reports[grader_type] = report

    # Summary
    if verbose and reports:
        print(f"\n{'=' * 60}")
        print("CALIBRATION SUMMARY")
        print(f"{'=' * 60}")
        for grader_type, report in reports.items():
            if report.get("calibrated"):
                rate = report["metrics"]["agreement_rate"]
                status = "OK" if rate >= 0.80 else "NEEDS WORK"
                print(f"  {grader_type}: {rate:.1%} agreement [{status}]")
            else:
                print(f"  {grader_type}: {report.get('error', 'Failed')}")

    return {
        "timestamp": datetime.now().isoformat(),
        "reports": reports,
    }


# ============================================================================
# Task Execution
# ============================================================================


def setup_environment(task: dict) -> dict:
    """
    Create an isolated working environment for the task.

    Runs any setup commands and copies context files to a temporary directory.
    Setup commands are treated as trusted input (see module-level security note).

    Returns:
        dict with work_dir path and start_time
    """
    work_dir = tempfile.mkdtemp(prefix="eval_")

    # Run setup commands if any
    setup_commands = task.get("input", {}).get("setup_commands", [])
    for cmd in setup_commands:
        result = subprocess.run(cmd, shell=True, cwd=work_dir, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Setup command failed (exit {result.returncode}): {cmd[:50]}")
            if result.stderr:
                logger.warning(f"  stderr: {result.stderr[:200]}")

    # Copy context files if any
    context_files = task.get("input", {}).get("context_files", [])
    for cf in context_files:
        src = Path(cf)
        if src.exists():
            dst = Path(work_dir) / src.name
            shutil.copy(src, dst)
        else:
            logger.warning(f"Context file not found, skipping: {cf}")

    return {
        "work_dir": work_dir,
        "start_time": time.time(),
    }


def cleanup_environment(env: dict):
    """Clean up the isolated environment."""
    if env.get("work_dir") and Path(env["work_dir"]).exists():
        shutil.rmtree(env["work_dir"], ignore_errors=True)


def extract_token_usage(json_output: str) -> dict:
    """
    Extract token usage from claude CLI JSON output.

    The JSON output contains multiple objects (newline-delimited or array).
    We look for the 'result' type which contains aggregated usage stats.
    """
    tokens = {
        "tokens_input": 0,
        "tokens_output": 0,
        "tokens_cache_read": 0,
        "tokens_cache_creation": 0,
        "tokens_total": 0,
        "cost_usd": 0.0,
    }

    try:
        # Parse the JSON output - it may be an array or newline-delimited
        if json_output.strip().startswith("["):
            items = json.loads(json_output)
        else:
            # Newline-delimited JSON
            items = [json.loads(line) for line in json_output.strip().split("\n") if line.strip()]

        # Find the result object which contains aggregated usage
        for item in items:
            if item.get("type") == "result":
                usage = item.get("usage", {})
                tokens["tokens_input"] = usage.get("input_tokens", 0)
                tokens["tokens_output"] = usage.get("output_tokens", 0)
                tokens["tokens_cache_read"] = usage.get("cache_read_input_tokens", 0)
                tokens["tokens_cache_creation"] = usage.get("cache_creation_input_tokens", 0)
                tokens["tokens_total"] = (
                    tokens["tokens_input"]
                    + tokens["tokens_output"]
                    + tokens["tokens_cache_read"]
                    + tokens["tokens_cache_creation"]
                )
                tokens["cost_usd"] = item.get("total_cost_usd", 0.0)
                break

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        # JSON parsing can fail for various reasons - log for debugging
        logger.warning(f"Failed to extract token usage from JSON output: {type(e).__name__}")

    return tokens


def extract_transcript_from_json(json_output: str) -> str:
    """
    Extract the actual response text from claude CLI JSON output.

    Collects text from assistant messages and the final result.
    """
    transcript_parts = []

    try:
        if json_output.strip().startswith("["):
            items = json.loads(json_output)
        else:
            items = [json.loads(line) for line in json_output.strip().split("\n") if line.strip()]

        for item in items:
            # Collect assistant message content
            if item.get("type") == "assistant":
                message = item.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        transcript_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        transcript_parts.append(block)

            # Also include the final result text
            if item.get("type") == "result":
                result_text = item.get("result", "")
                if result_text and result_text not in transcript_parts:
                    transcript_parts.append(result_text)

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        # If parsing fails, caller will use raw output as fallback
        logger.warning(f"Failed to extract transcript from JSON: {type(e).__name__}")

    return "\n".join(transcript_parts)


def extract_transcript_metrics(json_output: str) -> dict:
    """
    Extract transcript-level metrics from claude CLI JSON output.

    These metrics are essential for agentic evals per Anthropic's article:
    - n_turns: Number of conversational turns (user->assistant exchanges)
    - n_tool_calls: Total number of tool invocations
    - time_to_first_token: Time until first output (if available)
    - output_tokens_per_sec: Token generation rate

    Returns:
        Dict with transcript metrics for use in graders and reporting
    """
    metrics = {
        "n_turns": 0,
        "n_tool_calls": 0,
        "n_user_messages": 0,
        "n_assistant_messages": 0,
        "tool_calls_by_name": {},
        "first_response_time_ms": None,
        "output_tokens_per_sec": None,
    }

    try:
        if json_output.strip().startswith("["):
            items = json.loads(json_output)
        else:
            items = [json.loads(line) for line in json_output.strip().split("\n") if line.strip()]

        first_assistant_ts = None
        first_user_ts = None

        for item in items:
            item_type = item.get("type")

            if item_type == "user":
                metrics["n_user_messages"] += 1
                if first_user_ts is None:
                    first_user_ts = item.get("timestamp")

            elif item_type == "assistant":
                metrics["n_assistant_messages"] += 1
                if first_assistant_ts is None:
                    first_assistant_ts = item.get("timestamp")

                # Count tool calls in this message
                message = item.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        metrics["n_tool_calls"] += 1
                        tool_name = block.get("name", "unknown")
                        metrics["tool_calls_by_name"][tool_name] = metrics["tool_calls_by_name"].get(tool_name, 0) + 1

            elif item_type == "result":
                # Extract timing metrics if available
                usage = item.get("usage", {})
                output_tokens = usage.get("output_tokens", 0)

                # Try to compute output tokens per second from duration
                duration_ms = item.get("duration_ms")
                if duration_ms and output_tokens:
                    metrics["output_tokens_per_sec"] = (output_tokens / duration_ms) * 1000

        # Compute n_turns as min(user_messages, assistant_messages)
        # Each turn is a complete user->assistant exchange
        metrics["n_turns"] = min(metrics["n_user_messages"], metrics["n_assistant_messages"])

        # Compute time to first token if we have timestamps
        if first_user_ts and first_assistant_ts:
            try:
                from datetime import datetime as dt

                user_time = dt.fromisoformat(first_user_ts.replace("Z", "+00:00"))
                asst_time = dt.fromisoformat(first_assistant_ts.replace("Z", "+00:00"))
                metrics["first_response_time_ms"] = (asst_time - user_time).total_seconds() * 1000
            except (ValueError, TypeError) as e:
                # Timestamp parsing can fail with malformed dates
                logger.warning(f"Failed to parse timestamps for first response time: {e}")

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        # JSON parsing can fail - log for debugging
        logger.warning(f"Failed to extract transcript metrics: {type(e).__name__}")

    return metrics


def execute_agent(task: dict, env: dict) -> dict:
    """Execute the agent via claude CLI.

    Returns a dict with:
    - success: bool indicating if execution completed without errors
    - transcript: Human-readable transcript text
    - raw_json_output: Raw JSON for graders that need to inspect tool calls
    - All token usage metrics
    - Transcript metrics (n_turns, n_tool_calls, etc.) per Anthropic eval article
    - Latency breakdown (elapsed_seconds, first_response_time_ms, output_tokens_per_sec)
    """
    prompt = task["input"]["prompt"]
    agent = task["execution"].get("agent")
    skill = task["execution"].get("skill")
    timeout = task["execution"].get("timeout_seconds", 300)

    # Build the command - use JSON output for token tracking
    # Format: claude -p "prompt" --output-format json
    cmd = ["claude", "-p", prompt, "--output-format", "json"]

    # Add agent/skill context to prompt if specified
    if agent:
        cmd[2] = f"Use the {agent} agent. {prompt}"
    if skill:
        cmd[2] = f"/{skill} {prompt}"

    try:
        start = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=env["work_dir"],
        )
        elapsed = time.time() - start

        # Extract token usage from JSON output
        token_usage = extract_token_usage(result.stdout)

        # Extract transcript metrics (n_turns, n_tool_calls, latency breakdown)
        transcript_metrics = extract_transcript_metrics(result.stdout)

        # Extract readable transcript from JSON
        transcript = extract_transcript_from_json(result.stdout)
        if not transcript:
            # Fallback: use raw output if extraction failed
            transcript = result.stdout

        return {
            "success": result.returncode == 0,
            "transcript": transcript,
            "raw_json_output": result.stdout,  # For tool_calls grader
            "stderr": result.stderr,
            "elapsed_seconds": elapsed,
            "exit_code": result.returncode,
            # Token usage
            **token_usage,
            # Transcript metrics from Anthropic article
            "n_turns": transcript_metrics["n_turns"],
            "n_tool_calls": transcript_metrics["n_tool_calls"],
            "tool_calls_by_name": transcript_metrics["tool_calls_by_name"],
            # Latency breakdown
            "first_response_time_ms": transcript_metrics["first_response_time_ms"],
            "output_tokens_per_sec": transcript_metrics["output_tokens_per_sec"],
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "transcript": "",
            "raw_json_output": "",
            "stderr": f"Execution timed out after {timeout} seconds",
            "elapsed_seconds": timeout,
            "exit_code": -1,
            "tokens_input": 0,
            "tokens_output": 0,
            "tokens_cache_read": 0,
            "tokens_cache_creation": 0,
            "tokens_total": 0,
            "cost_usd": 0.0,
            "n_turns": 0,
            "n_tool_calls": 0,
            "tool_calls_by_name": {},
            "first_response_time_ms": None,
            "output_tokens_per_sec": None,
        }
    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "raw_json_output": "",
            "stderr": str(e),
            "elapsed_seconds": 0,
            "exit_code": -1,
            "tokens_input": 0,
            "tokens_output": 0,
            "tokens_cache_read": 0,
            "tokens_cache_creation": 0,
            "tokens_total": 0,
            "cost_usd": 0.0,
            "n_turns": 0,
            "n_tool_calls": 0,
            "tool_calls_by_name": {},
            "first_response_time_ms": None,
            "output_tokens_per_sec": None,
        }


def run_graders(task: dict, transcript: str, env: dict) -> list[dict]:
    """Run all configured graders on the task output."""
    results = []
    graders = task.get("graders", [])

    for grader_config in graders:
        grader_type = grader_config.get("type")
        config = grader_config.get("config", {})
        weight = grader_config.get("weight", 1.0)

        if grader_type not in GRADERS:
            results.append(
                {
                    "type": grader_type,
                    "passed": False,
                    "score": 0.0,
                    "weight": weight,
                    "details": f"Unknown grader type: {grader_type}",
                }
            )
            continue

        grader_fn = GRADERS[grader_type]
        result = grader_fn(transcript, env, config)
        result["weight"] = weight
        results.append(result)

    return results


def compute_weighted_score(grades: list[dict]) -> float:
    """Compute weighted average score from grader results."""
    if not grades:
        return 0.0

    total_weight = sum(g.get("weight", 1.0) for g in grades)
    if total_weight == 0:
        return 0.0

    weighted_sum = sum(g.get("score", 0.0) * g.get("weight", 1.0) for g in grades)
    return weighted_sum / total_weight


def save_transcript(task_id: str, transcript: str, trial_num: int = 0) -> Path:
    """Save transcript to a file for later grading or analysis."""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    transcript_file = results_dir / f"{task_id}-trial{trial_num}-transcript.txt"
    transcript_file.write_text(transcript)
    return transcript_file


def run_task(task_path: str, trial_num: int = 0, save_transcripts: bool = False) -> dict:
    """Run a single evaluation task."""
    # Load task
    with open(task_path) as f:
        task_data = yaml.safe_load(f)

    task = task_data.get("task", task_data)
    task_id = task.get("id", Path(task_path).stem)

    # Setup environment
    env = setup_environment(task)

    try:
        # Execute agent
        execution_result = execute_agent(task, env)

        # Add execution metrics to env so graders can access them
        # This enables transcript_constraint and tool_calls graders
        env["raw_json_output"] = execution_result.get("raw_json_output", "")
        env["n_turns"] = execution_result.get("n_turns", 0)
        env["n_tool_calls"] = execution_result.get("n_tool_calls", 0)
        env["tokens_total"] = execution_result.get("tokens_total", 0)
        env["elapsed_seconds"] = execution_result.get("elapsed_seconds", 0)

        # Optionally save transcript for agent-based grading later
        transcript_file = None
        if save_transcripts:
            transcript_file = save_transcript(task_id, execution_result["transcript"], trial_num)

        # Run graders
        grades = run_graders(task, execution_result["transcript"], env)

        # Compute score
        score = compute_weighted_score(grades)

        result = {
            "task_id": task_id,
            "task_name": task.get("name", ""),
            "trial": trial_num,
            "success": execution_result["success"],
            "score": score,
            "passed": score >= 0.7,  # Threshold for passing
            "grades": grades,
            "metrics": {
                # Existing metrics
                "elapsed_seconds": execution_result["elapsed_seconds"],
                "exit_code": execution_result["exit_code"],
                "tokens_input": execution_result.get("tokens_input", 0),
                "tokens_output": execution_result.get("tokens_output", 0),
                "tokens_cache_read": execution_result.get("tokens_cache_read", 0),
                "tokens_cache_creation": execution_result.get("tokens_cache_creation", 0),
                "tokens_total": execution_result.get("tokens_total", 0),
                "cost_usd": execution_result.get("cost_usd", 0.0),
                # V2 metrics from Anthropic eval article
                "n_turns": execution_result.get("n_turns", 0),
                "n_tool_calls": execution_result.get("n_tool_calls", 0),
                "tool_calls_by_name": execution_result.get("tool_calls_by_name", {}),
                # Latency breakdown
                "first_response_time_ms": execution_result.get("first_response_time_ms"),
                "output_tokens_per_sec": execution_result.get("output_tokens_per_sec"),
            },
            "transcript_preview": execution_result["transcript"][:500],
            "timestamp": datetime.now().isoformat(),
        }

        if transcript_file:
            result["transcript_file"] = str(transcript_file)

        return result

    finally:
        cleanup_environment(env)


def load_task_type(task_path: Path) -> str | None:
    """Load the type field from a task file."""
    try:
        with open(task_path) as f:
            task_data = yaml.safe_load(f)
        task = task_data.get("task", task_data)
        return task.get("type")
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Failed to load task type from {task_path}: {e}")
        return None


def run_suite(suite_path: str, num_trials: int = 1, task_type: str | None = None) -> dict:
    """Run all tasks in a directory.

    Args:
        suite_path: Path to directory containing task YAML files
        num_trials: Number of trials to run per task
        task_type: Filter to only run tasks of this type ("capability" or "regression")
    """
    suite_dir = Path(suite_path)
    if not suite_dir.is_dir():
        print(f"Error: {suite_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    task_files = list(suite_dir.glob("*.yaml"))
    if not task_files:
        print(f"No task files found in {suite_path}", file=sys.stderr)
        sys.exit(1)

    # Filter by type if specified
    if task_type:
        filtered_files = []
        for tf in task_files:
            file_type = load_task_type(tf)
            if file_type == task_type:
                filtered_files.append(tf)
        task_files = filtered_files
        if not task_files:
            print(f"No {task_type} tasks found in {suite_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Filtered to {len(task_files)} {task_type} task(s)")

    results = []
    for task_file in sorted(task_files):
        print(f"Running: {task_file.name}")

        # Get task type for reporting
        file_task_type = load_task_type(task_file) or "capability"

        task_results = []
        for trial in range(num_trials):
            if num_trials > 1:
                print(f"  Trial {trial + 1}/{num_trials}...")
            result = run_task(str(task_file), trial)
            task_results.append(result)
            print(f"  Score: {result['score']:.2f} ({'PASS' if result['passed'] else 'FAIL'})")

        # Compute pass@k and pass^k
        passes = sum(1 for r in task_results if r["passed"])
        pass_at_k = passes > 0  # At least one trial passed
        pass_power_k = passes == num_trials  # All trials passed

        # Aggregate token metrics for this task
        task_tokens_total = sum(r["metrics"]["tokens_total"] for r in task_results)
        task_cost_usd = sum(r["metrics"]["cost_usd"] for r in task_results)

        results.append(
            {
                "task_id": task_results[0]["task_id"],
                "task_name": task_results[0]["task_name"],
                "type": file_task_type,
                "trials": task_results,
                "pass@k": pass_at_k,
                "pass^k": pass_power_k,
                "pass_rate": passes / num_trials,
                "avg_score": sum(r["score"] for r in task_results) / num_trials,
                "tokens_total": task_tokens_total,
                "cost_usd": task_cost_usd,
            }
        )

    # Aggregate token metrics across all tasks
    total_tokens = sum(r["tokens_total"] for r in results)
    total_cost = sum(r["cost_usd"] for r in results)

    # Separate results by type
    capability_results = [r for r in results if r.get("type") == "capability"]
    regression_results = [r for r in results if r.get("type") == "regression"]

    # Compute type-specific metrics
    def type_summary(type_results: list) -> dict:
        if not type_results:
            return {}
        return {
            "total": len(type_results),
            # For capability: pass@k is the key metric
            "passed": sum(1 for r in type_results if r["pass@k"]),
            "pass_rate": sum(1 for r in type_results if r["pass@k"]) / len(type_results),
            # For regression: pass^k is the key metric
            "passed_all_trials": sum(1 for r in type_results if r["pass^k"]),
            "pass_all_rate": sum(1 for r in type_results if r["pass^k"]) / len(type_results),
            "avg_score": sum(r["avg_score"] for r in type_results) / len(type_results),
        }

    return {
        "suite": str(suite_path),
        "num_trials": num_trials,
        "type_filter": task_type,
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total_tasks": len(results),
            "passed_any": sum(1 for r in results if r["pass@k"]),
            "passed_all": sum(1 for r in results if r["pass^k"]),
            "avg_score": sum(r["avg_score"] for r in results) / len(results) if results else 0,
            "tokens_total": total_tokens,
            "cost_usd": total_cost,
            # Type-specific summaries
            "capability": type_summary(capability_results),
            "regression": type_summary(regression_results),
        },
    }


def save_results(results: dict, output_path: str | None = None):
    """Save results to JSON file."""
    if output_path is None:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = results_dir / f"eval-{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")
    return output_path


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Run evaluation tasks against Claude Code agents")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run single task
    run_parser = subparsers.add_parser("run", help="Run a single task")
    run_parser.add_argument("task", help="Path to task YAML file")
    run_parser.add_argument("--trials", type=int, default=1, help="Number of trials (for pass@k)")
    run_parser.add_argument("--output", "-o", help="Output JSON file path")
    run_parser.add_argument(
        "--save-transcripts",
        action="store_true",
        help="Save transcripts to results/ for agent-based grading",
    )

    # Run suite
    suite_parser = subparsers.add_parser("suite", help="Run all tasks in a directory")
    suite_parser.add_argument("path", help="Path to tasks directory")
    suite_parser.add_argument("--trials", type=int, default=1, help="Number of trials per task")
    suite_parser.add_argument("--output", "-o", help="Output JSON file path")
    suite_parser.add_argument(
        "--type",
        choices=["capability", "regression"],
        help="Filter to only run tasks of this type",
    )
    suite_parser.add_argument(
        "--save-transcripts",
        action="store_true",
        help="Save transcripts to results/ for agent-based grading",
    )

    # Calibrate graders
    calibrate_parser = subparsers.add_parser("calibrate", help="Calibrate graders against gold standard examples")
    calibrate_parser.add_argument(
        "grader",
        nargs="?",
        help="Grader type to calibrate (e.g., 'string_contains', 'llm_rubric')",
    )
    calibrate_parser.add_argument(
        "--all",
        action="store_true",
        help="Calibrate all graders with available calibration data",
    )
    calibrate_parser.add_argument("--output", "-o", help="Output JSON file path for calibration report")

    # Grade agent: Structural evaluation using agent-evaluation skill rubric
    grade_agent_parser = subparsers.add_parser(
        "grade-agent",
        help="Grade an agent or skill using the agent-evaluation rubric (100-point system)",
    )
    grade_agent_parser.add_argument("path", help="Path to agent (.md file) or skill (directory or SKILL.md)")
    grade_agent_parser.add_argument("--output", "-o", help="Output JSON file path")
    grade_agent_parser.add_argument(
        "--format",
        choices=["json", "markdown", "summary"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    grade_agent_parser.add_argument(
        "--batch",
        action="store_true",
        help="Grade all agents/skills in directory",
    )

    # Skill-test: Run eval tasks for a specific agent (testing-agents-with-subagents integration)
    skill_test_parser = subparsers.add_parser(
        "skill-test",
        help="Run all eval tasks for a specific agent (for testing-agents-with-subagents skill)",
    )
    skill_test_parser.add_argument("agent", nargs="?", help="Agent name to test (e.g., 'python-general-engineer')")
    skill_test_parser.add_argument("--trials", type=int, default=3, help="Number of trials per task (default: 3)")
    skill_test_parser.add_argument("--output", "-o", help="Output JSON file path")
    skill_test_parser.add_argument(
        "--format",
        choices=["json", "markdown", "skill-report"],
        default="skill-report",
        help="Output format (default: skill-report for testing skill integration)",
    )
    skill_test_parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List all agents with available eval tasks",
    )

    args = parser.parse_args()

    if args.command == "run":
        # Run single task
        results = []
        total_tokens = 0
        total_cost = 0.0
        for trial in range(args.trials):
            result = run_task(args.task, trial, save_transcripts=args.save_transcripts)
            results.append(result)
            tokens = result["metrics"]["tokens_total"]
            cost = result["metrics"]["cost_usd"]
            total_tokens += tokens
            total_cost += cost
            print(
                f"Trial {trial + 1}: Score={result['score']:.2f} "
                f"({'PASS' if result['passed'] else 'FAIL'}) "
                f"[{tokens:,} tokens, ${cost:.4f}]"
            )
            if args.save_transcripts and "transcript_file" in result:
                print(f"  Transcript: {result['transcript_file']}")

        if args.trials > 1:
            passes = sum(1 for r in results if r["passed"])
            print(f"\npass@{args.trials}: {passes > 0}")
            print(f"pass^{args.trials}: {passes == args.trials}")

        print(f"\nTotal: {total_tokens:,} tokens, ${total_cost:.4f}")

        output = {
            "task": args.task,
            "trials": results,
            "pass@k": any(r["passed"] for r in results),
            "tokens_total": total_tokens,
            "cost_usd": total_cost,
            "timestamp": datetime.now().isoformat(),
        }
        save_results(output, args.output)

    elif args.command == "suite":
        results = run_suite(args.path, args.trials, task_type=args.type)
        save_results(results, args.output)

        # Print summary
        print(f"\n{'=' * 50}")
        print("SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total tasks: {results['summary']['total_tasks']}")
        print(f"Passed (any trial): {results['summary']['passed_any']}")
        print(f"Passed (all trials): {results['summary']['passed_all']}")
        print(f"Average score: {results['summary']['avg_score']:.2f}")

        # Print type-specific summaries
        cap_summary = results["summary"].get("capability", {})
        reg_summary = results["summary"].get("regression", {})

        if cap_summary:
            print(f"\nCapability tasks ({cap_summary['total']}):")
            print(f"  pass@k: {cap_summary['passed']}/{cap_summary['total']} ({cap_summary['pass_rate']:.0%})")

        if reg_summary:
            print(f"\nRegression tasks ({reg_summary['total']}):")
            print(
                f"  pass^k: {reg_summary['passed_all_trials']}/{reg_summary['total']} ({reg_summary['pass_all_rate']:.0%})"
            )

        print(f"\nTotal tokens: {results['summary']['tokens_total']:,}")
        print(f"Total cost: ${results['summary']['cost_usd']:.4f}")

    elif args.command == "calibrate":
        # Calibrate graders
        if args.all:
            report = calibrate_all_graders(verbose=True)
        elif args.grader:
            report = calibrate_grader(args.grader, verbose=True)
        else:
            print("Error: Specify a grader type or use --all", file=sys.stderr)
            print(f"Available graders: {', '.join(GRADERS.keys())}", file=sys.stderr)
            sys.exit(1)

        # Save report if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\nCalibration report saved to: {args.output}")

    elif args.command == "grade-agent":
        # Import the agent assessment integration
        from integrations.agent_evaluation import format_report, run_agent_eval

        if args.batch:
            # Batch mode: grade all .md files in directory
            target_path = Path(args.path)
            if not target_path.is_dir():
                print(f"Error: {args.path} is not a directory", file=sys.stderr)
                sys.exit(1)

            # Check if it's an agents directory or skills directory
            if target_path.name == "agents" or "agents" in str(target_path):
                files = list(target_path.glob("*.md"))
            elif target_path.name == "skills" or "skills" in str(target_path):
                files = list(target_path.glob("*/SKILL.md"))
            else:
                # Try both
                files = list(target_path.glob("*.md")) + list(target_path.glob("*/SKILL.md"))

            if not files:
                print(f"No agent/skill files found in {args.path}", file=sys.stderr)
                sys.exit(1)

            results = []
            print(f"Grading {len(files)} files...")
            print("-" * 60)

            for file_path in sorted(files):
                result = run_agent_eval(str(file_path))
                results.append(result)
                name = Path(result["path"]).name
                score = result["overall_score"]
                grade = result["grade"]
                print(f"  {name}: {score}/100 ({grade})")

            # Summary statistics
            avg_score = sum(r["overall_score"] for r in results) / len(results)
            grade_counts = {}
            for r in results:
                g = r["grade"]
                grade_counts[g] = grade_counts.get(g, 0) + 1

            print("-" * 60)
            print(f"\nBatch Summary ({len(results)} files):")
            print(f"  Average Score: {avg_score:.1f}/100")
            print("  Grade Distribution:")
            for grade in ["A", "B", "C", "D", "F"]:
                count = grade_counts.get(grade, 0)
                pct = (count / len(results)) * 100
                print(f"    {grade}: {count} ({pct:.0f}%)")

            # Save batch results
            if args.output:
                batch_output = {
                    "batch_path": str(args.path),
                    "total_files": len(results),
                    "avg_score": avg_score,
                    "grade_distribution": grade_counts,
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                }
                with open(args.output, "w") as f:
                    json.dump(batch_output, f, indent=2)
                print(f"\nBatch results saved to: {args.output}")

        else:
            # Single file mode
            result = run_agent_eval(args.path)

            if "error" in result:
                print(f"Error: {result['error']}", file=sys.stderr)
                sys.exit(1)

            if args.format == "json":
                output = json.dumps(result, indent=2)
                print(output)
            elif args.format == "summary":
                name = Path(result["path"]).name
                score = result["overall_score"]
                grade = result["grade"]
                entity_type = result["entity_type"]
                print(f"{name} ({entity_type}): {score}/100 ({grade})")
            else:  # markdown
                output = format_report(result)
                print(output)

            # Save to file if requested
            if args.output:
                output_path = Path(args.output)
                if args.format == "json":
                    with open(output_path, "w") as f:
                        json.dump(result, f, indent=2)
                else:
                    output_path.write_text(format_report(result))
                print(f"\nResults saved to: {output_path}")

    elif args.command == "skill-test":
        # Import the testing skill integration
        from integrations.testing_skill import (
            format_skill_test_report,
            list_available_agents,
            run_agent_eval,
        )

        # Handle --list-agents flag
        if args.list_agents:
            agents = list_available_agents()
            if not agents:
                print("No agents with tasks found.")
                sys.exit(0)

            print("\nAgents with tasks:")
            print("-" * 40)
            for agent_name, task_count in sorted(agents.items()):
                print(f"  {agent_name}: {task_count} task(s)")
            print()
            sys.exit(0)

        # Require agent name if not listing
        if not args.agent:
            print("Error: Agent name is required.", file=sys.stderr)
            print("Usage: harness.py skill-test <agent-name>", file=sys.stderr)
            print("Use --list-agents to see available agents.", file=sys.stderr)
            sys.exit(1)

        # Run tests for the specified agent
        result = run_agent_eval(args.agent, num_trials=args.trials, verbose=True)

        if result.total_tasks == 0:
            print(f"\nNo tasks found for agent: {args.agent}")
            print("Use --list-agents to see available agents.")
            sys.exit(1)

        # Format and display results
        print(f"\n{'=' * 60}")
        print("RESULTS")
        print(f"{'=' * 60}")

        if args.format == "json":
            # Convert dataclass to dict for JSON serialization
            import dataclasses

            result_dict = dataclasses.asdict(result)
            output = json.dumps(result_dict, indent=2)
            print(output)
        elif args.format == "markdown":
            from integrations.testing_skill import format_eval_result

            output = format_eval_result(result)
            print(output)
        else:  # skill-report
            output = format_skill_test_report(result)
            print(output)

        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            if args.format == "json":
                import dataclasses

                with open(output_path, "w") as f:
                    json.dump(dataclasses.asdict(result), f, indent=2)
            else:
                output_path.write_text(output)
            print(f"\nResults saved to: {output_path}")

        # Print summary stats
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"Agent: {result.agent_name}")
        print(f"Tasks: {result.total_tasks}")
        print(f"Trials per task: {result.num_trials}")
        print(f"Pass rate (pass@k): {result.pass_rate:.1%}")
        print(f"Avg score: {result.avg_score:.2f}")
        print(f"Total tokens: {result.tokens_total:,}")
        print(f"Total cost: ${result.cost_usd:.4f}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
