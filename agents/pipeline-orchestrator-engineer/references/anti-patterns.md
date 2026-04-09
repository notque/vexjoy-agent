# Pipeline Orchestration — Anti-Patterns

> **Scope**: Common mistakes when creating, scaffolding, and routing toolkit pipelines. Does NOT cover general Go/Python anti-patterns — see those agents for language-specific issues.
> **Version range**: claude-code-toolkit all versions
> **Generated**: 2026-04-09 — verify detection commands against current repo structure

---

## Overview

Pipeline creation mistakes compound: a missing discovery step leads to duplicated components, a skipped validation step leads to broken chains at runtime, and a missed routing step produces dead-code pipelines that no user can find. Most failures trace to one of three root causes: skipping Phase 1 discovery, dispatching sub-agents without full context, or treating the agent body as sufficient without reference files.

---

## Anti-Pattern Catalog

### ❌ Dispatching Sub-Agents Without Context Package

**Detection**:
```bash
# Look for agent dispatch calls missing spec/manifest references in a worktree
grep -rn 'subagent_type' agents/ --include="*.md" | grep -v "spec\|manifest\|discovery"
```

**What it looks like**:
```
Agent(description="Create skill", prompt="Create a skill for Prometheus alerting.")
```

**Why wrong**: The sub-agent starts with no knowledge of existing components, naming conventions, or inter-component relationships. It will create components that conflict with or duplicate existing ones. The pipeline-creator A/B test validated this: agents dispatched without a Discovery Report produced orphaned components in 40% of runs.

**Fix**:
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

**Version note**: Required context package: (1) full component list, (2) Discovery Report or Pipeline Spec, (3) inter-component relationships. All three required. Missing any one produces orphaned output.

---

### ❌ Skipping `codebase-analyzer` Before Scaffolding

**Detection**:
```bash
# PRs that add agents without codebase-analyzer output in the ADR
grep -rn 'codebase-analyzer' adr/ --include="*.md" | wc -l
# If count is low relative to agent count, discovery was likely skipped
ls agents/*.md | wc -l
```

**What it looks like**: Creating `monitoring-engineer.md` when `prometheus-grafana-engineer.md` already exists with 80% coverage.

**Why wrong**: Creates a duplicate routing entry. Two agents with overlapping triggers produce non-deterministic routing — `/do` will route to whichever appears first in the routing table. Users get inconsistent behavior. The duplicate is harder to merge later than to prevent now.

**Fix**: Always run Phase 1 before Phase 3:
```bash
# In Phase 1
python3 scripts/artifact-utils.py discover --domain prometheus
# OR invoke codebase-analyzer skill for full coverage scan
```

Then check: if any existing agent covers 80%+ of the request, bind it with new skills instead of creating a new agent.

---

### ❌ Single Skill for Multi-Subdomain Domain

**Detection**:
```bash
# Skills that handle more than one distinct task type in their frontmatter description
grep -rn 'description:' skills/*/SKILL.md | grep ' and \| & ' | grep -v "test\|spec"
```

**What it looks like**:
```yaml
name: prometheus-skill
description: "Prometheus: metrics, alerting, dashboards, operations, performance tuning"
```

**Why wrong**: Each subdomain has different task types needing different pipeline chains. A skill handling 5 subdomains dilutes expertise, overloads context, and can't be routed independently. The A/B test on parallel dispatch showed sequential single-skill approaches lose 1.40 points on Examples quality vs. parallel N-skill approaches.

**Fix**: Decompose into N skills per domain:
```
prometheus-metrics-skill.md        — authoring and querying metrics
prometheus-alerting-skill.md       — alert rules, inhibition, routing
prometheus-operations-skill.md     — cluster ops, storage, retention
prometheus-dashboards-skill.md     — Grafana integration, panel patterns
```

Same agent, different recipes. Each skill in `pairs_with: [prometheus-grafana-engineer]`.

---

### ❌ Skipping `validate-chain` Before Scaffolding

**Detection**:
```bash
# Check if ADR files contain chain validation output
grep -rn 'validate-chain\|chain.*pass\|chain.*valid' adr/ --include="*.md"
# Zero hits = validation was likely skipped
```

**What it looks like**: Composing a chain intuitively — `research → draft → review → publish` — without checking that each step's output type matches the next step's expected input type.

**Why wrong**: Type incompatibilities surface at runtime, not during scaffolding. A `research` step produces a `ResearchReport` artifact; a `review` step expects `DraftContent`. Connecting them directly produces a type mismatch that silently produces empty or malformed output.

**Fix**:
```bash
python3 scripts/artifact-utils.py validate-chain \
  --chain "research,draft,review,publish" \
  --domain prometheus
```

Fix type mismatches by adding adapter steps or choosing compatible alternatives from the step menu before scaffolding.

---

### ❌ Routing Integration After Session End

**Detection**:
```bash
# Agents in agents/ that have no entry in skills/do/references/routing-tables.md
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(grep -o '`[a-z-]*-engineer\|[a-z-]*-agent`' skills/do/references/routing-tables.md | tr -d '`' | sort)
```

**What it looks like**: "I'll add the routing entry in a follow-up PR."

**Why wrong**: An unrouted pipeline is invisible. No trigger phrase reaches it. It exists as a file but is dead code — users get no error, just wrong routing to an unrelated agent. Routing integration takes 2 minutes; recovering user trust in the routing system takes longer.

**Fix**: Phase 4 INTEGRATE is not optional. Run `routing-table-updater` in the same session as Phase 3 SCAFFOLD. Gate: all components routable via `/do` before task is marked complete.

---

### ❌ Creating Agents Without `allowed-tools` Frontmatter

**Detection**:
```bash
# Agents missing allowed-tools field (ADR-063 compliance)
python3 ~/.claude/scripts/audit-tool-restrictions.py --audit 2>/dev/null | grep "missing"
# OR manually:
grep -rL 'allowed-tools' agents/*.md
```

**What it looks like**:
```yaml
---
name: my-new-agent
model: sonnet
description: "..."
---
```

**Why wrong**: Agents without `allowed-tools` get the full tool set regardless of their role. A read-only reviewer agent that can Edit/Write/Bash can silently modify files during review — a violation of the reviewer role. ADR-063 mandates tool restriction by role type.

**Fix**: Match tools to role:
```yaml
allowed-tools:  # for reviewers / research agents
  - Read
  - Glob
  - Grep
  - WebSearch

allowed-tools:  # for code-modifying agents
  - Read
  - Glob
  - Grep
  - Edit
  - Write
  - Bash
  - Agent
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `validate-chain: type mismatch at step N` | Step N output type ≠ step N+1 input type | Choose a compatible step from step-menu.md or add an adapter step |
| `routing-table-updater: trigger conflict with force-route` | New trigger overlaps existing force-route entry | Choose more specific trigger phrases; preserve existing force-routes |
| `audit-tool-restrictions: missing allowed-tools` | Agent frontmatter lacks `allowed-tools` | Add role-appropriate tool list per ADR-063 |
| `adr-enforcement: hash mismatch` | Pipeline Spec `adr_hash` doesn't match current ADR file | Recompute: `python3 ~/.claude/scripts/adr-query.py hash --adr {path}` |
| `skill-creator: template section missing` | Generated skill missing required frontmatter or operator context | Re-run with explicit `AGENT_TEMPLATE_V2.md` reference |

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
