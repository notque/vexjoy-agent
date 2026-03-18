---
name: anti-ai-editor
description: |
  Review and revise content to remove AI-sounding patterns. Voice-agnostic
  editor that detects cliches, passive voice, structural monotony, and
  meta-commentary. Use when content sounds robotic, needs de-AIing, or
  voice validation flags synthetic patterns. Use for "edit for AI",
  "remove AI patterns", "make it sound human", or "de-AI this".
  Do NOT use for grammar checking, factual editing, or full rewrites.
  Do NOT use for voice generation (use voice skills instead).
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
---

# Anti-AI Editor

## Operator Context

This skill operates as an operator for content editing, detecting and removing AI-generated writing patterns. It implements the **Targeted Revision** architectural pattern -- scan for patterns, propose minimal fixes, preserve meaning -- with **Wabi-Sabi Authenticity** ensuring human imperfections are features, not bugs.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before editing
- **Over-Engineering Prevention**: Make minimal fixes only. No rewrites, no "while I'm here" improvements
- **Preserve Meaning**: NEVER change actual meaning or intent while fixing style
- **Show All Changes**: Display before/after for every modification with reason
- **Context Awareness**: Some flagged words are appropriate in technical contexts
- **Wabi-Sabi Enforcement**: Human imperfections (run-ons, fragments, loose punctuation) are features -- do NOT "fix" them

### Default Behaviors (ON unless disabled)
- **Full Preview**: Show complete edited content before saving
- **Categorized Reporting**: Group issues by type (cliches, passive, structural, meta)
- **Actionable Fixes**: Every detected issue includes a specific replacement
- **Frontmatter Skip**: Skip YAML frontmatter, code blocks, and inline code
- **Voice Integration**: If voice specified, check voice-specific anti-patterns

### Optional Behaviors (OFF unless enabled)
- **Auto-Apply**: Apply changes without preview confirmation
- **Aggressive Mode**: Flag borderline cases (use for marketing content)
- **Stats Only**: Report issues without suggesting fixes

## What This Skill CAN Do
- Detect AI cliches and suggest natural replacements
- Identify passive voice overuse and suggest active alternatives
- Flag structural issues (monotonous sentence length, list overuse)
- Remove meta-commentary that adds no value
- Handle Hugo frontmatter correctly (skip YAML, edit content only)
- Preserve code blocks and technical terminology
- Show before/after comparisons for all changes

## What This Skill CANNOT Do
- Rewrite content entirely (use targeted fixes only)
- Change technical accuracy for stylistic reasons (meaning is sacred)
- Remove domain-specific jargon that is appropriate in context
- Fix factual errors (style-only skill, not a fact-checker)
- Generate new content (use voice skills instead)
- Polish away authentic imperfections (see [Wabi-Sabi](../shared-patterns/wabi-sabi-authenticity.md))

---

## Instructions

### Phase 1: ASSESS

**Goal**: Read file, identify skip zones, scan for AI patterns.

**Step 1: Read and classify the file**

Read the target file. Identify file type (blog post, docs, README). Skip frontmatter (YAML between `---` markers), code blocks, inline code, and blockquotes.

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

**Step 3: Wabi-sabi check**

Before proposing any fix, ask: "Would removing this imperfection make it sound MORE robotic?" If yes, do NOT flag it. Preserve:
- Run-on sentences that convey enthusiasm
- Fragment punches that create rhythm
- Loose punctuation that matches conversational flow
- Self-corrections mid-thought ("well, actually...")

**Gate**: Approach selected. Fixes prioritized. Wabi-sabi exceptions noted. Proceed only when gate passes.

### Phase 3: EDIT

**Goal**: Generate edit report, get confirmation, apply changes.

**Step 1: Generate the edit report**

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

---

## Examples

### Example 1: Blog Post (Heavy Editing)
User says: "De-AI this blog post"
Actions:
1. Read file, skip frontmatter, scan all categories (ASSESS)
2. Score 22 -- systematic paragraph-by-paragraph approach (DECIDE)
3. Generate report with 10 changes, show preview, apply after confirmation (EDIT)
4. Re-read, verify meaning preserved, no new AI patterns (VERIFY)
Result: 67% shorter intro, all AI cliches removed, voice preserved

### Example 2: Technical Docs (Light Editing)
User says: "Check this for AI patterns"
Actions:
1. Read file, identify technical context, scan for patterns (ASSESS)
2. Score 7 -- targeted fixes only, preserve technical terms (DECIDE)
3. Replace "utilizes" with "uses", remove throat-clearing, show preview (EDIT)
4. Verify technical accuracy unchanged (VERIFY)
Result: Clearer prose, same information, technical terms untouched

---

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

---

## Anti-Patterns

### Anti-Pattern 1: Changing Meaning While Fixing Style
**What it looks like**: Removing "edge cases" from "This solution robustly handles edge cases" -- losing meaningful technical information
**Why wrong**: Style edits must never change what the content says
**Do instead**: "This solution handles edge cases reliably" -- fix style, keep meaning

### Anti-Pattern 2: Over-Correcting Natural Informal Language
**What it looks like**: Removing "So basically" from a casual blog post because it sounds informal
**Why wrong**: "So basically" is natural spoken rhythm. Blog posts can be conversational.
**Do instead**: Leave natural voice markers alone. Only remove AI-generated patterns.

### Anti-Pattern 3: Ignoring Technical Context
**What it looks like**: Flagging "leverage" in "Use a lever to leverage mechanical advantage"
**Why wrong**: "Leverage" is technically correct when discussing actual mechanics
**Do instead**: Only flag words when used as corporate-speak, not in their literal or technical sense

### Anti-Pattern 4: Wholesale Rewrites Instead of Targeted Edits
**What it looks like**: Completely rewriting a paragraph instead of fixing specific patterns
**Why wrong**: Loses author voice, may introduce new AI patterns, harder to review
**Do instead**: Make the minimum changes needed. Multiple small edits beat one big rewrite.

### Anti-Pattern 5: Reporting Without Actionable Fixes
**What it looks like**: "Line 15: Contains AI-sounding language" with no specific fix
**Why wrong**: Useless feedback -- the user needs to know WHAT to change and HOW
**Do instead**: Show exact original text, exact replacement, and reason for the change

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Wabi-Sabi Authenticity](../shared-patterns/wabi-sabi-authenticity.md) - Preserves human imperfections

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "It's just a style word, keep it" | AI cliches are the most obvious tells | Check against cliche list, replace if matched |
| "Fixing this would lose the flow" | Flow from AI patterns is synthetic flow | Remove and let natural rhythm emerge |
| "Technical content needs formal language" | Formal does not mean AI-sounding | Keep technical terms, remove corporate-speak |
| "The author probably wrote it that way" | If 5+ AI patterns cluster, it's generated | Apply systematic editing regardless |
| "Minor issues, not worth fixing" | Minor issues accumulate into AI tells | Fix all detected patterns |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/cliche-replacements.md`: Complete list of 80+ AI phrases with replacements
- `${CLAUDE_SKILL_DIR}/references/detection-patterns.md`: Regex patterns for automated detection
- `${CLAUDE_SKILL_DIR}/references/detection-rules.md`: Inline detection rules and structural checks
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Before/after examples from real edits
