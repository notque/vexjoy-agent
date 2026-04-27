---
name: voice-writer
description: |
  Unified voice content generation pipeline with mandatory validation and
  joy-check. Phased pipeline: LOAD, GROUND, STATS-CHECKPOINT, GENERATE,
  VALIDATE, REFINE, JOY-CHECK, ANTI-AI, OUTPUT, CLEANUP. Use when writing
  articles, blog posts, or any content that uses a voice profile. Use for
  "write article", "blog post", "write in voice", "generate content",
  "draft article", "write about".
user-invocable: true
argument-hint: "<topic or title>"
command: /voice-writer
context: fork
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
  pairs_with:
    - voice-validator
    - anti-ai-editor
    - joy-check
    - voice-feynman
---

# Voice Writer

Thin wrapper preserving slash-command access. Load the full pipeline definition:

```
Read skills/workflow/references/voice-writer.md
```

Then follow all phases and gates defined there.
