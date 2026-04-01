# Pipeline Architecture

Complex tasks use structured pipelines with explicit phases and artifacts.

## Standard Pipeline Template

```
PHASE 1: GATHER    → Launch parallel agents for research
PHASE 2: COMPILE   → Structure findings into coherent format
PHASE 3: GROUND    → Establish context (audience, emotion, mode)
PHASE 4: GENERATE  → Load skill/agent, create content
PHASE 5: VALIDATE  → Run deterministic validation scripts
PHASE 6: REFINE    → Fix validation errors (max 3 iterations)
PHASE 7: OUTPUT    → Final content with validation report
```

## Available Pipelines

Pipelines live in `skills/workflow/references/*.md`. Each pipeline's frontmatter contains its
description and phase count. Run `ls skills/workflow/references/` for the current inventory.

Key pipelines referenced elsewhere in this document:
- `workflow-orchestrator`: Task orchestration (BRAINSTORM → WRITE-PLAN → VALIDATE-PLAN → EXECUTE-PLAN)
- `pr-pipeline`: Pull request lifecycle (Stage → Commit → Push → Create → Verify)
- `explore-pipeline`: Systematic codebase exploration
- `research-to-article`: Multi-agent research to voice content generation

## Pipeline Principles

1. **Artifacts over memory** - Each phase produces saved files, not just context
2. **Parallel where possible** - Launch independent agents simultaneously
3. **Deterministic validation** - Python scripts validate, not self-assessment
4. **Timeout management** - All parallel phases have timeouts (5 min default)
