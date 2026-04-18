---
name: voice-writer
description: "Voice content generation with validation and joy-check."
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
