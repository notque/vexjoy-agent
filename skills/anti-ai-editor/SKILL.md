---
name: anti-ai-editor
description: "Remove AI-sounding patterns from content."
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
    - "remove AI voice"
    - "humanize text"
  category: content-creation
  pairs_with:
    - voice-writer
    - voice-validator
    - joy-check
---

# Anti-AI Editor

Detect and remove AI-generated writing patterns through targeted, minimal edits. Scans for cliches, passive voice, structural monotony, and meta-commentary, then proposes specific replacements. Human imperfections (run-ons, fragments, loose punctuation) are features, not bugs; preserve them.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| AI Cliches | `cliche-replacements.md` | "delve", "leverage", "utilize", "robust" |
| News AI Tells | `detection-patterns.md` | "worth sitting with", "consequences extend beyond", "that's the kind of", dramatic rhythm |
| Copula Avoidance | `detection-patterns.md` | "serves as a", "boasts a", "features a" |
| Passive Voice | `detection-patterns.md` | "was done by", "has been", "will be" |
| Structural | `detection-rules.md` | Monotonous sentence lengths, excessive lists, boldface overuse, dramatic AI rhythm |
| Meta-commentary | `cliche-replacements.md` | "In this article", "Let me explain", "As we've discussed" |
| Dangling -ing | `detection-patterns.md` | "highlighting its importance", "underscoring the significance" |
| Puffery/Legacy | `detection-patterns.md` | "testament to", "indelible mark", "enduring legacy" |
| Generic Closers | `detection-patterns.md` | "future looks bright", "continues to evolve" |
| Curly Quotes | `detection-patterns.md` | “ ” ‘ ’ (ChatGPT-specific) |
| Dash-as-Separator | `detection-patterns.md` | ` -- ` sentence joiner, `—` em-dash in prose (not CLI flags) |
| Novelty Inflation | `detection-patterns.md` | "nobody's naming", "what nobody tells you", engagement bait |
| Synonym Cycling | `detection-patterns.md` | 3+ synonyms for same concept in one paragraph |
| False Concession | `detection-patterns.md` | "While X is impressive, Y remains" (both vague) |
| Emotional Flatline | `detection-patterns.md` | "What surprised me most", "I was fascinated" |

## Instructions

### Phase 1: ASSESS

**Goal**: Read file, identify skip zones, scan for AI patterns.

**Step 1: Read and classify the file**

Read the target file. Identify file type (blog post, docs, README). Skip frontmatter (YAML between `---`), code blocks, inline code, and blockquotes -- edits to these zones corrupt structure.

Auto-detect content profile (linkedin, blog, technical-blog, investor-email, docs, casual) per `references/context-profiles.md`. Apply profile-specific tolerance throughout.

If a voice profile is specified, also check voice-specific anti-patterns.

**Step 2: Scan for issues by category**

| Category | What to Find | Reference |
|----------|--------------|-----------|
| AI Cliches | "delve", "leverage", "utilize", "robust" | `references/cliche-replacements.md` |
| News AI Tells | "worth sitting with", "consequences extend beyond", dramatic rhythm | `references/detection-patterns.md` |
| Copula Avoidance | "serves as a", "boasts a", "features a" | `references/detection-patterns.md` |
| Passive Voice | "was done by", "has been", "will be" | `references/detection-patterns.md` |
| Structural | Monotonous lengths, excessive lists, boldface overuse | `references/detection-rules.md` |
| Meta-commentary | "In this article", "Let me explain" | `references/cliche-replacements.md` |
| Dangling -ing | "highlighting its importance" | `references/detection-patterns.md` |
| Puffery/Legacy | "testament to", "indelible mark" | `references/detection-patterns.md` |
| Generic Closers | "future looks bright", "continues to evolve" | `references/detection-patterns.md` |
| Curly Quotes | “ ” ‘ ’ | `references/detection-patterns.md` |
| Dash-as-Separator | ` -- ` joiner, `—` em-dash (not CLI) | `references/detection-patterns.md` |
| Novelty Inflation | "nobody's naming", engagement bait | `references/detection-patterns.md` |
| Synonym Cycling | 3+ synonyms for same concept | `references/detection-patterns.md` |
| False Concession | "While X is impressive, Y remains" | `references/detection-patterns.md` |
| Emotional Flatline | "What surprised me most" | `references/detection-patterns.md` |

Only flag words used as corporate-speak, not literal/technical usage. "Leverage" in "use a lever to leverage mechanical advantage" is correct.

**Step 3: Count and classify issues**

Record each with line number, category, severity weight:
- AI Cliche (Tier 1): weight 3
- News AI Tell (Tier 1-News): weight 3
- Copula Avoidance (Tier 1b): weight 3
- Novelty inflation (Tier 1g): weight 3
- Meta-commentary: weight 2
- Dangling -ing (Tier 2b): weight 2
- Significance puffery (Tier 2c): weight 2
- Generic positive conclusion (Tier 2d): weight 2
- Dramatic AI rhythm (Tier 1-News): weight 2
- Structural issue: weight 2
- Synonym cycling (Tier 1h): weight 2
- False concession (Tier 2e): weight 2
- Emotional flatline (Tier 2f): weight 2
- Reasoning chain artifact (Tier 2g): weight 2
- Dash-as-separator (style): weight 2
- Fluff phrase: weight 1
- Passive voice: weight 1
- Redundant modifier: weight 1
- Curly quotes (Tier 3b): weight 1
- Parenthetical hedging (Tier 3c): weight 1

