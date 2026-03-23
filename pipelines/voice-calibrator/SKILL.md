---
name: voice-calibrator
description: |
  Analyze writing samples and extract voice patterns to create or update
  voice skills with deterministic metrics and authorship-matching validation.
  Use when calibrating a new voice, refining an existing voice profile,
  validating content against a voice profile, or comparing two voices.
  Do NOT use for content generation, general writing, or non-voice editing.
version: 2.0.0
user-invocable: false
command: /voice
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
---

# Voice Calibrator

## Operator Context

This skill operates as an operator for voice calibration workflows, configuring Claude's behavior for rigorous, sample-driven voice profile creation and validation. It implements the **Deterministic Analysis** architectural pattern — extract metrics via scripts, interpret via AI, validate via scripts — with **Voice Fidelity** as the primary quality gate.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before calibration
- **Over-Engineering Prevention**: Extract observable patterns from samples, not theoretical analysis
- **Voice Fidelity**: Generated voice skills must pass authorship matching (4/5 roasters minimum)
- **Data Integrity**: NEVER modify curated calibration data, writing samples, or existing voice profile content outside explicit user request

### Default Behaviors (ON unless disabled)
- **Communication Style**: Display full analysis with A/B comparisons, never summarize pattern counts
- **Run voice_analyzer.py**: Always run deterministic script analysis before AI interpretation
- **Validation Loop**: Run voice_validator.py after generating output, iterate if needed (max 3)
- **Profile Persistence**: Save profile.json and config.json alongside SKILL.md
- **Distinctive Focus**: Prioritize patterns that differ from generic writing

### Optional Behaviors (OFF unless enabled)
- **Strict Mode**: Require 5/5 roaster match instead of 4/5 minimum
- **Cross-Voice Comparison**: Compare two calibrated voice profiles for differences
- **Batch Analysis**: Analyze all posts in content/posts/ at once
- **Export Mode**: Generate standalone style guide document

## What This Skill CAN Do
- Calibrate voice profiles from 50+ writing samples via deterministic scripts
- Analyze writing samples to extract quantitative voice metrics (sentence length, punctuation, contractions)
- Generate machine-readable profile.json with measurable targets and tolerances
- Generate SKILL.md voice skills with sample-first architecture for authorship matching
- Validate generated content against voice profile metrics
- Show A/B comparisons between default and calibrated output

## What This Skill CANNOT Do
- Modify curated calibration data, writing samples, or existing voice profile content
- Skip deterministic analysis (scripts MUST run before AI interpretation)
- Generate content without prior calibration (only calibrates, user must invoke voice skill separately)
- Analyze fewer than 3 samples (insufficient data for reliable patterns)
- Copy copyrighted content verbatim (only extract style patterns)

---

This skill analyzes writing samples and generates voice skill files. Each voice gets its own skill in `skills/voice-{name}/` with both AI instructions (SKILL.md) and machine-readable metrics (profile.json).

**Architecture**: Sample-first generation with prompt engineering best practices for maximum voice fidelity.

---

## THE CRITICAL LESSON: QUANTITY OF EXAMPLES MATTERS MORE THAN RULES

V7, V8, V9 of the voice skill all had the right **rules** but failed authorship matching (0/5 roasters said same author). V10 passed 5/5 because it had **100+ real samples categorized by pattern**.

**The breakthrough insight:**
- Rules tell the AI what to do
- Examples show the AI what the voice looks like
- LLMs are pattern matchers - examples are more powerful than rules
- Roasters detect when content captures IDEAS but not EXECUTION STYLE
- Execution style comes from extensive example exposure, not rule following

**What V10 had that V7-V9 didn't:**
1. 100+ Reddit comments saved and categorized
2. Examples organized by response type (short, medium, long)
3. Examples organized by pattern (admitting mistakes, acknowledging limits, disagreement)
4. Explicit phrase fingerprints ("For what I do / For what you do", "probably tomorrow but we will see")
5. Real typos from the person's writing documented as authenticity markers

**REQUIREMENT: Generated voice skills MUST include extensive sample collections, not just rules.**

---

## Prompt Engineering Best Practices

When generating voice skills, apply these techniques for maximum effectiveness:

### 1. Attention Anchoring (Bolding)

**Usage**: Apply **bold** strictly to negative constraints and safety guardrails.

```markdown
**You must strictly avoid** the "It's not X. It's Y" rhetorical pattern.
**NEVER use** em-dashes in any form.
```

**Mechanism**: Acts as attention flag for tokenizer, increasing statistical weight of constraint.

### 2. Cognitive Chunking (Headers)

**Usage**: Enforce clear hierarchy of instruction. Never present as wall of text.

```markdown
## Identity (Who the voice is)
## Core Directives (What the voice does)
## Style & Tone (How the voice speaks)
## Negative Constraints (What to avoid)
```

**Mechanism**: Helps model separate distinct logical tasks, reducing "instruction bleeding."

### 3. Context Isolation (Delimiters)

**Usage**: Separate static instructions from dynamic context.

```markdown
---
(Use horizontal rules between sections)

<context>
(Use XML tags for user-provided content)
</context>
```

**Mechanism**: Prevents model from confusing user input with system rules.

### 4. Probability Dampening (Adverbs)

**Usage**: Use adverbs when defining personality/tone. Avoid absolute binary instructions.

```markdown
Write in a **subtly** skeptical tone.
Be **generally** direct rather than absolutely blunt.
Sound **slightly** informal while maintaining clarity.
```

**Mechanism**: Restricts token probability distribution less aggressively, preventing caricature.

### 5. Chain-of-Thought Triggers

**Usage**: For complex voice generation, add explicit logic directives.

```markdown
Before writing, think step-by-step:
1. What is my actual position on this topic?
2. What would I say if asked about this in a forum?
3. What process did I go through to form this opinion?
```

**Mechanism**: Forces intermediate token generation, increasing accuracy.

### 6. Few-Shot Examples (Pattern Matching)

**Usage**: Include 1-3 examples of ideal interaction at end of skill.

```markdown
User: "Explain why caching is hard"
Model (WRONG): "Caching is not storage. It's a bet about the future."
Model (CORRECT): "Think of caching as a bet about the future, not persistent storage."
```

**Mechanism**: LLMs are pattern matchers. Examples are more powerful than instructions.

### 7. Sample-First Architecture

