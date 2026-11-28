# Condense

Strip prose filler from `.md` files while preserving every instruction.

## Phase 1: SCOPE

Identify targets:

1. **Single file**: User names a path. Read it.
2. **Glob**: User gives a pattern (`skills/**/SKILL.md`). Expand, list matches, confirm with user.
3. **Batch (10+ files)**: Dispatch parallel workers, one per file.

**Mechanical pre-pass** (deterministic, run before LLM condensing): strip trailing whitespace and consecutive blank lines that inflate token counts.

```bash
python3 scripts/check-whitespace.py --fix <target-file-or-dir>   # 0=clean, 1=violations fixed
```

Run on the scoped targets (defaults to `skills/**/*.md` when no path is given), then proceed to the LLM pass on the same files.

**Gate**: At least one target file identified and readable; mechanical pre-pass run.

---

## Phase 2: CONDENSE

For each file:

1. Read the full file and record its word count.
2. Rewrite in place applying the rules below.
3. Record the new word count.

### Rules

**KEEP** (never cut):
- Every instruction, rule, gate, phase, step
- Tables, code blocks, commands, paths
- YAML frontmatter (keep intact)
- Structure: headers, numbered lists, phase ordering
- Technical terms naming specific things
- Reference loading tables
- Error handling sections
- Non-obvious "because X" reasoning

**CUT**:
- Redundant restatements of the same rule
- "Because X" on obvious rules
- Motivational framing ("this will help you", "it is important to note")
- Filler phrases: "in order to", "it should be noted that", "it is worth mentioning"
- Examples that repeat what the phase already says
- Paragraphs saying the same thing from different angles — merge to one

**STYLE**: Short sentences. Active voice. Concrete words. If you can cut a word without losing an instruction, cut it.

### Delete Test

Before cutting any sentence, ask: "If I remove this, does the reader lose an instruction, rule, or decision?" No = cut. Yes = keep.

### Boundaries

Preserve section organization, meaning, paths/commands, tables, code blocks, and YAML frontmatter values.

---

## Phase 3: VERIFY

For each condensed file:

1. **YAML check**: Confirm frontmatter parses.
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('<file>').read().split('---')[1])"
   ```
2. **Report**: Show `| File | Before | After | Reduction |` table with word counts.
3. **Instruction check**: Grep original for key terms (phase names, gate names, commands). Confirm each appears in the condensed version; restore any missing term from the original.

**Gate**: YAML parses. No instructions lost. Reduction reported.

---

## Error Handling

- **No prose to cut**: Report 0% reduction and move to the next file.
- **Instruction removed**: Re-read original, restore the missing instruction, and re-verify.
- **YAML broken**: Restore original frontmatter verbatim and re-condense the body only.
- **Non-.md file**: Skip with a warning.