**Gate**: Issues documented with line numbers and categories. Total severity score calculated.

### Phase 2: DECIDE

**Goal**: Determine editing approach based on severity.

**Step 1: Choose approach**

| Severity Score | Approach |
|----------------|----------|
| 0-5 | Report "Content appears natural". Stop. |
| 6-15 | Targeted fixes |
| 16-30 | Group by paragraph, fix systematically |
| 30+ | Paragraph-by-paragraph review |

**Step 1b: Rewrite threshold** -- If score >30 AND 3+ categories flagged AND structural rhythm is uniform, advise full rewrite. Patching high-density AI text often introduces new patterns.

**Step 2: Prioritize fixes**

1. **Structural Issues** (overall readability)
2. **AI Cliches** (most obvious tells)
3. **Meta-commentary** (usually removable)
4. **Passive Voice** (case-by-case)

Every fix must be the minimum change needed. Multiple small edits beat one big rewrite -- rewrites lose author voice and may introduce new AI patterns. Every issue must include a specific replacement.

**Step 3: Wabi-sabi check**

Before any fix, ask: "Would removing this make it sound MORE robotic?" If yes, preserve it:
- Run-on sentences conveying enthusiasm
- Fragment punches creating rhythm
- Loose punctuation matching conversational flow
- Self-corrections mid-thought ("well, actually...")

Natural informal language like "So basically" is spoken rhythm, not an AI pattern. Only remove AI-generated patterns, not informal ones.

**Gate**: Approach selected. Fixes prioritized. Wabi-sabi exceptions noted.

### Phase 3: EDIT

**Goal**: Generate edit report, get confirmation, apply changes.

**Step 1: Generate the edit report**

Show before/after for every modification with reason.

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

=================================================================
 PREVIEW
=================================================================
[Show complete edited content]

=================================================================
 Apply changes? [Waiting for confirmation]
=================================================================
```

Fix the style word, keep the technical meaning. "This solution robustly handles edge cases" -> "This solution handles edge cases reliably." If removing a word loses information, rephrase rather than delete.

**Step 2: Apply changes after confirmation**

Use Edit tool for each change. Verify each applied correctly.

**Gate**: All changes applied. File re-read to confirm no corruption.

### Phase 4: VERIFY

**Goal**: Confirm edits preserved meaning and improved naturalness.

1. Re-read edited file completely
2. Verify no meaning lost or changed
3. Verify no new AI patterns introduced
4. Confirm frontmatter and code blocks untouched
5. Report final summary:

```markdown
## Edit Summary
File: [path]
Issues Found: [count]
Issues Fixed: [count]
Issues Skipped: [count with reasons]
Meaning Preserved: Yes/No
```

**Gate**: All verification steps pass. Edit complete.

## Reference Material

### Examples

#### Example 1: Blog Post (Heavy Editing)
User says: "De-AI this blog post"
1. Read file, skip frontmatter, scan all categories (ASSESS)
2. Score 22 -- systematic approach (DECIDE)
3. Generate report with 10 changes, show preview, apply after confirmation (EDIT)
4. Re-read, verify meaning preserved (VERIFY)
Result: 67% shorter intro, all AI cliches removed, voice preserved

#### Example 2: Technical Docs (Light Editing)
User says: "Check this for AI patterns"
1. Read file, identify technical context, scan (ASSESS)
2. Score 7 -- targeted fixes, preserve technical terms (DECIDE)
3. Replace "utilizes" with "uses", remove throat-clearing (EDIT)
4. Verify technical accuracy unchanged (VERIFY)
Result: Clearer prose, same information, technical terms untouched

## Error Handling

### Error: "File Not Found"
Cause: Path incorrect or file missing
Solution: Verify with `ls -la [path]`. Use `Glob **/*.md` to search. Check working directory.

### Error: "No Issues Found"
Cause: Content already natural, or scanner missed patterns
Solution: Report "Content appears natural." Show sentence length stats. Check structural patterns even without word-level flags.

### Error: "Frontmatter Corrupted After Edit"
Cause: Edit tool matched content inside YAML frontmatter
Solution: Re-read to verify YAML integrity. If corrupted, restore: `git checkout -- [file]`

## References

- `${CLAUDE_SKILL_DIR}/references/cliche-replacements.md`: 80+ AI phrases with replacements
- `${CLAUDE_SKILL_DIR}/references/detection-patterns.md`: Regex patterns for automated detection
- `${CLAUDE_SKILL_DIR}/references/detection-rules.md`: Inline detection rules and structural checks
- `${CLAUDE_SKILL_DIR}/references/context-profiles.md`: Content type profiles and tolerance matrix
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Before/after examples from real edits
