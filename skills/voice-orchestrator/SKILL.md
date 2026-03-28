---
name: voice-orchestrator
description: |
  Multi-step voice content generation with deterministic validation. Orchestrates
  a 7-phase pipeline: LOAD, GROUND, GENERATE, VALIDATE, REFINE, OUTPUT, CLEANUP.
  Use when generating content in a specific voice, writing as a persona, or
  validating existing content against a voice profile. Use for "voice write",
  "write as", "generate in voice", or "voice content". Route to other skills for creating
  new voice profiles (use voice-calibrator), analyzing writing samples (use
  voice_analyzer.py), or general content without a voice target.
version: 2.0.0
deprecated: true
deprecated_by: voice-writer
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
context: fork
routing:
  triggers: []
  category: voice
---

# Voice Orchestrator Skill

> **DEPRECATED**: This skill is deprecated in favor of `voice-writer` (ADR-068).
> Use `/voice-writer` for all blog post and article generation. The voice-writer
> pipeline includes mandatory de-ai scanning, joy-check validation, and voice
> metric verification that this skill lacks.

## Overview

This skill generates content in a specific voice through a 7-phase pipeline with mandatory deterministic validation. It enforces high-fidelity voice impersonation via Python scripts rather than self-assessment, iterates up to 3 times on violations, and produces validation reports at output. Use when you need to write content matching a voice profile, validate existing content, or generate persona-driven text.

## Instructions

### Phase 1: LOAD

**Goal**: Load all voice infrastructure files and verify they exist.

**Constraints**: All required files must exist and be valid before proceeding — missing infrastructure causes validation failures downstream (reason: deterministic validation requires profile.json and config.json to establish thresholds).

**Step 1: Locate voice directory**

```bash
ls $HOME/claude-code-toolkit/skills/voice-{name}/
```

**Step 2: Load required files**

| File | Purpose |
|------|---------|
| `skills/voice-{name}/SKILL.md` | AI instructions, patterns, anti-patterns |
| `skills/voice-{name}/profile.json` | Quantitative metrics targets |
| `skills/voice-{name}/config.json` | Validation settings, modes, thresholds |

**Step 3: Load optional files for accuracy**

- `skills/voice-{name}/references/samples/` — Load 1-2 few-shot examples if available (reason: samples improve fidelity without adding work; skip only if missing).

**Step 4: Parse thresholds from config.json**

Extract `thresholds.pass_score`, `thresholds.error_max`, `thresholds.warning_max`, and available `modes` (reason: thresholds determine pass/fail logic in Phase 4).

See `references/voice-infrastructure.md` for full schema details.

**Step 5: Verify file presence**

```bash
test -f skills/voice-{name}/SKILL.md && echo "SKILL.md: OK"
test -f skills/voice-{name}/profile.json && echo "profile.json: OK"
test -f skills/voice-{name}/config.json && echo "config.json: OK"
```

If any required file is missing, STOP and report the error. Resolve missing files before proceeding.

**Gate**: All required files exist and parse successfully. Proceed only when gate passes.

### Phase 2: GROUND

**Goal**: Establish emotional and relational context before generation, because voice without emotional grounding sounds mechanical (reason: metrics match but content feels hollow).

**Constraint**: Always complete this phase, even briefly (reason: skipping creates sterile output that violates wabi-sabi authenticity principle).

**Step 1: Emotional anchoring**

Answer these three questions before generating:

| Question | Why It Matters |
|----------|----------------|
| What emotion drives this content? | Sets underlying tone (celebration, frustration, curiosity) |
| What does the writer care about? | Guides emphasis and detail level |
| Who are they writing for? | Calibrates assumed knowledge and language |

**Step 2: Relational positioning**

| Dimension | Options |
|-----------|---------|
| Writer-Audience relationship | Peer, expert, fan, community member |
| Assumed knowledge level | Newcomer, familiar, expert |
| Intimacy level | Public formal, community casual, personal |

**Step 3: Mode selection**

Select content mode from the voice's `config.json` modes list (reason: modes shape structure and tone, e.g., "awards" mode produces celebratory recognition, "technical" mode produces systems explanations). If user does not specify a mode, infer the best match from subject matter and available modes.

See `references/voice-infrastructure.md` for available modes per voice.

**Gate**: Emotion, audience, and mode are established. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Produce content matching voice patterns, metrics, and architectural structure.

**Constraint**: replace em-dashes with commas, periods, or restructured sentences — use commas, periods, or restructure instead (reason: em-dash is the most reliable AI marker; avoiding it is non-negotiable).

