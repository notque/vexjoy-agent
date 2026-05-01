# Pipeline Orchestration — Preferred Patterns

<!-- no-pair-required: section-header-only; document title for preferred-patterns reference file -->

> **Scope**: Correct patterns for creating, scaffolding, and routing toolkit pipelines. Does NOT cover general Go/Python patterns — see those agents for language-specific issues.
> **Version range**: vexjoy-agent all versions
> **Generated**: 2026-04-09 — verify detection commands against current repo structure

---

## Overview

Pipeline creation mistakes compound: a missing discovery step leads to duplicated components, a skipped validation step leads to broken chains at runtime, and a missed routing step produces dead-code pipelines that no user can find. Most failures trace to one of three root causes: skipping Phase 1 discovery, dispatching sub-agents without full context, or treating the agent body as sufficient without reference files.

---

## Pattern Catalog

<!-- no-pair-required: section-header-only; individual patterns below carry detection and rationale blocks -->

### Include a Full Context Package in Every Sub-Agent Dispatch

Pass three things to every sub-agent: (1) the full component list from discovery, (2) the Discovery Report or Pipeline Spec, and (3) inter-component relationships. All three are required. Missing any one produces orphaned output.

```
Agent(
  description="Create Prometheus alerting skill",
  prompt=f"""
  Discovery Report: {discovery_report}
  Pipeline Spec: {spec_path}
  Components to create: alerting-skill.md
  Bound agent: prometheus-grafana-engineer
  Reuse: prometheus-grafana-engineer already handles metrics — bind, don't duplicate.
  Follow AGENT_TEMPLATE_V2.md structure exactly.
  """
)
```

**Why this matters**: A sub-agent dispatched without a discovery report starts with no knowledge of existing components, naming conventions, or inter-component relationships. The pipeline-creator A/B test validated this: agents dispatched without a Discovery Report produced orphaned components in 40% of runs.

**Detection**:
```bash
# Sub-agent dispatches missing spec/manifest/discovery references
grep -rn 'subagent_type' agents/ --include="*.md" | grep -v "spec\|manifest\|discovery"
```

---

### Run codebase-analyzer Before Scaffolding Any Component

Always run Phase 1 discovery before Phase 3 scaffolding. If any existing agent covers 80%+ of the request, bind it with new skills instead of creating a new agent. Duplicate agents create non-deterministic routing.

```bash
# Phase 1 discovery -- run before any scaffolding
python3 scripts/artifact-utils.py discover --domain prometheus
# OR invoke codebase-analyzer skill for full coverage scan
```

Then check: if an existing agent covers the domain, add reference files and skills to it. Creating a second agent for the same domain fragments the routing table and produces inconsistent behavior.

**Why this matters**: Two agents with overlapping triggers produce non-deterministic routing -- `/do` routes to whichever appears first in the table. Users get different behavior depending on routing order, which erodes trust in the system.

**Detection**:
```bash
# Compare agent count against codebase-analyzer output in ADRs
grep -rn 'codebase-analyzer' adr/ --include="*.md" | wc -l
ls agents/*.md | wc -l
# If analyzer mentions are low relative to agent count, discovery was likely skipped
```

---

### Create One Skill Per Subdomain, Not One Skill for Everything

Decompose multi-subdomain domains into N skills, one per subdomain. Same agent, different recipes. Each skill in `pairs_with: [the-umbrella-agent]`. This enables independent routing, independent context loading, and independent evaluation.

```yaml
# Correct: one skill per subdomain
prometheus-metrics-skill.md        # authoring and querying metrics
prometheus-alerting-skill.md       # alert rules, inhibition, routing
prometheus-operations-skill.md     # cluster ops, storage, retention
prometheus-dashboards-skill.md     # Grafana integration, panel patterns
```

**Why this matters**: Each subdomain has different task types needing different pipeline chains. A single skill handling 5 subdomains dilutes expertise, overloads context, and cannot be routed independently. The A/B test on parallel dispatch showed sequential single-skill approaches lose 1.40 points on Examples quality vs. parallel N-skill approaches.

**Detection**:
```bash
# Skills handling multiple subdomains (keywords "and" / "&" in description)
grep -rn 'description:' skills/*/SKILL.md | grep ' and \| & ' | grep -v "test\|spec"
```

---

### Validate the Chain Before Scaffolding

Run `validate-chain` on every composed pipeline chain before scaffolding any components. This catches type incompatibilities between steps at design time rather than at runtime, where they silently produce empty or malformed output.

```bash
python3 scripts/artifact-utils.py validate-chain \
  --chain "research,draft,review,publish" \
  --domain prometheus
```

Fix type mismatches by adding adapter steps or choosing compatible alternatives from the step menu before scaffolding.

**Why this matters**: A `research` step produces a `ResearchReport` artifact; a `review` step expects `DraftContent`. Connecting them directly produces a type mismatch that silently yields empty or malformed output. Composing chains "by intuition" works for simple cases but breaks on non-obvious type boundaries.

