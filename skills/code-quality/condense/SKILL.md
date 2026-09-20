---
name: condense
description: "Reduce instruction and documentation text while preserving every action-changing contract."
user-invocable: true
argument-hint: "<file-or-glob>"
allowed-tools: [Read, Edit, Write, Bash, Grep, Glob]
routing:
  triggers: [condense, reduce words, clarity pass, information density, remove prose, tighten, fewer words]
  pairs_with: [toolkit]
  complexity: Simple
  category: code-quality
---

# Condense

Edit the requested text in place for information density. For globs, state the resolved files before editing.

Preserve semantic obligations: commands and paths; authorization and safety boundaries; gates, ordering, fallbacks, thresholds, schemas, and output contracts; domain facts; hard-won failure knowledge; frontmatter values; and reasoning whose absence could change a decision. Preserve exact wording only when another program or test consumes it.

Remove generic advice a capable model already knows, motivational framing, repeated rules, exhaustive examples, obvious explanations, obsolete scaffolding, and prose that adds no decision. Merge duplicates and reorganize when that makes the surviving contract clearer. A shorter file that changes behavior is a regression.

Before editing, record word/byte counts and inspect callers when deleting headings, anchors, reference files, or machine-consumed phrases. After editing, parse frontmatter where present, validate links and commands, run the artifact's own validator if available, and report before/after counts plus any intentionally preserved redundancy.
