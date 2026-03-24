#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Auto-Plan Detection

Detects when a task requires automatic plan creation based on Manus methodology.
Injects planning instructions when complex task patterns are detected.

Trigger patterns:
- Agent routing detected (Simple+ complexity)
- Code modification verbs: implement, build, create, add, fix, debug, refactor
- Multi-step indicators: numbered lists, "first...then", "and also"
- Research tasks: research, investigate, understand

Design Principles:
- SILENT for trivial tasks (pure lookups, single reads)
- Injects planning context for complex tasks
- Fast execution (<50ms target)
- Non-blocking (always exits 0)
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output
from stdin_timeout import read_stdin

# =============================================================================
# Detection Patterns
# =============================================================================

# Verbs that indicate code modification (need planning)
CODE_MODIFICATION_VERBS = {
    "implement",
    "build",
    "create",
    "add",
    "fix",
    "debug",
    "refactor",
    "rename",
    "update",
    "modify",
    "change",
    "improve",
    "optimize",
    "migrate",
    "upgrade",
    "rewrite",
    "restructure",
}

# Research/investigation verbs (need planning for research notes)
RESEARCH_VERBS = {
    "research",
    "investigate",
    "explore",
    "analyze",
    "understand",
    "study",
    "examine",
    "review",
}

# Multi-step indicators (pre-compiled for performance)
MULTI_STEP_PATTERNS = [
    re.compile(r"first.*then", re.IGNORECASE),
    re.compile(r"step\s*1", re.IGNORECASE),
    re.compile(r"1\.\s+\w", re.IGNORECASE),  # Numbered list
    re.compile(r"and\s+also", re.IGNORECASE),
    re.compile(r"after\s+that", re.IGNORECASE),
    re.compile(r"next\s*,", re.IGNORECASE),
]

# Trivial task indicators (skip planning) - pre-compiled for performance
# Note: "show me" is specific to avoid matching "show me how to build X"
TRIVIAL_PATTERNS = [
    re.compile(r"^what\s+(is|are|does)", re.IGNORECASE),
    re.compile(r"^how\s+do\s+(i|you)", re.IGNORECASE),
    re.compile(r"^show\s+me\s+(the|this|that|my|your)\s+", re.IGNORECASE),  # More specific
    re.compile(r"^read\s+", re.IGNORECASE),
    re.compile(r"^cat\s+", re.IGNORECASE),
    re.compile(r"^ls\s+", re.IGNORECASE),
    re.compile(r"^git\s+status", re.IGNORECASE),
    re.compile(r"^git\s+log", re.IGNORECASE),
    re.compile(r"^git\s+diff", re.IGNORECASE),
    re.compile(r"explain\s+", re.IGNORECASE),
    re.compile(r"^help\s+", re.IGNORECASE),
]

# Agent routing triggers (from /do router)
AGENT_TRIGGERS = {
    # Domain agents
    "go",
    "golang",
    "python",
    "typescript",
    "react",
    "nextjs",
    "node",
    "nodejs",
    "kubernetes",
    "helm",
    "k8s",
    "ansible",
    "prometheus",
    "grafana",
    "opensearch",
    "elasticsearch",
    "rabbitmq",
    "postgres",
    "postgresql",
    "sqlite",
    # Task-type triggers
    "test",
    "tests",
    "testing",
    "api",
    "endpoint",
    "auth",
    "authentication",
    "database",
    "schema",
    "migration",
}


def get_user_prompt() -> str:
    """Get the user prompt from stdin (hook input)."""
    try:
        hook_input = json.loads(read_stdin(timeout=2))
        # Validate input is a dict (expected format from hook system)
        if not isinstance(hook_input, dict):
            print(f"[auto-plan] Expected dict input, got {type(hook_input).__name__}", file=sys.stderr)
            return ""
        # UserPromptSubmit provides prompt in 'prompt' field
        return hook_input.get("prompt", "").lower().strip()
    except json.JSONDecodeError as e:
        # Always log parse failures - users need to know hook input is malformed
        print(f"[auto-plan] JSON parse error: {e}", file=sys.stderr)
        return ""


