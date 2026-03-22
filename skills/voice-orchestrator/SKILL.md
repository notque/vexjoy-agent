---
name: voice-orchestrator
description: |
  Multi-step voice content generation with deterministic validation. Orchestrates
  a 7-phase pipeline: LOAD, GROUND, GENERATE, VALIDATE, REFINE, OUTPUT, CLEANUP.
  Use when generating content in a specific voice, writing as a persona, or
  validating existing content against a voice profile. Use for "voice write",
  "write as", "generate in voice", or "voice content". Do NOT use for creating
  new voice profiles (use voice-calibrator), analyzing writing samples (use
  voice_analyzer.py), or general content without a voice target.
version: 2.0.0
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
---

# Voice Orchestrator Skill

## Operator Context

This skill operates as an operator for voice content generation, configuring Claude's behavior for high-fidelity voice impersonation with measurable quality gates. It implements the **Pipeline** architectural pattern — LOAD, GROUND, GENERATE, VALIDATE, REFINE, OUTPUT, CLEANUP — with **Deterministic Validation** via Python scripts at the quality gate.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before generating
- **Over-Engineering Prevention**: Generate content that matches the voice, not perfect prose. Do not add features, modes, or structure the user did not request
- **Deterministic Validation**: ALWAYS use `scripts/voice_validator.py` for validation, NEVER self-assess voice quality
- **Iteration Limits**: Maximum 3 refinement iterations, then output best attempt with report
- **Em-Dash Prohibition**: NEVER generate em-dashes in any voice output. Use commas, periods, or restructure
- **Wabi-Sabi Authenticity**: Natural imperfections (run-ons, fragments, loose punctuation) are FEATURES of human writing. Sterile grammatical perfection is an AI tell. See `skills/shared-patterns/wabi-sabi-authenticity.md`
- **Voice Required**: Every generation MUST target a specific voice. No voiceless generation
- **Artifacts Over Memory**: Write content to files at each phase, not just context

### Default Behaviors (ON unless disabled)
- **Full Pipeline**: Run all 7 phases (LOAD, GROUND, GENERATE, VALIDATE, REFINE, OUTPUT, CLEANUP)
- **Validation Report**: Always include validation metrics in output
- **Sample Loading**: Load 1-2 reference samples as few-shot examples when available
- **Temp File Cleanup**: Remove generated temp files after completion
- **One Fix at a Time**: Address violations individually during refinement, not all at once
- **Document Findings**: Log validation scores and iteration results

### Optional Behaviors (OFF unless enabled)
- **Skip Validation**: Draft mode, bypasses validation step (`--skip-validation`)
- **Validate Only**: Check existing content without generation (`--validate`)
- **Verbose Output**: Show full validation JSON including all metrics (`--verbose`)
- **Custom Threshold**: Override default pass score from config.json

## What This Skill CAN Do
- Load voice skills with associated profile.json and config.json
- Generate content matching voice patterns, metrics, and signature phrases
- Run deterministic validation against voice profiles using Python scripts
- Refine content iteratively based on violation feedback (max 3 iterations)
- Produce validation reports with pass/fail status and metrics comparison
- Validate existing content against voice profiles without generation

## What This Skill CANNOT Do
- Create new voices (use `voice-calibrator` skill instead)
- Modify voice profiles (profiles are read-only during generation)
- Analyze writing samples (use `scripts/voice_analyzer.py` directly)
- Guarantee 100% pass rate (some content may fail after max iterations)
- Generate without a voice target (a `--voice` parameter is ALWAYS required)
- Self-assess voice quality (MUST use deterministic validator script)

---

## Instructions

### Phase 1: LOAD

**Goal**: Load all voice infrastructure files and verify they exist.

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

**Step 3: Load optional files**

- `skills/voice-{name}/references/samples/` — Few-shot examples (load 1-2 if available)

**Step 4: Parse thresholds from config.json**

Extract `thresholds.pass_score`, `thresholds.error_max`, `thresholds.warning_max`, and available `modes`.

See `references/voice-infrastructure.md` for full schema details.

**Step 5: Verify file presence**

```bash
test -f skills/voice-{name}/SKILL.md && echo "SKILL.md: OK"
test -f skills/voice-{name}/profile.json && echo "profile.json: OK"
test -f skills/voice-{name}/config.json && echo "config.json: OK"
```

If any required file is missing, STOP and report the error. Do not proceed with partial infrastructure.

**Gate**: All required files exist and parse successfully. Proceed only when gate passes.

### Phase 2: GROUND

**Goal**: Establish emotional and relational context before generation.

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

Select content mode from the voice's `config.json` modes list. Each voice defines modes that shape structure and tone (e.g., "awards" mode produces celebratory recognition pieces, "technical" mode produces systems explanations).

See `references/voice-infrastructure.md` for available modes per voice.

