---
name: create-pipeline
description: |
  Create a new pipeline from a task description. Fans out agent, skill, and
  hook scaffolding in parallel, then integrates into the routing system.
version: 1.0.0
route_to:
  agent: pipeline-orchestrator-engineer
  skill: workflow
  enhancements:
    - codebase-analyzer
    - routing-table-updater
trigger:
  hook: pipeline-context-detector
  event: UserPromptSubmit
parameters:
  required:
    - name: task
      description: What the pipeline should accomplish (e.g., "blog post publishing workflow")
  optional:
    - name: context
      description: Additional constraints, domain knowledge, or reference pipelines
    - name: components
      description: Override which components to scaffold (default: agent,skill,hook)
      default: "agent,skill,hook"
---

# create-pipeline

Entry point command for the Pipeline Creator meta-pipeline.

## Usage

```
/do create a pipeline for [task description]
```

## What It Does

1. **Context Detection** (`pipeline-context-detector` hook): Scans the repository for existing agents, skills, and hooks related to the task. Builds a JSON environment snapshot.
2. **Discovery** (`codebase-analyzer`): Analyzes existing components to prevent duplication and identify reusable patterns.
3. **Scaffolding** (fan-out via `workflow` skill, scaffolder phase): Dispatches parallel sub-agents to create:
   - Python detector hook (environment evaluation before LLM invocation)
   - Agent manifest (following `AGENT_TEMPLATE_V2.md`)
   - Skill definition (`SKILL.md` with phases and gates)
4. **Integration** (`routing-table-updater`): Injects the new pipeline into `/do` routing tables.

## Examples

```
/do create a pipeline for automated code review on push
/do create a pipeline for blog post publishing with voice validation
/do create a pipeline for database migration safety checks
```

## Routing

This command routes to `pipeline-orchestrator-engineer` with the `workflow` skill. The `/do` router recognizes these triggers:

- "create pipeline", "new pipeline", "scaffold pipeline"
- "build a pipeline for", "pipeline for"
