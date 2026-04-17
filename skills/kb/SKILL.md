---
name: kb
description: |
  Knowledge base operations on `research/{topic}/` wikis: compile raw sources
  into wiki articles, query the wiki for answers, or health-check wiki
  consistency. Use for "compile knowledge base", "kb compile", "query
  knowledge base", "kb query", "ask knowledge base", "lint knowledge base",
  "kb lint", or "knowledge base health".
user-invocable: false
agent: general-purpose
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
routing:
  triggers:
    - "compile knowledge base"
    - "kb compile"
    - "compile wiki"
    - "build knowledge base"
    - "compile raw sources"
    - "query knowledge base"
    - "kb query"
    - "ask knowledge base"
    - "search kb"
    - "kb question"
    - "lint knowledge base"
    - "kb lint"
    - "check kb health"
    - "knowledge base health"
    - "kb consistency"
  category: research
  complexity: medium
---

# KB Skill

Umbrella skill for knowledge base operations on `research/{topic}/` wikis. Routes to the correct reference based on the intent requested.

## Routing

Detect the user's intent and load the appropriate reference file:

| Intent | Trigger phrases | Reference |
|--------|----------------|-----------|
| **Compile** | "kb compile", "compile wiki", "build knowledge base", "compile raw sources" | `${CLAUDE_SKILL_DIR}/references/compile.md` |
| **Query** | "kb query", "ask knowledge base", "search kb", "kb question" | `${CLAUDE_SKILL_DIR}/references/query.md` |
| **Lint** | "kb lint", "check kb health", "knowledge base health", "kb consistency" | `${CLAUDE_SKILL_DIR}/references/lint.md` |

## Instructions

1. Identify the user's KB task from their message
2. Load the matching reference file from the table above
3. Follow the instructions in that reference file exactly
