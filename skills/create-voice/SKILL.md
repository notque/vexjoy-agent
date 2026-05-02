---
name: create-voice
description: "Create voice profiles from writing samples."
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
    - voice-validator
    - voice-writer
  complexity: Medium
  category: content
---

# Create Voice

Create a complete voice profile from writing samples through a 7-phase pipeline. This skill orchestrates existing tools (voice-analyzer.py, voice-validator.py, voice-calibrator template) into a guided, phase-gated workflow. It is a GUIDE and ORCHESTRATOR -- delegates all deterministic work to scripts, all template structure to the voice-calibrator skill. Does not duplicate or replace any existing component.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| extraction validation, pattern verdict, triple-validation | `extraction-validation.md` | Triple-validation rubric (recurrence, generative power, exclusivity) gating which patterns survive into the profile. |
| tasks related to this reference | `iteration-guide.md` | Loads detailed guidance from `iteration-guide.md`. |
| implementation patterns | `pattern-identification.md` | Loads detailed guidance from `pattern-identification.md`. |
| tasks related to this reference | `phase-banners.md` | Loads detailed guidance from `phase-banners.md`. |
| tasks related to this reference | `reference-implementations.md` | Loads detailed guidance from `reference-implementations.md`. |
| tasks related to this reference | `sample-collection.md` | Loads detailed guidance from `sample-collection.md`. |
| tasks related to this reference | `skill-generation.md` | Loads detailed guidance from `skill-generation.md`. |
| tasks related to this reference | `voice-rules-template.md` | Loads detailed guidance from `voice-rules-template.md`. |

## Instructions

### Overview

Read and follow the repository CLAUDE.md before starting.

The pipeline has 7 phases. Each produces artifacts saved to files and has a gate that must pass before proceeding. Report progress with phase status banners (templates in `references/phase-banners.md`). Be direct about pass/fail, not congratulatory.

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

**Goal**: Build a corpus capturing the full range of the person's voice.

Do not proceed past this step without 50+ samples. The system tried with 3-10 and FAILED. 50+ is where it starts working. Rules tell AI what to do; samples show what the voice looks like. V7-V9 had correct rules but failed authorship matching (0/5). V10 passed 5/5 with 100+ categorized samples.

See `references/sample-collection.md` for "Where to Find Samples", "Sample Quality Guidelines", "Directory Setup", and "Sample File Format".

**GATE**: Count the samples. Fewer than 50 distinct samples: STOP. Tell the user how many more are needed and where to find them.

See `references/phase-banners.md` for the Phase 1 status banner template.

---

### Step 2: EXTRACT -- Run Deterministic Analysis

**Goal**: Extract quantitative voice metrics using `voice-analyzer.py`.

Always run script-based analysis before AI interpretation -- scripts produce reproducible baselines. AI interpretation without data drifts toward "sounds like a normal person."

#### Run the Analyzer

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json
```

#### Also Get the Text Report

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --format text
```

Save it for reference during Steps 3-4.

#### What the Analyzer Extracts

| Category | Metrics | Why It Matters |
|----------|---------|---------------|
| Sentence metrics | Length distribution, average, variance | Rhythm fingerprint |
| Punctuation | Comma density, question rate, exclamation rate, em-dash count, semicolons | Punctuation signature |
| Word metrics | Contraction rate, first-person rate, second-person rate | Formality and perspective |
| Structure | Fragment rate, sentence starters by type | Structural patterns |
| Function words | Top 20 function word frequencies | Unconscious language fingerprint |

#### Verify the Output

Read `profile.json` and confirm all expected sections. If script exits non-zero, check Python 3 availability, sample file readability, and file paths.

**GATE**: `profile.json` exists, is valid JSON, contains `sentence_metrics`, `punctuation_metrics`, `word_metrics`, and `structure_metrics`. Script exit code was 0.

See `references/phase-banners.md` for the Phase 2 status banner template.

---

### Step 3: PATTERN -- Identify Voice Patterns (AI-Assisted)

**Goal**: Using samples + profile.json, identify the distinctive patterns that make this voice THIS voice.

The script extracted WHAT (numbers). This step identifies WHY those numbers are what they are and what PATTERNS produce them. A high contraction rate is a number; "uses contractions even in technical explanations, creating casual authority" is a pattern.

See `references/pattern-identification.md` for "Phrase Fingerprints", "Thinking Patterns", "Response Length Distribution", "Natural Typos", "Wabi-Sabi Markers", and all 4 "Linguistic Architectures" with documentation templates.

#### Apply the Triple-Validation Rubric

Every candidate pattern runs through `references/extraction-validation.md` before documentation. Each documented pattern carries an explicit verdict (KEEP, FOOTNOTE, or DROP) with evidence for cross-domain recurrence, generative power, and distinguishing exclusivity. KEEP and FOOTNOTE advance to Step 4; DROP patterns are recorded in working notes only. This rubric is mandatory -- patterns that pass on intuition alone tend to be generic-writer features.

