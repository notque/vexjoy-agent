# KB Compile Skill

Compile raw clipped sources (`research/{topic}/raw/`) into structured wiki articles (`research/{topic}/wiki/`). Produces concept articles, source summaries, and a maintained index.

## Phase 1: SCAN

**Goal**: Determine what needs compiling.

1. Read `research/{topic}/kb.yaml` to get topic config (description, source types, compile settings).
2. List all files in `research/{topic}/raw/` — these are the source markdown files. Ignore the `images/` subdirectory.
3. List all files in `research/{topic}/wiki/sources/` — these are already-compiled source summaries.
4. **Identify new sources**: Files in `raw/` whose slug does not appear as a corresponding file in `wiki/sources/`. A slug match means `raw/{slug}.md` has a corresponding `wiki/sources/{slug}.md`.
5. **Identify modified sources**: Not applicable in Phase 1 (treat all unmatched raw files as new).
6. Report to user: "Found N raw sources, M already compiled, K new to process."

If there are no new sources, proceed directly to Phase 4 (VERIFY) to confirm index consistency.

---

## Phase 2: COMPILE

**Goal**: For each new raw source, produce a wiki summary and update concept articles.

For **each new raw source file** (`research/{topic}/raw/{slug}.md`):

### 2a. Read and parse the raw source

- Read the raw markdown file.
- Extract the YAML frontmatter: title, source URL, clipped date, type.
- Read the markdown body: this is the clipped article content.

### 2b. Create source summary in `wiki/sources/{slug}.md`

Write a source summary file with this structure:

```markdown
---
title: "{title from raw frontmatter}"
source_url: "{source URL}"
clipped_date: "{clipped date}"
type: {article|paper|note|etc}
concepts:
  - concept-slug-1
  - concept-slug-2
---

## Summary

{2-4 paragraph summary of the key points from the source. Write in your own words - do NOT copy verbatim from the source. Focus on the most important ideas, arguments, and conclusions.}

## Key Points

- {bullet point 1}
- {bullet point 2}
- {bullet point 3}

## Source

Raw file: [../../raw/{slug}.md](../../raw/{slug}.md)
Original: [{title}]({source_url})
```

Identify **3-7 concepts** mentioned in this source. A concept is a distinct idea, term, technique, pattern, or named thing that appears meaningfully in the content. Use kebab-case slugs (e.g., `chain-of-thought`, `retrieval-augmented-generation`, `prompt-injection`). List these in the frontmatter `concepts` list.

### 2c. Update or create concept articles

For each concept identified in 2b:

**If `wiki/concepts/{concept}.md` already exists:**
- Read the existing file.
- Add this source to the `sources` list in the frontmatter (if not already present).
- Incorporate any new, non-duplicate information into the article body. Add a new section or expand an existing one. Do NOT rewrite the article from scratch - make targeted additions.
- Update `related_concepts` if this source suggests new connections.

**If `wiki/concepts/{concept}.md` does not exist:**
- Only create it if at least one of these is true:
  - The concept appears in 2+ sources (check existing `wiki/sources/` files for mentions)
  - The concept is clearly significant (a major named technique, a well-known algorithm, a foundational idea)
- Create `wiki/concepts/{concept}.md` with this structure:

```markdown
---
title: "{Concept Name (Title Case)}"
related_concepts:
  - related-concept-slug
sources:
  - {slug-of-first-source}
---

# {Concept Name}

{1-2 sentence definition or explanation of what this concept is.}

## Overview

{2-4 paragraphs of explanation. Cover: what it is, why it matters, how it works at a high level, and where it appears.}

## Key Properties

- {property 1}
- {property 2}

## Sources

- [{source title}](../sources/{slug}.md)
```

---

## Phase 2b: FLYWHEEL — Incorporate query outputs

**Goal**: Feed filed query answers back into concept articles, compounding accumulated knowledge.

Check `wiki/queries/` for any query files with `filed: true` in their frontmatter (and without `incorporated: true`, which marks already-processed queries).

For **each unprocessed filed query**:

1. Read the query file. Note the `query` field (the original question) and `sources_consulted` (the articles the query drew from).
2. Read each article listed in `sources_consulted`.
3. Review the query answer body for insights, connections, or synthesized knowledge that do not already appear in the concept articles. Look for:
   - Explicit answers or conclusions not currently stated in any concept article
   - Cross-concept connections the query identified
   - Clarifications or nuances added during synthesis
4. For each concept article that should be updated:
   - Make targeted additions only — do NOT rewrite from scratch
   - Add a "See also" reference at the bottom of the article's Sources section: `- [Query: {original question}](../queries/{query-filename}.md)`
5. Do NOT delete the query file — it is a permanent record.
6. Mark the query as processed by adding `incorporated: true` to its frontmatter.

If `wiki/queries/` does not exist or contains no unprocessed filed queries, skip this phase and proceed to Phase 3.

## Phase 3: INDEX

**Goal**: Rebuild `wiki/_index.md` to reflect current state.

1. List all files in `wiki/concepts/` and `wiki/sources/`.
2. For each file, read its frontmatter to get: title and (for concepts) related_concepts, (for sources) source_url.
3. Write a brief one-line summary for each entry - use the first sentence of the article body.
4. Rewrite `wiki/_index.md` with this structure:

```markdown
---
topic: {topic}
last_compiled: "{ISO 8601 timestamp}"
entry_count: {total concepts + sources}
---
# {Topic Display Name} Knowledge Base

## Concepts ({N})

- [Concept Name](concepts/slug.md) - one-line summary
- [Concept Name](concepts/slug.md) - one-line summary

## Sources ({M})

- [Source Title](sources/slug.md) - one-line summary (from {domain})
- [Source Title](sources/slug.md) - one-line summary (from {domain})
```

Extract the domain from `source_url` in the source frontmatter for the "(from {domain})" annotation.

---

## Phase 4: VERIFY

**Goal**: Confirm the wiki is internally consistent.

Run these checks:

1. **Raw coverage**: Every `raw/{slug}.md` file (excluding `images/`) has a corresponding `wiki/sources/{slug}.md`. Report any gaps as: "Missing source summary: {slug}".

2. **Concept backlinks**: Every concept slug listed in any `wiki/sources/*.md` frontmatter exists as `wiki/concepts/{slug}.md`. Report gaps as: "Missing concept article: {slug} (referenced in sources/{source_slug}.md)".

3. **Index completeness**: Every file in `wiki/concepts/` and `wiki/sources/` appears in `wiki/_index.md`. Report gaps as: "Not in index: {path}".

4. **Summary**: Report total counts - concepts, sources, images, gaps.

If there are gaps, offer to fix them. Do not silently patch gaps during verification - report first, then ask.

---

## Patterns to Detect and Fix

**Do NOT rewrite existing concept articles from scratch.** Incremental updates preserve the accumulated knowledge from prior compilations. If the existing article is good, only add what is new.

**Do NOT create concepts with a single source** unless the concept is clearly significant (a named algorithm, a major pattern, an established term). Single-source concepts that are not significant just create noise.

**Do NOT include raw source content verbatim.** Summarize and synthesize. The wiki is a compressed, queryable representation - not a mirror.

**Do NOT skip `_index.md` maintenance.** The index is the entry point for humans and LLMs querying the KB. A stale index defeats the purpose of the system. Always rebuild it after any compilation run.

**Do NOT create concepts without a definition.** Every concept article needs at least a one-sentence definition. A concept page with only a title and a sources list is not useful.
