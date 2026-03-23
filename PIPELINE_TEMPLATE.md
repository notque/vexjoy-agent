# Pipeline Template v1.0

The canonical structure for all pipelines in `pipelines/`. Every pipeline MUST match this template exactly. No exceptions, no alternative formats.

Pipelines are skills with explicit numbered phases and gates. They live in `pipelines/` but sync to `~/.claude/skills/` at install time.

## Structure

```
pipelines/
├── {pipeline-name}/
│   ├── SKILL.md              # Main pipeline file (under 10k words)
│   └── references/           # Optional: overflow content
│       ├── phase-details.md  # Verbose phase instructions
│       ├── error-catalog.md  # Comprehensive error patterns
│       └── examples.md       # Example inputs/outputs
```

---

## Complete Template

Below is the full template. Copy this verbatim when creating a new pipeline, then fill in the placeholders.

````markdown
---
name: {pipeline-name}
description: |
  {N}-phase pipeline for {purpose}: {PHASE_1}, {PHASE_2}, ..., {PHASE_N}.
  Use when {trigger conditions}. Use for "{trigger phrase 1}",
  "{trigger phrase 2}", "{trigger phrase 3}".
  Do NOT use for {exclusions and what to use instead}.
version: 1.0.0
user-invocable: true | false
command: /{command-name}           # Required if user-invocable: true
agent: {agent-name}                # Optional: default executor agent
model: opus | sonnet | haiku       # Optional: model preference
context: fork                      # Optional: run in isolated sub-agent
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
  - Skill
routing:
  triggers:
    - {trigger phrase 1}
    - {trigger phrase 2}
    - {trigger phrase 3}
  pairs_with:
    - {related-skill-1}
    - {related-skill-2}
  complexity: Simple | Medium | Complex | Comprehensive
  category: meta | content | review | documentation | infrastructure | devops | language
---

# {Pipeline Name}

## Operator Context

This pipeline {what it orchestrates and when it runs}.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any action
- **Over-Engineering Prevention**: Only do what the current phase requires — no speculative work
- **{Domain-Specific Rule 1}**: {Description}
- **{Domain-Specific Rule 2}**: {Description}

### Default Behaviors (ON unless disabled)
- **Artifact Persistence**: Save phase outputs to files, not just context
- **Phase Isolation**: Each phase completes fully before the next begins
- **{Domain Default 1}**: {Description}
- **{Domain Default 2}**: {Description}

### Optional Behaviors (OFF unless enabled)
- **{Optional 1}**: {Description}
- **{Optional 2}**: {Description}

---

## Instructions

### Phase 1: {PHASE_NAME}

**Goal**: {One sentence — what this phase achieves}

1. {Concrete action with specific tool, command, or script}
2. {Concrete action}
3. {Concrete action}

**Gate**: {Verifiable condition — "file exists at X", "script exits 0", "N items collected"}

---

### Phase 2: {PHASE_NAME}

**Goal**: {One sentence}

1. {Concrete action}
2. {Concrete action}
3. {Concrete action}

**Gate**: {Verifiable condition}

---

### Phase 3: {PHASE_NAME}

**Goal**: {One sentence}

1. {Concrete action}
2. {Concrete action}

**Gate**: {Verifiable condition}

---

## Error Handling

### Error: {Error Name}
**Cause**: {What triggers this error}
**Solution**: {Specific recovery steps — commands, not advice}

### Error: {Error Name}
**Cause**: {What triggers this error}
**Solution**: {Specific recovery steps}

### Error: {Error Name}
**Cause**: {What triggers this error}
**Solution**: {Specific recovery steps}

---

## Anti-Patterns

### Anti-Pattern 1: {Name}
**What it looks like**: {Description or code example}
**Why wrong**: {What breaks, degrades, or fails}
**Do instead**: {Correct approach with specific alternative}

### Anti-Pattern 2: {Name}
**What it looks like**: {Description or code example}
**Why wrong**: {What breaks, degrades, or fails}
**Do instead**: {Correct approach with specific alternative}

### Anti-Pattern 3: {Name}
**What it looks like**: {Description or code example}
**Why wrong**: {What breaks, degrades, or fails}
**Do instead**: {Correct approach with specific alternative}

---

## References

- [Anti-Rationalization](../../skills/shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../../skills/shared-patterns/verification-checklist.md) - Pre-completion checks
- [{Domain Reference}]({path}) - {Description}
````

---

## Required Sections — Compliance Matrix

Every pipeline SKILL.md is validated against this matrix. All items are **REQUIRED** unless marked otherwise.

### Frontmatter

| Field | Required | Rule |
|-------|----------|------|
| `name` | **Yes** | Kebab-case, matches directory name exactly |
| `description` | **Yes** | Lists all phases in order. Contains "Use for" with 2+ trigger phrases. Contains "Do NOT use for" with exclusions |
| `version` | **Yes** | SemVer (e.g., `1.0.0`) |
| `user-invocable` | **Yes** | `true` or `false` |
| `command` | **Conditional** | Required when `user-invocable: true` |
| `allowed-tools` | **Yes** | Explicit YAML list of every tool the pipeline uses |
| `routing.triggers` | **Yes** | At least 2 trigger phrases |
| `routing.pairs_with` | **Yes** | At least 1 related skill (use `[]` if truly standalone) |
| `routing.complexity` | **Yes** | One of: Simple, Medium, Complex, Comprehensive |
| `routing.category` | **Yes** | One of: meta, content, review, documentation, infrastructure, devops, language |

