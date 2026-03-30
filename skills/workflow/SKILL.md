---
name: workflow
version: 2.0.0
description: "Structured multi-phase workflows: review, debug, refactor, deploy, create, research, and more."
user-invocable: false
context: fork
model: sonnet
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep
  - Agent
  - Skill
---

# Workflow

Umbrella skill for all structured multi-phase workflows (formerly pipelines/).
Load the appropriate workflow reference based on the task.

## Available Workflows

| Category | Workflow | Reference |
|----------|----------|-----------|
| **Code Review** | Comprehensive multi-wave review | `references/comprehensive-review.md` |
| **Code Review** | Systematic code review | `references/systematic-code-review.md` |
| **Debugging** | Evidence-based debugging pipeline | `references/systematic-debugging.md` |
| **Refactoring** | Safe refactoring with test gates | `references/systematic-refactoring.md` |
| **Features** | End-to-end feature lifecycle | `references/feature-pipeline.md` |
| **PR Workflow** | PR creation pipeline | `references/pr-pipeline.md` |
| **Research** | Formal research with source gates | `references/research-pipeline.md` |
| **Research** | Research to article pipeline | `references/research-to-article.md` |
| **Content** | Voice content generation | `references/voice-writer.md` |
| **Content** | Voice calibration | `references/voice-calibrator.md` |
| **Content** | Article evaluation | `references/article-evaluation-pipeline.md` |
| **Content** | De-AI content pipeline | `references/de-ai-pipeline.md` |
| **Content** | Documentation pipeline | `references/doc-pipeline.md` |
| **Exploration** | Codebase exploration | `references/explore-pipeline.md` |
| **Exploration** | Multi-perspective analysis | `references/do-perspectives.md` |
| **Creation** | Skill creation pipeline | `references/skill-creation-pipeline.md` |
| **Creation** | Hook development pipeline | `references/hook-development-pipeline.md` |
| **Creation** | MCP server pipeline | `references/mcp-pipeline-builder.md` |
| **Creation** | Pipeline scaffolding | `references/pipeline-scaffolder.md` |
| **Creation** | Domain research for pipelines | `references/domain-research.md` |
| **Creation** | Chain composition | `references/chain-composer.md` |
| **Creation** | Auto-pipeline generation | `references/auto-pipeline.md` |
| **Upgrade** | Agent/skill upgrade | `references/agent-upgrade.md` |
| **Upgrade** | System upgrade | `references/system-upgrade.md` |
| **Upgrade** | Toolkit improvement | `references/toolkit-improvement.md` |
| **Testing** | Pipeline test runner | `references/pipeline-test-runner.md` |
| **Testing** | Pipeline retro | `references/pipeline-retro.md` |
| **Perses** | Dashboard-as-Code | `references/perses-dac-pipeline.md` |
| **Perses** | Plugin pipeline | `references/perses-plugin-pipeline.md` |
| **GitHub** | Profile rules extraction | `references/github-profile-rules.md` |
| **Orchestration** | Task orchestration | `references/workflow-orchestrator.md` |

## How to use

1. Identify the workflow category from the user's task
2. Read the appropriate reference file
3. Follow the phases and gates defined in that reference