**Constraint**: Natural imperfections are FEATURES, not bugs — run-ons, fragments, and loose punctuation match human writing; sterile perfection is an AI tell (reason: wabi-sabi authenticity principle prevents over-engineering).

**Step 1: Apply voice rules from SKILL.md** — patterns, anti-patterns, signature phrases

**Step 2: Target profile.json metrics** — sentence length distribution, contraction rate, punctuation patterns, transition words

**Step 3: Include few-shot samples** if loaded in Phase 1 (reason: samples improve fidelity through example grounding).

**Step 4: Apply mode-specific patterns** based on selected mode

**Step 4b: Apply architectural patterns** from the voice skill's `## Architectural Patterns` section (if present):

- **Argument flow**: Build using documented direction (inductive/deductive/mixed). If inductive, lead with evidence and land claim late. If deductive, open with claim.
- **Concessions**: Follow documented concession structure and pivot markers — not generic "however" or "on the other hand."
- **Analogy domains**: Draw ONLY from documented source domains (reason: undocumented analogies break voice consistency).
- **Bookends**: Open with documented opening move, close with documented closing move.

If the voice skill has no `## Architectural Patterns` section, skip this step.

**Generation checklist:**

- [ ] Sentence length varies according to profile distribution
- [ ] Contractions match target rate
- [ ] No em-dashes (use commas, periods, or restructure)
- [ ] Opening matches voice pattern signatures
- [ ] Closing matches voice pattern signatures
- [ ] Transition words from profile preferred list
- [ ] Banned patterns avoided (exploration verbs, corporate jargon)
- [ ] Argument builds in documented direction (if architectural patterns present)
- [ ] Concessions use documented structure and pivot markers (if applicable)
- [ ] Analogies drawn from documented domains only (if applicable)

**Step 5: Write to temp file**

```bash
cat > /tmp/voice-content-draft.md << 'CONTENT'
[Generated content here]
CONTENT
```

**Gate**: Content written to file. All checklist items addressed. Proceed only when gate passes.

### Phase 4: VALIDATE (Deterministic)

**Goal**: Run the voice validator script against generated content — use the validator script instead of self-assessing.

**Constraint**: ALWAYS use `scripts/voice_validator.py` for validation, use scripts/voice_validator.py for all voice quality assessment (reason: LLMs cannot reliably self-assess stylistic accuracy; deterministic validator catches patterns humans miss).

**Step 1: Execute validation**

```bash
python3 $HOME/claude-code-toolkit/scripts/voice_validator.py validate \
  --content /tmp/voice-content-draft.md \
  --profile $HOME/claude-code-toolkit/skills/voice-{name}/profile.json \
  --voice {name} \
  --format json
```

See `references/validation-scripts.md` for full command reference and output schema.

**Step 2: Decision logic**

| Condition | Action |
|-----------|--------|
| `pass == true` AND `score >= threshold` | Proceed to Phase 6: OUTPUT |
| `pass == false` AND `iterations < 3` | Proceed to Phase 5: REFINE |
| `pass == false` AND `iterations >= 3` | Proceed to Phase 6: OUTPUT with failure report |

**Gate**: Validation result captured. Decision made. Proceed only when gate passes.

### Phase 5: REFINE (if needed)

**Goal**: Fix violations identified by validator. Maximum 3 iterations.

**Constraint**: Maximum 3 iterations total (reason: over-iteration creates sterile output that violates wabi-sabi; warnings are informational, errors are blockers).

**Constraint**: One targeted fix per violation — make targeted fixes only (reason: unrelated changes introduce new violations and destabilize passing characteristics).

**Constraint**: Fix errors before warnings (reason: errors block pass, warnings inform but inform without blocking).

**Step 1: Process violations in severity order** (errors first, then warnings)

For each violation:
1. Read line number, text, type, and suggested fix
2. Apply targeted fix (see `references/voice-infrastructure.md` for fix strategies)
3. Keep changes targeted to the specific violation

**Step 2: Write updated content to temp file**

**Step 3: Re-validate** by returning to Phase 4

**Step 4: After 3 iterations, stop** and proceed to Phase 6 with best attempt (reason: diminishing returns on iteration; user can manually refine if needed).

**Gate**: Content re-validated. Score improved or max iterations reached. Proceed only when gate passes.

### Phase 6: OUTPUT

**Goal**: Format and display final content with validation metrics (reason: validation report documents which patterns passed and why, enabling user trust and future refinement).

**Constraint**: Always include validation metrics in output — include the report even on failure (reason: violations report informs user of gaps between intent and voice fidelity).

**Output format:**