**Usage**: Present actual writing samples BEFORE rules.

```markdown
## Phase 1: Voice Grounding (Read Before Writing)

Read these actual samples to internalize the voice:

### Sample A: Technical Explanation
> [Actual sample text from user's writing]

### Sample B: Personal Opinion
> [Another sample showing different context]
```

**Mechanism**: Samples show HOW the voice sounds. Rules tell WHAT it should be. Samples are more effective.

---

## Human Authenticity Markers (CRITICAL)

These patterns distinguish human writing from AI-generated content. Voice skills MUST teach these explicitly or generated content will fail authenticity checks.

### 1. Incomplete Work Admissions

**Requirement**: Include at least one admission of something incomplete, imperfect, or "inelegant."

```markdown
Examples:
- "I haven't yet built the X feature"
- "it misses a bunch of detail"
- "that's a pretty inelegant solution"
- "it works but it's not pretty"
```

**Why**: AI presents finished, polished work. Humans admit gaps.

### 2. Tangential Tool/Process References

**Requirement**: Allow tangents that don't directly serve the narrative but show the writer's actual workflow.

```markdown
Examples:
- "I built a custom tool for that (called X)"
- "I had Claude Code do the rest of the investigation"
- "I used my shot-scraper har command to grab..."
```

**Why**: AI stays on-message. Humans can't resist showing their tools.

### 3. Assumed Shared Context (Parenthetical Asides)

**Requirement**: Include parenthetical winks that assume reader knowledge.

```markdown
Examples:
- "(that Rob Pike)"
- "(so I hope it continues to work)"
- "You won't be surprised to hear..."
- "—new to me, suggested by Claude—"
```

**Why**: AI explains everything. Humans assume shared context with their audience.

### 4. Evolution/Iteration Narrative

**Requirement**: Show history of attempts, not just final solution.

```markdown
Examples:
- "I've made several past attempts at solving this problem"
- "a late refactoring, the initial system used..."
- "The first was X, but that missed Y"
```

**Why**: AI presents optimal solutions. Humans show the messy path.

### 5. Mid-Thought Discoveries

**Requirement**: Include moments where learning happens during writing.

```markdown
Examples:
- "—new to me, suggested by Claude—"
- "I ended up using that trick in X itself!"
- "Turns out X knows the trick where..."
```

**Why**: AI writes from complete knowledge. Humans discover as they write.

### 6. Unhedged Strong Opinions

**Requirement**: State opinions directly without AI safety hedges.

```markdown
WRONG (AI pattern):
- "This raises important concerns about..."
- "One might argue that..."
- "It's worth noting that..."

RIGHT (Human pattern):
- "I don't like this at all."
- "I totally understand his rage."
- "This completely misses the point!"
```

**Why**: AI hedges everything. Humans assert.

### 7. Playful/Subversive Notes

**Requirement**: Allow personality to bleed through in unexpected moments.

```markdown
Examples:
- "it felt a bit more subversive to have OpenAI Codex do it instead"
- "is a truly science fiction way of working"
- "The really neat trick there is..."
```

**Why**: AI is earnest. Humans have attitude.

### 8. Specific Artifacts (Not Hypotheticals)

**Requirement**: Reference real, specific things that can be verified.

```markdown
Examples:
- Actual commit hashes: "c80b1dee Rename tool..."
- Real commands: "uvx claude-code-transcripts"
- Specific dependencies: "questionary—new to me"
```

**Why**: AI generates plausible examples. Humans cite real artifacts.

### 9. Visible Self-Correction

**Requirement**: Show thinking that changes direction mid-paragraph.

```markdown
Examples:
- "At first I thought... but then I realized"
- "or rather, it was my willingness to..."
- "Actually, that's not quite right—"
```

**Why**: AI resolves neatly. Humans think out loud.

### 10. Raw Emotion/Profanity (When Quoting)

**Requirement**: When quoting others' strong reactions, preserve them raw.

```markdown
Examples:
- Quote profanity verbatim when relevant
- Don't soften: "He was upset" → "Fuck you people"
- Preserve intensity of original
```

**Why**: AI sanitizes. Humans quote reality.

### 11. Exploration Admission

**Requirement**: Admit when exploration yielded nothing valuable.

```markdown
Examples:
- "not everything is valuable"
- "The result essentially of this work was inconclusive"
- "nothing of real value came about from"
- "It's possible I find nothing of value and revert"
```

**Why**: AI always finds insights. Humans admit dead ends.

### 12. Soft Future Planning

**Requirement**: Plans should have uncertainty built in.

```markdown
Examples:
- "likely tomorrow but we will see"
- "I may take a break and relax today, but I think I need to"
- "I will likely create"
- "Today is an exploration day"
```

**Why**: AI commits to plans. Humans hedge their schedules.

### 13. Metaphor as Framing Device

**Requirement**: Use metaphors to frame complex ideas, not explain them.

```markdown
Examples:
- "I'm thinking of the ouroboros. The Snake that eats it's own tail."
- "It's effectively microservices principles applied to agentic cognition"
- "Rather than giving the agent a hammer, we give it a specific set of motions"
```

**Why**: AI explains metaphors. Humans drop them and assume understanding.

### 14. Not-X-but-Y Lists (Contrast Pairs)

**Requirement**: When explaining alternatives, use contrast pair format.

```markdown
Examples:
- "Not kubectl get logs: a crashloop-investigator skill"
- "Not just check service: a service-endpoint-verifier"
```

**Note**: This is DIFFERENT from the forbidden "It's not X. It's Y" rhetorical pivot. This is listing alternatives with "Not X: Y" format for technical specifications.

**Why**: Shows concrete alternatives, not rhetorical flourish.

### 15. Hypothesis-Experiment Framing

**Requirement**: Frame technical investigations as experiments with explicit uncertainty.

```markdown
Examples:
- "The hypothesis is that by making skills this granular..."
- "I'm going to build it and find out"
- "Does it orchestrate well? Does it improve outcomes?"
- "No idea if it will work, but I find this an interesting topic"
```

**Why**: AI presents conclusions. Humans run experiments.

### 16. Casual Closers/Interjections

**Requirement**: End thoughts with casual, almost throwaway observations.

```markdown
Examples:
- "so sounds super fun"
- "you get the point"
- "but okay, it doesn't take much to do that"
- "but we will see"
```

