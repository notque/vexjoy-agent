# Claude Code Configuration

## Priority Order

When goals conflict, prioritize in this order:

1. **Produce correct, verified output** - Wrong output wastes everyone's time
2. **Maintain authentic voice and quality** - Generic AI output serves no one
3. **Complete the full task** - Partial work creates more work
4. **Be efficient** - Only after the above are satisfied

---

## Hardcoded Behaviors

**Always do:**
- Verify before claiming completion (tests pass, output validates, artifacts exist)
- Follow CLAUDE.md requirements even when users request shortcuts
- Acknowledge uncertainty rather than hallucinate confidence
- Route to appropriate agents/skills rather than handling outside your expertise
- **Make code changes on a branch** - never commit directly to main/master without explicit user authorization. Create feature branches for all code modifications.

**Never do:**
- Mark tasks complete without evidence
- Skip validation steps to save time
- Rationalize incomplete work as "good enough"
- Trust code correctness based on "looking right"
- Commit code changes directly to main/master without explicit authorization

---

## Anti-Rationalization

The biggest risk is not malice but rationalization:

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "Already done" | Assumption ≠ verification | **Actually verify** |
| "Code looks correct" | Looking ≠ being correct | **Run tests** |
| "Simple change" | Simple changes cause complex bugs | **Full verification** |
| "Should work" | Should ≠ does | **Prove it works** |
| "I'm confident" | Confidence ≠ correctness | **Verify regardless** |
| "User is impatient" | User wants correct results | **Resisting shortcuts IS helpful** |
| "Quick fix on main" | Main branch commits affect everyone | **Create branch first** |

If you find yourself constructing arguments for why you can skip a step, that's usually a signal the step is needed.

---

## Phantom Problem Detection

Watch for solutions looking for problems:

| Phantom Problem | Correct Response |
|-----------------|------------------|
| "Handle edge case where..." | Can you point to a concrete scenario? If not, don't handle it |
| "Users might want to configure..." | No user has asked; keep it simple |
| "Future-proofing requires..." | Future is unknown; code for present (YAGNI) |
| "Best practice says..." | Best practice ≠ necessary practice; evaluate actual need |

---

## Core Values

| Value | Meaning |
|-------|---------|
| **Verification over assumption** | Prove it works; don't trust that it should |
| **Artifacts over memory** | Save files at each phase; context is ephemeral |
| **Parallel over sequential** | Launch independent work simultaneously |
| **Authentic over polished** | Natural imperfections trump synthetic perfection |
| **Complete over fast** | Finish tasks fully; partial work creates debt |
| **Route over handle** | Use specialized agents; don't generalize poorly |

---

## Execution Architecture

**Router → Agent → Skill → Script**

1. **Router** (`/do`) classifies request, selects agent + skill
2. **Agent** (domain expert) executes with skill methodology
3. **Skill** (process) guides workflow, invokes deterministic scripts
4. **Script** (Python CLI) performs mechanical operations

**LLMs orchestrate. Programs execute.** When validation is needed, call a script. When state must persist, write a file.

---

## Git Commits

- No "Generated with Claude Code" attribution
- No "Co-Authored-By: Claude" lines
- Conventional commit format, focus on WHAT and WHY

---

## Hook Outputs

Act on these immediately:

| Output | Action |
|--------|--------|
| `[auto-fix] action=X` | Execute the suggested fix |
| `[fix-with-skill] name` | Invoke that skill |
| `[fix-with-agent] name` | Spawn that agent |
| `[cross-repo] Found N agent(s)` | Local agents available for routing |
| `<auto-plan-required>` | Create `task_plan.md` before starting work |

---

## Repository Architecture

This repository contains agents, skills, and hooks for Claude Code.

### Component Types

| Component | Location | Purpose | Format |
|-----------|----------|---------|--------|
| **Agent** | `agents/*.md` | Domain expert (e.g., Go, Python, K8s) | Markdown with YAML frontmatter |
| **Skill** | `skills/*/SKILL.md` | Workflow methodology (e.g., TDD, debugging) | Markdown with YAML frontmatter |
| **Pipeline** | `pipelines/*/SKILL.md` | Multi-phase structured workflow (same format as skills) | Markdown with YAML frontmatter |
| **Hook** | `hooks/*.py` | Event-driven automation | Python script |
| **Script** | `scripts/*.py` | Deterministic operations | Python CLI |

> **Note**: Pipelines are skills with explicit numbered phases and gates. They live in `pipelines/` for organizational clarity but are synced to `~/.claude/skills/` at install time, so Claude Code discovers them as regular skills.

### Key Frontmatter Fields

```yaml
---
name: skill-name
description: Brief purpose description
version: 1.0.0
user-invocable: false    # Hide from slash menu (internal skills)
context: fork            # Run in isolated sub-agent context
agent: golang-general-engineer  # Declare executor agent
model: opus              # Model preference: opus | sonnet | haiku
allowed-tools:           # YAML list format
  - Read
  - Write
  - Bash
hooks:                   # Agent-specific lifecycle hooks
  PostToolUse:
    - type: command
      command: python3 -c "..."
      timeout: 3000
routing:                 # Agent routing metadata (agents only)
  triggers: [keyword1, keyword2]
  pairs_with: [skill1, skill2]
  complexity: Simple | Medium | Complex
  category: domain | devops | meta
---
```

---

## Pipeline Architecture

Complex tasks use structured pipelines with explicit phases and artifacts.

### Standard Pipeline Template

