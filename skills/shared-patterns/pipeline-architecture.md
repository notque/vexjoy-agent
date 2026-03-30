# Pipeline Architecture Pattern

## Overview

**Pipelines are the key to high-quality AI-assisted work.**

A pipeline is a structured sequence of phases where each phase:
1. Has a specific purpose
2. Produces artifacts for the next phase
3. Includes quality gates
4. Can be parallelized where appropriate

This pattern was validated through a reference article that achieved 97/100 validation score, and should be applied to **all complex tasks**.

---

## Research Findings

### What Others Are Doing

Based on research (January 2026), several approaches exist:

| Approach | Source | Description |
|----------|--------|-------------|
| [Claude Flow](https://github.com/ruvnet/claude-flow) | ruvnet | Enterprise swarm orchestration with Queen-led coordination |
| [Claude Code Workflow](https://github.com/catlog22/Claude-Code-Workflow) | catlog22 | JSON-driven multi-agent with context-first architecture |
| [Anthropic Research System](https://www.anthropic.com/engineering/multi-agent-research-system) | Anthropic | Orchestrator-worker pattern with parallel subagents |
| [Microsoft Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) | Azure | Sequential, parallel, and conditional workflows |
| [Google ADK Parallel Agents](https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/) | Google | Parallel execution with shared state management |

### What Makes Our Approach Unique

Most frameworks focus on **agent coordination**. We focus on **quality through structure**:

1. **Research-first**: Parallel agents gather comprehensive data before generation
2. **Artifact accumulation**: Each phase produces saved files, not just LLM output
3. **Deterministic validation**: Python scripts validate output, not self-assessment
4. **Wabi-sabi principle**: Pipeline prevents over-polishing through explicit rules

---

## Core Pipeline Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE TEMPLATE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 1: GATHER                                             │
│  ├── Launch parallel agents for comprehensive context        │
│  ├── Each agent has specific focus area                      │
│  └── Save artifacts: research docs, data files               │
│                                                              │
│  PHASE 2: COMPILE                                            │
│  ├── Structure findings into coherent format                 │
│  ├── Identify story arc / purpose / key points               │
│  └── Save artifact: compiled research document               │
│                                                              │
│  PHASE 3: GROUND                                             │
│  ├── Establish context before generation                     │
│  ├── Who is audience? What emotion? What mode?               │
│  └── No artifact, but documented in generation prompt        │
│                                                              │
│  PHASE 4: GENERATE                                           │
│  ├── Load appropriate skill/agent                            │
│  ├── Reference research artifacts                            │
│  └── Save artifact: generated content                        │
│                                                              │
│  PHASE 5: VALIDATE                                           │
│  ├── Run deterministic validation (Python scripts)           │
│  ├── Score against quality metrics                           │
│  └── Save artifact: validation report                        │
│                                                              │
│  PHASE 6: REFINE (if needed)                                 │
│  ├── Fix validation errors                                   │
│  ├── Re-run validation                                       │
│  └── Maximum 3 iterations                                    │
│                                                              │
│  PHASE 7: OUTPUT                                             │
│  ├── Final content with validation report                    │
│  └── Ready for next stage (upload, commit, publish)          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Types

### 1. Research-to-Article Pipeline (Proven)

**Used for**: Blog posts, documentation, any written content

```
5 Parallel Research Agents
         │
         ▼
    Compile Research
         │
         ▼
    Ground Context
         │
         ▼
    Voice Generation
         │
         ▼
    Deterministic Validation
         │
         ▼
    Output + Upload
```

**Skill**: `research-to-article`
**Example**: Reference article achieved 97/100 validation score

---

### 2. Code Implementation Pipeline

**Used for**: Feature development, bug fixes, refactoring

```
Understand Requirements
         │
         ▼
    Plan Implementation
         │
         ▼
    Execute with Subagents
         │
         ▼
    Run Tests + Linting
         │
         ▼
    Code Review (parallel)
         │
         ▼
    Commit + PR
```

**Skill**: `workflow-orchestrator` + `subagent-driven-development`

---

### 3. Review Pipeline

**Used for**: Code review, PR review, content review

```
    ┌────────────────────────────────────────┐
    │      3 PARALLEL REVIEWERS              │
    │                                        │
    │  Security    Business    Code Quality  │
    │  Reviewer    Logic       Reviewer      │
    │     │           │            │         │
    │     └───────────┼────────────┘         │
    │                 │                      │
    │                 ▼                      │
    │        Aggregate Findings              │
    │        by Severity                     │
    └────────────────────────────────────────┘
```

**Skill**: `parallel-code-review`

---

### 4. Voice Calibration Pipeline

**Used for**: Creating new voice profiles

```
Collect Writing Samples
         │
         ▼
    Analyze with voice_analyzer.py
         │
         ▼
    Generate profile.json
         │
         ▼
    Test with sample generation
         │
         ▼
    Validate with voice_validator.py
         │
         ▼
    Calibrate thresholds
```

**Skill**: `voice-calibrator`

---

### 5. Agent/Skill Creation Pipeline

**Used for**: Creating new agents or skills

```
Define Requirements
         │
         ▼
    Research Existing Patterns
         │
         ▼
    Generate Structure
         │
         ▼
    Verify Against Checklist
         │
         ▼
    Test with Subagent
         │
         ▼
    Add to Routing
```

**Skill**: `skill-creator`

---

## Pipeline Principles

### 1. Artifacts Over Memory

**Each phase produces saved files, not just LLM context.**

| Phase | Artifact |
|-------|----------|
| Research | `content/[site]/test/[subject]-research.md` |
| Generation | `content/[site]/test/[subject]-article.md` |
| Validation | Validation report in output |
| Upload | WordPress post ID |

Why: LLM context is ephemeral. Files persist across sessions.

### 2. Parallel Where Possible

**Launch independent agents simultaneously.**

```python
# WRONG: Sequential research
agent1_result = await research_career()
agent2_result = await research_storylines()
agent3_result = await research_music()

# RIGHT: Parallel research (single message, multiple Task calls)
Task(agent1, "Research career...")
Task(agent2, "Research storylines...")
Task(agent3, "Research music...")
# Wait for all to complete
```

### 3. Deterministic Validation

**Python scripts, not self-assessment.**

```bash
# Validation is deterministic, reproducible
python3 ~/.claude/scripts/voice_validator.py validate \
  --content article.md \
  --voice {voice-name} \
  --format json
```

Why: LLMs hallucinate quality. Scripts measure it.

### 4. Wabi-Sabi at Every Stage

**Don't over-polish. Natural imperfections are features.**

- Research: Include conflicting viewpoints
- Generation: Let enthusiasm overflow punctuation
- Validation: Pass threshold 60, not 100
- Refinement: Fix errors only, keep warnings

### 5. Explicit Phase Gates

**Don't proceed without completing the current phase.**

```
✗ Research incomplete → Cannot compile
✗ Validation failed → Cannot output
✗ Errors remain → Cannot proceed
```

### 6. Deterministic Scripts Over Inline Bash

**Use Python scripts for mechanical, repeatable operations. Reserve skills for LLM-orchestrated workflows.**

When a pipeline step performs a deterministic operation (repo classification, file validation, metric calculation, format conversion), extract it into a `scripts/*.py` CLI tool instead of writing inline bash in the skill's instructions. This:

- **Saves tokens**: A single `python3 ~/.claude/scripts/classify-repo.py --type-only` call replaces 5+ lines of bash and associated explanation
- **Ensures consistency**: The same script runs identically across all skills that reference it
- **Enables testing**: Scripts can be unit-tested independently of the skill
- **Separates concerns**: `scripts/` = deterministic ops, `skills/` = LLM orchestration

**Examples in this repo:**
- `scripts/classify-repo.py` — deterministic repo classification (used by pr-pipeline, pr-sync)
- `scripts/usage-report.py` — skill/agent usage telemetry
- `scripts/voice_validator.py` — deterministic voice validation

**Rule**: If a pipeline step doesn't need LLM judgment, it should be a script.

### 7. Timeout Management (CRITICAL)

**All parallel agent phases MUST have timeouts to prevent runaway execution.**

| Phase | Timeout | Action on Timeout |
|-------|---------|-------------------|
| Research agents | 5 minutes per agent | Proceed with gathered data |
| WebFetch calls | 30 seconds each | Skip and note missing source |
| Validation | 60 seconds | Proceed with warning |
| Subagent tasks | 10 minutes | Kill and fallback |

#### Implementation Pattern

```python
# When launching parallel agents, always use background mode with monitoring
Task(agent, prompt, run_in_background=True)

# Check progress periodically (every 30-60 seconds)
TaskOutput(task_id, block=False)  # Non-blocking check

# After timeout threshold, proceed with available data
# DO NOT wait indefinitely for agents that may be stuck on web fetches
```

#### Timeout Decision Tree

```
Agent Running > 5 minutes?
        │
        ├── YES → Check progress with TaskOutput(block=False)
        │         │
        │         ├── Making progress? → Wait 2 more minutes
        │         │
        │         └── Stuck on web fetch? → PROCEED WITHOUT
        │
        └── NO → Continue waiting
```

#### Why Timeouts Matter

A featured subject's article (January 2026) demonstrated the problem:
- 5 research agents launched
- Washington Post paywall caused repeated fetch timeouts
- Agents stuck in infinite retry loops
- 29+ minutes elapsed with no progress

**Solution applied:**
1. Proceeded with directly-gathered research
2. Article still achieved 97/100 validation
3. Lesson: Sufficient research > comprehensive research

#### Graceful Degradation

| Agents Completed | Action |
|------------------|--------|
| 5 of 5 | Full pipeline |
| 3-4 of 5 | Proceed, note gaps |
| 1-2 of 5 | Supplement with direct research |
| 0 of 5 | Fallback to synchronous research |

---

## When to Use Pipelines

| Task | Pipeline? | Why |
|------|-----------|-----|
| Write article | YES | Research, generate, validate |
| Fix typo | NO | Single action |
| Implement feature | YES | Plan, execute, test, review |
| Answer question | MAYBE | If research needed first |
| Create agent | YES | Define, structure, verify, route |
| Run single command | NO | Trivial |
| Review PR | YES | Parallel reviewers, aggregate |

**Rule of Thumb**: If the task has more than 2 distinct phases, use a pipeline.

---

## How to Remember to Use Pipelines

### 1. CLAUDE.md Default

Add to CLAUDE.md:
```
For complex tasks, consider:
- Can this be parallelized?
- What phases are needed?
- What artifacts should be saved?
- How will quality be validated?
```

### 2. /do Router Awareness

The router already suggests pipelines:
- "research then write" → research-to-article
- "comprehensive review" → parallel-code-review
- "implement feature" → workflow-orchestrator

### 3. Skill Triggers

Skills themselves reference pipelines:
- `voice-writer` has 8 steps
- `research-to-article` has explicit phases
- `workflow-orchestrator` has UNDERSTAND/PLAN/EXECUTE/VERIFY

### 4. Session Start Reminder

Consider adding a hook that reminds:
```
[pipeline-check] Complex task detected. Consider:
  → research-to-article for content
  → workflow-orchestrator for code
  → parallel-code-review for review
```

---

## Pipeline Inventory

Current pipelines in this repository:

| Pipeline | Skill | Phases |
|----------|-------|--------|
| Research-to-Article | `research-to-article` | 7 (RESEARCH→COMPILE→GROUND→GENERATE→VALIDATE→REFINE→OUTPUT) |
| Voice Writing | `voice-writer` | 8 (LOAD→GROUND→GENERATE→VALIDATE→REFINE→JOY-CHECK→OUTPUT→CLEANUP) |
| Workflow Orchestration | `workflow-orchestrator` | 4 (UNDERSTAND→PLAN→EXECUTE→VERIFY) |
| Subagent Development | `subagent-driven-development` | 3 (SPEC→EXECUTE→REVIEW) |
| Parallel Code Review | `parallel-code-review` | 3 (DISPATCH→EXECUTE→AGGREGATE) |
| Test-Driven Development | `test-driven-development` | 4 (RED→GREEN→REFACTOR→VERIFY) |
| Systematic Debugging | `systematic-debugging` | 5 (REPRODUCE→ISOLATE→HYPOTHESIZE→TEST→FIX) |
| Voice Calibration | `voice-calibrator` | 5 (COLLECT→ANALYZE→GENERATE→TEST→CALIBRATE) |
| Agent Creation | `skill-creator` | 6 (DEFINE→RESEARCH→STRUCTURE→VERIFY→TEST→ROUTE) |

---

## Opportunities for New Pipelines

Tasks that could benefit from explicit pipelines:

| Task | Proposed Pipeline | Phases |
|------|-------------------|--------|
| Documentation | doc-pipeline | RESEARCH→OUTLINE→GENERATE→VERIFY→PUBLISH |
| PR Submission | pr-pipeline | STAGE→COMMIT→PUSH→CREATE→VERIFY |
| Codebase Exploration | explore-pipeline | SCAN→MAP→ANALYZE→REPORT |
| Release | release-pipeline | CHANGELOG→VERSION→TAG→PUBLISH→ANNOUNCE |
| Onboarding | onboard-pipeline | DISCOVER→ANALYZE→DOCUMENT→VERIFY |

---

## Integration with Existing Architecture

```
                    /do Router
                        │
                        ▼
              ┌─────────────────┐
              │ Skill Selection │
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │Pipeline │   │Pipeline │   │Pipeline │
    │  Skill  │   │  Skill  │   │  Skill  │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
         ▼             ▼             ▼
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │Parallel │   │Parallel │   │Parallel │
    │ Agents  │   │ Agents  │   │ Agents  │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
         └─────────────┼─────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Deterministic   │
              │ Validation      │
              │ (Python Scripts)│
              └─────────────────┘
                       │
                       ▼
                  ┌─────────┐
                  │ Output  │
                  │Artifacts│
                  └─────────┘
```

---

## Quick Reference

**To use a pipeline:**
1. Identify task type
2. Select appropriate skill from inventory
3. Follow phase sequence
4. Save artifacts at each phase
5. Run deterministic validation
6. Don't skip phases

**Pipeline selection:**
- Content → `research-to-article`
- Code → `workflow-orchestrator`
- Review → `parallel-code-review`
- Voice → `voice-writer`
- Debug → `systematic-debugging`
- Test → `test-driven-development`

---

## References

- [Anthropic Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Azure AI Agent Design Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [Google ADK Parallel Agents](https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/)
- [V7 Labs Multi-Agent AI Systems](https://www.v7labs.com/blog/multi-agent-ai)
- [9 Agentic AI Workflow Patterns](https://www.marktechpost.com/2025/08/09/9-agentic-ai-workflow-patterns-transforming-ai-agents-in-2025/)