**Why**: AI wraps up neatly. Humans trail off naturally.

---

## Authenticity Checklist for Generated Skills

Before finalizing any voice skill, verify it teaches these patterns:

**Core 10 (Required):**
- [ ] Incomplete work admissions (teaches vulnerability)
- [ ] Tool/process tangents (teaches showing work)
- [ ] Parenthetical asides (teaches assumed context)
- [ ] Evolution narrative (teaches iteration visibility)
- [ ] Mid-thought discoveries (teaches learning in public)
- [ ] Unhedged opinions (teaches assertion over hedging)
- [ ] Playful moments (teaches personality)
- [ ] Specific artifacts (teaches concreteness)
- [ ] Visible self-correction (teaches thinking out loud)
- [ ] Raw emotion preservation (when quoting)

**Extended 6 (From calibration samples):**
- [ ] Exploration admission (admits dead ends)
- [ ] Soft future planning (hedged schedules)
- [ ] Metaphor as framing (drops metaphors, doesn't explain)
- [ ] Contrast pair lists (Not X: Y format for alternatives)
- [ ] Hypothesis-experiment framing (explicit uncertainty)
- [ ] Casual closers (trails off naturally)

**If core markers are missing, content will be AI-detectable.**
**If extended markers are missing, content won't match the target voice specifically.**

---

## Anti-Essay Patterns (CRITICAL FOR AUTHORSHIP MATCHING)

These patterns prevent generated content from sounding like "polished blog writing" instead of authentic conversational voice. The difference is critical: roasters can tell when content captures ideas but not execution style.

### Core Insight

> **Essay voice**: Has a thesis. Delivers considered opinions. Performs for an audience.
> **Conversational voice**: Has observations. Thinks out loud. Explains to one person.

Voice skills MUST teach the conversational patterns or generated content will sound like a different author entirely.

### 1. Staccato Rhythm (No Flow)

**Requirement**: Break sentences apart. One thought per paragraph. Stop frequently.

```markdown
WRONG (Essay flow):
"At first I thought the newest model would solve whatever problem I was stuck on. GPT-4 will fix my agent issues. Claude 3 will understand my prompts better."

RIGHT (Staccato):
"I thought new models would solve things.

They didn't.

GPT-4 wasn't it. Claude 3 wasn't either."
```

**Why**: Essay writers connect thoughts. Conversational writers stack them.

### 2. No Rhetorical Signposting

**Requirement**: Never announce your conclusions. Just state them.

```markdown
FORBIDDEN PHRASES:
- "Here's where I landed:"
- "That's the part nobody talks about."
- "The iteration history here matters."
- "You won't be surprised to hear that"

CORRECT:
- Just state the conclusion directly
- Let the reader follow without announcements
```

**Why**: Signposting is essay scaffolding. Conversation doesn't need it.

### 3. No Rule of Three

**Requirement**: Don't use tricolon (three parallel items) for rhetorical effect.

```markdown
WRONG:
"GPT-4 will fix my agent issues. Claude 3 will understand my prompts better. Gemini 1.5 will handle my long contexts."

RIGHT:
"I kept thinking the next model would fix things. It didn't."
```

**Why**: Rule of three is a writing technique. Conversation doesn't use it.

### 4. Concede-Then-Assert (Not Assert-Then-Hedge)

**Requirement**: Uncertainty comes FIRST, then your position.

```markdown
WRONG (Assert-then-hedge):
"The answer is: it doesn't matter much. Maybe that's just my experience."

RIGHT (Concede-then-assert):
"I'm not sure if this applies to everyone. For me, the answer is it doesn't matter much."
```

**Why**: Essay writers defend positions. Conversational writers explore them.

### 5. Flat Emotional Delivery

**Requirement**: Don't name emotions. Let them emerge from content.

```markdown
WRONG (Named emotion):
"What a waste of time that was."
"I hate this obsession with benchmarks."

RIGHT (Flat delivery):
"Total waste of time."
"Benchmarks don't measure anything useful."
```

**Why**: Theatrical emotion is performance. Flat delivery is authentic.

### 6. Sparse First-Person

**Requirement**: Let ideas lead sentences, not "I".

```markdown
WRONG (I-heavy):
"I ran Sonnet 3.5 against Opus 3. I compared the outputs. I found the differences were marginal."

RIGHT (Ideas lead):
"Running Sonnet against Opus. Comparing outputs. The differences? Marginal."
```

**Why**: Essay writers narrate their experience. Conversational writers report observations.

### 7. No Parenthetical Self-Deprecation

**Requirement**: Don't apologize for your tools or methods in parentheses.

```markdown
WRONG:
"(I built a janky spreadsheet for this, nothing pretty)"
"(current)" as a label

RIGHT:
"I built a spreadsheet. Nothing fancy."
Or just don't mention it at all.
```

**Why**: Parenthetical self-deprecation is a blogging trick to seem relatable. It feels performed.

### 8. Genuine Check-Ins (Not Rhetorical)

**Requirement**: Check-ins should verify understanding, not seek validation.

```markdown
WRONG (Seeking validation):
"Does that resonate with your experience?"

RIGHT (Verifying understanding):
"Does that help?"
"Does that track?"
"Am I making sense?"
```

**Why**: "Does that resonate?" is copywriting. "Does that help?" is conversation.

### 9. Mid-Sentence Pivots

**Requirement**: Show course-corrections inside sentences, not between them.

```markdown
WRONG (Clean self-correction):
"I thought the model was the problem. But then I realized it was architectural."

RIGHT (Mid-sentence pivot):
"I thought the model was-- actually no, it was architectural."
Or: "I'm not sure if-- my problems are solved doing it my way."
```

**Why**: Essay writers present polished revisions. Conversational writers think out loud.

### 10. Single-Sentence Paragraphs

**Requirement**: Most paragraphs should be 1-2 sentences. Never exceed 3.

```markdown
WRONG:
[4-6 sentence paragraph]

RIGHT:
"Short thought.

Another short thought.

A third, building on the second."
```

**Why**: Essay writers develop ideas in paragraphs. Conversational writers stack observations.

---

## Anti-Essay Checklist for Generated Skills

Before finalizing any voice skill, verify it teaches these patterns:

- [ ] Staccato rhythm (one thought per paragraph)
- [ ] No rhetorical signposting ("Here's where I landed")
- [ ] No rule of three constructions
- [ ] Concede-then-assert structure
- [ ] Flat emotional delivery (no "I hate", "What a waste")
- [ ] Sparse first-person (ideas lead, not "I")
- [ ] No parenthetical self-deprecation
- [ ] Genuine check-ins ("Does that help?")
- [ ] Mid-sentence pivots when self-correcting
- [ ] Single-sentence paragraphs as default

**If these are missing, content will sound like a different author than the samples.**

---

## Deterministic Infrastructure

This skill uses Python scripts for quantitative analysis. AI handles interpretation and skill generation.

### Scripts Used

| Script | Purpose | When Called |
|--------|---------|-------------|
| `voice_analyzer.py analyze` | Extract metrics from samples | Step 2 of calibration |
| `voice_analyzer.py compare` | Compare two voice profiles | Voice comparison mode |
| `voice_validator.py validate` | Validate generated output | Step 4 of calibration |
| `voice_validator.py check-banned` | Quick pattern check | During refinement |
| `voice_validator.py check-rhythm` | Check sentence rhythm only | Rhythm validation |

### Generated Files

After calibration, the voice skill directory contains:

```
skills/voice-{name}/
├── SKILL.md          # AI instructions (generated)
├── profile.json      # Machine-readable metrics (from analyzer)
├── config.json       # Validation settings
└── references/
    └── samples/      # Input samples (copied)
```

### Profile.json Structure

The analyzer outputs this structure:

```json
{
  "meta": {
    "samples_analyzed": 3,
    "total_words": 5000,
    "total_sentences": 250,
    "generated_at": "2025-01-15T10:30:00Z"
  },
  "sentence_metrics": {
    "length_distribution": {
      "short_3_10": 0.35,
      "medium_11_20": 0.45,
      "long_21_30": 0.15,
      "very_long_31_plus": 0.05
    },
    "average_length": 14.2,
    "variance": 6.8,
    "max_consecutive_similar": 2
  },
  "punctuation_metrics": {
    "comma_density": 0.045,
    "exclamation_rate": 0.02,
    "question_rate": 0.08,
    "em_dash_count": 0,
    "semicolon_rate": 0.01
  },
  "word_metrics": {
    "contraction_rate": 0.85,
    "first_person_rate": 0.025,
    "second_person_rate": 0.018,
    "function_word_signature": {"the": 0.045, "to": 0.032, "...": "..."}
  },
  "structure_metrics": {
    "avg_paragraph_sentences": 3.2,
    "fragment_rate": 0.12,
    "sentence_starters": {
      "pronoun": 0.28,
      "conjunction": 0.15,
      "article": 0.22,
      "adverb": 0.10,
      "other": 0.25
    }
  },
  "pattern_signatures": {
    "transition_words": ["but", "so", "and", "..."],
    "avoided_transitions": ["however", "moreover", "furthermore"],
    "opening_patterns": ["direct_statement", "pronoun_start"],
    "closing_patterns": ["statement", "callback"]
  }
}
```

---

## Multi-Voice Support

### Available Voices

Voices are stored in `skills/voice-{name}/`. List available voices with:

```bash
ls skills/voice-*/SKILL.md
```

### Creating a New Voice

```
/voice calibrate --name yourname --samples [file1] [file2] [file3]
```

This will:
1. Copy samples to `skills/voice-{name}/references/samples/`
2. Run `voice_analyzer.py` to extract metrics
3. Generate profile.json, config.json, and SKILL.md
4. Run `voice_validator.py` on test output
5. Show A/B comparison

### Updating an Existing Voice

```
/voice refine --name your-voice --samples [additional samples]
```

This merges new patterns with existing calibration.

---

## Instructions

### Mode 1: Full Calibration (ANALYZE-GENERATE-VALIDATE)

Use when: First calibration or major style update

#### Step 1: COLLECT Samples (EXTENSIVE COLLECTION REQUIRED)

```
CRITICAL: You need 50-100+ writing samples for authorship matching to work.

V7-V9 failed with 3-10 samples. V10 passed with 100+ samples.
The samples ARE the skill. Rules are secondary.

Sources to mine:
- Reddit comment history (most valuable - casual voice)
- HackerNews comments
- Forum posts
- Blog posts
- Email threads (if provided)
- Chat logs (if provided)

Required minimum:
- 50+ individual samples
- Mix of response lengths (short, medium, long)
- Mix of contexts (technical, casual, disagreement)

Save samples to: skills/voice-{name}/references/samples/
Organize by source:
  reddit-samples-YYYY-MM-DD.md
  hn-samples-YYYY-MM-DD.md
  blog-samples.md

Commands:
  mkdir -p skills/voice-{name}/references/samples

If user only provides 3-5 samples:
  STOP. Ask for more. Explain that authorship matching requires 50+ samples.
  Suggest: "Can you export your Reddit/HN comment history?"
```

#### Step 2: ANALYZE (Deterministic)

```bash
# Run voice analyzer on samples
python3 scripts/voice_analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json

# View text report for interpretation
python3 scripts/voice_analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --format text
```

The script extracts:
- Sentence length distribution (short/medium/long/very long percentages)
- Punctuation metrics (comma density, em-dash count, question rate)
- Word metrics (contraction rate, person usage, function word signature)
- Structure metrics (paragraph length, fragment rate, sentence starters)
- Pattern signatures (transitions used/avoided, opening/closing patterns)

#### Step 3: GENERATE (AI)

Using profile.json as foundation, generate:

1. **config.json** - Validation settings:
   - metric_tolerance (how strict)
   - required_checks (must pass)
   - voice_specific_patterns (custom rules)

2. **SKILL.md** - AI instructions with EXTENSIVE SAMPLE SECTIONS:

   **CRITICAL: The SKILL.md must be LONG (2000+ lines minimum).**

   Most of the file should be SAMPLES, not rules.

   Required sections (in order of importance):

   a. **Extensive Authentic Samples** (~400+ lines):
      - Samples organized by response length (10+ each for short/medium/long)
      - Samples organized by pattern (5+ each for mistakes/limits/disagreement/technical)
      - This section should be the LONGEST section in the skill

   b. **Phrase Fingerprints** (~50 lines):
      - 10+ distinctive phrase patterns with exact quotes
      - These are what roasters use to match authorship

   c. **Natural Typos** (~20 lines):
      - 5+ real typos from their writing
      - Authenticity markers

   d. **Voice Metrics** (~100 lines):
      - Quantitative targets from profile.json
      - Sentence length, contraction rate, etc.

   e. **Rules and Prohibitions** (~200 lines):
      - Anti-essay patterns
      - Human authenticity markers
      - Banned phrases

   f. **Generation Protocol** (~100 lines):
      - Pre/During/Post checklists

   **If SKILL.md is under 1500 lines, you don't have enough samples.**

See "Config.json Template" and "Voice Skill Output Structure" sections below.

#### Step 4: VALIDATE (Deterministic)

```bash
# Generate test content (AI), save to temp file
# Then validate against profile

python3 scripts/voice_validator.py validate \
  --content test-output.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text \
  --verbose
```

Exit codes:
- 0 = pass (score >= 70)
- 1 = fail (score < 70)
- 2 = execution error

If validation fails:
- Show violations (errors, warnings, info)
- Adjust SKILL.md guidance based on violations
- Regenerate test content and revalidate (max 3 iterations)

#### Step 5: OUTPUT

Display calibration summary:

```
===============================================================
 VOICE CALIBRATION COMPLETE
===============================================================

 Voice: {name}
 Samples: {N} files analyzed

 Generated Files:
   [check] skills/voice-{name}/profile.json    (metrics)
   [check] skills/voice-{name}/config.json     (settings)
   [check] skills/voice-{name}/SKILL.md        (AI instructions)
   [check] skills/voice-{name}/references/samples/  (copied samples)

 Validation: PASSED (score: {score}/100)

 Key Metrics (from profile.json):
   Avg sentence length: {X} words
   Contraction rate: {X}%
   Em-dash usage: {em_dash_count} (target: 0 for most voices)
   Short sentences: {X}%
   Fragment rate: {X}%

===============================================================
```

---

### Mode 2: Refinement

Use when: Adjusting specific parameters based on feedback

```
Supported adjustments:
- "Make sentences shorter" -> Reduce avg length target by 20%
- "Use fewer lists" -> Set list_usage to "rare"
- "More direct openings" -> Increase direct_statement percentage
- "Less formal" -> Adjust formality marker

Process:
1. Load existing profile.json
2. Apply adjustment to relevant metric
3. Update config.json thresholds if needed
4. Regenerate SKILL.md sections
5. Validate with check-banned for quick feedback

Quick validation:
python3 scripts/voice_validator.py check-banned \
  --content test-output.md \
  --voice {name} \
  --format text
```

---

### Mode 3: A/B Comparison Only

Use when: Testing calibration on new topic

```
Process:
1. Read existing profile.json
2. Take topic from user
3. Generate DEFAULT output (generic Claude style)
4. Generate CALIBRATED output (apply SKILL.md)
5. Validate CALIBRATED output:
   python3 scripts/voice_validator.py validate \
     --content calibrated-output.md \
     --profile skills/voice-{name}/profile.json \
     --format text
6. Highlight specific differences
```

---

### Mode 4: Voice Comparison

Use when: Comparing two calibrated voices

```bash
python3 scripts/voice_analyzer.py compare \
  --profile1 skills/voice-profile-a/profile.json \
  --profile2 skills/voice-profile-b/profile.json \
  --format text
```

Shows differences in:
- Sentence metrics (average length, variance, distribution)
- Punctuation metrics (comma density, em-dash usage)
- Word metrics (contraction rate, person usage)
- Pattern signatures (unique transitions, opening/closing patterns)

---

## Config.json Template

```json
{
  "name": "{Voice Name}",
  "version": "2.0.0",
  "description": "{Voice description}",
  "modes": ["chat", "blog", "technical"],
  "validation": {
    "strict_banned_patterns": true,
    "em_dash_forbidden": true,
    "metric_tolerance": 0.20,
    "required_checks": ["banned_phrases", "punctuation", "rhythm"],
    "optional_checks": ["metrics", "sentence_starters"]
  },
  "thresholds": {
    "pass_score": 70,
    "error_max": 0,
    "warning_max": 5
  },
  "voice_specific_patterns": [
    {
      "name": "example_pattern",
      "type": "forbidden",
      "patterns": ["pattern1", "pattern2"],
      "severity": "warning",
      "message": "This pattern doesn't match the voice"
    }
  ],
  "metrics": {
    "contraction_rate": 0.85,
    "comma_density": 0.045,
    "avg_sentence_length": 14.2
  }
}
```

---

## Voice Skill Output Structure (V6 Complete Format)

When calibration completes, generate a voice skill following this COMPLETE structure. This template incorporates all prompt engineering best practices and must be followed exactly.

### CRITICAL GENERATION REQUIREMENTS

Before generating any voice skill, ensure ALL of the following:

1. **Quantitative Targets are EXPLICIT** - Include exact percentages for:
   - Sentence length distribution (short/medium/long/very long)
   - Average sentence length (target word count)
   - Pronoun starter percentage (often 20-30%)
   - Contraction rate

2. **Probability Dampening is APPLIED** - Use adverbs in trait descriptions:
   - "**subtly** skeptical" not "skeptical"
   - "**slightly** informal" not "informal"
   - "**generally** direct" not "direct"

3. **Context Isolation is APPLIED** - Use XML tags:
   - `<context type="static-instructions">` for core directives
   - `<context type="safety-guardrails">` for prohibitions

4. **Attention Anchoring is APPLIED** - Bold negative constraints:
   - "**NEVER use**", "**You must strictly avoid**"

5. **Contrastive Examples are COMPLETE** - Include:
   - Table comparing voice aspects
   - Full paragraph-level comparison (Generic AI vs This Voice)

6. **Generation Protocol has CHECKLIST** - Pre/During/Post phases with checkbox list

7. **Quick Reference Card at END** - Scannable summary of voice DNA

---

### OUTPUT TEMPLATE (Copy and Fill)

```markdown
---
name: voice-{name}
description: {Name}'s personal writing voice (v6 - complete format with quantitative targets)
version: 6.0.0
---

# Voice: {Name} (V6 - Complete Format)

This skill uses sample-first architecture with explicit quantitative targets.
Samples demonstrate HOW the voice sounds. Metrics ensure MEASURABLE consistency.

**Architecture**: Reference injection -> Pre-generation calibration -> Chunked generation -> Validation

---

## Identity (Who)

{Name} is a [role description] who communicates with **subtly** [trait1] and **slightly** [trait2]. The voice is [characteristic1], [characteristic2], and grounded in [grounding].

**Core traits:**
- **Slightly** [trait with adverb modifier]
- **Generally** [trait with adverb modifier]
- [Observable behavior pattern]
- [Observable behavior pattern]

---

## Core Directives (What)

<context type="static-instructions">

### Primary Objectives

1. **[Directive 1]** - [Brief explanation]
2. **[Directive 2]** - [Brief explanation]
3. **[Directive 3]** - [Brief explanation]
4. **[Directive 4]** - [Brief explanation]

### Pre-Generation Thinking (Chain-of-Thought Required)

**Before writing any response, think step-by-step:**

1. What is my actual position on this topic?
2. What personal experience or process informs this position?
3. What might the reader misunderstand that I should clarify?
4. What valid counterpoints exist that I should acknowledge?
5. [Voice-specific thinking prompt]

Only after answering these questions internally should generation begin.

</context>

---

## Style & Tone (How)

### Phase 1: Voice Grounding (Read Before Writing)

Read these actual samples to internalize the voice. The goal is pattern absorption, not rule following.

**CRITICAL: This section must be EXTENSIVE. 50-100+ samples organized by category.**

The difference between V7-V9 (failed authorship matching) and V10 (passed 5/5) was the quantity and organization of samples. Rules tell AI what to do. Samples show AI what the voice actually looks like.

---

### Extensive Authentic Samples (REQUIRED - Minimum 50)

#### Response Length Distribution

**Very short (1 sentence, ~25% of responses):**
```
[Include 10+ real very short responses]
```

**Short (2-3 sentences, ~35% of responses):**
```
[Include 15+ real short responses]
```

**Medium (4-6 sentences, ~25% of responses):**
```
[Include 10+ real medium responses]
```

**Long (paragraph+, ~15% of responses):**
```
[Include 5+ real long responses]
```

#### Pattern-Organized Samples (CRITICAL FOR AUTHORSHIP MATCHING)

**Admitting Mistakes (REQUIRED PATTERN):**
```
[Include 5+ examples of how this person admits errors]
```

**Acknowledging Limits (REQUIRED PATTERN):**
```
[Include 5+ examples of how this person says "I don't know"]
```

**Incomplete Work Admissions (REQUIRED PATTERN):**
```
[Include 5+ examples of "haven't finished", "on my list for months"]
```

**Respectful Disagreement (REQUIRED PATTERN):**
```
[Include 5+ examples showing how they disagree without accusation]
```

**Technical Expertise Delivered Casually:**
```
[Include 5+ examples of technical explanation style]
```

**Casual Closers:**
```
[Include 5+ examples: "but we'll see", "does that help?", etc.]
```

**Strong Opinions (Delivered Directly):**
```
[Include 5+ examples of unhedged opinions]
```

**Sarcasm/Wit (if present):**
```
[Include examples if this is part of the voice]
```

#### Phrase Fingerprints (CRITICAL)

These exact phrase patterns appearing in both samples and generated content are what roasters use to confirm authorship.

| Fingerprint | Example from Samples |
|-------------|---------------------|
| [Unique phrase 1] | "[Exact quote]" |
| [Unique phrase 2] | "[Exact quote]" |
| [Unique phrase 3] | "[Exact quote]" |
[Include 10+ distinctive phrase patterns]

#### Natural Typos/Errors (AUTHENTICITY MARKERS)

Real typos from the person's writing. Include occasional typos to match:
- "[typo1]" (correct: [word])
- "[typo2]" (correct: [word])
[Include 5+ real typos from their writing]

---

**If you don't have 50+ samples organized this way, the generated skill will fail authorship matching. Go get more samples before proceeding.**

---

### Phase 2: Voice Metrics (QUANTITATIVE TARGETS)

These metrics are extracted from [N] sentences across [N] writing samples.
**These are TARGETS to hit, not just observations.**

#### Sentence Architecture (MUST MATCH)

| Metric | Target | Tolerance | Notes |
|--------|--------|-----------|-------|
| Average length | **{X} words** | ±2 words | Primary rhythm indicator |
| Short (3-10 words) | **{X}%** | ±5% | For emphasis and pacing |
| Medium (11-20 words) | **{X}%** | ±5% | For explanation |
| Long (21-30 words) | **{X}%** | ±3% | For complex ideas |
| Very long (31+ words) | **{X}%** | ±2% | Rare, for building arguments |
| Fragment rate | {X}% | ±3% | Intentional fragments for emphasis |

#### Sentence Starters (CRITICAL DIFFERENTIATOR)

| Type | Target | Examples |
|------|--------|----------|
| **Pronoun** | **{X}%** | "I think", "It works", "That's what" |
| Other | {X}% | Topic-driven starts |
| Conjunction | {X}% | "But the reality", "And now" |
| Article | {X}% | "The problem", "A skill" |
| Adverb | {X}% | Occasionally, for emphasis |

**Key insight**: [Explain what the pronoun percentage indicates about voice]

#### Punctuation Signature

| Element | Target | Rule |
|---------|--------|------|
| Comma density | {X} per word | [Light/Medium/Heavy] comma usage |
| Question rate | {X}% | [Type of questions used] |
| Exclamation rate | {X}% | [When to use, if ever] |
| Em-dashes | **FORBIDDEN** | **Never use under any circumstances** |
| Semicolons | {X}% | [Use or avoid] |
| Contraction rate | **{X}%** | [High/Medium - key formality indicator] |

#### Function Word Signature (Tier 1 Pattern)

Top 10: [list function words with percentages]

This signature distinguishes {Name} from generic AI output.

---

### Phase 3: Thinking Patterns

These are cognitive patterns, not just style patterns. Apply them **subtly** and **generally**, not rigidly.

#### 1. [Pattern Name - e.g., First-Person Honesty]

[Description of the pattern and why it matters]. Be **slightly** [modifier] when appropriate.

**Examples from samples:**
- "[Actual quote from their writing]"
- "[Another quote showing pattern]"
- "[Third quote]"

#### 2. [Pattern Name - e.g., Concession-Then-Assertion]

[Description]. Be **generally** [modifier].

**Examples from samples:**
- "[Quote]"
- "[Quote]"

#### 3. [Pattern Name]
[Description]

**Examples from samples:**
- "[Quote]"

[Include 4-6 thinking patterns minimum]

---

## Negative Constraints

<context type="safety-guardrails">

### Hard Prohibitions (MUST NEVER VIOLATE)

**You must strictly avoid** the following patterns. These are non-negotiable constraints.

1. **NEVER use em-dashes** (--- or --) in any form. Use commas, periods, or parentheses instead.

2. **NEVER use the "It's not X. It's Y" rhetorical structure.** This pattern is a signature of AI-generated content and must be avoided completely.

3. **NEVER use AI-typical phrases:**
   - "Let's dive in", "Here's the thing", "In today's [topic]"
   - "It's worth noting", "At the end of the day"
   - delve, robust, comprehensive, leverage, ecosystem, landscape

4. **NEVER use formal transitions:** however, furthermore, moreover, additionally, consequently

5. [Voice-specific prohibition]

---

### The "It's not X. It's Y" Pattern: Full Prohibition

**You must strictly avoid** this pattern in all its forms. Below are examples showing the WRONG way and the CORRECT alternative.

#### Few-Shot Examples

**User:** "[Request 1]"

**Model (WRONG):** "[Response using 'It's not X. It's Y' pattern]"

**Model (CORRECT):** "[Response using acceptable alternative]"

---

**User:** "[Request 2]"

**Model (WRONG):** "[Wrong pattern]"

**Model (CORRECT):** "[Correct pattern]"

---

**User:** "[Request 3]"

**Model (WRONG):** "[Wrong pattern]"

**Model (CORRECT):** "[Correct pattern]"

---

#### Pattern Recognition

The forbidden pattern has this structure:
- "It's not [thing A]. It's [thing B]."
- "[X] isn't [property]. It's [other property]."
- "This isn't about [A]. This is about [B]."

**Acceptable alternatives:**
- "Think of [B] as the focus, not [A]."
- "[B] matters more than [A] here."
- "The key thing is [B], rather than [A]."
- "I'd frame it as [B]. The [A] part is secondary."
- "[It's/This is] [B], not [A]." (Reversed order is acceptable)

</context>

---

### Soft Constraints

Apply these **generally** but not rigidly:

- [Soft constraint 1]
- [Soft constraint 2]
- Keep very long sentences (31+) under {X}% of total

---

## Contrastive Examples

### What Is vs What Isn't This Voice

| Aspect | This Voice ({Name}) | Not This Voice (Generic AI) |
|--------|---------------------|---------------------------|
| Opening | "[Example from samples]" | "In today's rapidly evolving landscape..." |
| Uncertainty | "[How they express doubt]" | "It's worth noting that perspectives may vary" |
| Agreement | "[How they agree]" | "I absolutely agree with your insightful point" |
| Disagreement | "[How they disagree]" | "While there are valid concerns, I would respectfully suggest..." |
| Conclusion | "[How they end]" | "In conclusion, we have explored..." |
| Technical | "[Technical explanation style]" | "This represents a robust paradigm for..." |

### Full Contrastive Example (Paragraph Level)

**Generic AI:**
> In today's rapidly evolving technological landscape, the concept of [topic] has become increasingly important. This article will delve into the nuances of how modern systems handle [topic], exploring the various approaches and their implications.

**{Name} Voice:**
> [Actual paragraph from samples showing the same topic handled in their voice]

---

## Human Authenticity Requirements (MANDATORY)

These patterns MUST be included or content will be flagged as AI-generated.

### Required Authenticity Markers

1. **Incomplete Work Admission** - At least one admission of imperfection:
   - "I haven't yet built X"
   - "it's not pretty but it works"
   - "that's a pretty inelegant solution"

2. **Tool/Process Tangent** - Show your actual workflow:
   - "I built a custom tool for that (called X)"
   - "I used my [tool] command to grab..."

3. **Parenthetical Aside** - Assume shared context with reader:
   - "(that [famous person])"
   - "(so I hope it continues to work)"
   - "You won't be surprised to hear..."

4. **Evolution Narrative** - Show iteration, not just final solution:
   - "I've made several past attempts"
   - "a late refactoring, the initial version used..."

5. **Unhedged Opinion** - Assert directly, don't hedge:
   - WRONG: "This raises important concerns"
   - RIGHT: "I don't like this at all."

6. **Mid-Thought Discovery** - Learn while writing:
   - "Turns out X knows the trick where..."
   - "I ended up using that trick in X itself!"

7. **Visible Self-Correction** - Change direction mid-thought:
   - "At first I thought... but then I realized"
   - "or rather, it was my willingness to..."

---

## Generation Protocol

### Pre-Generation (Chain-of-Thought Required)

**Before writing, think step-by-step and answer these questions internally:**

1. What is my actual position on this?
2. What would I say if asked about this in a forum?
3. What process did I go through to form this opinion?
4. What valid counterpoints should I acknowledge?
5. What imperfection or gap can I honestly admit?
6. What tangent about my process might be interesting?

### During Generation

1. **Start with your position**, not background
2. **Use first-person** when stating opinions ({X}% pronoun starts target)
3. **Target {X} word average** sentence length
4. **Include {X}% short sentences** (3-10 words) for rhythm
5. **Include at least one incomplete/imperfect admission**
6. **Include at least one parenthetical aside**
7. **Allow one tangent that shows your process**
8. Write in a **subtly** [trait] tone
9. Be **slightly** [trait] but [qualifier]

### Post-Generation Validation

**You must verify** all of these before finalizing:

**Anti-AI Patterns:**
- [ ] No em-dashes anywhere
- [ ] No "It's not X. It's Y" patterns (check carefully)
- [ ] No AI-typical phrases or formal transitions
- [ ] No excessive hedging ("It's worth noting", "One might argue")

**Voice Metrics:**
- [ ] First-person used for opinions
- [ ] Sentence length distribution approximately matches targets
- [ ] At least {X}% of sentences start with pronouns
- [ ] Contraction rate matches target ({X}%)

**Authenticity Markers (REQUIRED):**
- [ ] At least one incomplete work admission
- [ ] At least one parenthetical aside
- [ ] At least one unhedged strong opinion
- [ ] At least one mid-thought discovery or self-correction
- [ ] [Voice-specific validation item]

---

## Quick Reference Card

**Voice DNA:**
- [Key trait 1]
- [Key trait 2]
- [Key trait 3]
- [Key trait 4]
- **Subtly** [adverb-modified trait]
- **Generally** [adverb-modified trait]

**Sentence Profile (TARGETS):**
- {X}% short, {X}% medium, {X}% long
- **{X}%** start with pronouns
- **{X}%** contractions
- {X}% questions
- Average: **{X} words**

**Forbidden (Hard Constraints):**
- **Em-dashes** (never, under any circumstances)
- **"It's not X. It's Y"** (use reversed order or alternative phrasing)
- **Formal transitions** (however, furthermore, moreover)
- **AI opening phrases** (let's dive in, here's the thing)
```

---

### VALIDATION CHECKLIST FOR GENERATED SKILL

Before finalizing any generated voice skill, verify:

**SAMPLE COLLECTION (CRITICAL - This is what makes authorship matching work):**
- [ ] **50+ real samples included** (not 5-7, not 10, FIFTY MINIMUM)
- [ ] Samples organized by response length (very short / short / medium / long)
- [ ] Samples organized by pattern type (mistakes / limits / disagreement / technical)
- [ ] **10+ phrase fingerprints documented** with exact quotes
- [ ] **5+ real typos documented** as authenticity markers
- [ ] Samples show EXECUTION STYLE, not just ideas

**QUANTITATIVE TARGETS:**
- [ ] All metrics have explicit targets with tolerances
- [ ] Pronoun starter percentage is highlighted as CRITICAL DIFFERENTIATOR
- [ ] Average sentence length target is specified

**PROMPT ENGINEERING:**
- [ ] Probability dampening adverbs used throughout (subtly, slightly, generally)
- [ ] XML context tags used for static instructions and safety guardrails
- [ ] Attention anchoring (bold) used for all negative constraints
- [ ] "It's not X. It's Y" prohibition has 3+ few-shot examples

**STRUCTURE:**
- [ ] Contrastive table covers 6+ aspects
- [ ] Full paragraph-level contrastive example included
- [ ] Generation Protocol has Pre/During/Post phases
- [ ] Post-Generation has checkbox validation list
- [ ] Quick Reference Card at end summarizes voice DNA and targets

**AUTHORSHIP MATCHING REQUIREMENT:**
The generated skill MUST pass this test:
1. Generate test content using the skill
2. Have 5 roasters compare it to original samples
3. At least 4/5 roasters should say "SAME AUTHOR"
4. If not, add more samples and retry

See your own voice skill's SKILL.md for reference implementations that pass authorship matching.

---

## Error Handling

### Error: "Insufficient samples"

Minimum 3 samples required. If fewer provided:
1. List available posts in content/posts/
2. Suggest using batch mode to analyze all
3. Request additional samples

### Error: "Samples too similar"

All samples from same time period or topic:
1. Note potential bias in profile
2. Recommend diverse sample selection
3. Proceed with warning in profile

### Error: "No existing profile for comparison"

When A/B mode requested without prior calibration:
1. Run full calibration first
2. Or use DEFAULT voice as baseline

### Error: "Validation failed after 3 iterations"

When content repeatedly fails validation:
1. Check if profile metrics are achievable
2. Review banned patterns for false positives
3. Consider relaxing metric_tolerance in config.json
4. Manual review of SKILL.md instructions

### Error: "Script execution failed"

```
python3 scripts/voice_analyzer.py --help
python3 scripts/voice_validator.py --help
```

Check:
1. Python 3 available
2. Scripts executable
3. File paths valid

---

## Reference Files

- `scripts/voice_analyzer.py`: Deterministic metrics extraction
- `scripts/voice_validator.py`: Content validation against profile
- `scripts/data/banned-patterns.json`: Shared banned pattern database

## Reference Implementations

Create your own voice skill using the voice-calibrator workflow. A complete voice skill includes:
- A SKILL.md with voice patterns, anti-patterns, and validation rules
- A profile.json with statistical voice metrics
- Sample files organized by writing context (forums, blogs, comments)

**Study `pipelines/voice-calibrator/SKILL.md` to understand the calibration process.**

---

## Quick Reference

| Command | Action |
|---------|--------|
| `/voice calibrate --name [name] --samples [files]` | Create new voice with deterministic analysis |
| `/voice refine --name [name] --samples [files]` | Update voice with additional samples |
| `/voice validate --name [name] --content [file]` | Validate content against voice profile |
| `/voice compare --name [name] [topic]` | A/B comparison on topic |
| `/voice compare-voices --voice1 [name] --voice2 [name]` | Compare two voice profiles |
| `/voice show --name [name]` | Display voice profile.json |
| `/voice list` | List all available voices |
| `/voice check --name [name] --content [file]` | Quick banned pattern check |

---

## API Usage (Web App Integration)

The scripts can be imported as modules:

```python
# Import analyzers
from voice_analyzer import analyze_samples, compare_profiles
from voice_validator import validate_content, check_banned_patterns

# Analyze samples -> profile
profile = analyze_samples(["sample1.md", "sample2.md", "sample3.md"])
print(profile.to_dict())

# Compare two profiles
comparison = compare_profiles(profile1, profile2)
print(comparison)

# Validate content against profile
result = validate_content(
    content=content_text,
    profile=profile_dict,
    voice="your-voice"
)
print(f"Pass: {result.passed}, Score: {result.score}")
for v in result.violations:
    print(f"  [{v.severity}] {v.message}")

# Quick banned check only
from voice_validator import load_banned_patterns, check_banned_patterns
banned = load_banned_patterns()
violations = check_banned_patterns(content_text, banned, voice="your-voice")
```

Future: `scripts/voice_generator.py` will generate CLAUDE.md files for external users who want voice profiles without Claude Code access.

---

## Integration with Content Creation

After calibration, use the voice profile when:

1. **Creating new posts**: Load SKILL.md before writing
2. **Editing drafts**: Validate against profile.json
3. **Review mode**: Compare draft patterns to profile metrics

Validation command for drafts:

```bash
python3 scripts/voice_validator.py validate \
  --content draft.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text \
  --verbose
```

The profile is NOT automatically applied. Invoke explicitly:
- "Write [topic] using my voice profile"
- "Review this draft against my voice profile"
- "Validate this content against the voice"

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations during calibration
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks for calibration output
