"""Antigravity CLI (agy) Python run_workflow template for parallel fan-out and synthesis.

Counterpart to skills/process/workflow/references/fan-out-workflow.js for the
Antigravity `run_workflow` tool (Python async orchestration).

Runtime globals provided by Antigravity's `run_workflow` harness:
  - phase(title: str) -> None
  - await agent(prompt: str, *, schema: dict | type | None = None,
                role: str | None = None, type_name: str = "self",
                workspace: str = "inherit", model: str = "inherit")
  - await parallel(coroutines_or_callables)
  - trajectory(agent_result) -> list[dict]

Every worker prompt begins with a line-anchored `[do-route]` marker so
`hooks/agy-hook-adapter.py` + `hooks/routing-decision-recorder.py` record one
routing decision row per dispatched specialist.
"""

from __future__ import annotations

import json
import re
from typing import Any

MAX_ROSTER_SIZE = 10
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title"],
    "properties": {
        "title": {"type": "string"},
        "location": {"type": "string"},
        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
        "detail": {"type": "string"},
    },
}

WORKER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["verdict", "summary"],
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "CONCERN", "BLOCK", "INFO"]},
        "summary": {"type": "string", "minLength": 1},
        "findings": {"type": "array", "items": FINDING_SCHEMA},
        "lens": {"type": "string"},
    },
}

SYNTH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["verdict", "summary"],
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "CONCERN", "BLOCK", "INFO"]},
        "summary": {"type": "string", "minLength": 1},
        "key_findings": {"type": "array", "items": FINDING_SCHEMA},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
}

MANDATORY_INJECTIONS = (
    "\n\nBefore starting work, consult the Reference Loading Table in your agent .md file "
    "and read the references that match this task.\n\n"
    "Deliver the finished product. Ship the complete thing.\n\n"
    "Follow the Dense-Complete Writing rules in `agents/base-instructions.md`.\n\n"
    "Follow its Google Developer Documentation Style rules and precedence.\n\n"
    "Before starting work, also load `agents/base-instructions.md` for universal operational rules.\n\n"
    "End your reply with this exact final line, nothing after it: "
    "`route-fit: <ok|wrong-agent|wrong-skill|needs-coordinator|underspecified>` — "
    "your honest read of whether this agent and skill fit the task."
)


def validate_name(value: str, label: str) -> str:
    """Validate an agent or skill identifier against [a-z0-9][a-z0-9-]*."""
    cleaned = str(value or "").strip().lower()
    if not cleaned or not _NAME_RE.match(cleaned):
        raise ValueError(f"Invalid {label}: {value!r}")
    return cleaned


