# Pipeline Orchestration — Fan-Out/Fan-In Patterns

> **Scope**: Concrete patterns for dispatching parallel sub-agents, collecting outputs, and enforcing phase gates. Covers the orchestrator role only — not individual component templates.
> **Version range**: claude-code-toolkit all versions
> **Generated**: 2026-04-09 — verify Agent tool parameter names against current SDK

---

## Overview

Pipeline orchestration is structurally a fan-out/fan-in problem: independent components (agents, skills, hooks) can be scaffolded in parallel, then integrated at a fan-in gate. The orchestrator's job is to prepare context packages, dispatch sub-agents, enforce gates, and merge outputs. The most common failure is dispatching without context — sub-agents produce orphaned components that can't be integrated.

---

## Pattern Table

| Pattern | When | Avoid When |
|---------|------|------------|
| Fan-out by creator type | 3+ independent components | Single component — unnecessary overhead |
| Context package pre-flight | Every sub-agent dispatch | Never skip — not optional |
| Hard gate before fan-in | Phase 3→4 transition | Never skip — missing files discovered at routing break integration |
| ADR hash embed | Domain pipelines (full 7-phase) | Simple single-skill pipelines (Phase 0→1→3→4) |
| Sequential within sub-agent | When one component depends on another | Components of the same type (parallel by default) |

---

## Correct Patterns

### Fan-Out by Creator Type

Group components by who creates them, dispatch one sub-agent per creator type in parallel.

```
Orchestrator
  ├── skill-creator (all new agents + skills)    ← parallel
  ├── hook-development-engineer (all hooks)       ← parallel
  └── Direct (Python scripts)                     ← parallel

Gate: wait for ALL three before Phase 4 INTEGRATE
```

**Why**: These are fully independent — no component type depends on another during creation. Sequential scaffolding is pure waste. The gate before integration ensures you're not wiring a half-built system.

---

### Context Package Structure

Every sub-agent dispatch must include all four fields:

```python
Agent(
  description="Create {N} skills for {domain}",
  prompt=f"""
  ## Context Package

  ### Components to Create
  {component_list}  # Full list with names, purposes, and bound agents

  ### Discovery Report
  {discovery_report}  # What exists — what to reuse, what to skip

  ### Inter-Component Relationships
  {relationships}  # Which agent binds which skill; which hook triggers which agent

  ### Template Reference
  Follow AGENT_TEMPLATE_V2.md for agents. Standard frontmatter + operator context for skills.
  Required sections: frontmatter, operator context, capabilities, error handling, anti-patterns.

  ### Architecture Rules
  See skills/workflow/references/architecture-rules.md.
  Critical: Rule 12 (parallel research), Rule 18 (ADR hash), ADR-063 (tool restrictions).
  """
)
```

**Why**: Sub-agents have no shared context with the orchestrator. Each starts fresh. Without the discovery report, it will create duplicates. Without inter-component relationships, it will produce orphaned files. Without the template reference, it will produce non-compliant agents.

---

### Phase Gate Enforcement

Gates are explicit checks, not assumptions.

```bash
# Gate: Phase 3 → Phase 4 (after SCAFFOLD, before INTEGRATE)
# Verify every expected file exists
for component in "${expected_components[@]}"; do
  if [[ ! -f "$component" ]]; then
    echo "GATE FAIL: $component missing — do not proceed to Phase 4"
    exit 1
  fi
done

# Verify template compliance for agents
python3 scripts/validate-references.py --agent {name}

# Verify hook syntax
for hook in hooks/{pipeline-name}*.py; do
  python3 -c "import ast; ast.parse(open('$hook').read())" || echo "Syntax error: $hook"
done
```

**Why**: Missing files discovered during routing integration cause partial pipelines. Broken hooks discovered after install deadlock the session (see: deploy-hooks-before-register retro). The gate costs 30 seconds. A partial integration costs a session restart.

---

### ADR Context Injection for Critical Sub-Agents

For complex pipelines, pre-populate sub-agent prompts with role-targeted ADR context:

```bash
# Get role-targeted context for a skill-creator sub-agent
adr_context=$(python3 ~/.claude/scripts/adr-query.py context \
  --adr adr/{pipeline-name}.md \
  --role skill-creator)

# Prepend to sub-agent prompt
Agent(
  description="Create skills per Pipeline Spec",
  prompt=f"{adr_context}\n\n## Task\n{task_description}"
)
```

**Why**: The `adr-context-injector.py` hook handles this automatically for most sub-agents once `adr-query.py register` runs. Manual injection is only needed when a sub-agent needs the full ADR section relevant to its specific role, not just the session-level context.

---

### Simple vs. Domain Pipeline Decision