**GATE**: At least 10 phrase fingerprints with exact quotes AND triple-validation verdicts. At least 3 thinking patterns with verdicts. Response length distribution estimated. At least 5 natural typos. Wabi-sabi markers identified. At least 2 of 4 linguistic architectures documented with evidence quotes and verdicts. Every documented pattern carries KEEP or FOOTNOTE verdict.

See `references/phase-banners.md` for the Phase 3 status banner template.

---

### Step 4: RULE -- Build Voice Rules

**Goal**: Transform patterns from Step 3 into actionable rules.

Rules set boundaries; samples show execution. Both needed, but samples do the heavy lifting -- V7-V9 had detailed rules and failed 0/5 authorship matching; V10 passed with samples. Rules prevent worst failures (AI phrases, wrong structure).

See `references/voice-rules-template.md` for "What This Voice IS" positive identity format, "What This Voice IS NOT" contrastive table, "Hard Prohibitions", "Wabi-Sabi Rules", "Anti-Essay Patterns", and "Architectural Patterns" template.

Build rules only from KEEP and FOOTNOTE patterns from Step 3's triple-validation (`references/extraction-validation.md`). FOOTNOTE patterns scope to the domain where verified -- write the rule with a guard clause. DROP candidates are absent from the rules document.

**GATE**: Positive identity has 4+ traits with dampening adverbs, each traceable to a KEEP-verdict pattern. Contrastive table covers 6+ aspects. At least 3 hard prohibitions. Wabi-sabi rules specify preserved imperfections. Anti-essay patterns documented. Architectural patterns documented for each KEEP/FOOTNOTE architecture from Step 3.

See `references/phase-banners.md` for the Phase 4 status banner template.

---

### Step 5: GENERATE -- Create the Voice Skill

**Goal**: Generate the complete voice skill files following the voice-calibrator template.

Do not modify voice-analyzer.py, voice-validator.py, banned-patterns.json, voice-calibrator, voice-writer, or any existing skill/script. This skill only creates new files in `skills/voice-{name}/`.

Show users any existing voice implementation in `skills/voice-*/` as a concrete example.

Follow the template structure from voice-calibrator (lines 1063-1512 of `skills/workflow/references/voice-calibrator.md`) -- it was refined over 10 iterations and embeds prompt engineering best practices (attention anchoring, probability dampening, XML context tags, few-shot examples for prohibitions).

See `references/skill-generation.md` for "Files to Create", "SKILL.md Structure" table, "SKILL.md Frontmatter", "Sample Organization", "Voice Metrics Section", "Two-Layer Architecture", "Prompt Engineering Techniques", and `config.json` template.

**GATE**: `SKILL.md` exists with 2000+ lines. Samples section has 400+ lines. All template sections present (samples, metrics, rules, fingerprints, protocol, typos, contrastive examples, thinking patterns). `config.json` exists with valid JSON. Frontmatter has correct fields.

See `references/phase-banners.md` for the Phase 5 status banner template.

---

### Step 6: VALIDATE -- Test Against Profile

**Goal**: Generate test content using the new skill, then validate with deterministic scripts.

Validate with scripts, not self-assessment -- the model will convince itself the output sounds right. Scripts measure whether metrics actually match targets.

Run both `voice-validator.py validate` and `voice-validator.py check-banned` during this step.

See `references/iteration-guide.md` for "Generate Test Content" steps, validation commands, score interpretation table, wabi-sabi check, and "If Validation Fails" recovery.

**GATE**: At least one test piece scores 60+ with 0 errors (threshold calibrated against real human writing). No banned pattern violations. If failed after 3 iterations, proceed to Step 7 with best score and report issues.

See `references/phase-banners.md` for the Phase 6 status banner template.

---

### Step 7: ITERATE -- Refine Until Authentic

**Goal**: Test against human judgment through authorship matching -- metrics measure surface features but humans detect deeper patterns. A piece can pass all metrics and still feel synthetic.

Maximum 3 iterations before escalating to user.

See `references/iteration-guide.md` for "Authorship Matching Test", "If Authorship Matching Fails" failure pattern table, "The V10 Lesson", and "Wabi-Sabi Final Check".

**GATE**: 4/5 roasters say SAME AUTHOR. If roaster test not feasible, use self-assessment: Does generated content feel like reading the original samples? Could you tell them apart? If yes, more work needed.

See `references/phase-banners.md` for the Phase 7 status banner template.

---

### Final Output

See `references/phase-banners.md` for the "VOICE CREATION COMPLETE" final output template.

---

## Error Handling

See `references/error-handling.md` for the full error matrix (insufficient samples, voice-analyzer failures, validation score too low, authorship matching failures, SKILL.md too short, wabi-sabi violations).

---

## References

See `references/reference-implementations.md` for the "Reference Implementations" table and the "Components This Skill Delegates To" table.
