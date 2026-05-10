#!/usr/bin/env python3
"""Prompt builder for /do routing pipeline.

Generates complete prompts for Haiku routing, routing banners,
worker agent dispatch, and task specifications. All templates
live in this script — zero LLM context cost until called.

Usage:
    python3 scripts/do-build-prompt.py --mode haiku-prompt --request "..." --manifest "..."
    python3 scripts/do-build-prompt.py --mode routing-banner --agent X --skill Y --reasoning "..."
    python3 scripts/do-build-prompt.py --mode agent-prompt --agent X --skill Y --request "..."
    python3 scripts/do-build-prompt.py --mode task-spec --request "..." --complexity Medium
"""

from __future__ import annotations

import argparse
import sys

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

HAIKU_PROMPT = """\
You are a routing agent. Given a user request and a manifest of available \
agents, skills, and pipelines, select the BEST agent+skill combination.

USER REQUEST: {request}

ROUTING MANIFEST:
{manifest}

Return your answer as JSON:
{{
  "agent": "agent-name or null",
  "skill": "skill-name or null",
  "pipeline": "pipeline-name or null",
  "reasoning": "one sentence why",
  "confidence": "high/medium/low"
}}

FORCE-ROUTE RULE: Entries marked "FORCE" in the manifest MUST be selected \
when their domain clearly matches the user's intent. FORCE matching is \
SEMANTIC, not keyword-based — match what the user MEANS, not individual words.
Examples:
- "push my changes" → pr-workflow (FORCE) ✓ (git push)
- "push back on this design" → NOT pr-workflow (resist/argue)
- "quick fix to the login page" → quick (FORCE) ✓ (small edit)
- "quick overview of the architecture" → NOT quick (exploration)

Rules:
- Most specific match wins. "Go tests" → golang-general-engineer + go-patterns.
- Agent = domain. Skill = methodology. Pick both when possible.
- Task verb (review, debug, refactor, test) → prefer matching skill.
- No match → return all nulls with reasoning.
- Semantic match over keyword overlap.
- Git ops (push, commit, PR, merge) → ALWAYS pr-workflow.
- Return a single skill name string, not an array."""


BANNER = """\
===================================================================
 ROUTING: {summary}
===================================================================
 Selected:
   -> Agent: {agent}{agent_detail}
   -> Skill: {skill}{skill_detail}
{extra} Invoking...
==================================================================="""


AGENT_INJECTIONS = """\
Load `agents/base-instructions.md` for universal operational rules.
Read your agent .md file's Reference Loading Table. Load EVERY matching reference.
Deliver the finished product. Ship the complete thing.
Write dense: high fidelity, minimum words. Cut filler, prefer tables, report what changed."""


TASK_SPEC = """\
## Task Specification (auto-extracted)

**Intent:** {intent}
**Constraints:** {constraints}
**Acceptance criteria:** {acceptance}
**Operator context:** {operator_context}"""


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_haiku_prompt(request: str, manifest: str) -> str:
    """Build the Haiku routing agent prompt."""
    return HAIKU_PROMPT.format(request=request, manifest=manifest)


def build_routing_banner(
    agent: str,
    skill: str,
    reasoning: str,
    pipeline: str | None = None,
    rigor: str | None = None,
) -> str:
    """Build the user-visible routing decision banner."""
    summary = f"{agent} + {skill}" if skill else agent
    extra = ""
    if pipeline:
        extra += f"   -> Pipeline: {pipeline}\n"
    if rigor:
        extra += f"   -> Extra Rigor: {rigor}\n"
    return BANNER.format(
        summary=summary,
        agent=agent,
        agent_detail=f" - {reasoning}" if reasoning else "",
        skill=skill or "none",
        skill_detail=f" - {reasoning}" if reasoning else "",
        extra=extra,
    )


def build_task_spec(
    request: str,
    complexity: str,
    constraints: str | None = None,
    operator_context: str | None = None,
) -> str:
    """Build the task specification block for Medium+ tasks."""
    intent = request.split(".")[0].strip() if "." in request else request.strip()
    if len(intent) > 120:
        intent = intent[:117] + "..."

    return TASK_SPEC.format(
        intent=intent,
        constraints=constraints or "branch safety (do not merge to main)",
        acceptance="observable: task completed, no errors",
        operator_context=operator_context or "personal — full autonomy",
    )


def build_agent_prompt(
    agent: str,
    skill: str,
    complexity: str,
    request: str,
    thinking: str | None = None,
    enhancements: str | None = None,
    local_only: bool = False,
    constraints: str | None = None,
    operator_context: str | None = None,
) -> str:
    """Build the complete worker agent dispatch prompt."""
    parts: list[str] = []

    # Thinking directive first (verbatim, no framing)
    if thinking:
        parts.append(thinking)
        parts.append("")

    # Local-only constraint
    if local_only:
        parts.append(
            "**LOCAL-ONLY MODE.** Do not push, commit, create PRs, or deploy. "
            "All work stays on disk. Read-only git is fine."
        )
        parts.append("")

    # Standard injections
    parts.append(AGENT_INJECTIONS)
    parts.append("")

    # Task specification for Medium+
    if complexity in ("Medium", "Complex"):
        parts.append(build_task_spec(request, complexity, constraints, operator_context))
        parts.append("")

    # The request itself
    parts.append("## Request")
    parts.append(request)

    # Skill methodology
    if skill:
        parts.append("")
        parts.append(f"Use the `{skill}` skill methodology for this task.")

    # Enhancements
    if enhancements:
        parts.append("")
        parts.append(f"Additional skills to apply: {enhancements}")

    # Commit instruction
    parts.append("")
    parts.append("Commit your changes on the branch.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Build prompts for /do routing pipeline")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["haiku-prompt", "routing-banner", "agent-prompt", "task-spec"],
    )
    parser.add_argument("--request", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--agent", default="")
    parser.add_argument("--skill", default="")
    parser.add_argument("--complexity", default="Simple")
    parser.add_argument("--thinking", default="")
    parser.add_argument("--enhancements", default="")
    parser.add_argument("--reasoning", default="")
    parser.add_argument("--pipeline", default="")
    parser.add_argument("--rigor", default="")
    parser.add_argument("--constraints", default="")
    parser.add_argument("--operator-context", default="")
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()

    if args.mode == "haiku-prompt":
        print(build_haiku_prompt(args.request, args.manifest))

    elif args.mode == "routing-banner":
        print(
            build_routing_banner(
                args.agent,
                args.skill,
                args.reasoning,
                args.pipeline or None,
                args.rigor or None,
            )
        )

    elif args.mode == "agent-prompt":
        print(
            build_agent_prompt(
                args.agent,
                args.skill,
                args.complexity,
                args.request,
                args.thinking or None,
                args.enhancements or None,
                args.local_only,
                args.constraints or None,
                args.operator_context or None,
            )
        )

    elif args.mode == "task-spec":
        print(
            build_task_spec(
                args.request,
                args.complexity,
                args.constraints or None,
                args.operator_context or None,
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
