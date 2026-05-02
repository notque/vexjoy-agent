---
name: joy-check
description: "Validate content framing on joy-grievance spectrum."
user-invocable: false
argument-hint: "[--fix] [--strict] [--mode writing|instruction] <file>"
command: /joy-check
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - joy check
    - check framing
    - tone check
    - negative framing
    - joy validation
    - too negative
    - reframe positively
    - positive framing check
    - instruction framing
  pairs_with:
    - voice-writer
    - anti-ai-editor
    - voice-validator
    - skill-creator
  complexity: Simple
  category: content
---

# Joy Check

Two modes:

- **writing** — Joy-grievance spectrum for human-facing content (blog posts, emails, articles). Evaluates curiosity/generosity vs. grievance/accusation framing.
- **instruction** — Positive framing for LLM-facing content (agents, skills, pipelines). Evaluates "what to do" vs. "what to avoid" (ADR-127).

Evaluates each paragraph/instruction independently, produces a score (0-100), suggests reframes without modifying content. Flags: `--fix` rewrites flagged items in place and re-verifies; `--strict` fails on any item below 60; `--mode writing|instruction` overrides auto-detection.

Checks *framing*, not *topic* or *voice*. Voice fidelity → voice-validator. AI pattern detection → anti-ai-editor.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `instruction-rubric.md` | Loads detailed guidance from `instruction-rubric.md`. |
| tasks related to this reference | `writing-rubric.md` | Loads detailed guidance from `writing-rubric.md`. |

## Instructions

### Phase 0: DETECT MODE

Auto-detection (priority order):
1. Explicit `--mode` flag → use that
2. `agents/*.md` → **instruction**
3. `skills/*/SKILL.md` → **instruction**
4. `skills/workflow/references/*.md` → **instruction**
5. `CLAUDE.md` or `README.md` → **instruction**
6. Everything else → **writing**

Load `references/{mode}-rubric.md` for scoring criteria and examples.

**GATE**: Mode determined, rubric loaded.

### Phase 1: PRE-FILTER

Regex scanning as a fast gate before LLM semantic analysis.

**Writing mode**:
```bash
python3 ~/.claude/scripts/scan-negative-framing.py [file]
```

**Instruction mode**:
```bash
grep -nE 'NEVER|do NOT|must NOT|FORBIDDEN' [file]
grep -nE "^-?\s*Don't|^-?\s*Avoid|^#+.*Anti-[Pp]attern|^#+.*Avoid" [file]
```

Report findings with reframe suggestions from the rubric. If `--fix`, apply reframes and re-run.

**GATE**: Zero regex/grep hits. Resolve obvious patterns before Phase 2.

### Phase 2: ANALYZE

**Step 1: Read content**

Read full file. Skip frontmatter and code blocks.
- **Writing**: Identify paragraphs (blank-line separated). Skip blockquotes.
- **Instruction**: Identify instructional statements — bullets, table cells, imperatives, headings. Skip examples, code blocks, quoted dialogue, file paths.

**Step 2: Evaluate against rubric**

Apply scoring dimensions from `references/{mode}-rubric.md`.

For **writing**: Joy-grievance lens. Watch for subtle patterns in `references/writing-rubric.md` (defensive disclaimers, accumulative grievance, passive-aggressive factuality, reluctant generosity).

For **instruction**: Positive-negative lens. Check against patterns table in `references/instruction-rubric.md`. Contextual exceptions: subordinate negatives attached to positive instructions are PASS, as are negatives in code examples, writing samples, and technical terms.

**Step 3: Score each item**

Apply the rubric's scoring scale. For items scoring CAUTION/GRIEVANCE (writing) or NEGATIVE-LEANING/PROHIBITION-HEAVY (instruction), draft specific reframe suggestions preserving substance.

If an item seems "too subtle to flag" — that is precisely when flagging matters. Subtle patterns are the primary purpose of this LLM phase.

**GATE**: All items scored. Reframe suggestions drafted for flagged items.

### Phase 3: REPORT

**Step 1: Calculate overall score**

Average all item scores. Pass criteria:
- **Writing**: Score >= 60 AND no GRIEVANCE paragraphs
- **Instruction**: Score >= 60 AND no primary negative patterns in instructional context

**Step 2: Output**

```
JOY CHECK: [file]
Mode: [writing|instruction]
Score: [0-100]
Status: PASS / FAIL

Items:
  [writing mode]
  P1 (L10-12): JOY [85] -- explorer framing, curiosity
  P3 (L18-22): CAUTION [40] -- "confused" leans defensive
    -> Reframe: Focus on what you learned from the confusion

  [instruction mode]
  L33: NEGATIVE [20] -- "NEVER edit code directly"
    -> Rewrite: "Route all code modifications to domain agents"
  L45: PASS [90] -- "Create feature branches for all changes"
  L78: PASS [85] -- "Credentials stay in .env files, never in code" (subordinate negative OK)

Overall: [summary of framing arc]
```

**Step 3: Fix mode**

If `--fix`:
1. Rewrite flagged items using drafted suggestions
2. Preserve substance — change only framing
3. Re-run Phase 2 on rewrites to verify
4. Maximum 3 iterations if fixes introduce new flags

**GATE**: Report produced. If `--fix`, all rewrites applied and re-verified.

---

### Integration

**Writing pipeline**:
```
CONTENT --> voice-validator --> scan-ai-patterns --> joy-check --mode writing --> anti-ai-editor
```

**Instruction pipeline**:
```
SKILL.md --> joy-check --mode instruction --> fix flagged patterns --> re-verify
```

**Auto-invocation points**:
- `skill-creator`: after generating a new skill
- `agent-upgrade`: after modifying an agent
- `voice-writer`: during validation
- `doc-pipeline`: for toolkit documentation

Invoke standalone via `/joy-check [file]` (auto-detects mode) or with explicit `--mode`.

---

## Error Handling

### Error: "File Not Found"
Verify path with `ls -la`. Use glob to search: `Glob **/*.md`. Confirm working directory.

### Error: "Regex Scanner Fails or Not Found"
Verify `scripts/scan-negative-framing.py` exists. Requires Python 3.10+. If unavailable, skip to Phase 2 — the pre-filter is an optimization, not a requirement.

### Error: "All Paragraphs Score GRIEVANCE"
Content is fundamentally grievance-framed. Report scores honestly. Suggest full rewrite with different framing premise, not paragraph-level fixes.

### Error: "Fix Mode Fails After 3 Iterations"
Output best version with remaining concerns. Explain which rubric dimensions resist correction. The framing premise itself may need rethinking.

---

## References

### Rubric Files
- `references/writing-rubric.md` — Joy-grievance spectrum, subtle patterns, scoring, examples
- `references/instruction-rubric.md` — Positive framing rules, patterns, rewrite strategies, examples

### Scripts
- `scan-negative-framing.py` — Regex pre-filter for grievance patterns (writing mode, Phase 1)

### Complementary Skills
- `voice-validator` — Voice fidelity (different concern)
- `anti-ai-editor` — AI pattern detection (different concern)
- `voice-writer` — Invokes joy-check during validation
- `skill-creator` — Invokes joy-check in instruction mode
