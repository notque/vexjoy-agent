---
name: roast
promoted_to: research
description: "Compatibility stub for evidence-based multi-perspective critique; new critique routes through assessment/research."
user-invocable: false
argument-hint: "<target to critique>"
allowed-tools: [Read, Glob, Grep, Bash, Task]
context: fork
routing:
  triggers: [roast code, devil's advocate, stress test idea, roast this, stress test this idea, poke holes in this]
  category: analysis
  pairs_with: [assessment, review]
---

# Roast

This capability is promoted to read-only assessment/research. For compatibility, critique from five perspectives: skeptical senior, precision-focused pedant, newcomer, contrarian, and pragmatic builder. Run perspectives independently, then verify every factual claim against supplied evidence. Final output separates validated problems, validated strengths, and dismissed claims; citations use `file:line` where files exist. Persona confidence or consensus never substitutes for evidence.
