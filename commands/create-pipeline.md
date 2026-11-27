---
name: create-pipeline
description: |
  Create a new pipeline from a task description. Fans out agent, skill, and
  hook scaffolding in parallel, then integrates into the routing system.
version: 1.0.0
route_to:
  agent: general-purpose
  skill: workflow
parameters:
  - name: task
    required: true
    description: "What the pipeline should accomplish (e.g., blog post publishing workflow)"
  - name: context
    required: false
    description: "Additional constraints, domain knowledge, or reference pipelines"
  - name: components
    required: false
    description: "Override which components to scaffold (default: agent,skill,hook)"
    default: "agent,skill,hook"
---

# create-pipeline

Entry point command for the Pipeline Creator meta-pipeline.

## Usage

```
/do create a pipeline for [task description]
```

## What It Does

1. **Discovery**: Scans existing skills, pipelines, and hooks related to the task to prevent duplication and identify reusable patterns.
2. **Scaffolding** (fan-out via `workflow` skill, scaffolder phase): Dispatches parallel workers to create:
   - Skill definition (`SKILL.md` with phases and gates) and deep references
   - Optional Python detector hook or deterministic helper script
   - Optional overlay agent manifest (following `skills/meta/toolkit/references/agent-creator/agent-frontmatter-template.md`)
3. **Integration**: Updates `skills/process/workflow/references/pipeline-index.json` and regenerates the routing indexes.

## Examples

```
/do create a pipeline for automated code review on push
/do create a pipeline for blog post publishing with voice validation
/do create a pipeline for database migration safety checks
```

## Routing

This command routes to a `general-purpose` worker with the `workflow` skill and its `references/pipeline-orchestrator.md` reference. The `/do` router recognizes these triggers:

- "create pipeline", "new pipeline", "scaffold pipeline"
- "build a pipeline for", "pipeline for"
