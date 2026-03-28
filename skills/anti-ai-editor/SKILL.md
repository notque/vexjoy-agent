---
name: anti-ai-editor
description: |
  Review and revise content to remove AI-sounding patterns. Voice-agnostic
  editor that detects cliches, passive voice, structural monotony, and
  meta-commentary. Use when content sounds robotic, needs de-AIing, or
  voice validation flags synthetic patterns. Use for "edit for AI",
  "remove AI patterns", "make it sound human", or "de-AI this".
  Route to other skills for grammar checking, factual editing, or full rewrites.
  Route to other skills for voice generation (use voice skills instead).
version: 2.1.0
user-invocable: false
command: /edit
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - "remove AI patterns"
    - "de-AI content"
    - "make it sound human"
  category: content-creation
---

# Anti-AI Editor

Detect and remove AI-generated writing patterns through targeted, minimal edits. This skill scans for cliches, passive voice, structural monotony, and meta-commentary, then proposes specific replacements -- always targeted, minimal edits. Human imperfections (run-ons, fragments, loose punctuation) are features, not bugs; preserve them.

## Instructions

### Phase 1: ASSESS

**Goal**: Read file, identify skip zones, scan for AI patterns.

**Step 1: Read and classify the file**

Read the target file. Identify file type (blog post, docs, README). Skip frontmatter (YAML between `---` markers), code blocks, inline code, and blockquotes -- edits to these zones corrupt structure and would corrupt structure.

If a voice profile is specified, also check voice-specific anti-patterns alongside the standard categories.

**Step 2: Scan for issues by category**

| Category | What to Find | Reference |
|----------|--------------|-----------|
| AI Cliches | "delve", "leverage", "utilize", "robust" | `references/cliche-replacements.md` |
| News AI Tells | "worth sitting with", "consequences extend beyond", "that's the kind of", dramatic rhythm | `references/detection-patterns.md` |
| Copula Avoidance | "serves as a", "boasts a", "features a" | `references/detection-patterns.md` |
| Passive Voice | "was done by", "has been", "will be" | `references/detection-patterns.md` |
| Structural | Monotonous sentence lengths, excessive lists, boldface overuse, dramatic AI rhythm | `references/detection-rules.md` |
| Meta-commentary | "In this article", "Let me explain", "As we've discussed" | `references/cliche-replacements.md` |
| Dangling -ing | "highlighting its importance", "underscoring the significance" | `references/detection-patterns.md` |
| Puffery/Legacy | "testament to", "indelible mark", "enduring legacy" | `references/detection-patterns.md` |
| Generic Closers | "future looks bright", "continues to evolve" | `references/detection-patterns.md` |
| Curly Quotes | \u201C \u201D \u2018 \u2019 (ChatGPT-specific) | `references/detection-patterns.md` |

Some flagged words are appropriate in technical contexts. "Leverage" in "Use a lever to leverage mechanical advantage" is correct -- only flag words when used as corporate-speak, not in their literal or technical sense.

**Step 3: Count and classify issues**

Record each issue with line number, category, and severity weight:
- AI Cliche (Tier 1): weight 3
- News AI Tell (Tier 1-News): weight 3 (pseudo-profound, philosophizing, meta-significance)
- Copula Avoidance (Tier 1b): weight 3
- Meta-commentary: weight 2
- Dangling -ing clause (Tier 2b): weight 2
- Significance puffery (Tier 2c): weight 2
- Generic positive conclusion (Tier 2d): weight 2
- Dramatic AI rhythm (Tier 1-News): weight 2
- Structural issue: weight 2
- Fluff phrase: weight 1
- Passive voice: weight 1
- Redundant modifier: weight 1
- Curly quotes (Tier 3b): weight 1

**Gate**: Issues documented with line numbers and categories. Total severity score calculated. Proceed only when gate passes.

### Phase 2: DECIDE

**Goal**: Determine editing approach based on severity.

**Step 1: Choose approach by issue count**

| Severity Score | Approach |
|----------------|----------|
| 0-5 | Report "Content appears natural". Stop. |
| 6-15 | Apply targeted fixes |
| 16-30 | Group by paragraph, fix systematically |
| 30+ | Paragraph-by-paragraph review |

**Step 2: Prioritize fixes**

1. **Structural Issues** (affect overall readability)
2. **AI Cliches** (most obvious tells)
3. **Meta-commentary** (usually removable)
4. **Passive Voice** (case-by-case judgment)

Every fix must be the minimum change needed. Multiple small edits beat one big rewrite because rewrites lose author voice and may introduce new AI patterns. Every detected issue must include a specific replacement -- reporting "Contains AI-sounding language" without a concrete fix is useless.

