---
name: voice-writer
description: |
  Unified voice content generation pipeline with mandatory validation and
  joy-check. 8-phase pipeline: LOAD, GROUND, GENERATE, VALIDATE, REFINE, JOY-CHECK,
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
    - write blog
    - article about
    - publish post
    - content for blog
    - hugo post
    - write for website
    - long-form content
    - write piece
    - write essay
    - ghost write
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

Load `SKILL.md`, `profile.json`, and `config.json` from `skills/voice-{name}/`. Also load 1-2 samples from `references/samples/` if available.

See `references/voice-infrastructure.md` for file table, schema details, and threshold parsing.

**Step 3: Verify file presence**

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

**Step 1: Emotional anchoring** — Answer the three grounding questions (what emotion, what the writer cares about, who they're writing for).

**Step 2: Relational positioning** — Establish writer-audience relationship, assumed knowledge level, and intimacy level.

**Step 3: Mode selection** — Select content mode from the voice's `config.json`. Infer from subject matter if user does not specify.

**Step 4: Blog post assessment** (if blog post or article) — Capture topic, scope, audience, and estimated length.

**Step 5: Structure planning** (if blog post or article) — Plan opening pattern, sections, closing pattern, and callback element. Draft Hugo frontmatter if applicable.

See `references/grounding-guide.md` for full question tables, templates, and content type selection.

**Important constraint**: This grounding is mandatory, not optional. Content generated without emotional anchor and mode selection sounds mechanical regardless of metrics match. The validator catches style mismatches but cannot fix a hollow emotional foundation. Do not skip this step even briefly — complete it fully before moving to GENERATE.

**Gate**: Emotion, audience, and mode are established. If blog post, topic assessed and structure planned. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Produce content matching voice patterns from profile and SKILL.md.

**Step 1: Apply voice rules from SKILL.md** -- patterns, anti-patterns, signature phrases

**Step 2: Target profile.json metrics** -- sentence length distribution, contraction rate, punctuation patterns, transition words

**Step 3: Include few-shot samples** if loaded in Phase 1

**Step 4: Apply mode-specific patterns** based on selected mode

**Step 4b: Apply architectural patterns** from the voice skill's `## Architectural Patterns` section (if present): argument flow direction, concession pivot markers, analogy domains, and bookend moves. Skip if no such section exists.

See `references/generation-checklist.md` for the full 12-item generation checklist, architectural patterns application rules, and em-dash prohibition details.

**Step 5: Write to temp file**

```bash
cat > /tmp/voice-content-draft.md << 'CONTENT'
[Generated content here]
CONTENT
```

**Important constraints**: Single voice per piece; no over-engineering; preview before write unless Direct Write Mode is enabled.

**Gate**: Content written to file. All checklist items addressed. Proceed only when gate passes.

### Phase 4: VALIDATE (Deterministic)

**Goal**: Run the voice validator script against generated content. No self-assessment.

This phase is non-negotiable. Do not skip validation for "good enough" content. Human perception drifts. Deterministic validation catches patterns you miss. Self-assessment is not validation. Use `--skip-validation` only for true drafts the user explicitly requests as drafts.

**Step 1: Execute validation** — Run `voice_validator.py validate` against the draft. See `references/validation-scripts.md` for full command syntax and output schema.

**Step 2: Decision logic** — Pass → JOY-CHECK. Fail + iterations < 3 → REFINE. Fail + iterations ≥ 3 → JOY-CHECK with failure report. See `references/validation-scripts.md` for the full decision table.

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
2. Apply targeted fix — see `references/voice-infrastructure.md` for fix strategies by violation type
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

**Step 2: Evaluate each paragraph against the Joy Framing Rubric** — Score each paragraph as JOY (80-100), NEUTRAL (50-79), CAUTION (30-49), or GRIEVANCE (0-29) across five dimensions: subject position, other people, difficult experiences, uncertainty, and closing energy.

**Step 3: Score each paragraph** — One GRIEVANCE is a FAIL condition for the whole piece. CAUTION paragraphs are acceptable if the overall piece passes.

**Step 4: Rewrite GRIEVANCE paragraphs** — Rewrite preserving substance, shifting framing toward curiosity/generosity/earned satisfaction. Maximum 3 joy-check iterations.

See `references/joy-check-rubric.md` for the full rubric table, scoring system, rewrite rules, and the important constraint about facts arranged as prosecution.

**Gate**: No GRIEVANCE paragraphs remain. Joy-check passes. Proceed only when gate passes.

### Phase 7: OUTPUT

**Goal**: Format and display final content with validation report.

Display content followed by a validation report showing status, score, iterations, per-check results, metrics comparison table, and joy-check summary. Always include validation metrics — do not ship without showing the measurements. Show target file path if writing to file. Await user approval before writing unless Direct Write Mode is enabled.

See `references/output-format.md` for the full report template and status indicators.

**Gate**: Output displayed with validation report. Proceed only when gate passes.

### Phase 8: CLEANUP

**Goal**: Remove temporary files created during the pipeline.

**Step 1**: Remove `/tmp/voice-content-draft.md` and any iteration drafts

```bash
rm -f /tmp/voice-content-draft.md
rm -f /tmp/voice-content-draft-*.md
```

**Step 2**: Confirm final content is saved to user-specified location (if requested)

**Step 3**: Report pipeline completion with final status. See `references/output-format.md` for the completion report template.

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

| Error | Cause | Solution |
|-------|-------|----------|
| Voice Not Found | Misspelled name or missing directory | Check spelling; `ls $HOME/claude-code-toolkit/skills/voice-*/`; use `create-voice` |
| Profile or Config Missing | Files absent from voice directory | Run `voice-calibrator`; see `references/voice-infrastructure.md` for schema |
| Validator Script Failed (Exit Code 2) | File not found, invalid JSON, or Python issue | Verify paths; check `python3 --version`; test with `--help` flag |
| Validation Failed After 3 Iterations | Content cannot meet threshold | Output best attempt with failure report; user edits flagged lines; recalibrate if systemic |
| Regex Scanner Fails or Not Found | `scan-negative-framing.py` missing or error | Skip regex pre-filter; proceed to LLM-based joy-check analysis — it's an optimization, not a requirement |
| Joy-Check Failed After 3 Iterations | Underlying premise is grievance-based | Output best version; flag rubric dimensions that resist correction; suggest rethinking the framing premise |
| No voice specified | User omitted voice parameter | Default to configured voice skill; notify user; proceed with Phase 1 |
| Topic too broad for target length | Scope exceeds word count | Ask user to narrow scope; suggest 2-3 specific angles |

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