```
===============================================================
 VOICE CONTENT: {Voice Name}
===============================================================

[Generated content here]

===============================================================
 VALIDATION REPORT
===============================================================

 Status: PASSED / FAILED
 Score: {score}/100
 Iterations: {N}

 Checks:
   [check] Banned patterns: None detected
   [check] Em-dash: 0 found
   [check] Rhythm: Varied sentence lengths
   [warn] Contraction rate: 65% (target: 72%)

 Metrics Comparison:
   | Metric            | Target | Actual | Status |
   |-------------------|--------|--------|--------|
   | Avg sentence len  | 15.3   | 14.8   | [ok]   |
   | Contraction rate  | 0.72   | 0.65   | [warn] |
   | Short sentences   | 0.35   | 0.32   | [ok]   |

===============================================================
```

**Status indicators**: `[check]` = passed, `[warn]` = warning, `[fail]` = error, `[ok]` = within threshold

**Gate**: Output displayed with validation report. Proceed only when gate passes.

### Phase 7: CLEANUP

**Goal**: Remove temporary files and report completion.

**Constraint**: Always cleanup temp files after completion (reason: orphaned temp files accumulate and pollute /tmp; temp files exist only to support iteration, not final output).

**Step 1**: Remove `/tmp/voice-content-draft.md` and any iteration drafts

```bash
rm -f /tmp/voice-content-draft.md
rm -f /tmp/voice-content-draft-*.md
```

**Step 2**: Confirm final content is saved to user-specified location (if requested)

**Step 3**: Report pipeline completion with final status

```markdown
## Pipeline Complete
Voice: {name}
Status: PASSED/FAILED
Score: {score}/100
Iterations: {N}
Output: [location or displayed inline]
```

**Gate**: No orphaned temp files. Pipeline complete.

---

## Examples

### Example 1: Voice Content Generation
User says: "/voice-write --voice myvoice --subject 'Year-End Awards' --mode awards"
Actions:
1. Load voice-myvoice SKILL.md, profile.json, config.json (LOAD)
2. Establish emotional anchor: celebration, community recognition (GROUND)
3. Generate awards content matching the voice's metrics and patterns (GENERATE)
4. Run voice_validator.py, score: 58, 3 violations found (VALIDATE)
5. Fix "delve into" banned phrase, em-dash, rhythm violation (REFINE)
6. Re-validate: score 82, PASSED. Display with report (OUTPUT)
7. Remove temp files (CLEANUP)
Result: Voice-consistent content with validation report showing PASSED at 82/100

### Example 2: Validate Existing Content
User says: "/voice-write --validate --voice myvoice --content /path/to/draft.md"
Actions:
1. Load voice-myvoice profile.json and config.json (LOAD)
2. Skip GROUND and GENERATE phases (validate-only mode)
3. Run voice_validator.py against provided content (VALIDATE)
4. Display validation report with metrics comparison (OUTPUT)
5. No temp files to clean (CLEANUP)
Result: Validation report showing pass/fail status and specific violations

---

## Error Handling

### Error: "Voice Not Found"
Cause: Voice name misspelled or voice directory does not exist
Solution:
1. Check spelling of voice name
2. List available voices: `ls $HOME/claude-code-toolkit/skills/voice-*/`
3. Create new voice using `voice-calibrator` skill

### Error: "Profile or Config Missing"
Cause: Voice directory exists but required files (profile.json, config.json) are absent
Solution:
1. Run voice-calibrator to generate missing files
2. Or use voice analyzer: `python3 ~/.claude/scripts/voice_analyzer.py analyze --samples [files] --output profile.json`
3. For config.json, see `references/voice-infrastructure.md` for schema and example

### Error: "Validator Script Failed (Exit Code 2)"
Cause: File not found, invalid JSON, or Python environment issue
Solution:
1. Verify content file path exists
2. Check Python 3 is available: `python3 --version`
3. Test script directly: `python3 $HOME/claude-code-toolkit/scripts/voice_validator.py --help`
4. Verify profile.json is valid JSON

### Error: "Validation Failed After 3 Iterations"
Cause: Content cannot meet threshold within iteration limit
Solution:
1. Output best attempt with full failure report showing remaining violations
2. User can manually edit flagged lines
3. User can re-validate with `/voice-write --validate`
4. Consider recalibrating voice profile if failures are systemic

---

## References

- `${CLAUDE_SKILL_DIR}/references/validation-scripts.md`: Full validation command reference and output schema
- `${CLAUDE_SKILL_DIR}/references/voice-infrastructure.md`: Voice file structure, config/profile schemas, modes, fix strategies
