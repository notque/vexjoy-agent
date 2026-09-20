---
name: workflow-help
description: "Explain this repository's live agents, skills, pipelines, and routing; route execution requests instead of answering them as help."
effort: low
user-invocable: true
argument-hint: "[<topic>]"
allowed-tools: [Read, Grep, Glob, Bash]
routing:
  force_route: true
  triggers: ["how does routing work", "what skills exist", "system help", "explain workflow", "I am stuck", "toolkit help"]
  category: meta-tooling
  pairs_with: [workflow, do]
---

# Workflow help

Answer only the requested question. This is an explanatory interface, not an
execution workflow. If the user actually wants work performed, route that
request through `do` or the named skill.

## Live catalog contract

Do not answer from memory. Use `scripts/list-capabilities.py`:

| Need | Command |
|---|---|
| Counts | `python3 scripts/list-capabilities.py summary` |
| Skills | `python3 scripts/list-capabilities.py skills [--category X] [--brief]` |
| Agents | `python3 scripts/list-capabilities.py agents [--brief]` |
| Exact component | `python3 scripts/list-capabilities.py show NAME` |
| Fuzzy discovery | `python3 scripts/list-capabilities.py search QUERY` |

`show` exits 1 when absent; use `search` for nearby names. Catalog commands
exit 2 when their generated index is older than source files. In that case,
report the drift and regenerate with `scripts/generate-skill-index.py` and/or
`scripts/generate-agent-index.py` before quoting counts.

For behavior beyond catalog metadata, read the exact file printed by `show`.
For routing behavior, read `skills/meta/do/SKILL.md` and the live manifest.
Never invent a missing component or invocation syntax.

## Response

Lead with the answer. Include live names, paths, or commands only when useful.
For a system overview, the repository composition is:

`router -> domain agent -> methodology skill -> deterministic script`

Mention related components only when they materially help the current choice.
If a name is absent, say so and offer the closest catalog match.
