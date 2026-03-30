---
name: de-ai-pipeline
description: "Scan-fix-verify loop for removing AI writing patterns from docs."
version: 1.0.0
user-invocable: false
argument-hint: "[<path-or-glob>]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Agent
routing:
  force_route: true
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

Automated scan-fix-verify loop that removes AI writing patterns from documentation files. Uses `scripts/scan-ai-patterns.py` for deterministic detection against `scripts/data/banned-patterns.json` (323 patterns, 24 categories), then dispatches fix agents per file, then re-scans to verify fixes. Repeats until zero errors or max 3 iterations.

## Instructions

### Phase 1: SCAN

**Goal**: Run the scanner and identify all files with errors.

**Step 1: Run scan-ai-patterns.py**

Always use the scanner script for detection — never self-assess a file as "clean" without running the tool. The scanner catches patterns humans miss.

```bash
python3 ~/.claude/scripts/scan-ai-patterns.py --errors-only --json
```

Parse the JSON output. Group hits by file.

**Step 2: Classify results**

For each hit, classify as:
- **Fixable**: The pattern is a genuine AI tell that can be rephrased while preserving all factual content.
- **False positive**: The pattern match is a technical term, skill name, command name, or schema value that should be skipped.

Report false positives separately for pattern refinement. These become data for improving the banned-patterns database over time.

**Gate**: Scan complete. If zero errors, report clean and stop. If errors found, proceed to Phase 2.

### Phase 2: FIX

**Goal**: Fix all errors in each file while preserving meaning.

**Step 1: Read each file with errors and apply targeted fixes**

For each error hit, use this strategy table:

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

**Critical constraint**: Preserve all factual content. Only rephrase sentences; never remove information to avoid a pattern match. If rephrasing is hard, skip the hit and note it in the final report.

**Step 2: Respect protected zones**

Do NOT modify text inside:
- Code blocks (``` ... ```)
- Inline code (` ... `)
- YAML frontmatter (--- ... ---)
- Blockquotes (> ...)

These zones stay untouched. Scan results inside protected zones are automatically false positives.

**Step 3: Dispatch parallel fixes for multiple files**

When 2 or more files have errors, dispatch one Agent per file to fix them simultaneously. Each agent gets the file path and the specific hits to fix. This parallelizes the work.

**Gate**: All fixable errors addressed. Proceed to Phase 3.

### Phase 3: VERIFY

**Goal**: Re-scan to confirm fixes worked and no new errors were introduced.

**Step 1: Re-run the scanner**

```bash
python3 ~/.claude/scripts/scan-ai-patterns.py --errors-only
```

**Step 2: Check results**

- **Zero errors**: Report success. Proceed to Phase 4 (REPORT).
- **Errors remain**: Increment iteration counter. If less than 3 iterations, return to Phase 2 and fix again. If 3 iterations reached, proceed to Phase 4 with remaining errors noted in the report.

This max-3-iteration constraint stops infinite loops while capturing as many fixes as possible.

**Gate**: Either zero errors or max iterations reached. Proceed to Phase 4.

### Phase 4: REPORT

**Goal**: Report results and stage changes. Do not commit automatically — let the user decide.

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

Report staged files. Do not run `git commit` — the user owns the final commit decision.

**Gate**: Report delivered. Pipeline complete.

---

## Error Handling

### Error: "scan-ai-patterns.py not found"
**Cause**: Script not in expected location
**Solution**: Check `scripts/scan-ai-patterns.py` exists. If not, the toolkit may need re-installation.

### Error: "Pattern match is a false positive"
**Cause**: Technical term, skill name, or schema value matches a banned pattern
**Solution**: Skip the fix. Note the false positive in the report and suggest pattern refinement (e.g., tighten the regex, add context requirement). These notes feed back into the pattern database.

### Error: "Fix introduces new errors"
**Cause**: Rephrased sentence contains a different banned pattern
**Solution**: Rephrase again to clear both patterns. If stuck after 3 attempts on one sentence, skip and note in report. Prioritize clarity over pattern avoidance.

---

## References

- `scripts/scan-ai-patterns.py` — Deterministic pattern scanner with 323 banned patterns across 24 categories
- `scripts/data/banned-patterns.json` — Pattern database with regex rules and categories