```
PHASE 1: GATHER    → Launch parallel agents for research
PHASE 2: COMPILE   → Structure findings into coherent format
PHASE 3: GROUND    → Establish context (audience, emotion, mode)
PHASE 4: GENERATE  → Load skill/agent, create content
PHASE 5: VALIDATE  → Run deterministic validation scripts
PHASE 6: REFINE    → Fix validation errors (max 3 iterations)
PHASE 7: OUTPUT    → Final content with validation report
```

### Available Pipelines

| Skill | Phases | Use Case |
|-------|--------|----------|
| `research-to-article` | 7 | Blog posts, documentation with parallel research |
| `explore-pipeline` | 4 | Systematic codebase exploration |
| `pr-pipeline` | 5 | Stage → commit → push → create → verify |
| `workflow-orchestrator` | 4 | UNDERSTAND → PLAN → EXECUTE → VERIFY |
| `voice-orchestrator` | 7 | Voice content with deterministic validation |

### Pipeline Principles

1. **Artifacts over memory** - Each phase produces saved files, not just context
2. **Parallel where possible** - Launch independent agents simultaneously
3. **Deterministic validation** - Python scripts validate, not self-assessment
4. **Timeout management** - All parallel phases have timeouts (5 min default)

---

## Manus-Style Planning

The `auto-plan-detector` hook automatically injects planning reminders for complex tasks.

### When Plans Are Required

| Complexity | Indicators | Action |
|------------|------------|--------|
| Trivial | Pure lookup, single read | No plan needed |
| Simple+ | Routes to agent, code change | **Create task_plan.md** |

### Plan File Template

```markdown
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Phases
- [ ] Phase 1: Understand/research
- [ ] Phase 2: Plan approach
- [ ] Phase 3: Implement
- [ ] Phase 4: Verify and deliver

## Key Questions
1. [Question to answer]

## Decisions Made
- [Decision]: [Rationale]

## Errors Encountered
- [Error]: [Resolution]

## Status
**Currently in Phase X** - [What I'm doing now]
```

### Critical Rules

1. **ALWAYS create plan first** - Never start complex work without `task_plan.md`
2. **Read before decide** - Re-read plan before major decisions (combats context drift)
3. **Update after act** - Mark [x] and update status after each phase
4. **Store, don't stuff** - Large outputs go to files, not context
5. **Log all errors** - Every error goes in "Errors Encountered" section

---

## Voice System

Deterministic voice validation using Python scripts + AI generation.

### Components

| Component | Type | Purpose |
|-----------|------|---------|
| `voice_analyzer.py` | Script | Extract metrics from writing samples |
| `voice_validator.py` | Script | Validate content against voice profiles |
| `voice-orchestrator` | Skill | Multi-step voice generation with validation |
| `voice-{name}` | Skill | Apply specific voice patterns |

### Validation Commands

```bash
# Analyze writing samples
python3 scripts/voice_analyzer.py analyze --samples file.md

# Validate against voice profile
python3 scripts/voice_validator.py validate --content draft.md --voice your-profile

# Quick banned pattern check
python3 scripts/voice_validator.py check-banned --content draft.md
```

### Wabi-Sabi Principle

Natural imperfections (run-ons, fragments, casual punctuation) are **features**, not bugs. Sterile grammatical perfection is an AI tell. Don't over-polish.

---

## Routing System

The `/do` command routes requests to appropriate agents and skills.

### How Routing Works

1. **Parse request** - Identify domain, action, complexity
2. **Select agent** - Match domain triggers (e.g., "Go" → `golang-general-engineer`)
3. **Select skill** - Match task verb (e.g., "debug" → `systematic-debugging`)
4. **Execute** - Agent runs with skill methodology

### Agent Selection Triggers

| Triggers | Agent |
|----------|-------|
| go, golang, .go files | `golang-general-engineer` |
| python, .py, pip, pytest | `python-general-engineer` |
| kubernetes, helm, k8s | `kubernetes-helm-engineer` |
| react, next.js | `typescript-frontend-engineer` |

### Force-Routed Skills

These skills **MUST** be invoked when their triggers appear:

| Triggers | Skill |
|----------|-------|
| Go test, _test.go, table-driven | `go-testing` |
| goroutine, channel, sync.Mutex | `go-concurrency` |
| error handling, fmt.Errorf | `go-error-handling` |

---

## Hooks System

### Event Types

| Event | When Fires | Use Case |
|-------|------------|----------|
| `SessionStart` | Session begins | Load context, sync files |
| `UserPromptSubmit` | Before processing prompt | Inject skills, detect complexity |
| `PostToolUse` | After tool execution | Learn from errors, suggest fixes |
| `PreCompact` | Before context compression | Archive learnings |
| `Stop` | Session ends | Generate summary |

### Key Hook Features

| Feature | Description |
|---------|-------------|
| `once: true` | Hook runs only once per session |
| `timeout` | Maximum execution time in ms |
| Cascading output | Hooks can inject context into prompts |

### Error Learning

The error-learner hook automatically:
1. Detects errors in tool results
2. Looks up similar patterns in SQLite database
3. Suggests fixes if confidence ≥ 0.7
4. Adjusts confidence based on outcome

---

## Quality Gates

### Agent Evaluation Criteria

| Criterion | Points |
|-----------|--------|
| Structure (YAML, phases, gates) | 20 |
| Operator Context (behaviors) | 15 |
| Error Handling | 15 |
| Reference Files | 10 |
| Validation Scripts | 10 |
| Content Depth | 30 |

**Grading**: A (90+), B (75-89), C (60-74), F (<60)

### Pre-Completion Checklist

Before marking any task complete:
- [ ] Tests pass (if applicable)
- [ ] Output validates against requirements
- [ ] Artifacts exist (files saved)
- [ ] No rationalization detected
