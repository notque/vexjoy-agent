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

Most pipelines live in `skills/process/workflow/references/*.md`. Each pipeline's frontmatter
contains its description. `skills/process/workflow/references/pipeline-index.json` is the
inventory: it maps each pipeline name to its file, including the few that live in another skill.

Key pipelines referenced elsewhere in this document:
- `workflow-orchestrator`: Task orchestration (BRAINSTORM → WRITE-PLAN → VALIDATE-PLAN → EXECUTE-PLAN). A pipeline, not a skill: load it through the `workflow` skill.
- `pr-pipeline`: Pull request lifecycle (Classify Repo → Stage → Review → Commit → Push → Review-Fix Loop → Create → Verify), in `skills/process/pr-workflow/references/pipeline.md`
- `explore-pipeline`: Systematic codebase exploration

## Pipeline Principles

1. **Artifacts over memory** - Each phase produces saved files, not just context
2. **Parallel where possible** - Launch independent agents simultaneously
3. **Deterministic validation** - Python scripts validate, not self-assessment
4. **Timeout management** - All parallel phases have timeouts (5 min default)
