---
name: voice-writer
description: |
  Unified voice content generation pipeline with mandatory validation and
  joy-check. 9-phase pipeline: LOAD, GROUND, GENERATE, VALIDATE, REFINE,
  JOY-CHECK, OUTPUT, CLEANUP. Use when writing articles, blog posts, or any
  content that uses a voice profile. Use for "write article", "blog post",
  "write in voice", "generate content", "draft article", "write about".
version: 2.0.0
user-invocable: true
argument-hint: "<topic or title>"
command: /voice-writer
context: fork
model: sonnet
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - "write article"
    - "blog post"
    - "write in voice"
    - "blog post voice"
    - "content pipeline"
  category: voice
---

# Voice Writer

Thin wrapper preserving slash-command access. Load the full pipeline definition:

```
Read skills/workflow/references/voice-writer.md
```

Then follow all phases and gates defined there.