If user does not specify a mode, infer the best match from the subject matter and available modes.

**Gate**: Emotion, audience, and mode are established. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Produce content matching voice patterns from profile and SKILL.md.

**Step 1: Apply voice rules from SKILL.md** — patterns, anti-patterns, signature phrases

**Step 2: Target profile.json metrics** — sentence length distribution, contraction rate, punctuation patterns, transition words

**Step 3: Include few-shot samples** if loaded in Phase 1

**Step 4: Apply mode-specific patterns** based on selected mode

**Step 4b: Apply architectural patterns** from the voice skill's `## Architectural Patterns` section (if present):

- **Argument flow**: Build the piece using the documented direction (inductive/deductive/mixed). If inductive, lead with evidence and land the claim late. If deductive, open with the claim.
- **Concessions**: When handling disagreement, follow the documented concession structure and use the documented pivot markers — not generic "however" or "on the other hand."
- **Analogy domains**: Draw analogies ONLY from the documented source domains. Do NOT use generic analogies from undocumented domains.
- **Bookends**: Open with the documented opening move, close with the documented closing move.

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

**Goal**: Run the voice validator script against generated content. No self-assessment.

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

**Goal**: Fix violations identified by the validator. Maximum 3 iterations.

**Step 1: Process violations in severity order** (errors first, then warnings)

For each violation:
1. Read line number, text, type, and suggested fix
2. Apply targeted fix (see `references/voice-infrastructure.md` for fix strategies)
3. Do NOT make unrelated changes

**Step 2: Write updated content to temp file**

**Step 3: Re-validate** by returning to Phase 4

**Refinement rules:**
- Fix errors before warnings
- One targeted fix per violation
- Do not rewrite entire sections — fix the specific issue
- After 3 iterations, stop and output best attempt

**Gate**: Content re-validated. Score improved or max iterations reached. Proceed only when gate passes.

### Phase 6: OUTPUT

**Goal**: Format and display final content with validation report.

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

**Goal**: Remove temporary files created during the pipeline.

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
2. Or use voice analyzer: `python3 scripts/voice_analyzer.py analyze --samples [files] --output profile.json`
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

## Anti-Patterns

### Anti-Pattern 1: Skipping Validation for "Good Enough"
**What it looks like**: "The content sounds fine to me, I'll skip validation."
**Why wrong**: Human perception drifts. Deterministic validation catches patterns you miss. Self-assessment is not validation.
**Do instead**: ALWAYS validate. Use `--skip-validation` only for true drafts the user explicitly requests as drafts.

### Anti-Pattern 2: Self-Assessing Voice Quality
**What it looks like**: "I read the content and it matches the voice profile."
**Why wrong**: LLMs cannot reliably self-assess stylistic accuracy. That is why the deterministic validator exists.
**Do instead**: Run `voice_validator.py`. Trust the script output, not your assessment.

### Anti-Pattern 3: Skipping the Grounding Step
**What it looks like**: Jumping straight from LOAD to GENERATE without establishing context.
**Why wrong**: Voice without emotional grounding sounds mechanical. Metrics match but the content feels hollow.
**Do instead**: Complete Phase 2 GROUND, even briefly. Establish emotion, audience, and mode before generating.

### Anti-Pattern 4: Over-Iterating on Warnings
**What it looks like**: Spending 5+ iterations trying to eliminate all warnings.
**Why wrong**: Warnings are informational. Errors are blockers. Over-polishing creates sterile output that violates wabi-sabi.
**Do instead**: Fix all errors, address warnings if easy, ship when score >= threshold. Maximum 3 iterations.

### Anti-Pattern 5: Rewriting Entire Sections During Refinement
**What it looks like**: Rewriting paragraphs to fix a single banned phrase violation.
**Why wrong**: Introduces new violations. Changes voice characteristics that were passing.
**Do instead**: Apply targeted, surgical fixes. Change only the violating text.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transitions
- [Wabi-Sabi Authenticity](../shared-patterns/wabi-sabi-authenticity.md) - Natural imperfections as features

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The validator is too strict" | Validator catches real AI patterns humans miss | Fix violations or adjust profile through calibration |
| "This voice doesn't need validation" | All voices drift without measurement | ALWAYS validate with script |
| "The metrics don't matter for this piece" | Metrics ensure consistency across outputs | Address deviations |
| "Manual review is sufficient" | Humans miss patterns deterministic checks catch | Use script validation |
| "One em-dash won't hurt" | Em-dash is the most reliable AI marker | NEVER use em-dashes |
| "Content sounds right to me" | Self-assessment is not validation | Run voice_validator.py |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/validation-scripts.md`: Full validation command reference and output schema
- `${CLAUDE_SKILL_DIR}/references/voice-infrastructure.md`: Voice file structure, config/profile schemas, modes, fix strategies