def validate_roster(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate the caller-supplied specialist roster (1..MAX_ROSTER_SIZE)."""
    if not isinstance(roster, list) or not (1 <= len(roster) <= MAX_ROSTER_SIZE):
        raise ValueError(f"roster must be a non-empty list of at most {MAX_ROSTER_SIZE} entries")
    validated: list[dict[str, Any]] = []
    for entry in roster:
        agent_type = validate_name(entry.get("agentType", ""), "agentType")
        raw_skills = entry.get("skills") or []
        if not isinstance(raw_skills, list) or not raw_skills:
            raise ValueError(f"roster entry for {agent_type!r} requires at least one skill")
        skills = [validate_name(s, "skill") for s in raw_skills]
        validated.append(
            {
                "agentType": agent_type,
                "skills": skills,
                "lens": str(entry.get("lens") or "").strip(),
                "workspace": str(entry.get("workspace") or "inherit").strip(),
                "model": str(entry.get("model") or "inherit").strip(),
            }
        )
    return validated


def build_worker_prompt(entry: dict[str, Any], scope: dict[str, Any], complexity: str = "complex") -> str:
    """Build a worker prompt with a line-start [do-route] marker and mandatory injections."""
    primary_skill = entry["skills"][0]
    stack = entry["skills"][1:]
    stack_token = f" stack={{{','.join(stack)}}}" if stack else ""
    model_token = entry.get("model") or "gemini-4-argon"
    marker = (
        f"[do-route] agent={entry['agentType']} skill={primary_skill} "
        f"complexity={complexity} model={model_token} health=-{stack_token}"
    )
    skill_calls = "\n".join(f"Load and follow the `{s}` skill (`skills/{s}/SKILL.md`)." for s in entry["skills"])
    lens = f"Apply this lens: {entry['lens']}." if entry.get("lens") else "Apply your specialist lens."
    return (
        f"{marker}\n\n"
        f"You are `{entry['agentType']}` (`agents/{entry['agentType']}.md`). {lens}\n"
        f"{skill_calls}\n\n"
        f"## Task Specification (auto-extracted)\n\n"
        f"**Request (verbatim):** {scope.get('request_verbatim', scope.get('intent', 'Execute assigned scope'))}\n"
        f"**Intent:** {scope.get('intent', 'Complete specialist analysis and implementation within lens.')}\n"
        f"**Acceptance criteria:** Return schema-valid output with concrete file:line evidence.\n"
        f"**Relevant file locations:** {scope.get('files', '.')}\n"
        f"**Decisions:** {scope.get('decisions', 'Follow repository conventions.')}\n"
        f"**Prior results:** {scope.get('prior_results', 'None')}\n\n"
        f"## Repo state\n\n"
        f"Work this scope:\n{json.dumps(scope, indent=2)}"
        f"{MANDATORY_INJECTIONS}"
    )


async def run_fan_out_workflow(
    *,
    scope: dict[str, Any],
    roster: list[dict[str, Any]],
    synth_agent_type: str = "research-coordinator-engineer",
    tier: int | None = None,
    phase_fn: Any = None,
    agent_fn: Any = None,
    parallel_fn: Any = None,
    trajectory_fn: Any = None,
) -> dict[str, Any]:
    """Execute parallel specialist fan-out followed by typed in-memory synthesis."""
    workers = validate_roster(roster)
    synthesizer = validate_name(synth_agent_type, "synth_agent_type")

    _phase = phase_fn or globals().get("phase")
    _agent = agent_fn or globals().get("agent")
    _parallel = parallel_fn or globals().get("parallel")
    _trajectory = trajectory_fn or globals().get("trajectory")

    if callable(_phase):
        _phase("fan-out")

    async def _invoke_worker(w: dict[str, Any]) -> Any:
        prompt = build_worker_prompt(w, scope)
        return await _agent(
            prompt,
            schema=WORKER_SCHEMA,
            role=f"{w['agentType']} ({w['lens'] or w['skills'][0]})",
            type_name=w.get("type_name", "self"),
            workspace=w.get("workspace", "inherit"),
            model=w.get("model", "inherit"),
        )

    if callable(_parallel):
        raw_results = await _parallel([_invoke_worker(w) for w in workers])
    else:
        raw_results = [await _invoke_worker(w) for w in workers]

    results = [r for r in raw_results if r is not None]
    trajectories = [_trajectory(r) for r in results] if callable(_trajectory) else []

    if callable(_phase):
        _phase("synthesize")

    synthesis = None
    if results and callable(_agent):
        synth_prompt = (
            f"You are `{synthesizer}`. Synthesize these {len(results)} typed specialist results "
            f"into one verdict + summary. Merge overlapping findings, preserve the highest severity, "
            f"and provide actionable recommendations.\n\n"
            f"Typed specialist results:\n{json.dumps(results, indent=2)}"
            f"{MANDATORY_INJECTIONS}"
        )
        synthesis = await _agent(
            synth_prompt,
            schema=SYNTH_SCHEMA,
            role=f"Synthesizer ({synthesizer})",
            type_name="self",
            workspace="inherit",
            model="inherit",
        )

    return {
        "tier": tier,
        "workers_ran": len(results),
        "roster": workers,
        "trajectory_steps": [len(t) for t in trajectories if isinstance(t, list)],
        "synthesis": synthesis,
    }
