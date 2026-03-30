---
name: create-voice
description: "Create voice profiles from writing samples."
version: 1.0.0
user-invocable: false
argument-hint: "<voice-name> <sample-files...>"
command: /create-voice
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
    - create voice
    - new voice
    - build voice
    - voice from samples
    - calibrate voice
    - voice profile from scratch
    - make a voice
  pairs_with:
    - voice-calibrator
    - voice-writer
  complexity: Medium
  category: content
---

# Create Voice

Create a complete voice profile from writing samples through a 7-phase pipeline. This skill is the user-facing entry point for the voice system. It orchestrates existing tools (voice_analyzer.py, voice_validator.py, voice-calibrator template) into a guided, phase-gated workflow.

**Architecture**: This skill is a GUIDE and ORCHESTRATOR. It delegates all deterministic work to existing scripts and all template structure to the voice-calibrator skill. It does not duplicate or replace any existing component.

---

## Instructions

### Overview

Read and follow the repository CLAUDE.md before starting any work.

The pipeline has 7 phases. Each phase produces artifacts saved to files (because context is ephemeral; files persist) and has a gate that must pass before proceeding. Report progress with phase status banners at each gate. Be direct about what passed or failed, not congratulatory.

| Phase | Name | Artifact | Gate |
|-------|------|----------|------|
| 1 | COLLECT | `skills/voice-{name}/references/samples/*.md` | 50+ samples exist |
| 2 | EXTRACT | `skills/voice-{name}/profile.json` | Script exits 0, metrics present |
| 3 | PATTERN | Pattern analysis document | 10+ phrase fingerprints identified |
| 4 | RULE | Voice rules document | Rules have contrastive examples |
| 5 | GENERATE | `skills/voice-{name}/SKILL.md` + `config.json` | SKILL.md has 2000+ lines, samples section has 400+ lines |
| 6 | VALIDATE | Validation report | Score >= 70, no banned pattern violations |
| 7 | ITERATE | Final validated skill | 4/5 authorship match (or 3 iteration limit reached) |

---

### Step 1: COLLECT -- Gather 50+ Writing Samples

**Goal**: Build a corpus of real writing that captures the full range of the person's voice.

Stop and resolve before proceeding past this step without 50+ samples, because the system tried with 3-10 and FAILED. 50+ is where it starts working. LLMs are pattern matchers -- rules tell AI what to do but samples show AI what the voice looks like. V7-V9 had correct rules but failed authorship matching (0/5 roasters). V10 passed 5/5 because it had 100+ categorized samples.

See `references/sample-collection.md` for the "Where to Find Samples" table, "Sample Quality Guidelines", "Directory Setup", and "Sample File Format".

**GATE**: Count the samples. If fewer than 50 distinct writing samples exist across all files, STOP. Tell the user how many more are needed and where to find them. Stop and resolve before proceeding.

```
Phase 1/7: COLLECT
  Samples: {count} across {file_count} files
  Sources: {list of source types}
  GATE: {PASS if >= 50 / FAIL if < 50}
```

---

### Step 2: EXTRACT -- Run Deterministic Analysis

**Goal**: Extract quantitative voice metrics from the samples using `voice_analyzer.py`.

Always run script-based analysis before AI interpretation, because scripts produce reproducible, quantitative baselines. AI interpretation without data drifts toward "sounds like a normal person" rather than capturing what makes THIS person distinctive. The numbers ground everything that follows.

#### Run the Analyzer

```bash
python3 ~/.claude/scripts/voice_analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json
```

#### Also Get the Text Report

```bash
python3 ~/.claude/scripts/voice_analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --format text
```

The text report gives a human-readable summary. Save it for reference during Steps 3-4.

#### What the Analyzer Extracts

