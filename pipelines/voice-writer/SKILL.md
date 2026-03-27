---
name: voice-writer
description: |
  Unified voice content generation pipeline with mandatory validation and
  joy-check. Replaces voice-orchestrator and absorbs blog-post-writer.
  8-phase pipeline: LOAD, GROUND, GENERATE, VALIDATE, REFINE, JOY-CHECK,
  OUTPUT, CLEANUP. Use when writing articles, blog posts, or any content
  that uses a voice profile. Use for "write article", "blog post", "write
  in voice", "generate content", "draft article", "write about". Do NOT
  use for voice profile creation (use create-voice), voice analysis
  (use voice-calibrator), or non-voiced documentation (use doc-pipeline).
version: 1.0.0
user-invocable: true
argument-hint: "<topic or title>"
command: /voice-writer
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
  force_route: true
  force_routing: true
  triggers:
    - write article
    - blog post
    - write in voice
    - generate voice content
    - voice workflow
    - draft article
    - write about
    - write post
    - blog about
    - create content
  pairs_with:
    - create-voice
    - voice-calibrator
    - voice-validator
    - joy-check
    - anti-ai-editor
    - research-to-article
  complexity: Medium
  category: content
---

# Voice Writer Skill

This skill operates as the unified entry point for all voiced content generation. It implements an 8-phase pipeline architecture with deterministic validation at quality gates, joy-check enforcement before output, and strict iteration limits.

---

## Instructions

### Phase 1: LOAD

**Goal**: Load all voice infrastructure files and verify they exist.

Before loading, understand that this skill **requires a voice target** — content cannot be generated without a voice. If the user has not specified a voice, default to the repository's configured voice skill or ask the user which voice to use.

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

- `skills/voice-{name}/references/samples/` -- Few-shot examples (load 1-2 if available)

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

**Important constraint**: This phase is mandatory. Skipping Phase 1 will result in generation without voice infrastructure, producing hollow-sounding content that metrics match but feels mechanically written. Complete this phase fully before proceeding.

**Gate**: All required files exist and parse successfully. Proceed only when gate passes.

### Phase 2: GROUND

**Goal**: Establish emotional, relational, and structural context before generation.

Grounding prevents over-engineered output. Only write what was explicitly requested. Do not add "Future Implications" sections, "Related Topics" sidebars, or any unsolicited structure — ask before adding anything extra.

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

**Step 4: Blog post assessment** (if the request is a blog post or article)

When the content is a blog post, article, or similar structured piece, also perform:

```markdown
## Assessment
- Topic: [user-provided topic]
- Scope: [narrow / medium / broad]
- Audience: [beginner / intermediate / expert]
- Estimated length: [short 500-800 / medium 1000-1500 / long 2000+]
```

**Step 5: Structure planning** (if the request is a blog post or article)

Plan the post structure using voice patterns and structure templates:

```markdown
## Plan
- Opening pattern: [Provocative Question / News Lead / Bold Claim / Direct Answer]
- Draft opening: [first sentence or question]
- Core metaphor: [conceptual lens, if voice uses extended metaphors]
- Sections:
  1. [Section name]: [purpose]
  2. [Section name]: [purpose]
  ...
- Closing pattern: [Callback / Implication / Crescendo]
- Callback element: [what from opening returns]
```

Draft frontmatter if writing to a Hugo site:

```yaml
---
title: "Post Title Here"
slug: "post-slug-here"
date: YYYY-MM-DD
draft: false
tags: ["tag1", "tag2"]
summary: "One sentence description for list views"
---
```

Select content type from `references/structure-templates.md` if available:
- **Problem-Solution**: Bug fix, debugging session, resolution
- **Technical Explainer**: Concept, technology, how it works
- **Walkthrough**: Step-by-step instructions for a task

**Important constraint**: This grounding is mandatory, not optional. Content generated without emotional anchor and mode selection sounds mechanical regardless of metrics match. The validator catches style mismatches but cannot fix a hollow emotional foundation. Do not skip this step even briefly — complete it fully before moving to GENERATE.

**Gate**: Emotion, audience, and mode are established. If blog post, topic assessed and structure planned. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Produce content matching voice patterns from profile and SKILL.md.