def is_trivial_task(prompt: str) -> bool:
    """Check if the task is trivial and doesn't need planning."""
    return any(pattern.search(prompt) for pattern in TRIVIAL_PATTERNS)


def has_code_modification_intent(prompt: str) -> bool:
    """Check if the prompt indicates code modification."""
    words = set(prompt.split())
    return bool(words & CODE_MODIFICATION_VERBS)


def has_research_intent(prompt: str) -> bool:
    """Check if the prompt indicates research/investigation."""
    words = set(prompt.split())
    return bool(words & RESEARCH_VERBS)


def has_multi_step_indicators(prompt: str) -> bool:
    """Check if the prompt contains multi-step indicators."""
    return any(pattern.search(prompt) for pattern in MULTI_STEP_PATTERNS)


def has_agent_triggers(prompt: str) -> bool:
    """Check if the prompt contains agent routing triggers."""
    words = set(re.findall(r"\b\w+\b", prompt))
    return bool(words & AGENT_TRIGGERS)


def detect_complexity(prompt: str) -> tuple[bool, str]:
    """
    Detect if the task is complex enough to require auto-planning.

    Returns:
        Tuple of (needs_plan, reason)
    """
    # Skip trivial tasks
    if is_trivial_task(prompt):
        return False, "trivial"

    # Check for complexity indicators
    reasons = []

    if has_code_modification_intent(prompt):
        reasons.append("code modification")

    if has_research_intent(prompt):
        reasons.append("research task")

    if has_multi_step_indicators(prompt):
        reasons.append("multi-step task")

    if has_agent_triggers(prompt) and (has_code_modification_intent(prompt) or has_research_intent(prompt)):
        reasons.append("agent-level work")

    if reasons:
        return True, ", ".join(reasons)

    return False, "simple"


def get_plan_injection() -> str:
    """Get the planning context injection for complex tasks."""
    return """
<auto-plan-required>
**MANUS AUTO-PLAN TRIGGERED**

This task requires automatic plan creation. Before starting work:

1. **CREATE `task_plan.md`** in the working directory:
```markdown
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Phases
- [ ] Phase 1: Understand/research
- [ ] Phase 2: Plan approach
- [ ] Phase 3: Implement
- [ ] Phase 4: Verify and deliver

## Key Questions
1. [Question to answer]

## Decisions Made
- [Decision]: [Rationale]

## Errors Encountered
- [Error]: [Resolution]

## Status
**Currently in Phase 1** - [What I'm doing now]
```

2. **Re-read plan before major decisions** (keeps goals in attention window)

3. **Update after each phase** - mark [x] and update Status section

4. **Log errors** - Every error goes in "Errors Encountered" section

**For research tasks**, also create `notes.md` to store findings (don't stuff context).
</auto-plan-required>
"""


def main():
    """Main entry point for the hook."""
    event_name = "UserPromptSubmit"
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        prompt = get_user_prompt()

        if not prompt:
            empty_output(event_name).print_and_exit()

        needs_plan, reason = detect_complexity(prompt)

        if not needs_plan:
            # Silent for simple tasks
            empty_output(event_name).print_and_exit()

        # Log detection reason for debugging visibility
        if debug:
            print(f"[auto-plan] Triggered: {reason}", file=sys.stderr)

        # Inject planning context
        injection = get_plan_injection()
        context_output(event_name, injection).print_and_exit()

    except Exception as e:
        # Always log error to stderr for observability
        # Full stack trace only in debug mode
        if debug:
            print(f"[auto-plan] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            # Include exception message, not just type name
            print(f"[auto-plan] Error: {type(e).__name__}: {e}", file=sys.stderr)
        empty_output(event_name).print_and_exit()


if __name__ == "__main__":
    main()