**Step 3: Wabi-sabi check**

Before proposing any fix, ask: "Would removing this imperfection make it sound MORE robotic?" If yes, preserve it. Preserve:
- Run-on sentences that convey enthusiasm
- Fragment punches that create rhythm
- Loose punctuation that matches conversational flow
- Self-corrections mid-thought ("well, actually...")

Natural informal language like "So basically" in a casual blog post is spoken rhythm, not an AI pattern. Only remove patterns that are AI-generated, not patterns that are merely informal.

**Gate**: Approach selected. Fixes prioritized. Wabi-sabi exceptions noted. Proceed only when gate passes.

### Phase 3: EDIT

**Goal**: Generate edit report, get confirmation, apply changes.

**Step 1: Generate the edit report**

Show before/after for every modification with the reason -- always show before/after for every modification with the reason.

```
=================================================================
 ANTI-AI EDIT: [filename]
=================================================================

 ISSUES FOUND: [total]
   AI Cliches: [count]
   Passive Voice: [count]
   Structural: [count]
   Meta-commentary: [count]

 CHANGES:

 Line [N]:
   - "[original text]"
   + "[replacement text]"
   Reason: [specific explanation]

 [Continue for all changes]

=================================================================
 PREVIEW
=================================================================
[Show complete edited content]

=================================================================
 Apply changes? [Waiting for confirmation]
=================================================================
```

Style edits must preserve what the content says. When fixing "This solution robustly handles edge cases", write "This solution handles edge cases reliably" -- fix the style word, keep the technical meaning intact. If removing a flagged word would lose meaningful information, rephrase rather than delete.

**Step 2: Apply changes after confirmation**

Use the Edit tool for each change. Verify each edit applied correctly.

**Gate**: All changes applied. File re-read to confirm no corruption. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm edits preserved meaning and improved naturalness.

**Step 1**: Re-read edited file completely

**Step 2**: Verify no meaning was lost or changed

**Step 3**: Verify no new AI patterns were introduced by edits

**Step 4**: Confirm frontmatter and code blocks are untouched

**Step 5**: Report final summary

```markdown
## Edit Summary
File: [path]
Issues Found: [count]
Issues Fixed: [count]
Issues Skipped: [count with reasons]
Meaning Preserved: Yes/No
```

**Gate**: All verification steps pass. Edit is complete.

## Reference Material

### Examples

#### Example 1: Blog Post (Heavy Editing)
User says: "De-AI this blog post"
Actions:
1. Read file, skip frontmatter, scan all categories (ASSESS)
2. Score 22 -- systematic paragraph-by-paragraph approach (DECIDE)
3. Generate report with 10 changes, show preview, apply after confirmation (EDIT)
4. Re-read, verify meaning preserved, no new AI patterns (VERIFY)
Result: 67% shorter intro, all AI cliches removed, voice preserved

#### Example 2: Technical Docs (Light Editing)
User says: "Check this for AI patterns"
Actions:
1. Read file, identify technical context, scan for patterns (ASSESS)
2. Score 7 -- targeted fixes only, preserve technical terms (DECIDE)
3. Replace "utilizes" with "uses", remove throat-clearing, show preview (EDIT)
4. Verify technical accuracy unchanged (VERIFY)
Result: Clearer prose, same information, technical terms untouched

## Error Handling

### Error: "File Not Found"
Cause: Path incorrect or file does not exist
Solution:
1. Verify path with `ls -la [path]`
2. Use glob pattern to search: `Glob **/*.md`
3. Confirm correct working directory

### Error: "No Issues Found"
Cause: Content is already natural, or scanner missed patterns
Solution:
1. Report "Content appears natural -- no AI patterns detected"
2. Show sentence length statistics for manual verification
3. Check structural patterns (monotony, list overuse) even if no word-level flags

### Error: "Frontmatter Corrupted After Edit"
Cause: Edit tool matched content inside YAML frontmatter
Solution:
1. Fall back to treating entire file as content
2. Re-read file to verify YAML integrity
3. If corrupted, restore from git: `git checkout -- [file]`

## References

- `${CLAUDE_SKILL_DIR}/references/cliche-replacements.md`: Complete list of 80+ AI phrases with replacements
- `${CLAUDE_SKILL_DIR}/references/detection-patterns.md`: Regex patterns for automated detection
- `${CLAUDE_SKILL_DIR}/references/detection-rules.md`: Inline detection rules and structural checks
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Before/after examples from real edits