| Category | Metrics | Why It Matters |
|----------|---------|---------------|
| Sentence metrics | Length distribution, average, variance | Rhythm fingerprint |
| Punctuation | Comma density, question rate, exclamation rate, em-dash count, semicolons | Punctuation signature |
| Word metrics | Contraction rate, first-person rate, second-person rate | Formality and perspective |
| Structure | Fragment rate, sentence starters by type | Structural patterns |
| Function words | Top 20 function word frequencies | Unconscious language fingerprint |

#### Verify the Output

Read `profile.json` and confirm it contains all expected sections. If the script exits non-zero, check:

1. Python 3 is available
2. Sample files are readable
3. File paths are correct (glob expansion can be tricky)

**GATE**: `profile.json` exists, is valid JSON, and contains `sentence_metrics`, `punctuation_metrics`, `word_metrics`, and `structure_metrics` sections. Script exit code was 0.

```
Phase 2/7: EXTRACT
  Profile: skills/voice-{name}/profile.json
  Samples analyzed: {N}
  Total words: {N}
  Total sentences: {N}
  Average sentence length: {X} words
  GATE: {PASS/FAIL}
```

---

### Step 3: PATTERN -- Identify Voice Patterns (AI-Assisted)

**Goal**: Using the samples + profile.json, identify the distinctive patterns that make this voice THIS voice and not generic writing.

The script extracted WHAT (numbers). This step identifies WHY those numbers are what they are and what distinctive PATTERNS produce them. A high contraction rate is a number; "uses contractions even in technical explanations, creating casual authority" is a pattern.

See `references/pattern-identification.md` for detailed guidance on "Phrase Fingerprints", "Thinking Patterns", "Response Length Distribution", "Natural Typos", "Wabi-Sabi Markers", and all 4 "Linguistic Architectures" (Argument, Concession, Analogy, Bookend) with documentation templates.

**GATE**: At least 10 phrase fingerprints documented with exact quotes. At least 3 thinking patterns identified. Response length distribution estimated. At least 5 natural typos found. Wabi-sabi markers identified. At least 2 of 4 linguistic architectures documented with evidence quotes.

```
Phase 3/7: PATTERN
  Phrase fingerprints: {count}
  Thinking patterns: {count}
  Linguistic architectures: {count}/4 documented
  Length distribution: {very short}% / {short}% / {medium}% / {long}%
  Natural typos: {count}
  Wabi-sabi markers: {list}
  GATE: {PASS/FAIL}
```

---

### Step 4: RULE -- Build Voice Rules

**Goal**: Transform the patterns identified in Step 3 into actionable rules for the voice skill.

Rules set boundaries while samples show execution. You need both, but samples do the heavy lifting, because V7-V9 had detailed rules and failed 0/5 authorship matching -- V10 passed with samples. Rules prevent the worst failures (AI phrases, wrong structure). Samples guide the model toward authentic output.

See `references/voice-rules-template.md` for the full "What This Voice IS" positive identity format, the "What This Voice IS NOT" contrastive table template, "Hard Prohibitions" checklist, "Wabi-Sabi Rules", "Anti-Essay Patterns", and the "Architectural Patterns" template with all 4 rule sections (Argument Flow, Concessions, Analogy Domains, Bookends).

**GATE**: Positive identity has 4+ traits with dampening adverbs. Contrastive table covers 6+ aspects. At least 3 hard prohibitions defined. Wabi-sabi rules specify which imperfections to preserve. Anti-essay patterns documented. Architectural patterns documented for each architecture identified in Step 3.

```
Phase 4/7: RULE
  Positive traits: {count} (with dampening)
  Contrastive aspects: {count}
  Hard prohibitions: {count}
  Wabi-sabi rules: {count}
  Anti-essay patterns: {list}
  Architectural patterns: {count}
  GATE: {PASS/FAIL}
```

---

### Step 5: GENERATE -- Create the Voice Skill

**Goal**: Generate the complete voice skill files following the voice-calibrator template.

keep modifications out of scope — voice_analyzer.py, voice_validator.py, banned-patterns.json, voice-calibrator, voice-writer, or any existing skill/script, because the existing tools work. This skill only creates new files in `skills/voice-{name}/`.

