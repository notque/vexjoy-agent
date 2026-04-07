---
name: research-pipeline
description: |
  Formal 5-phase research pipeline with artifact saving and source quality gates:
  SCOPE, GATHER, SYNTHESIZE, VALIDATE, DELIVER. Parallel research agents
  mandatory (min 3). Saves findings to research/{topic}/ for future reference.
  Use for "research pipeline", "formal research", "research with artifacts".
version: 2.0.0
user-invocable: true
argument-hint: "<research topic>"
agent: research-coordinator-engineer
context: fork
model: sonnet
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Write
routing:
  triggers:
    - "research-pipeline"
    - "research"
    - "formal research"
    - "research with artifacts"
    - "systematic investigation"
    - "research report"
    - "gather evidence"
  category: research
---

# Research Pipeline

Thin wrapper preserving slash-command access. Load the full pipeline definition:

```
Read skills/workflow/references/research-pipeline.md
```

Then follow all phases and gates defined there.
