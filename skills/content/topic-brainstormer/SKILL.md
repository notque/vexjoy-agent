---
name: topic-brainstormer
promoted_to: content
description: "Mine technical story ideas using this publication's vex-to-resolution editorial filter."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
command: /brainstorm
routing:
  triggers: ["brainstorm topics", "content ideas", "blog topic ideas", "what to write about", "story angles"]
  category: content-creation
  pairs_with: [content, research]
---

# Topic brainstormer

This publication's narrow editorial identity is a resolved technical struggle.
Keep an idea only when supplied evidence supports all three:

- genuine friction (time lost, blocked progress, misleading behavior, or failed attempts);
- a satisfying resolution (root cause, reliable fix, prevention, or transferable insight);
- value to another reader facing a reproducible/searchable version of the problem.

Mine evidence from the repository and user-provided history: fix/workaround
commits, CI failures, retrospectives, unresolved internal links, promised
follow-ups, and reader questions. Do not inspect private shell/browser/chat
history unless the user explicitly supplies or authorizes it. A setup tutorial,
opinion, trend, or adjacent technology is not a fit merely because a plausible
frustration could be invented.

Title candidates around the observed failure/result (for example, “A works but
B fails”), recording the source evidence and any missing fact. Rank only after
filtering: prioritize breadth of affected readers, severity of actual friction,
and quality of the known resolution. Do not fabricate numeric scores from thin
evidence. When asked for angles on one topic, vary perspective, abstraction,
data, counter-frame, and timeliness; keep only angles with a concrete reader payoff.