```
Is the request for a single skill/agent with one clear purpose?
  YES → Simple pipeline: Phase 0 → Phase 1 (legacy discover) → Phase 3 → Phase 4
        Skip Phases 2, 5, 6. No subdomain decomposition needed.

  NO / "Create pipelines for {broad domain}" →
        Domain pipeline: Full 7-phase flow. Requires:
        - Phase 1: workflow skill (research phase) → Component Manifest with 2+ subdomains
        - Phase 2: workflow skill (composition phase) → Pipeline Spec JSON with validate-chain
        - Phase 3: workflow skill (scaffolder phase) → enforces ADR hash gate
        - Phases 5-6: test-runner + retro → generator improvements
```

**Why**: Domain pipelines need subdomain decomposition because different subdomains have different task types. Applying simple-pipeline flow to a domain produces a monolithic skill that handles conflicting task types badly. Applying domain-pipeline flow to a single skill creates unnecessary overhead (4+ research agents for a trivial request).

---

## Anti-Pattern Catalog

### ❌ Fan-Out Without Waiting for All Sub-Agents

**Detection**:
```bash
# In pipeline orchestration code, look for synthesis before all agents complete
grep -rn 'integrate\|routing-table' agents/pipeline-orchestrator-engineer.md | head -5
# Conceptually: synthesis lines appearing before all agent completions
```

**What it looks like**: Starting Phase 4 INTEGRATE after only 2 of 3 scaffolding sub-agents complete (e.g., skills and hooks done, but agent manifest still running).

**Why wrong**: Partial integration produces inconsistent routing. An agent registered in INDEX.json that doesn't yet exist on disk will cause Agent tool failures. A skill registered in routing-tables.md whose agent isn't created yet produces "unknown agent" errors at dispatch time.

**Do instead**: Hard gate — `wait for ALL dispatched agents to complete` before any integration step. There is no acceptable partial state.

---

### ❌ Skipping Phase 0 ADR for Domain Pipelines

**Detection**:
```bash
# Domain pipeline PRs without a corresponding ADR file
# (ADR files are gitignored — check local disk)
ls adr/pipeline-*.md 2>/dev/null | wc -l
```

**What it looks like**: Starting Phase 1 research without creating `adr/pipeline-{name}.md` first.

**Why wrong**: Without an ADR, context drifts across phases. Phase 3 sub-agents don't know the Phase 2 decisions. The component manifest from Phase 1 gets lost between phases. In sessions longer than 30 minutes, orchestrators re-derive decisions already made in earlier phases — wasting context and sometimes reversing earlier conclusions.

**Do instead**: Phase 0 is always Phase 0. Create the ADR file, register the session:
```bash
python3 ~/.claude/scripts/adr-query.py register --adr adr/{pipeline-name}.md
```
The hook auto-injects ADR context into all subsequent sub-agent prompts — preventing context drift for free.

---

### ❌ Decomposing Too Aggressively (Pipeline Overhead for Trivial Requests)

**Detection**:
```bash
# Pipelines with 5+ components for a single-purpose use case
# Check: does the domain have genuinely distinct task types?
python3 scripts/artifact-utils.py discover --domain {name} 2>/dev/null | grep "subdomains"
```

**What it looks like**: Creating 4 sub-agents, a hook, and 3 scripts for a request that needed one skill bound to an existing agent.

**Why wrong**: Over-decomposition creates maintenance overhead. Each component needs its own routing entry, its own template compliance check, its own reference files. A pipeline with 8 components for a 2-component problem adds 6 units of maintenance debt with zero user benefit.

**Do instead**: Apply the 80% coverage rule — if an existing agent covers 80%+ of the request, bind new skills to it rather than creating new agents. Three reused components beat one new monolithic agent.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Agent tool: unknown subagent_type` | Sub-agent created during session not yet available | Restart Claude Code session; new agents load at startup only |
| `python3 -c "import hooks/X"` fails | Hook file has syntax error or wrong import path | Check `hooks/lib/hook_utils.py` base class; run `python3 -m py_compile hooks/X.py` |
| `routing-table-updater: no triggers found` | New agent/skill has no `triggers:` in frontmatter | Add `routing.triggers` list to agent/skill frontmatter |
| Fan-in incomplete — orphaned component | Sub-agent completed but file at wrong path | Check sub-agent's actual output path vs. expected; rename or move |
| `validate-chain: unknown step type` | Chain references a step not in step-menu.md | Run `python3 scripts/artifact-utils.py list-steps` to see valid options |

---

## Detection Commands Reference

```bash
# Verify all expected components were created after Phase 3
for f in agents/{name}.md skills/{name}/SKILL.md hooks/{name}*.py; do
  [[ -f "$f" ]] && echo "OK: $f" || echo "MISSING: $f"
done

# Verify all agents in INDEX.json
python3 -c "
import json
data = json.load(open('agents/INDEX.json'))
names = {a['name'] for a in data['agents']}
print(f'Indexed agents: {len(names)}')
"

# Find unindexed agents
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(python3 -c "import json; [print(a['name']) for a in json.load(open('agents/INDEX.json'))['agents']]" | sort)

