---
name: research-pipeline
description: "Research pipeline: scope, gather, synthesize, validate, deliver."
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