Before generating, show users any existing voice implementation in `skills/voice-*/` as a concrete example of "done", because reference implementations ground expectations.

Follow the template structure from voice-calibrator (lines 1063-1512 of `pipelines/voice-calibrator/SKILL.md`), because it was refined over 10 iterations and embeds prompt engineering best practices (attention anchoring, probability dampening, XML context tags, few-shot examples for prohibitions). Deviating from the template means losing those lessons.

See `references/skill-generation.md` for "Files to Create", the "SKILL.md Structure" table (sections by line count), "SKILL.md Frontmatter", "Sample Organization" (by length and by pattern type), "Voice Metrics Section" format, "Two-Layer Architecture", "Prompt Engineering Techniques" (5 validated techniques), and the `config.json` template.

**GATE**: `SKILL.md` exists with 2000+ lines. Samples section has 400+ lines. All template sections present (samples, metrics, rules, fingerprints, protocol, typos, contrastive examples, thinking patterns). `config.json` exists with valid JSON. Frontmatter has correct fields.

```
Phase 5/7: GENERATE
  SKILL.md: {line_count} lines
  Samples section: {line_count} lines
  config.json: created
  Template sections: {present_count}/{required_count}
  GATE: {PASS/FAIL}
```

---

### Step 6: VALIDATE -- Test Against Profile

**Goal**: Generate test content using the new skill, then validate it against the profile using deterministic scripts.

Validate with scripts, not self-assessment, because self-assessment drifts. The model will convince itself the output sounds right. Scripts measure whether sentence length, punctuation density, and contraction rate actually match the targets. Objective measurement prevents rationalization.

Run both `voice_validator.py validate` and `voice_validator.py check-banned` during this step.

#### Generate Test Content

Using the new voice skill, generate 3 test pieces:
1. A short response (2-3 sentences) to a casual prompt
2. A medium response (paragraph) to a technical question
3. A long response (multi-paragraph) to an opinion question

Save each to a temp file.

#### Run Validation

For each test piece:

```bash
python3 ~/.claude/scripts/voice_validator.py validate \
  --content /tmp/voice-test-{name}-{N}.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text \
  --verbose
```

#### Run Banned Pattern Check

```bash
python3 ~/.claude/scripts/voice_validator.py check-banned \
  --content /tmp/voice-test-{name}-{N}.md \
  --voice {name}
```

#### Interpret Results

| Score | Status | Action |
|-------|--------|--------|
| 60+ with 0 errors | PASS | Proceed to Step 7. The script's pass threshold is 60 (calibrated against real human writing which scored ~66). 70+ is ideal but not required. |
| 50-59 with warnings only | MARGINAL | Review warnings, fix if simple, or proceed |
| < 50 or errors present | FAIL | Identify top 3 violations, fix in SKILL.md, regenerate, revalidate |

**Wabi-sabi check**: If validation flags natural imperfections as errors (run-on sentences, fragments, loose punctuation that match the samples), adjust the validator threshold in config.json, NOT the content, because the authentic writing scored what it scored and synthetic content should match it, not exceed it. If the original writing "fails" validation, the validator is wrong, not the writing.

#### If Validation Fails

1. Read the violation report carefully
2. Identify the top 3 violations by severity
3. For each violation, determine if it's:
   - A **real problem** (AI phrase, wrong structure) -- fix in SKILL.md rules or add more samples
   - A **false positive** (natural imperfection flagged as error) -- adjust config.json thresholds
4. Make targeted fixes (one at a time, not wholesale rewrites)
5. Regenerate test content and revalidate
6. Maximum 3 validation/refinement iterations before escalating to user

**GATE**: At least one test piece scores 60+ with 0 errors (script pass threshold is 60, calibrated against real human writing). No banned pattern violations. If failed after 3 iterations, proceed to Step 7 with best score and report issues.