**Step 1: Apply voice rules from SKILL.md** -- patterns, anti-patterns, signature phrases

**Step 2: Target profile.json metrics** -- sentence length distribution, contraction rate, punctuation patterns, transition words

**Step 3: Include few-shot samples** if loaded in Phase 1

**Step 4: Apply mode-specific patterns** based on selected mode

**Step 4b: Apply architectural patterns** from the voice skill's `## Architectural Patterns` section (if present):

- **Argument flow**: Build the piece using the documented direction (inductive/deductive/mixed). If inductive, lead with evidence and land the claim late. If deductive, open with the claim.
- **Concessions**: When handling disagreement, follow the documented concession structure and use the documented pivot markers -- not generic "however" or "on the other hand."
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
- [ ] Banned words avoided (scan against `references/banned-words.md`)
- [ ] Argument builds in documented direction (if architectural patterns present)
- [ ] Concessions use documented structure and pivot markers (if applicable)
- [ ] Analogies drawn from documented domains only (if applicable)
- [ ] Specific numbers included for all claims, not vague adjectives

**Em-dash prohibition**: NEVER generate em-dashes in any voice output. Em-dashes are the most reliable AI marker. Use commas, periods, or restructure sentences instead.

**Step 5: Write to temp file**

```bash
cat > /tmp/voice-content-draft.md << 'CONTENT'
[Generated content here]
CONTENT
```

**Important constraints**:
- **Single voice per piece**: Do not blend voice patterns. Use exactly one voice profile per piece and follow that voice skill's patterns exclusively.
- **No over-engineering**: Generate the content the user requested, nothing more. Do not add features, modes, or structure the user did not request.
- **Preview before write**: Display full draft for approval before writing to file unless Direct Write Mode is enabled.

**Gate**: Content written to file. All checklist items addressed. Proceed only when gate passes.

### Phase 4: VALIDATE (Deterministic)

**Goal**: Run the voice validator script against generated content. No self-assessment.

This phase is non-negotiable. Do not skip validation for "good enough" content. Human perception drifts. Deterministic validation catches patterns you miss. Self-assessment is not validation. Use `--skip-validation` only for true drafts the user explicitly requests as drafts.

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
| `pass == true` AND `score >= threshold` | Proceed to Phase 6: JOY-CHECK |
| `pass == false` AND `iterations < 3` | Proceed to Phase 5: REFINE |
| `pass == false` AND `iterations >= 3` | Proceed to Phase 6: JOY-CHECK with failure report |

**Important constraints**:
- **Trust the validator, not intuition**: Do not rationalize validator strictness — it catches real AI patterns humans miss. If the validator rejects content, fix violations or adjust the profile through calibration.
- **Address warnings carefully**: Fix all errors, address warnings if easy, ship when score >= threshold. Over-polishing creates sterile output that violates wabi-sabi (natural imperfections as features of human writing). Sterile grammatical perfection is an AI tell. Do not spend 5+ iterations eliminating all warnings — warnings are informational, errors are blockers.
- **One fix at a time**: During refinement, address violations individually. Do not fix multiple violations simultaneously — this introduces new violations and changes voice characteristics that were passing.

**Gate**: Validation result captured. Decision made. Proceed only when gate passes.

### Phase 5: REFINE (if needed)

**Goal**: Fix violations identified by the validator. Maximum 3 iterations.

Refinement is targeted, surgical fixing — not wholesale rewriting. Each iteration should fix one specific violation, not rewrite entire sections. Rewriting sections introduces new violations and changes voice characteristics.

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
- Do not rewrite entire sections -- fix the specific issue
- After 3 iterations, stop and proceed to JOY-CHECK with best attempt

**Gate**: Content re-validated. Score improved or max iterations reached. Proceed only when gate passes.

### Phase 6: JOY-CHECK (Mandatory)

**Goal**: Validate content for joy-centered tonal framing. No grievance-framed content ships.

Joy-check is not optional, not even if validation passed. Voice validation checks stylistic fidelity. Joy-check checks tonal framing. Content can match a voice perfectly while framing through grievance, bitterness, accusation, or victimhood. Grievance framing slips in subtly — regex + rubric catch what visual scanning misses.

**Step 1: Run regex pre-filter**

