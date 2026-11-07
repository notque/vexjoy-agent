# Frontmatter Compliance Reference

> **Scope**: YAML frontmatter validation for agents and skills — required fields, advisory tool lists, type rules, and detection commands. Does not cover skill phase/gate structure.
> **Version range**: v2.0 template (current standard)
> **Generated**: 2026-04-15

---

## Overview

Agent and skill frontmatter is the contract between a component and the routing system. Broken frontmatter silently removes a component from discovery — the router never finds it, and the component disappears from all coverage reports. The most common failure modes are missing required fields, tool lists that do not match the agent's role, and YAML parse errors from unquoted special characters.

---

## Required Fields (v2.0 Template)

| Field | Type | Required In | Example |
|-------|------|-------------|---------|
| `name` | string | agents, skills | `name: golang-general-engineer` |
| `version` | string (semver) | agents, skills | `version: 1.0.0` |
| `description` | string (quoted if special chars) | agents, skills | `description: "Go dev: features, debugging"` |
| `routing.triggers` | list of strings | agents, skills | `triggers: [edit skill, update routing]` |
| `routing.complexity` | enum | agents, skills | `complexity: Medium` |
| `routing.category` | string | agents, skills | `category: meta` |
| `allowed-tools` | list of strings (advisory for agents) | agents, skills | `allowed-tools: [Read, Glob, Grep]` |
| `color` | string | agents | `color: blue` |
| `model` | string | agents | `model: sonnet` |

---

## Tool Lists by Agent Type (advisory)

Claude Code reads `tools:` for subagents and ignores `allowed-tools:` (the skill field), so an agent's `allowed-tools` restricts nothing: every repo agent runs with all tools. The list documents the tools the role needs, and `add-companion-skills.py`, `build-subagent-spec.py`, and `validate-references.py --check-skill-calls` read it. Renaming the field to `tools:` would start enforcing it; that is an owner decision, so leave the field name alone.

| Agent Role | Listed Tools | Rationale |
|------------|-----------------|-----------|
| Reviewer / auditor | `Read`, `Glob`, `Grep`, read-only `Bash` | Documents read-only intent; the body's no-write rule is what holds |
| Code modifier / engineer | `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep` | Full access for implementation work |
| Orchestrator / coordinator | `Read`, `Agent`, `Bash` | Dispatches agents; no direct file edits |
| Skill-invoker | `Read`, `Bash`, `Glob`, `Grep` | Executes skills but doesn't write files |

**Rule**: Match `allowed-tools` to the agent's actual role and to what its body tells it to use. Describe the list as advisory, never as enforced, and state any read-only rule in the agent body.

---

## Correct Patterns

### Quoting Descriptions with Special Characters

Descriptions containing colons, commas, or markdown are YAML special characters and must be quoted.

```yaml
# Correct — colon inside quotes
description: "Toolkit governance: edit skills, update routing tables"

# Correct — simple description, no quotes needed
description: Go development and debugging
```

**Why**: Unquoted colons in YAML values cause parse errors — the YAML parser interprets the colon as a key-value separator, silently truncating the description.

---

### Complexity Tier Values

```yaml
routing:
  complexity: Low     # Single-file edits, read-only audits
  complexity: Medium  # Multi-file edits, routing table updates
  complexity: High    # Full compliance sweeps, ADR consultations
```

**Why**: Complexity matching is case-sensitive. Values outside `Low/Medium/High` are silently ignored — the router defaults to Medium.

---

### Tool List Format

```yaml
# Correct — block list
allowed-tools:
  - Read
  - Edit
  - Glob
  - Grep

# Also correct — inline list
allowed-tools: [Read, Edit, Glob, Grep]
```

**Why**: Mixed formats cause parse errors in strict YAML parsers. Pick one and be consistent within a file.

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### Include `allowed-tools` in Agent Frontmatter

**Detection**:
```bash
grep -rL "allowed-tools" agents/*.md
rg -L 'allowed-tools' --glob 'agents/*.md'
```

**Signal**: <!-- no-pair-required: sub-block split by code-comment heading; Do instead is inline below -->
```yaml
---
name: my-agent
description: "Does something"
routing:
  triggers: [do thing]
  complexity: Medium
  category: engineering
# allowed-tools: missing entirely
---
```

**Why this matters**: Without `allowed-tools`, nobody reading the agent can see its intended tool scope, `add-companion-skills.py` fails on an agent with companion skills, and `validate-references.py --check-skill-calls` cannot confirm the `Skill` tool. Claude Code grants the agent all tools either way.

**Preferred action:**

Add `allowed-tools` matched to the agent's role: reviewers get `[Read, Glob, Grep]` plus read-only `Bash`, code modifiers get `[Read, Edit, Write, Bash, Glob, Grep]`, orchestrators get `[Read, Agent, Bash]`. Consult the Tool Lists table at the top of this file for the full mapping.

**Preferred action**: Add `allowed-tools` matching the agent's role type per the Tool Lists table above.