```
Phase 6/7: VALIDATE
  Test 1 (short): {score}/100 - {PASS/FAIL}
  Test 2 (medium): {score}/100 - {PASS/FAIL}
  Test 3 (long): {score}/100 - {PASS/FAIL}
  Banned patterns: {CLEAN/violations found}
  Iterations: {N}/3
  GATE: {PASS/FAIL}
```

---

### Step 7: ITERATE -- Refine Until Authentic

**Goal**: Test the voice against human judgment through authorship matching, because metrics measure surface features but humans detect deeper patterns -- the "feel" of a voice. A piece can pass all metrics and still feel synthetic. Treat validation as one gate among several.

Maximum 3 iterations in this step before escalating to user.

#### The Authorship Matching Test

1. Select 3-5 original writing samples that were NOT included in the SKILL.md (hold-out samples)
2. Generate 3-5 new pieces using the voice skill on similar topics
3. Present both sets (mixed, unlabeled) to 5 "roasters" (people familiar with the original voice)
4. Ask each roaster: "Were these written by the same person?"
5. Target: 4/5 roasters say "SAME AUTHOR"

#### If Authorship Matching Fails

The answer is almost always MORE SAMPLES, not more rules, because adding "just one more rule" was tried through V7-V9 and produced zero improvement -- what worked was adding 100+ categorized samples in V10.

| Failure Pattern | Diagnosis | Fix |
|----------------|-----------|-----|
| "Ideas match but style doesn't" | Insufficient samples in SKILL.md | Add 20-50 more samples, especially short responses |
| "Too polished, too perfect" | Wabi-sabi not applied strongly enough | Increase fragment rate target, add more typos, loosen punctuation rules |
| "Phrases feel generic" | Phrase fingerprints not prominent enough | Bold the fingerprints, add more examples of each |
| "Wrong rhythm" | Sentence length distribution off | Check profile.json targets against generated metrics |
| "Right voice, wrong length" | Response length distribution wrong | Adjust default mode or add stronger length constraints |

#### The V10 Lesson

One voice went through 10 versions during development:
- V1-V6: Incremental rule improvement. Modest gains.
- V7-V9: Rules were correct but authorship matching failed 0/5. The voice had the right CONSTRAINTS but not enough EXAMPLES.
- V10: Added 100+ samples organized by pattern. Passed 5/5.

**The breakthrough was not better rules. It was more samples.**

If you find yourself tweaking rules and not improving, step back and ask: "Do I need more samples in the SKILL.md?" The answer is almost certainly yes.

#### Wabi-Sabi Final Check

Before declaring the voice complete, verify:

- [ ] Generated content contains natural imperfections from the samples (not manufactured imperfections)
- [ ] Run-on sentences appear at approximately the same rate as in the original samples
- [ ] Fragments appear for emphasis, matching sample patterns
- [ ] Typos from the natural typos list appear occasionally (not forced)
- [ ] Content reads with the same level of polish as the original samples (unless the original voice IS polished)
- [ ] If content is too perfect, the skill needs MORE samples and LOOSER constraints, not fewer
- [ ] If generated content "feels too rough," compare against original samples before adjusting -- if it matches the samples' roughness, it's correct

**GATE**: 4/5 roasters say SAME AUTHOR. If roaster test is not feasible, use self-assessment checklist: Does the generated content feel like reading the original samples? Could you tell them apart? If yes (you can tell them apart), more work is needed.

```
Phase 7/7: ITERATE
  Authorship match: {X}/5 roasters
  Iterations completed: {N}
  Final validation score: {X}/100
  GATE: {PASS/FAIL}
```

---

### Final Output

After all phases complete:

```
===============================================================
 VOICE CREATION COMPLETE: {name}
===============================================================
 Files created:
   skills/voice-{name}/SKILL.md              (voice skill)
   skills/voice-{name}/profile.json          (metrics)
   skills/voice-{name}/config.json           (validation config)
   skills/voice-{name}/references/samples/   (organized samples)

 Validation: {PASSED/FAILED} (score: {X}/100)
 Authorship Match: {X}/5 roasters
===============================================================
```

