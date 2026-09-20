---
name: comment-quality
description: "Review code comments for change-history language that will go stale, and rewrite them as current invariants or rationale."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
routing:
  triggers: [review comments, fix temporal references, comment quality, stale comments, outdated comment]
  category: code-quality
  pairs_with: [code-quality, review]
---

# Comment Quality

Comments should explain a current invariant, constraint, surprising mechanism, or rationale. Version control owns change history.

Scan only the requested files. `references/temporal-keywords.md` is a candidate list, not a verdict: inspect comment syntax and surrounding code before classifying a match. Ignore string literals and identifiers. Preserve legal headers, generated markers, required API/version annotations, and deprecation notices whose migration contract remains useful. Words such as `current`, `before`, `after`, and `since` are valid when they describe runtime state, ordering, or an API contract rather than development history.

Flag comments whose meaning depends on an unstated earlier revision, for example “now uses JWT,” “fixed retry handling,” or “faster than before.” For each finding:

1. Read the enclosing function or section.
2. Decide whether the durable fact is behavior, rationale, or neither.
3. Rewrite to that durable fact, or delete the comment when code already says it.
4. Report `file:line`, original, replacement/deletion, and the inferred invariant.

Do not invent rationale from code shape alone. When the historical context is the only apparent meaning and intent is unclear, leave it unchanged and identify the ambiguity. Apply edits only when requested, and re-read each edited block afterward.
