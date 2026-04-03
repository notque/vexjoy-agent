---
name: kb-query
description: "Query a knowledge base topic and optionally file the answer."
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
    - "query knowledge base"
    - "kb query"
    - "ask knowledge base"
    - "search kb"
    - "kb question"
  category: research
  complexity: medium
---

# KB Query Skill

Answer a question using the compiled wiki for a knowledge base topic. Reads relevant articles from the wiki, synthesizes an answer, and optionally files the response as a permanent query record that feeds back into the next compile cycle.

## Invocation

```
/kb query {topic} "{question}"
/kb query {topic} "{question}" --no-file
```

- `{topic}` — directory name under `research/` (e.g., `llm-security`)
- `{question}` — the question to answer (quoted string)
- `--no-file` — output only to conversation, do not save a query file

---

## Phase 1: LOCATE

**Goal**: Confirm the topic exists and load its index.

1. Parse the invocation to extract `{topic}`, `{question}`, and whether `--no-file` was specified.
2. Read `research/{topic}/kb.yaml` — if it does not exist, stop and report: "Topic `{topic}` not found. Run `python3 scripts/kb-init.py {topic}` to initialize it."
3. Read `research/{topic}/wiki/_index.md` — this is the full index of compiled concepts and source summaries. If it does not exist, stop and report: "Wiki index not found for `{topic}`. Run `/kb compile {topic}` first."
4. Confirm to yourself: you now have the index and know what articles are available. Do not proceed to Phase 2 until you have read the index.

---

## Phase 2: IDENTIFY

**Goal**: Select the wiki articles most likely to contain the answer.

Using only the `_index.md` (do NOT read individual articles yet), identify the **3-10 most relevant** concept and/or source articles for this question.

For each selected article, note:
- Its path relative to `research/{topic}/wiki/`
- One sentence of reasoning: why this article is likely relevant to the question

Prefer concept articles for questions about ideas, patterns, or mechanisms. Prefer source articles for questions about specific documents, papers, or implementations.

If the index contains no obviously relevant entries, select the closest 3 and note the uncertainty.

---

## Phase 3: SYNTHESIZE

**Goal**: Read the selected articles and produce a comprehensive answer.

1. Read each article identified in Phase 2.
2. Synthesize an answer to the question. Requirements:
   - Answer directly — lead with the answer, not with preamble
   - Cite sources inline using this format: `[Source: concept-name](concepts/concept-name.md)` or `[Source: source-slug](sources/source-slug.md)`
   - If multiple articles address the same point, synthesize them rather than listing them separately
   - If the articles contradict each other, note the contradiction and your best synthesis
   - If the KB does not contain enough information to fully answer the question, say so explicitly. Name what is missing and which raw sources, if any, could be added to fill the gap.
3. Aim for 300-1200 words. Shorter if the answer is simple. Longer only when the question requires depth.

Do NOT draw on general knowledge when the KB has relevant content. Prefer KB sources. If you must supplement with general knowledge (because the KB is silent on a point), mark it clearly: "(from general knowledge, not in KB)".

---

## Phase 4: FILE

**Goal**: Persist the query and answer as a permanent wiki record.

If `--no-file` was specified: output the answer to the conversation and stop. Do not save any file.

Otherwise:

1. Derive a slug from the question:
   - Lowercase, strip punctuation, replace spaces with hyphens
   - Max 60 characters
   - Example: "What is prompt injection?" → `what-is-prompt-injection`

2. Get today's date in `YYYY-MM-DD` format.

3. Write the answer to `research/{topic}/wiki/queries/{date}-{slug}.md` with this structure:

```markdown
---
query: "{the exact question asked}"
date: "{ISO 8601 timestamp, e.g. 2026-04-02T14:30:00}"
sources_consulted:
  - concepts/relevant-concept.md
  - sources/relevant-source.md
filed: true
---

# {the question, as a title}

{the full synthesized answer, with inline citations}
```

Populate `sources_consulted` with the relative paths (within `wiki/`) of every article you read during Phase 3.

4. Confirm to the user: "Answer filed to `research/{topic}/wiki/queries/{date}-{slug}.md`. It will be incorporated into concept articles during the next `/kb compile {topic}` run."

---

## Anti-Patterns

**Do NOT answer from general knowledge if the KB has relevant content.** The point of the system is to build and use a local knowledge base. Bypassing it defeats the flywheel.

**Do NOT read every wiki file.** Use the `_index.md` to select relevant articles. Reading every file wastes time and context on irrelevant material.

**Do NOT write query files longer than 1500 words.** If the answer requires more than that, it is probably two separate questions. Answer the specific question asked.

**Do NOT omit `sources_consulted`.** This field is the data the flywheel uses during the next compile run. An empty or incomplete list breaks the feedback loop.

**Do NOT skip filing unless `--no-file` was explicitly specified.** Filed queries accumulate domain knowledge. Each one makes the next query better.
