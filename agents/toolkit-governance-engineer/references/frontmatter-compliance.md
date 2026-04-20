# Frontmatter Compliance Reference

> **Scope**: YAML frontmatter validation for agents and skills — required fields, tool restrictions, type rules, and detection commands. Does not cover skill phase/gate structure.
> **Version range**: v2.0 template (current standard)
> **Generated**: 2026-04-15

---

## Overview

Agent and skill frontmatter is the contract between a component and the routing system. Broken frontmatter silently removes a component from discovery — the router never finds it, and the component disappears from all coverage reports. The most common failure modes are missing required fields, overly permissive `allowed-tools`, and YAML parse errors from unquoted special characters.

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
| `allowed-tools` | list of strings | agents only | `allowed-tools: [Read, Glob, Grep]` |
| `color` | string | agents | `color: blue` |
| `model` | string | agents | `model: sonnet` |

---

## Tool Restrictions by Agent Type (ADR-063)

| Agent Role | Permitted Tools | Rationale |
|------------|-----------------|-----------|
| Reviewer / auditor | `Read`, `Glob`, `Grep` | Read-only prevents unauthorized changes |
| Code modifier / engineer | `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep` | Full access for implementation work |
| Orchestrator / coordinator | `Read`, `Agent`, `Bash` | Dispatches agents; no direct file edits |
| Skill-invoker | `Read`, `Bash`, `Glob`, `Grep` | Executes skills but doesn't write files |

**Rule**: `allowed-tools` must match the agent's actual role. Granting `Edit` to a reviewer or `Agent` to a non-orchestrator violates ADR-063.

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

### ❌ Missing `allowed-tools` in Agent Frontmatter

**Detection**:
```bash
grep -rL "allowed-tools" agents/*.md
rg -L 'allowed-tools' --glob 'agents/*.md'
```

**What it looks like**: <!-- no-pair-required: sub-block split by code-comment heading; Do instead is inline below -->
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

**Why wrong**: Without `allowed-tools`, the agent inherits an undefined tool set. Behavior varies by runtime — some runtimes grant all tools (dangerous), others grant none (agent cannot function).

**Do instead:**

Add `allowed-tools` matched to the agent's role: reviewers get `[Read, Glob, Grep]`, code modifiers get `[Read, Edit, Write, Bash, Glob, Grep]`, orchestrators get `[Read, Agent, Bash]`. Consult the Tool Restrictions table at the top of this file for the full mapping.

**Fix**: Add `allowed-tools` matching the agent's role type per the Tool Restrictions table above.

---

### ❌ Unquoted Description with Colon

**Detection**:
```bash
grep -n "^description: [^\"'].*:" agents/*.md
grep -n "^description: [^\"'].*:" skills/*/SKILL.md
```

**What it looks like**:
```yaml
description: Toolkit governance: edit skills, update routing  # YAML parse error
```

**Why wrong**: The YAML parser sees `Toolkit governance` as the value and `edit skills` as an unknown key, producing a parse error. The component becomes invisible to the routing system.

**Do instead:**

Wrap any description containing a colon, comma, or markdown syntax in double quotes: `description: "Toolkit governance: edit skills, update routing"`. Run `grep -n "^description: [^\"'].*:" agents/*.md` to find all unquoted descriptions with colons.

**Fix**:
```yaml
description: "Toolkit governance: edit skills, update routing"
```

---

### ❌ Wrong Complexity Casing

**Detection**:
```bash
grep -rn "complexity:" agents/*.md skills/*/SKILL.md | grep -vE "complexity: (Low|Medium|High)"
```

**What it looks like**:
```yaml
routing:
  complexity: moderate  # wrong casing
  complexity: medium    # wrong casing — must be capitalized
```

**Why wrong**: Complexity matching is case-sensitive. `medium` does not match `Medium` — the router silently assigns a default.

**Do instead:**

Use exactly `Low`, `Medium`, or `High` (capital first letter). Run `grep -rn "complexity:" agents/*.md | grep -vE "complexity: (Low|Medium|High)"` to find all mismatched values and correct them.

**Fix**: Use exactly `Low`, `Medium`, or `High`.

---

### ❌ Reviewer Agent with Write/Edit Tools (ADR-063 Violation)

**Detection**:
```bash
grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"
```

**What it looks like**:
```yaml
name: reviewer-code-quality
allowed-tools:
  - Read
  - Edit    # violation: reviewers should not modify files
  - Grep
```

**Why wrong**: Reviewer agents with write access can modify files during review passes, creating unintended side-effects. ADR-063 requires reviewers to be read-only.

**Do instead:**

Set reviewer `allowed-tools` to `[Read, Glob, Grep]` only. Run `grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"` to find violations. Remove `Edit` and `Write` from any reviewer's tool list and verify the agent still functions correctly with read-only access.

**Fix**: Remove `Edit` and `Write` from reviewer `allowed-tools`. Reviewers use `Read`, `Glob`, `Grep` only.

---

### ❌ Pre-Production Version on Stable Agent

**Detection**:
```bash
grep -rn "^version: 0\." agents/*.md
```

**What it looks like**:
```yaml
```

**Why wrong**: Agents in active production use should be at `1.x.x` or higher. `0.x.x` affects coverage reporting confidence scores.

**Do instead:**

Bump to `version: 1.0.0` when the agent ships its first production-ready capability. Run `grep -rn "^version: 0\." agents/*.md` to find all pre-production versioned agents that are in active routing use and need a version bump.

**Fix**: Bump to `version: 1.0.0` once the agent is in stable use.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Agent missing from routing coverage report | Broken YAML frontmatter (parse error) | `python3 -c "import yaml; yaml.safe_load(open('agents/name.md').read().split('---')[1])"` |
| Agent in INDEX.json but not routed | Missing `routing.triggers` | Add `routing.triggers` list with at least one trigger string |
| `allowed-tools` grants unexpected access | Field absent from frontmatter | Add `allowed-tools` explicitly; never rely on runtime defaults |
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

# Find reviewer agents with write tools (ADR-063)
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
