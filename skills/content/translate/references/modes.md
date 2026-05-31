# Translate Skill: Mode Reference

> **Load when**: Phase 1 of every translation task.
> **Scope**: Mode detection, per-mode workflow, chunk detection, chunking algorithm, parallel dispatch.

---

## Mode Detection Table

| Request contains | Mode | Notes |
|---|---|---|
| "quick", "fast", "draft", "rough" | quick | Single-pass, no analysis phase |
| "professional", "publication-quality", "polished", "refined" | refined | Full 4-step pipeline |
| "slow", "careful", "accurate" | normal | Emphasizes analysis depth |
| (no qualifier) | normal | Default |

When multiple signals conflict ("quick professional translation"), prefer the higher-effort mode.

---

## Quick Mode

**Use for**: Short text under 500 words, informal content, draft output where speed matters more than polish.

**Workflow**:
1. Detect source and target language.
2. Translate in a single pass using translation principles from SKILL.md Phase 3.
3. Deliver immediately. Skip Phase 2 (ANALYZE) and Phase 4 (POLISH).

**Chunking in quick mode**: For documents over 2000 words that explicitly request quick mode, apply the chunking algorithm below but skip the analysis pass per chunk. Build only a minimal glossary (proper nouns and brand names only).

---

## Normal Mode

**Use for**: Standard documents where accuracy and register matter but publication polish is not required.

**Workflow**:
1. Phase 2: ANALYZE — full analysis pass (language/dialect, register, document type, terminology list).
2. Phase 3: TRANSLATE — single-pass translation using analysis output.
3. Phase 5: DELIVER — report summary.

**Offer refined pass**: After delivering, offer the user an optional refined pass if the output would benefit from idiom review.

---

## Refined Mode

**Use for**: Publication-quality translation, formal documents, content that will be read by native speakers.

**Workflow**:
1. Phase 2: ANALYZE — full analysis pass.
2. Phase 3: TRANSLATE — initial translation draft.
3. Phase 4: POLISH — register scan, idiom review, term audit.
4. Phase 5: DELIVER — report summary including what was changed in the polish pass.

**Register note**: In refined mode, flag every passage where the initial translation sounds like a translation. A skilled native writer would rephrase these; the polish pass rewrites them.

---

## Chunk Detection

Apply chunking when the document exceeds approximately 2000 words. Use this threshold because a single context window produces less consistent term handling and register over long documents than parallel bounded passes do.

**Boundary detection order** (prefer the highest-structure boundary available):

1. Level-2 headings (`## Heading`) — split after the heading, keep heading with its following content.
2. Level-3 headings (`### Heading`) — use when no level-2 headings exist.
3. Blank-line paragraph boundaries — for prose without headings.
4. Sentence boundary — only as a last resort for very long paragraphs with no blank lines.

**Minimum chunk size**: 200 words. Merge chunks below minimum with the preceding chunk.

**Maximum chunk size**: 600 words. Split at next available boundary if a chunk exceeds this.

---

## Chunking Algorithm

```
1. Scan document and identify all split boundaries (in order of preference above).
2. Assign each paragraph/section to a chunk, respecting min/max sizes.
3. Build a session glossary:
   a. In normal/refined mode: extract specialized terms from Phase 2 ANALYZE.
   b. In quick mode: extract proper nouns and brand names only.
   c. Format: markdown table with columns Source Term | Target Term | Notes.
4. For each chunk (dispatch in parallel):
   a. Inject session glossary as a prefix instruction.
   b. Inject document context: "This is chunk N of M from a {document-type} in {register} register."
   c. Translate the chunk using the translation principles from SKILL.md Phase 3.
   d. Capture the translated chunk.
5. Reassemble: concatenate translated chunks in original order, preserving headings and blank lines.
6. Consistency check: scan reassembled output for term variations. If a glossary term appears in multiple forms, normalize to the session glossary form.
```

---

## Parallel Subagent Dispatch Pattern

When dispatching chunks as parallel subagents, structure each subagent call with:

```
System: You are a professional translator. Translate from {source-language} to {target-language}.
Context: This is chunk {N} of {M} from a {document-type}. Register: {register}. 

Session glossary (use these translations consistently):
{glossary-table}

Translate the following text. Preserve all markdown formatting, code blocks, and headings.
Return only the translated text, no commentary.

---
{chunk-text}
```

After all subagents return, proceed to step 5 (reassemble) in the chunking algorithm above.

---

## See Also

- `glossary-template.md` — Glossary format, build procedure, term-preservation rules, example