# Check ADR session is registered
ls -la .adr-session.json 2>/dev/null || echo "ADR session not registered"
```

---

## Phase 4 — Integration Verification Checklist

After wiring all components, run these checks before declaring Phase 4 complete:

- Confirm ALL agents appear in `agents/INDEX.json`
- Confirm routing entries match trigger keywords in `skills/do/SKILL.md` and `skills/do/references/routing-tables.md`
- Confirm ALL hook files are syntactically valid Python: `python3 -c "import hooks/{name}"`
- Confirm ALL skills follow frontmatter + operator context pattern
- Confirm component graph has no orphans (every component referenced by at least one other)

---

## Phase 3 — Creator Sub-Agent Table

Group components by creator type before dispatching:

| Creator Sub-Agent | Components It Creates | Template |
|-------------------|----------------------|----------|
| `skill-creator` | All new agent manifests (1..N) and skill SKILL.md files + references (1..M) | `AGENT_TEMPLATE_V2.md` / Standard skill format |
| `hook-development-engineer` | All new Python hooks (1..K) | `hooks/lib/hook_utils.py` conventions |
| Direct (orchestrator) | Python scripts (1..J) | `scripts/` conventions |

For domain pipelines, the Pipeline Spec tells exactly what to create. Use `skills/workflow/references/generated-skill-template.md` (when it exists) as the template for each subdomain skill.

**For each sub-agent, provide**:
- Complete list of components to create (names, purposes, relationships)
- Discovery Report / Pipeline Spec (so it knows what to reuse and what chains to embed)
- Bound skills/agents (from reuse list)
- Patterns to follow (from `skills/workflow/references/architecture-rules.md`)
- Inter-component relationships (which agent binds which skill, which hook triggers which agent)

---

## ADR Template (Phase 0)

Create `adr/pipeline-{name}.md` with the following structure:

```markdown
# ADR: Pipeline {Name}

## Status
PROPOSED | ACCEPTED | IMPLEMENTED | DEPRECATED

## Context
[Why this pipeline is needed. What problem it solves. What triggered its creation.]

## Decision
[The pipeline design: components, flow, triggers, integration points.]

## Component Manifest
[Full list of agents, skills, hooks, scripts to create — updated as discovery proceeds.]

## Constraints
- [Architectural constraints from architecture-rules.md]
- [Existing components that must be reused]
- [Naming conventions to follow]

## Consequences
- [What changes in the routing system]
- [What new triggers are introduced]
- [What existing pipelines are affected]

## Test Plan
[How this pipeline will be validated after creation]
```

---

## Capabilities Summary

**CAN Do**: Orchestrate creation of complete pipelines with multiple agents, skills, hooks, scripts, and reference docs; plan a full component graph; fan out scaffolding tasks to `skill-creator` and `hook-development-engineer` in parallel (multiple instances); detect and reuse existing components via `codebase-analyzer`; integrate new pipelines into `/do` routing via `routing-table-updater`; generate Python scripts for deterministic operations; research domains to discover subdomains via `workflow` skill; compose valid pipeline chains from the step menu; produce N skills per domain (one per subdomain); validate chain type compatibility.

**CANNOT Do**: Write domain-specific business logic (route to domain agents); modify existing pipelines (use the specific agent/skill directly); create pipelines without routing integration (every pipeline must be routable via `/do`); compose chains without validation (must use `workflow` skill and `validate-chain` script); create monolithic single-skill pipelines for multi-subdomain domains.

---

## Output Format

This agent uses the **Planning Schema**.

**Required Sections**:
1. Discovery Report / Domain Research — what exists, what subdomains were found, what to reuse, what to create
2. Pipeline Spec (domain pipelines) — validated chains per subdomain
3. Execution Plan — fan-out assignments with component specs
4. Integration Checklist — routing entries, index updates
5. Completion Report — what was created, usage examples
6. Session Restart Notice — MANDATORY final output (see below)

**Session Restart Notice (MANDATORY)**: After every pipeline creation, the LAST thing output MUST be this notice verbatim (fill in `{agent-name}` and `{trigger phrase}`):

```
SESSION RESTART REQUIRED
New agent '{agent-name}' was created and synced to ~/.claude/agents/.
Claude Code compiles available subagent types at session startup:
agents added during a session are NOT available as subagent_type
until the next session.

To use this pipeline:
  1. Restart Claude Code (Ctrl+C, then rerun `claude`)
  2. Then invoke: /do {trigger phrase}

The agent will be available immediately after restart.
```

This notice applies even if the pipeline has no new agent (skill-only pipelines are immediately available).

---

## See Also

- `anti-patterns.md` — common pipeline creation mistakes with detection commands
- `skills/workflow/references/step-menu.md` — valid steps and type signatures
- `skills/workflow/references/architecture-rules.md` — all 18+ architecture rules
- `scripts/artifact-utils.py` — discovery, chain validation, step listing utilities