---

## Error Handling

### Error: "Insufficient samples" (< 50)

**Cause**: User provided fewer than 50 writing samples.
**Solution**:
1. Count current samples and report the gap
2. Suggest specific sources based on what's already provided (e.g., "You have 20 Reddit comments. Try also pulling from HN history, blog posts, or email")
3. Stop and resolve before proceeding past Step 1. The system does not work with fewer than 50 samples.

### Error: "voice_analyzer.py fails"

**Cause**: Script execution error.
**Solution**:
1. Check Python 3 is available: `python3 --version`
2. Check script exists: `ls scripts/voice_analyzer.py`
3. Check file paths: Glob expansion may not work as expected in all shells. Try listing files first: `ls skills/voice-{name}/references/samples/*.md`
4. Try with explicit file list instead of glob: `--samples file1.md file2.md file3.md`

### Error: "Validation score too low" (< 50 after 3 iterations)

**Cause**: Generated content does not match voice profile metrics.
**Solution**:
1. Check if profile.json metrics are achievable (some metrics from small sample sets may be skewed)
2. Review banned patterns for false positives specific to this voice
3. Consider relaxing `metric_tolerance` in config.json from 0.20 to 0.25
4. Check if the SKILL.md has enough samples (the answer is usually: add more samples)
5. Manual review of SKILL.md instructions for contradictory rules

### Error: "Authorship matching fails" (< 4/5 roasters)

**Cause**: Generated content does not sound like the original author.
**Solution**: See the failure pattern table in Step 7. The fix is almost always more samples, not more rules.

### Error: "SKILL.md too short" (< 2000 lines)

**Cause**: Not enough samples or sections in the generated skill.
**Solution**:
1. Check that all sample categories are populated (length-based AND pattern-based)
2. Verify all template sections are present
3. Add more samples -- they are the bulk of the line count
4. Keep content substantive — with verbose rules. The goal is 2000+ lines of USEFUL content, primarily samples.

### Error: "Wabi-sabi violations flagged as errors"

**Cause**: Validator is flagging natural imperfections that are actually part of the voice.
**Solution**: Adjust config.json thresholds, NOT the content. If the authentic writing "fails" validation, the validator is wrong, not the writing.

---

## References

### Reference Implementations

Study any existing voice profile in `skills/voice-*/` to understand what "done" looks like. A complete voice profile contains:

| File | Typical Size | What to Learn |
|------|-------------|---------------|
| `skills/voice-{name}/SKILL.md` | 2000+ lines | Voice rules, samples, patterns, metrics |
| `skills/voice-{name}/references/samples/` | 5-10 files | How samples should be organized by source and date |
| `skills/voice-{name}/config.json` | ~20 lines | Validation configuration structure |
| `skills/voice-{name}/profile.json` | ~80 lines | Profile structure from voice_analyzer.py |

### Components This Skill Delegates To

| Component | Type | What It Does | When Called |
|-----------|------|-------------|-------------|
| `scripts/voice_analyzer.py analyze` | Script | Extract quantitative metrics from writing samples | Step 2: EXTRACT |
| `scripts/voice_analyzer.py compare` | Script | Compare two voice profiles | Optional (cross-voice comparison) |
| `scripts/voice_validator.py validate` | Script | Validate generated content against voice profile | Step 6: VALIDATE |
| `scripts/voice_validator.py check-banned` | Script | Quick banned pattern check | Step 6: VALIDATE |
| `scripts/data/banned-patterns.json` | Data | AI pattern database used by validator | Step 6 (via validator) |
| `pipelines/voice-calibrator/SKILL.md` | Skill | Voice skill template (lines 1063-1554, including the validation checklist) | Step 5: GENERATE (template reference) |
