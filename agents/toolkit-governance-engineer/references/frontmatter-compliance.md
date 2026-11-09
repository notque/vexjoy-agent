# Frontmatter Compliance Reference

> **Scope**: YAML frontmatter validation for agents and skills — required fields, advisory tool lists, type rules, and detection commands. Does not cover skill phase/gate structure.
> **Version range**: v2.0 template (current standard)
> **Generated**: 2026-04-15

---

## Overview

Agent and skill frontmatter is the contract between a component and the routing system. Broken frontmatter silently removes a component from discovery — the router never finds it, and the component disappears from all coverage reports. The most common failure modes are missing required fields, tool lists that do not match the agent's role, and YAML parse errors from unquoted special characters.

---

## Frontmatter Fields

| Field | Type | Required In | Example |
|-------|------|-------------|---------|
| `name` | string | agents, skills | `name: golang-general-engineer` |
| `description` | string (quoted if special chars) | agents, skills | `description: "Go dev: features, debugging"` |
| `routing.triggers` | list of strings | agents, skills | `triggers: [edit skill, update routing]` |
| `routing.complexity` | free-form label | agents, skills | `complexity: Medium` |
| `routing.category` | string | agents, skills | `category: meta` |
| `allowed-tools` | list of strings (advisory for agents) | agents, skills | `allowed-tools: [Read, Glob, Grep]` |
| `color` | string | agents (optional) | `color: blue` |
| `model` | string | optional; omit to inherit | `model: opus` |

No agent carries `version`; `validate-skill-frontmatter.py --strict` checks it on skills only. For `model`, the policy (owner 2026-11-01; Fable tier added 2026-11-09) allows `opus`, `fable`, and `inherit`, `haiku` only on an agent whose `tools:` list (the field Claude Code enforces) cannot change files, and `sonnet` only through an exemption in `validate_component_models.py`. A read-only `allowed-tools` list does not qualify, because it restricts nothing.

The same validator scans dispatch scripts: every `.js` and `.mjs` file in `skills/process/workflow/references/`, plus any under `skills/` or `agents/` that calls `agent(`. It fails on any literal model string outside comments, allowed models included. A script gets its model from `modelFor(role, modelOverride)` in `workflow-helpers.js`, the one script that may name models.

---

## Tool Lists by Agent Type (advisory)

Claude Code reads `tools:` for subagents and ignores `allowed-tools:` (the skill field), so an agent's `allowed-tools` restricts nothing: every repo agent runs with all tools. The list documents the tools the role needs, and `add-companion-skills.py`, `build-subagent-spec.py`, and `audit-tool-restrictions.py` read it; `validate_component_models.py` deliberately reads only `tools:`. Renaming the field to `tools:` would start enforcing it; that is an owner decision, so leave the field name alone.

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
  complexity: Medium          # Focused single-domain work
  complexity: Medium-Complex  # Multi-file or multi-phase work
  complexity: Complex         # Broad implementation or orchestration
  complexity: Comprehensive   # Full audits and system-wide sweeps
```

**Why**: These are the four values agents use today. The field is a label: `generate-agent-index.py` copies it into `agents/INDEX.json`, `list-capabilities.py` prints it, and `check-index-colocation.py` watches it for index drift. No router matches on it, so pick the closest existing value for consistency rather than inventing a new one.

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

**Why this matters**: Without `allowed-tools`, nobody reading the agent can see its intended tool scope, `add-companion-skills.py` fails on an agent with companion skills, and `validate-references.py --check-skill-calls` fails an agent that calls the Skill tool. Claude Code grants the agent all tools either way, so `validate_component_models.py` rejects a `model: haiku` pin unless a read-only `tools:` list limits the agent.

**Preferred action:**

Add `allowed-tools` matched to the agent's role: reviewers get `[Read, Glob, Grep]` plus read-only `Bash`, code modifiers get `[Read, Edit, Write, Bash, Glob, Grep]`, orchestrators get `[Read, Agent, Bash]`. Consult the Tool Lists table at the top of this file for the full mapping.

**Preferred action**: Add `allowed-tools` matching the agent's role type per the Tool Lists table above.

---

### Quote Descriptions Containing Colons

**Detection**:
```bash
grep -n "^description: [^\"'].*:" agents/*.md
grep -n "^description: [^\"'].*:" skills/*/*/SKILL.md
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

### Use an Existing Complexity Label

**Detection**:
```bash
grep -h "^  complexity:" agents/*.md | sort | uniq -c
```

**Signal**:
```yaml
routing:
  complexity: moderate  # a one-off label no other agent uses
```

**Why this matters**: Nothing routes on the label, but a one-off value makes `INDEX.json` and capability listings harder to compare across agents.

**Preferred action:**

Reuse one of `Medium`, `Medium-Complex`, `Complex`, or `Comprehensive`. Run `grep -h "^  complexity:" agents/*.md | sort | uniq -c` to see the labels in use and pick the closest.

**Preferred action**: Use a label that other agents already use.

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

List only `Read`, `Glob`, `Grep`, and read-only `Bash` for a reviewer. Add `Edit` only when its body defines a `--fix` mode (`reviewer-code`, `reviewer-system`), and `Write` only where that mode creates files (`reviewer-code`'s test-analyzer). Keep the read-only rule in the body. Run `grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"` and check each hit against the agent's fix mode.

**Preferred action**: Match each reviewer's list to its body: read-only tools by default, `Edit` only for a documented fix mode.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Agent missing from routing coverage report | Broken YAML frontmatter (parse error) | `python3 -c "import yaml; yaml.safe_load(open('agents/name.md').read().split('---')[1])"` |
| Agent in INDEX.json but not routed | Missing `routing.triggers` | Add `routing.triggers` list with at least one trigger string |
| Agent changed files during a review | `allowed-tools` is advisory, so nothing blocked the write | Put the read-only rule in the agent body; the list documents intent only |
| Description truncated in INDEX.json | Unquoted colon in description | Wrap description in double quotes |
| `validate_component_models.py` rejects an agent | `model` pin outside the model policy | Use `opus`, `fable`, or `inherit`, or omit `model`; keep `haiku` for agents whose `tools:` list cannot write (no Edit, Write, Bash, Agent, or Task) |
| `validate_component_models.py` reports `literal model string` at `file:line` | A workflow script names a model in code | Replace the literal with `modelFor(role, modelOverride)` from `workflow-helpers.js`; roles are `gather`, `work`, and `lead` |

---

## Detection Commands Reference

```bash
# Find agents missing allowed-tools
grep -rL "allowed-tools" agents/*.md

# Find unquoted descriptions with colons
grep -n "^description: [^\"'].*:" agents/*.md

# List the complexity labels in use
grep -h "^  complexity:" agents/*.md | sort | uniq -c

# Find reviewer agents that list write tools (fix-mode reviewers may list Edit)
grep -l "reviewer" agents/*.md | xargs grep -l "Edit\|Write"

# Validate frontmatter YAML for a single agent
python3 -c "import yaml; yaml.safe_load(open('agents/AGENTNAME.md').read().split('---')[1])"

# Run the agent checks CI runs (the generator rewrites the gitignored agents/INDEX.json)
python3 scripts/generate-agent-index.py && python3 scripts/validate-index-integrity.py
python3 scripts/validate_component_models.py
```

---

## See Also

- `routing-table-patterns.md` — routing entry structure, trigger conflicts, phantom route prevention
- `agents/INDEX.json` — coverage index; regenerate after frontmatter changes
- `docs/PHILOSOPHY.md` — progressive disclosure and specialist separation principles