```bash
python3 $HOME/claude-code-toolkit/scripts/scan-negative-framing.py /tmp/voice-content-draft.md
```

If regex hits are found, fix them before proceeding. These are high-confidence negative framing patterns (victimhood, accusation, bitterness, passive aggression). Apply the scanner's suggested reframes and re-run until clean.

If the script is unavailable, skip the regex pre-filter and proceed directly to LLM-based joy-check analysis — the regex pre-filter is an optimization, not a requirement.

**Step 2: Evaluate each paragraph against the Joy Framing Rubric**

| Dimension | Joy-Centered (PASS) | Grievance-Centered (FAIL) |
|-----------|-------------------|--------------------------|
| **Subject position** | Author as explorer, builder, learner | Author as victim, wronged party, unrecognized genius |
| **Other people** | Fellow travelers, interesting minds, people figuring things out | Opponents, thieves, people who should have done better |
| **Difficult experiences** | Interesting, surprising, made me think differently | Unfair, hurtful, someone should fix this |
| **Uncertainty** | Comfortable, curious, "none of us know" | Anxious, defensive, "I need to prove" |
| **Closing energy** | Forward-looking, building, sharing, exploring | Cautionary, warning, demanding, lamenting |

**Step 3: Score each paragraph**

For each paragraph, assign one of:
- **JOY** (80-100): Frames through curiosity, generosity, or earned satisfaction
- **NEUTRAL** (50-79): Factual, neither joy nor grievance
- **CAUTION** (30-49): Leans toward grievance but recoverable with reframing
- **GRIEVANCE** (0-29): Frames through accusation, victimhood, or bitterness

**Step 4: Rewrite GRIEVANCE paragraphs**

If any paragraph scores GRIEVANCE:
1. Rewrite preserving substance, changing only the framing
2. Shift toward curiosity, generosity, or earned satisfaction
3. Re-evaluate the rewritten paragraph to confirm it no longer scores GRIEVANCE
4. Maximum 3 joy-check iterations

**Joy-check rules:**
- Reframe, don't suppress -- negative experiences are valid topics, only the framing changes. This is editorial craft, not dishonesty — substance stays the same.
- Preserve substance -- change the lens, not the facts
- One GRIEVANCE paragraph is a FAIL condition for the whole piece
- CAUTION paragraphs are acceptable if the overall piece passes

**Important constraint**: Do not rationalize that "the content is factual, so the framing is fine." Facts arranged as prosecution are framing, not neutrality. Evaluate the arrangement of facts, not just their accuracy. The reframe would not be dishonest — it is how we choose to tell the truth.

**Gate**: No GRIEVANCE paragraphs remain. Joy-check passes. Proceed only when gate passes.

### Phase 7: OUTPUT

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

 Joy Check:
   Status: PASSED
   Overall Joy Score: {score}/100
   Paragraphs: {N} JOY, {N} NEUTRAL, {N} CAUTION, 0 GRIEVANCE

===============================================================
```

**Status indicators**: `[check]` = passed, `[warn]` = warning, `[fail]` = error, `[ok]` = within threshold

Show target file path if writing to a file. Await user approval before writing unless Direct Write Mode is enabled.

**Important constraint**: Always include validation metrics in output. Do not ship content without showing the measurements that prove it passes.

**Gate**: Output displayed with validation report. Proceed only when gate passes.

### Phase 8: CLEANUP

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
Joy Score: {joy_score}/100
Iterations: {N}
Output: [location or displayed inline]
```

**Gate**: No orphaned temp files. Pipeline complete.

---

## Examples

### Example 1: Blog Post Generation
User says: "/voice-writer --voice myvoice --subject 'Year-End Awards'"
Actions:
1. Load voice-myvoice SKILL.md, profile.json, config.json (LOAD)
2. Assess topic: awards, community audience. Plan structure: opening pattern, 5 sections, callback closing. Establish emotional anchor: celebration, community recognition (GROUND)
3. Generate awards content matching the voice's metrics, patterns, and architectural patterns (GENERATE)
4. Run voice_validator.py, score: 58, 3 violations found (VALIDATE)
5. Fix "delve into" banned phrase, em-dash, rhythm violation (REFINE)
6. Re-validate: score 82, PASSED. Run scan-negative-framing.py: clean. Evaluate paragraphs: all JOY/NEUTRAL (JOY-CHECK)
7. Display with validation and joy-check report (OUTPUT)
8. Remove temp files (CLEANUP)
Result: Voice-consistent blog post with validation report showing PASSED at 82/100, joy score 88/100

