---
name: de-ai-pipeline
description: |
  Scan-fix-verify loop for removing AI writing patterns from docs. Runs
  scan-ai-patterns.py to find errors, dispatches fix agents per file,
  re-scans to verify, repeats until zero errors or max 3 iterations.
  Use for "de-ai docs", "clean ai patterns", "fix ai writing",
  "scan and fix docs", "remove ai tells from docs".
version: 1.0.0
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Agent
routing:
  triggers:
    - de-ai docs
    - clean ai patterns
    - fix ai writing
    - scan and fix docs
    - remove ai tells
    - de-ai pipeline
  pairs_with:
    - anti-ai-editor
    - voice-validator
  complexity: Medium
  category: content
---

# De-AI Pipeline

## Operator Context

Automated scan-fix-verify loop that removes AI writing patterns from documentation files. Uses `scripts/scan-ai-patterns.py` for deterministic detection against `scripts/data/banned-patterns.json` (323 patterns, 24 categories), then dispatches fix agents per file, then re-scans to verify fixes. Repeats until zero errors or max 3 iterations.

### Hardcoded Behaviors (Always Apply)
- **Script-First Detection**: Use `scan-ai-patterns.py` for all scanning. Do not self-assess AI patterns.
- **Preserve Meaning**: Fixes must not change factual content. Only rephrase, never remove information.
- **Skip Zones**: Do not modify content inside code blocks, YAML frontmatter, inline code, or blockquotes.
- **Max 3 Iterations**: Stop after 3 scan-fix cycles even if errors remain. Report remaining errors.
- **False Positive Awareness**: When a pattern match is a technical term, skill name, or schema value, skip it and note the false positive.

### Default Behaviors (ON unless disabled)
- **Parallel File Fixes**: When 2+ files have errors, dispatch fix agents in parallel.
- **Commit After Clean**: After reaching zero errors, stage and report (do not auto-commit).

### Optional Behaviors (OFF unless enabled)
- **Single File Mode**: Pass a specific file path to scan and fix only that file.
- **Scan Only**: Run the scanner without fixing. Report errors and exit.

## What This Skill CAN Do
- Scan all docs for AI pattern violations using deterministic regex matching
- Fix detected patterns by rephrasing sentences to avoid triggers
- Verify fixes by re-scanning after edits
- Handle em-dash replacement, jargon substitution, structural rewrites
- Report false positives for pattern refinement

## What This Skill CANNOT Do
- Fix patterns in agent definitions or skill files (those are system prompts, not prose)
- Remove technical terms that happen to match patterns (false positives)
- Rewrite entire documents (targeted fixes only)
- Change meaning to avoid a pattern match

---

## Instructions

### Phase 1: SCAN

**Goal**: Run the scanner and identify all files with errors.

**Step 1: Run scan-ai-patterns.py**

```bash
python3 scripts/scan-ai-patterns.py --errors-only --json
```

Parse the JSON output. Group hits by file.

**Step 2: Classify results**

For each hit, classify as:
- **Fixable**: The pattern is a genuine AI tell that can be rephrased
- **False positive**: The pattern match is a technical term, skill name, command name, or schema value

Report false positives separately for pattern refinement.

**Gate**: Scan complete. If zero errors, report clean and stop. If errors found, proceed to Phase 2.

### Phase 2: FIX

**Goal**: Fix all errors in each file.

**Step 1: For each file with errors, apply targeted fixes**

Read the file. For each error hit:

| Pattern Category | Fix Strategy |
|-----------------|--------------|
| `forbidden_punctuation` (em-dashes) | Replace with colons, commas, periods, or restructure |
| `corporate_verbs` | Substitute plain verbs (use, help, improve) |
| `abstract_nouns` | Name the specific thing |
| `empty_adjectives` | Remove or replace with concrete description |
| `throat_clearing` | Delete the phrase, start with the actual point |
| `performative_emphasis` | Delete, let facts carry the weight |
| `false_agency` | Name the human actor |
| `vague_declaratives` | Replace with the specific fact |
| `dramatic_fragmentation` | Complete the sentence |
| `meta_commentary` | Delete, let the text flow |
| `ai_rhetorical_structures` | State Y directly, drop the negation |
| `opening_phrases` | Start with the actual content |
| `conclusion_phrases` | End with the final thought directly |
| `negative_listing` | State the positive claim directly |
| `adverb_crutches` | Remove the adverb, strengthen the verb |
| `lazy_extremes` | Replace with specific count or qualifier |
| `formulaic_constructions` | Rewrite with specific detail |
| `hedging_language` | State directly or qualify specifically |
| `ai_significance_phrases` | State the significance directly |
| `exploration_verbs` | Use direct verbs: examine, look at, consider |

**Step 2: Preserve skip zones**

Do NOT modify text inside:
- Code blocks (``` ... ```)
- Inline code (` ... `)
- YAML frontmatter (--- ... ---)
- Blockquotes (> ...)

**Step 3: For 2+ files, fix in parallel**

When multiple files have errors, dispatch one Agent per file to fix them simultaneously. Each agent gets the file path and the specific hits to fix.

**Gate**: All fixable errors addressed. Proceed to Phase 3.

### Phase 3: VERIFY

**Goal**: Re-scan to confirm fixes worked and no new errors were introduced.

**Step 1: Re-run scanner**

```bash
python3 scripts/scan-ai-patterns.py --errors-only
```

**Step 2: Check results**

- **Zero errors**: Report success. Proceed to Phase 4 (REPORT).
- **Errors remain**: Increment iteration counter. If < 3 iterations, return to Phase 2. If = 3, proceed to Phase 4 with remaining errors noted.

**Gate**: Either zero errors or max iterations reached. Proceed to Phase 4.

### Phase 4: REPORT

**Goal**: Report results and stage changes.

**Step 1: Report**

```
DE-AI PIPELINE: [CLEAN | PARTIAL | FAILED]
  Iterations: N/3
  Files scanned: N
  Files fixed: N
  Errors found: N (initial) -> N (final)
  False positives: N (list them for pattern refinement)
```

**Step 2: Stage changes**

```bash
git add [fixed files]
git status
```

Do NOT commit. Report staged files and let the user decide.

**Gate**: Report delivered. Pipeline complete.

---

## Error Handling

### Error: "scan-ai-patterns.py not found"
Cause: Script not in expected location
Solution: Check `scripts/scan-ai-patterns.py` exists. If not, the toolkit may need re-installation.

### Error: "Pattern match is a false positive"
Cause: Technical term, skill name, or schema value matches a banned pattern
Solution: Skip the fix, note the false positive in the report. Suggest pattern refinement (e.g., tighten the regex, add context requirement).

### Error: "Fix introduces new errors"
Cause: Rephrased sentence contains a different banned pattern
Solution: Rephrase again avoiding both patterns. If stuck after 3 attempts on one sentence, skip and note in report.

---

## Anti-Patterns

### Anti-Pattern 1: Self-Assessing Instead of Scanning
**What it looks like**: Deciding a file "looks clean" without running the script
**Do instead**: Run `scan-ai-patterns.py`. The script catches patterns humans miss.

### Anti-Pattern 2: Changing Meaning to Avoid Patterns
**What it looks like**: Removing a sentence because rephrasing is hard
**Do instead**: Preserve all factual content. Rephrase, don't delete.

### Anti-Pattern 3: Ignoring False Positives
**What it looks like**: Forcing awkward rewrites for legitimate technical terms
**Do instead**: Note the false positive in the report. The pattern database gets refined over time.
