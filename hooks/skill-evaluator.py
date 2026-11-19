#!/usr/bin/env python3
# hook-version: 1.1.0
"""
UserPromptSubmit Hook: Dynamic Skill/Agent Evaluation

Discovers available skills and agents from filesystem,
injecting a targeted evaluation protocol when meaningful.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error

REPO_ROOT = Path(__file__).parent.parent

# Domain skills. The repo's specialist agents are retired (plans/009): the
# worker is the built-in general-purpose agent and a domain skill carries the
# domain that an agent used to hold.
DOMAIN_SKILLS = {
    "programming": "Go, Python, Rust, Kotlin, Swift, PHP, TypeScript debugging, OpenStack, Node APIs, MCP servers",
    "frontend": "TypeScript UI, React, Next.js, React Native, design systems, web performance",
    "game-dev": "PixiJS rendering, Rive animation, combat effects",
    "kubernetes": "K8s, Helm, Ansible, Prometheus/Grafana, OpenSearch, RabbitMQ, Perses",
    "data": "Pipelines, schema design, query plans, SQLite/Peewee",
    "testing": "Unit/E2E tests, Playwright, coverage",
    "review": "Code, system, domain, and multi-perspective review",
    "research": "Multi-source research and synthesis",
    "workflow": "Multi-step coordination and pipeline scaffolding",
    "toolkit": "Skills, hooks, routing tables, ADRs, toolkit upgrades",
    "writing": "Technical docs, articles, explainers",
}

# Complete skill routing guide
SKILL_ROUTING = {
    # Code Quality
    "systematic-code-review": "Review code changes, PRs, security audits",
    "systematic-debugging": "4-phase root cause analysis, no guessing",
    "systematic-refactoring": "Safe refactoring with phase gates",
    "test-driven-development": "RED-GREEN-REFACTOR cycle",
    "code-cleanup": "Stale TODOs, unused imports, missing types",
    "comment-quality": "Fix temporal/development-activity comments",
    # Language-Specific Quality
    "go-patterns": "Go testing, concurrency, errors, review, quality, sapcc conventions",
    "python-quality-gate": "ruff, pytest, mypy, bandit",
    "universal-quality-gate": "Multi-language quality checks",
    "code-linting": "Python (ruff) + JavaScript (Biome) linting",
    # Git/CI
    "pr-workflow": "PR lifecycle umbrella: commit, codex-review, sync, status, fix, cleanup, miner, branch-name, ci-check",
    # Research/Analysis
    "codebase-overview": "Rapidly understand unfamiliar codebases",
    # codebase-analyzer: demoted to codebase-overview
    "pr-miner": "Mine PR comments for coding standards",
    "pr-mining-coordinator": "Coordinate PR mining operations",
    # Process
    "workflow": "Multi-step tasks, brainstorming, planning",
    "verification-before-completion": "Multiple validation layers before done",
    "read-only-ops": "Exploration and reporting without modifications",
    # skill-composer: demoted to workflow
    # Evaluation
    "agent-evaluation": "Evaluate agents/skills for quality",
    "agent-comparison": "A/B test agent variants",
    "roast": "5-persona constructive criticism",
    # Specialized
    "distinctive-frontend-design": "Unique aesthetics, avoid generic AI patterns",
    "professional-communication": "Transform technical to business formats",
    "service-health-check": "Service health, endpoint validation, CVE source auditing",
    "cron-automation": "Audit and create cron jobs with safety",
    "docs-sync-checker": "Verify all skills/agents documented",
    "routing-table-updater": "Maintain /do routing tables",
    # Plan Management
    "planning": "Planning umbrella: spec, pre-plan, plan-files, check, manage, pause, resume",
}


def classify_complexity(prompt: str) -> str:
    """Classify request complexity."""
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())

    if word_count < 10 and "?" in prompt:
        return "trivial"

    complex_signals = [
        "implement",
        "create",
        "build",
        "refactor",
        "review",
        "analyze",
        "debug",
        "fix",
        "add feature",
        "and also",
        "then",
        "first",
        "after that",
    ]

    complex_count = sum(1 for s in complex_signals if s in prompt_lower)

    if complex_count >= 2 or word_count > 50:
        return "complex"
    elif complex_count >= 1 or word_count > 20:
        return "medium"
    return "simple"


def get_evaluation_prompt(complexity: str) -> str:
    """Generate skill evaluation injection prompt."""

    # Group agents by category for readability
    agent_sections = (
        """
**Domain skills (worker: general-purpose; the skill carries the domain):**
"""
        + "\n".join(f"- {name}: {desc}" for name, desc in DOMAIN_SKILLS.items())
        + """
- Critique: roast skill (5 personas: contrarian, newcomer, builder, senior, pedant)"""
    )

    skill_sections = """
**Skills by Purpose:**
- Code Review: systematic-code-review, systematic-debugging, systematic-refactoring
- Quality Gates: go-patterns, python-quality-gate, universal-quality-gate
- Git: pr-workflow (umbrella: commit, codex-review, sync, status, fix, cleanup, miner, branch-name, ci-check)
- Process: workflow, verification-before-completion, test-driven-development
- Analysis: codebase-overview, agent-evaluation
- Cleanup: code-cleanup, comment-quality, code-linting"""

    phases = {
        "trivial": "",
        "simple": "**SIMPLE**: UNDERSTAND → EXECUTE → VERIFY",
        "medium": "**MEDIUM**: UNDERSTAND (restate) → PLAN (steps) → EXECUTE → VERIFY",
        "complex": """**COMPLEX** (ALL required):
1. UNDERSTAND: Request, criteria, assumptions
2. PLAN: Steps, tools, risks
3. EXECUTE: Show progress
4. VERIFY: Criteria met, no side effects""",
    }

    systematic = phases.get(complexity, "")

    return f"""<skill-evaluation-protocol>
EVALUATE before responding:
{agent_sections}
{skill_sections}

{systematic}

Route with: `skill: [name]`; dispatch the general-purpose agent with that skill
</skill-evaluation-protocol>"""


def should_skip(prompt: str) -> bool:
    """Determine if prompt should skip evaluation."""
    prompt_lower = prompt.lower().strip()

    if len(prompt_lower) < 20:
        return True

    skip_patterns = [
        "hello",
        "hi ",
        "hey ",
        "thanks",
        "thank you",
        "what is",
        "how do i",
        "can you explain",
        "help",
    ]

    if any(p in prompt_lower for p in skip_patterns):
        return True

    return bool(prompt_lower.endswith("?") and len(prompt_lower) < 50)


_BYPASS_ENV = "SKILL_EVALUATOR_BYPASS"


def main():
    """Process UserPromptSubmit hook event.

    DISABLED: The routing cheat sheet this hook injects (~1.8KB per prompt)
    is redundant. When /do is active, SKILL.md has full routing tables.
    When /do is NOT active, the user is talking directly and doesn't need
    routing guidance injected. The Agent tool descriptions in the system
    prompt already list all available agents.
    """
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[skill-evaluator] Bypassed via SKILL_EVALUATOR_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("skill-evaluator", e)
    finally:
        sys.exit(0)