**Detection**:
```bash
# ADR files should contain chain validation output
grep -rn 'validate-chain\|chain.*pass\|chain.*valid' adr/ --include="*.md"
# Zero hits = validation was likely skipped
```

---

### Integrate Routing in the Same Session as Scaffolding

Phase 4 INTEGRATE is not optional. Run `routing-table-updater` in the same session as Phase 3 SCAFFOLD. Gate: all components must be routable via `/do` before the task is marked complete. "I'll add the routing entry in a follow-up PR" is how dead-code pipelines are born.

**Why this matters**: An unrouted pipeline is invisible. No trigger phrase reaches it. It exists as a file but is dead code -- users get no error, just wrong routing to an unrelated agent. Routing integration takes 2 minutes; recovering user trust in the routing system takes longer.

**Detection**:
```bash
# Agents in agents/ that have no entry in routing tables
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(grep -o '`[a-z-]*-engineer\|[a-z-]*-agent`' skills/do/references/routing-tables.md | tr -d '`' | sort)
```

---

### Set allowed-tools in Every Agent's Frontmatter

Match tools to the agent's role type per ADR-063. Reviewers and research agents get read-only tools. Code-modifying agents get full access. Agents without `allowed-tools` get the full tool set regardless of their role, which means a reviewer can silently modify files during review.

```yaml
# Reviewers / research agents -- read-only
allowed-tools:
  - Read
  - Glob
  - Grep
  - WebSearch

# Code-modifying agents -- full access
allowed-tools:
  - Read
  - Glob
  - Grep
  - Edit
  - Write
  - Bash
  - Agent
```

**Why this matters**: An agent without `allowed-tools` gets every tool. A read-only reviewer that can `Edit` and `Write` can silently modify files during review -- a violation of role separation that undermines the specialist model.

**Detection**:
```bash
# Agents missing allowed-tools field (ADR-063 compliance)
grep -rL 'allowed-tools' agents/*.md
```

---

### Fan Out Independent Components in Parallel

When scaffolding agent, skill, and hook files, dispatch all three in parallel using the Task tool. These are independent components with no data dependencies between them. Sequential execution wastes time.

**Why this matters**: Agent, skill, and hook files do not depend on each other's content during creation. Sequential scaffolding adds latency proportional to the number of components, with no quality benefit.

**Detection**: Review session logs for sequential dispatch of independent components. If agent creation, skill creation, and hook creation run back-to-back with no data dependency, they should be parallelized.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `validate-chain: type mismatch at step N` | Step N output type does not match step N+1 input type | Choose a compatible step from step-menu.md or add an adapter step |
| `routing-table-updater: trigger conflict with force-route` | New trigger overlaps existing force-route entry | Choose more specific trigger phrases; preserve existing force-routes |
| `audit-tool-restrictions: missing allowed-tools` | Agent frontmatter lacks `allowed-tools` | Add role-appropriate tool list per ADR-063 |
| `adr-enforcement: hash mismatch` | Pipeline Spec `adr_hash` doesn't match current ADR file | Recompute: `python3 ~/.claude/scripts/adr-query.py hash --adr {path}` |
| `skill-creator: template section missing` | Generated skill missing required frontmatter or operator context | Re-run with explicit `AGENT_TEMPLATE_V2.md` reference |
| Duplicate Component Detected | codebase-analyzer found an existing agent/skill covering the requested pipeline's purpose | Bind the existing component instead of creating a new one. Report the reuse decision to the user |
| Chain Validation Failure | A composed pipeline chain has type incompatibilities between steps | Re-invoke the `workflow` skill (composition phase) with the failing chain and the validation error |
| Domain Research Insufficient | The `workflow` skill returned fewer than 2 subdomains | The domain may be too narrow for multi-subdomain treatment. Fall back to single-pipeline mode |

---

## Detection Commands Reference

```bash
# Sub-agents dispatched without context package
grep -rn 'subagent_type' agents/ --include="*.md" | grep -v "spec\|manifest\|discovery"

# Agents without tool restrictions (ADR-063)
grep -rL 'allowed-tools' agents/*.md

# Agents not registered in routing tables
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(grep -oP '[a-z-]+-engineer|[a-z-]+-agent' skills/do/references/routing-tables.md | sort -u)

# Skills that bundle multiple subdomains (should be split)
grep -rn 'description:' skills/*/SKILL.md | grep ' and \| & '

# Chains not validated before scaffolding (check ADR coverage)
grep -rn 'validate-chain' adr/ --include="*.md"
```

---

## See Also

- `orchestration-patterns.md` — correct fan-out/fan-in patterns and gate idioms
- `skills/workflow/references/step-menu.md` — valid pipeline steps and their type signatures
- `scripts/artifact-utils.py` — chain validation and discovery utilities
