---
name: headlines
promoted_to: content
description: "Generate accurate headline, title, and subject-line options from a supplied brief or draft."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
routing:
  triggers: ["headline", "headlines", "article title", "title options", "subject line", "better title"]
  category: content-creation
  pairs_with: [writing, content]
---

# Headlines

Find the strongest source-supported tension: who is affected, what changed, and
what is at stake. If the input contains no tension, use accurate utilitarian
titles or ask for the missing result; do not manufacture drama.

Generate a broad set across materially different reader promises (specific
failure/result, contrast, stakes, question, how-to, reader voice, or timely
peg), then retain 3–5 distinct options. Verify every claim, number, entity, and
causal implication against the source. Prefer concrete nouns and error strings
from the brief. Adapt only to requested formats and apply their current hard
limits. End with one recommendation and the source detail that makes it strongest.
