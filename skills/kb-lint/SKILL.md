---
name: kb-lint
description: "Health check and lint a knowledge base wiki for consistency and gaps."
version: 1.0.0
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
    - "lint knowledge base"
    - "kb lint"
    - "check kb health"
    - "knowledge base health"
    - "kb consistency"
  category: research
  complexity: medium
---

# KB Lint Skill

Health check a knowledge base wiki under `research/{topic}/` for structural consistency, broken references, and content quality gaps. Produces a structured lint report.

## Invocation

```
/kb-lint --topic TOPIC [--fix]
```

- `--topic TOPIC` — the topic slug under `research/`
- `--fix` — attempt to auto-fix structural errors (missing index entries, broken links)

## Phase 1: INVENTORY

Read `research/{topic}/kb.yaml`. Count all files:

- `raw/` — raw source markdown files
- `wiki/concepts/` — concept articles
- `wiki/sources/` — source summary articles
- `wiki/queries/` — saved query outputs

Read `research/{topic}/wiki/_index.md`.

Report current state:

```
KB '{topic}': N raw sources, M concepts, P source summaries, Q queries.
Last compiled: {last_compiled from _index.md frontmatter, or "never"}.
```

## Phase 2: STRUCTURAL CHECKS

Run deterministic checks. Read file contents and frontmatter as needed. Do NOT read raw sources for structural checks — wiki files only.

| Check | Pass Condition | Severity |
|-------|----------------|----------|
| Raw coverage | Every `raw/*.md` has a matching `wiki/sources/*.md` | ERROR |
| Concept backlinks | Every concept slug in source frontmatter `concepts:` list exists as `wiki/concepts/{slug}.md` | ERROR |
| Source backlinks | Every source slug in concept frontmatter `sources:` list exists as `wiki/sources/{slug}.md` | WARN |
| Index completeness | Every `.md` file under `wiki/` (excluding `_index.md`) appears in `_index.md` | ERROR |
| Orphan concepts | Concepts that appear in 0 source `concepts:` lists | WARN |
| Empty articles | Wiki files with fewer than 50 words of content (excluding frontmatter block) | WARN |
| Stale index | `_index.md` frontmatter `last_compiled` is more than 7 days old | WARN |
| Missing frontmatter | Any wiki file (concepts, sources, queries) that lacks a valid YAML frontmatter block | ERROR |
| Broken cross-links | Markdown links `[text](path)` within wiki files that point to non-existent files | ERROR |

For each check:
- Collect all failures with specific file names
- Accumulate counts: errors, warnings

## Phase 3: CONTENT QUALITY

LLM-judged quality checks on concept articles. Read up to 10 concept articles (or all if fewer than 10). For each:

**Article-level checks:**
- Is the article just a title with no substance? (fewer than 3 sentences of actual content)
- Does the article have a definition or overview section?
- Does the article contain contradictory statements?

**Cross-article checks (after reading the sample):**
- Concept overlap: are two concepts covering substantially the same topic? Flag pairs and suggest merging.
- Gap analysis: based on sources referenced and concepts present, are there obvious missing concepts? List up to 5 significant gaps only — do not suggest minor terms.

## Phase 4: REPORT

Produce a structured report to stdout. Format:

```markdown
# KB Lint Report: {topic}

## Summary
- Total: N raw, M concepts, P sources, Q queries
- Errors: X | Warnings: Y | Suggestions: Z

## Errors
- [ERROR] {description with specific file name(s)}

## Warnings
- [WARN] {description with specific file name(s)}

## Suggestions
- [SUGGEST] {description}

## Recommended Actions
1. {specific action to fix most critical issue}
2. {next action}
3. ...
```

If there are no errors, no warnings, and no suggestions, output:

```
KB '{topic}' is healthy. No issues found.
```

### Auto-fix behavior (`--fix`)

If `--fix` was specified AND structural errors were found, offer to repair:

- **Missing index entries**: append missing file paths to `_index.md` articles list
- **Broken `[[wiki/path]]`-style links**: report only (cannot safely infer correct target)

Before fixing, print each planned change and ask for confirmation. Do NOT auto-fix content quality issues — those require human or LLM judgment during compile.

## Anti-patterns

- Do NOT fix issues silently — always report before fixing
- Do NOT suggest concepts for every minor term — only significant gaps (max 5)
- Do NOT report passing checks — only failures and suggestions
- Do NOT read every raw source during lint — structural checks use wiki files only
- Do NOT treat missing `research/{topic}/` as a lint failure — exit with a clear error message before phase 1