### Section Order

Sections MUST appear in this exact order:

| # | Section | Minimum Content |
|---|---------|-----------------|
| 1 | `# {Title}` | Pipeline name as H1 |
| 2 | `## Operator Context` | Contains all three subsections below |
| 2a | `### Hardcoded Behaviors (Always Apply)` | 2+ behaviors (bold name + description) |
| 2b | `### Default Behaviors (ON unless disabled)` | 2+ behaviors |
| 2c | `### Optional Behaviors (OFF unless enabled)` | 1+ behavior |
| 3 | `## Instructions` | Contains numbered phases |
| 3a | `### Phase N: {NAME}` | 3+ phases, each with **Goal** + numbered steps + **Gate** |
| 4 | `## Error Handling` | 2+ errors, each with **Cause** + **Solution** |
| 5 | `## Anti-Patterns` | 3+ anti-patterns, each with **What it looks like** + **Why wrong** + **Do instead** |
| 6 | `## References` | 1+ links to shared patterns, reference files, or external docs |

### Phase Format

Every phase MUST follow this exact structure:

```markdown
### Phase N: {UPPERCASE_NAME}

**Goal**: {Single sentence}

1. {Step}
2. {Step}

**Gate**: {Verifiable condition}
```

- Phase names: UPPERCASE single words (SCAN, MAP, ANALYZE, GENERATE, VALIDATE, etc.)
- Goals: One sentence, starts with a verb
- Steps: Numbered list with concrete actions (tools, commands, scripts)
- Gates: Must be verifiable — "file exists", "script exits 0", "count > 0", "no errors in output"
- Gates must NOT be subjective — never "looks good", "seems right", "output is reasonable"
- Phases separated by `---` horizontal rules

### Anti-Pattern Format

Every anti-pattern MUST use this exact structure:

```markdown
### Anti-Pattern N: {Name}
**What it looks like**: {Description}
**Why wrong**: {Consequence}
**Do instead**: {Alternative}
```

No tables. No `AP-1:` prefixes. No `❌` emoji prefixes. Exactly this format.

### Error Handling Format

Every error MUST use this exact structure:

```markdown
### Error: {Name}
**Cause**: {What triggers it}
**Solution**: {How to fix it — specific commands or steps}
```

### References Format

References MUST be a markdown bullet list of links:

```markdown
## References

- [{Name}]({path}) - {Description}
- [{Name}]({path}) - {Description}
```

---

## Migration Checklist

Use this when upgrading an existing pipeline to match this template:

### Frontmatter
- [ ] `name` matches directory name
- [ ] `description` lists all phases in order
- [ ] `description` has "Use for" with trigger phrases
- [ ] `description` has "Do NOT use for" with exclusions
- [ ] `version` is SemVer
- [ ] `user-invocable` is explicitly set
- [ ] `command` set if user-invocable
- [ ] `allowed-tools` is complete
- [ ] `routing.triggers` has 2+ entries
- [ ] `routing.pairs_with` is present
- [ ] `routing.complexity` is set
- [ ] `routing.category` is set

### Operator Context
- [ ] `## Operator Context` exists
- [ ] `### Hardcoded Behaviors (Always Apply)` with 2+ entries
- [ ] `### Default Behaviors (ON unless disabled)` with 2+ entries
- [ ] `### Optional Behaviors (OFF unless enabled)` with 1+ entry

### Phases
- [ ] `## Instructions` exists
- [ ] 3+ phases as `### Phase N: {NAME}`
- [ ] Every phase has `**Goal**:` line
- [ ] Every phase has numbered steps
- [ ] Every phase has `**Gate**:` line
- [ ] Gates are verifiable (not subjective)
- [ ] Phases separated by `---`

### Error Handling
- [ ] `## Error Handling` exists
- [ ] 2+ errors with `**Cause**:` and `**Solution**:`

### Anti-Patterns
- [ ] `## Anti-Patterns` exists
- [ ] 3+ anti-patterns with `**What it looks like**:`, `**Why wrong**:`, `**Do instead**:`

### References
- [ ] `## References` exists
- [ ] 1+ links to shared patterns or reference files

---

## Key Distinction: Pipelines vs Agents vs Skills

| | Agent | Skill | Pipeline |
|-|-------|-------|----------|
| **Answers** | "Who does the work?" | "How is it done?" | "In what order, with what checkpoints?" |
| **Core** | Expertise + behaviors | Methodology + instructions | **Numbered phases + gates** |
| **Location** | `agents/` | `skills/` | `pipelines/` |
| **Phases** | Optional | Optional | **Required (3+)** |
| **Gates** | Not required | Not required | **Required per phase** |
| **Template** | `AGENT_TEMPLATE_V2.md` | (no formal template) | `PIPELINE_TEMPLATE.md` |

---

## Size Guidelines

| Complexity | Phases | Main File | references/ |
|------------|--------|-----------|-------------|
| Simple | 3-4 | 2k-4k words | 0-2k words |
| Medium | 5-6 | 4k-7k words | 2k-5k words |
| Complex | 7-9 | 7k-10k words | 5k-15k words |
| Comprehensive | 10+ | 10k (hard limit) | 15k+ words |