---

### Quote Descriptions Containing Colons

**Detection**:
```bash
grep -n "^description: [^\"'].*:" agents/*.md
grep -n "^description: [^\"'].*:" skills/*/SKILL.md
```

**Signal**:
```yaml
description: Toolkit governance: edit skills, update routing  # YAML parse error
```

**Why this matters**: The YAML parser sees `Toolkit governance` as the value and `edit skills` as an unknown key, producing a parse error. The component becomes invisible to the routing system.

**Preferred action:**

Wrap any description containing a colon, comma, or markdown syntax in double quotes: `description: "Toolkit governance: edit skills, update routing"`. Run `grep -n "^description: [^\"'].*:" agents/*.md` to find all unquoted descriptions with colons.

**Preferred action**:
```yaml
description: "Toolkit governance: edit skills, update routing"
```

---

### Use Exact Casing for Complexity Values

**Detection**:
```bash
grep -rn "complexity:" agents/*.md skills/*/SKILL.md | grep -vE "complexity: (Low|Medium|High)"
```

**Signal**:
```yaml
routing:
  complexity: moderate  # wrong casing
  complexity: medium    # wrong casing — must be capitalized
```

**Why this matters**: Complexity matching is case-sensitive. `medium` does not match `Medium` — the router silently assigns a default.

**Preferred action:**

Use exactly `Low`, `Medium`, or `High` (capital first letter). Run `grep -rn "complexity:" agents/*.md | grep -vE "complexity: (Low|Medium|High)"` to find all mismatched values and correct them.

**Preferred action**: Use exactly `Low`, `Medium`, or `High`.

---

### Keep Reviewer Tool Lists Read-Only

**Detection**:
```bash
grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"
```

**Signal**:
```yaml
name: reviewer-example
allowed-tools:
  - Read
  - Edit    # documents write intent on a reviewer with no fix mode
  - Grep
```

**Why this matters**: A reviewer that changes files during a review pass alters what it is reviewing. The tool list cannot stop that, because Claude Code ignores `allowed-tools` for agents; the read-only rule in the agent body is the control, and the list should agree with it.

**Preferred action:**

List only `Read`, `Glob`, `Grep`, and read-only `Bash` for a reviewer, and add `Edit` only when its body defines a `--fix` mode (`reviewer-code`, `reviewer-system`). Keep the read-only rule in the body. Run `grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"` and check each hit against the agent's fix mode.

**Preferred action**: Match each reviewer's list to its body: read-only tools by default, `Edit` only for a documented fix mode.

---

### Bump Stable Agents to v1.0.0+

**Detection**:
```bash
grep -rn "^version: 0\." agents/*.md
```

**Signal**:
```yaml
```

**Why this matters**: Agents in active production use should be at `1.x.x` or higher. `0.x.x` affects coverage reporting confidence scores.

**Preferred action:**

Bump to `version: 1.0.0` when the agent ships its first production-ready capability. Run `grep -rn "^version: 0\." agents/*.md` to find all pre-production versioned agents that are in active routing use and need a version bump.

**Preferred action**: Bump to `version: 1.0.0` once the agent is in stable use.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Agent missing from routing coverage report | Broken YAML frontmatter (parse error) | `python3 -c "import yaml; yaml.safe_load(open('agents/name.md').read().split('---')[1])"` |
| Agent in INDEX.json but not routed | Missing `routing.triggers` | Add `routing.triggers` list with at least one trigger string |
| Agent changed files during a review | `allowed-tools` is advisory, so nothing blocked the write | Put the read-only rule in the agent body; the list documents intent only |
| Description truncated in INDEX.json | Unquoted colon in description | Wrap description in double quotes |
| Agent routes but hits wrong complexity tier | `complexity` casing mismatch | Verify exact: `Low`, `Medium`, `High` |

---

## Detection Commands Reference

```bash
# Find agents missing allowed-tools
grep -rL "allowed-tools" agents/*.md

# Find unquoted descriptions with colons
grep -n "^description: [^\"'].*:" agents/*.md

# Find wrong complexity casing
grep -rn "complexity:" agents/*.md | grep -vE "complexity: (Low|Medium|High)"

# Find reviewer agents that list write tools (fix-mode reviewers may list Edit)
grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"

# Find pre-production versions on deployed agents
grep -rn "^version: 0\." agents/*.md

# Validate frontmatter YAML for a single agent
python3 -c "import yaml; yaml.safe_load(open('agents/AGENTNAME.md').read().split('---')[1])"

# Scan all agents for required fields
python3 scripts/validate-frontmatter.py --all 2>/dev/null || grep -c "^name:" agents/*.md
```

---

## See Also

- `routing-table-patterns.md` — routing entry structure, trigger conflicts, phantom route prevention
- `agents/INDEX.json` — coverage index; regenerate after frontmatter changes
- `docs/PHILOSOPHY.md` — progressive disclosure and specialist separation principles