### Example 2: Validate Existing Content
User says: "/voice-writer --validate --voice myvoice --content /path/to/draft.md"
Actions:
1. Load voice-myvoice profile.json and config.json (LOAD)
2. Skip GROUND and GENERATE phases (validate-only mode)
3. Run voice_validator.py against provided content (VALIDATE)
4. Skip REFINE (validate-only mode)
5. Run joy-check against provided content (JOY-CHECK)
6. Display validation and joy-check report with metrics comparison (OUTPUT)
7. No temp files to clean (CLEANUP)
Result: Validation report showing pass/fail status, specific violations, and joy scores

### Example 3: Voice Content (Non-Blog)
User says: "/voice-writer --voice myvoice --subject 'Why I switched to Nix' --mode technical"
Actions:
1. Load voice infrastructure (LOAD)
2. Establish emotional anchor: curiosity about tooling decisions. Select technical mode (GROUND)
3. Generate technical piece with voice patterns and architectural patterns -- argument flow, analogy domains (GENERATE)
4. Validate against profile (VALIDATE)
5. Fix violations if any (REFINE)
6. Run scan-negative-framing.py, evaluate paragraphs against rubric (JOY-CHECK)
7. Display with reports (OUTPUT)
8. Clean up (CLEANUP)
Result: Voice-consistent technical piece with full validation

---

## Error Handling

### Error: "Voice Not Found"
Cause: Voice name misspelled or voice directory does not exist
Solution:
1. Check spelling of voice name
2. List available voices: `ls $HOME/claude-code-toolkit/skills/voice-*/`
3. Create new voice using `create-voice` skill

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
3. User can re-validate with `/voice-writer --validate`
4. Consider recalibrating voice profile if failures are systemic

### Error: "Regex Scanner Fails or Not Found"
Cause: `scan-negative-framing.py` script missing or Python error
Solution:
1. Verify script exists: `ls scripts/scan-negative-framing.py`
2. Check Python version: `python3 --version` (requires 3.10+)
3. If script unavailable, skip regex pre-filter and proceed directly to LLM-based joy-check analysis -- the regex pre-filter is an optimization, not a requirement

### Error: "Joy-Check Failed After 3 Iterations"
Cause: Rewritten paragraphs keep introducing new GRIEVANCE patterns, often because the underlying premise is grievance-based
Solution:
1. Output the best version achieved with flagged remaining concerns
2. Explain which specific rubric dimensions resist correction
3. Suggest the framing premise itself may need rethinking, not just the language

### Error: "No voice specified"
Cause: User did not specify a voice parameter
Solution:
1. Default to the user's configured voice skill
2. Notify user which voice is being used
3. Proceed with Phase 1

### Error: "Topic too broad for target length"
Cause: Topic scope exceeds estimated word count
Solution:
1. Ask user to narrow scope
2. Suggest 2-3 specific angles derived from the topic
3. Proceed once user selects a narrower focus

---

## References

- `${CLAUDE_SKILL_DIR}/references/validation-scripts.md`: Full validation command reference and output schema
- `${CLAUDE_SKILL_DIR}/references/voice-infrastructure.md`: Voice file structure, config/profile schemas, modes, fix strategies
- `${CLAUDE_SKILL_DIR}/references/banned-words.md`: Words and phrases that signal AI-generated content
- `${CLAUDE_SKILL_DIR}/references/structure-templates.md`: Templates for Problem-Solution, Technical Explainer, and Walkthrough content types

### Related Skills and Scripts
- `joy-check` -- Standalone joy framing validation (invoked as Phase 6 of this pipeline)
- `scan-negative-framing.py` -- Regex pre-filter for obvious negative framing patterns
- `voice-validator` -- Deterministic voice fidelity validation
- `voice-calibrator` -- Voice profile creation and tuning
- `anti-ai-editor` -- AI pattern detection and removal
- `create-voice` -- New voice profile creation
