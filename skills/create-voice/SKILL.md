---
name: create-voice
description: |
  Create a new voice profile from writing samples. 7-phase pipeline:
  Collect, Extract, Pattern, Rule, Generate, Validate, Iterate.
  Wabi-sabi (natural imperfections as features) is the core principle.
  Use when creating a new voice, starting voice calibration, or
  building a voice profile from scratch. Use for "create voice",
  "new voice", "build voice", "voice from samples", "calibrate voice".
  Do NOT use for generating content in an existing voice (use
  voice-orchestrator), editing content (use anti-ai-editor), or
  comparing voices (use voice-calibrator compare mode).
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
    - voice-orchestrator
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

Do NOT proceed past this step without 50+ samples, because the system tried with 3-10 and FAILED. 50+ is where it starts working. LLMs are pattern matchers -- rules tell AI what to do but samples show AI what the voice looks like. V7-V9 had correct rules but failed authorship matching (0/5 roasters). V10 passed 5/5 because it had 100+ categorized samples.

#### Where to Find Samples

| Source | What to Look For | File Naming |
|--------|-----------------|-------------|
| Reddit history | Comments, posts, replies | `reddit-samples-YYYY-MM-DD.md` |
| Hacker News | Comments, Ask HN answers | `hn-samples-YYYY-MM-DD.md` |
| Blog posts | Published articles | `blog-samples.md` |
| Forum posts | Any discussion forum | `forum-samples-YYYY-MM-DD.md` |
| Emails | Professional and casual | `email-samples.md` |
| Chat logs | Slack, Discord, iMessage | `chat-samples.md` |
| Social media | Twitter/X threads | `social-samples.md` |

#### Sample Quality Guidelines

- **Mix of lengths**: Very short (1 sentence), short (2-3 sentences), medium (paragraph), long (multi-paragraph). The distribution matters because most people write short responses most of the time.
- **Mix of contexts**: Technical, casual, disagreement, agreement, teaching, joking, emotional. Different contexts reveal different facets of voice.
- **Mix of topics**: Not all about the same subject. Topic diversity reveals stable voice patterns vs topic-specific patterns.
- **DO NOT clean up samples**: Typos, run-on sentences, fragments, loose punctuation ARE the voice, because cleaning destroys authenticity markers. This is the wabi-sabi principle (natural imperfections are features, not bugs) in action at the very first step.
- **DO NOT cherry-pick**: Include mediocre posts alongside great ones, because the mundane reveals default patterns.

#### Directory Setup

```bash
mkdir -p skills/voice-{name}/references/samples/
```

Place all sample files in `skills/voice-{name}/references/samples/`. Each file should contain multiple samples, separated by `---` or clear headers.

#### Sample File Format

Each sample file should preserve the original writing exactly:

```markdown
# Reddit Samples - 2025-12-30

## r/subreddit - Thread Title
[Exact text of comment, typos and all]

---

## r/subreddit - Another Thread
[Exact text]

---
```

**GATE**: Count the samples. If fewer than 50 distinct writing samples exist across all files, STOP. Tell the user how many more are needed and where to find them. Do NOT proceed.

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

#### Phrase Fingerprints (CRITICAL)

Read through ALL samples and identify 10+ distinctive phrases that recur. These are what authorship-matching roasters use to confirm identity.

Look for:
- **Signature openers**: How do they start responses? ("I think the issue is...", "So basically...", "Here's what I've found...")
- **Signature closers**: How do they end? ("but we'll see", "does that help?", "anyway, that's my take")
- **Filler phrases**: Verbal tics that appear across contexts ("For what it's worth", "to be fair", "honestly")
- **Hedging patterns**: How they express uncertainty ("probably", "I suspect", "my guess is")
- **Emphasis patterns**: How they stress a point ("the key thing is", "the part people miss")

Document each fingerprint with 2-3 exact quotes from the samples showing it in context.

#### Thinking Patterns

How does this person reason? This is deeper than style; it's cognitive architecture.

Common patterns to check for:
- **Concede-then-assert**: "That's fair, but..." (acknowledges opposing view, then states own position)
- **Hypothesis-experiment**: "My theory is... I tried... and found..."
- **Systems framing**: "The way this works is..." (explains mechanisms, not just opinions)
- **Experience-based**: "In my experience..." (grounds claims in personal observation)
- **Question-led**: "The question is..." (frames issues as questions to investigate)
- **Analogy-driven**: Uses metaphors and comparisons from specific domains

#### Response Length Distribution

From the samples, estimate what percentage of responses fall into each bucket:
- Very short (1 sentence): ____%
- Short (2-3 sentences): ____%
- Medium (4-6 sentences): ____%
- Long (paragraph+): ____%

This distribution is critical because most people write short responses most of the time, and AI tends to generate medium-to-long responses by default.

#### Natural Typos (Authenticity Markers)

Scan samples for 5+ real typos. Document them with the correct spelling. These become wabi-sabi markers that signal authenticity. Do NOT treat these as errors to correct, because those "imperfections" ARE the voice -- perfection is an AI tell.

Examples of what to look for:
- Missing apostrophes ("dont" instead of "don't")
- Common word swaps ("there" for "their")
- Dropped letters ("probabl" for "probably")
- Double-typed characters ("tthe")
- Missing spaces after punctuation ("works.But")

#### Wabi-Sabi Markers

Identify which "imperfections" ARE the voice. These are not bugs to fix; they are features to preserve.

- Run-on sentences: Does this person chain clauses with commas?
- Fragments: Do they use sentence fragments for emphasis?
- Loose punctuation: Is comma usage inconsistent? Is that part of the texture?
- Self-corrections: Do they change direction mid-sentence? ("Well, actually..." or "I mean,")
- Tangential asides: Do they go on tangents? (Parenthetical digressions?)

#### Linguistic Architectures

Beyond sentence-level patterns, identify the **structural moves** that operate across sentences and paragraphs. These are what AI erases most aggressively -- the model defaults to claim -> evidence -> hedged conclusion regardless of the writer's actual architecture.

Analyze ALL samples (not just a few) for each dimension:

**Argument Architecture** -- How does the writer build a case?
- **Direction**: Inductive (examples -> conclusion) vs deductive (claim -> evidence) vs mixed? Where does the main claim appear relative to supporting evidence?
- **Escalation**: Do stakes increase through the piece? Narrow -> broad? Low -> high severity?
- **Ending reframe**: Does the ending restate the opening, or transform it into something new?

Document with exact quotes: "In {N} of {M} samples, the writer builds inductively -- evidence first, conclusion last. Example from sample X: [quote showing the build]"

**Concession Architecture** -- How does the writer handle "yes, but"?
- **Structure**: Short admission -> pivot? Long qualification -> reversal? Never concedes?
- **Pivot markers**: Which words signal the turn? ("but", "though", "the thing is", "and yet", "that said")
- **Position**: Where do concessions appear? Opening? Mid-argument? Never at the end?

Document with exact quotes: "Concessions follow a [short admission -> blunt pivot] pattern. Example: [quote showing concession shape]"

**Analogy Architecture** -- Where do metaphors and references come from?
- **Source domains**: Which fields? (cooking, construction, sports, warfare, nature, machinery, music, software, etc.)
- **Deployment**: Are analogies used to open? To explain mid-section? To close with a memorable image?
- **Density**: Every post? Rarely? Only for technical concepts?

Document with exact quotes: "Analogies cluster around {domains}. Example: [quote showing analogy from that domain]"

**Bookend Architecture** -- How do pieces open and close?
- **Opening moves**: Question? Declarative claim? Anecdote? Provocation? Scene-setting?
- **Closing moves**: Reframe? Fragment punch? Circle back to opening? Call to action? Open question?
- **Symmetry**: Does the closing echo or answer the opening?

Document with exact quotes: "Opens with [pattern] in {N}/{M} samples. Closes with [pattern]. Opening and closing are [symmetric/independent]."

**Note**: Not all writers exhibit all 4 architectures. Tweet-only writers may not have argument or bookend architecture. The gate requires 2 of 4, not 4 of 4.

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

#### What This Voice IS (Positive Identity)

Write 4-6 core traits with examples from the samples. Use probability dampening to avoid caricature:

- **"subtly" skeptical** not "skeptical" -- dampens the trait so it appears naturally, not performatively
- **"generally" conversational** not "conversational" -- allows for variation
- **"slightly" self-deprecating** not "self-deprecating" -- prevents over-application

For each trait, include 2-3 exact quotes from samples that demonstrate it.

Use dampening adverbs because without them the model cranks traits to 100%. "Skeptical" becomes every-sentence-is-a-challenge. "Conversational" becomes aggressively casual.

#### What This Voice IS NOT (Contrastive Identity)

Build a contrastive table showing THIS voice vs Generic AI for at least 6 aspects:

| Aspect | This Voice | Generic AI |
|--------|-----------|------------|
| Opening | [Example from samples] | "In today's rapidly evolving landscape..." |
| Uncertainty | [How they express doubt] | "It's worth noting that perspectives may vary" |
| Agreement | [How they agree] | "I absolutely agree with your insightful point" |
| Disagreement | [How they disagree] | "While there are valid concerns, I would respectfully suggest..." |
| Conclusion | [How they end] | "In conclusion, we have explored..." |
| Technical | [Technical style] | "This represents a robust paradigm for..." |

#### Hard Prohibitions

Identify patterns this voice NEVER uses. Apply attention anchoring (**bold**) to all negative constraints because the model pays more attention to bolded text:

Common prohibitions to evaluate:
- **Em-dashes**: Does this person ever use them? If not, FORBIDDEN
- **Formal transitions**: "However", "Furthermore", "Moreover", "Additionally", "Consequently"
- **AI-typical phrases**: "Let's dive in", "Here's the thing", "delve", "robust", "leverage", "ecosystem"
- **The "It's not X. It's Y" pattern**: Signature AI structure. Almost always prohibited
- **Excessive hedging**: "It's worth noting", "One might argue", "At the end of the day"

For each prohibition, explain WHY it's prohibited for this specific voice (not just "because it's AI-sounding").

#### Wabi-Sabi Rules

Which "errors" MUST be preserved? This is the inversion of typical quality rules. Only include imperfections actually observed in the samples, because manufactured imperfections feel forced and are as detectable as forced perfection:

- If they write run-on sentences: "Allow comma-chain sentences up to {N} words when expressing enthusiasm or building arguments"
- If they use fragments: "Target {X}% fragment rate for emphasis and pacing"
- If punctuation is loose: "Do not standardize comma usage; match the inconsistent pattern from samples"
- If they self-correct: "Include at least one visible direction change per long-form response"

#### Anti-Essay Patterns

Most voices are NOT essay-writers. Identify the structural anti-patterns:

- Staccato rhythm? (Short sentences dominating)
- No signposting? (No "First... Second... Third...")
- Single-sentence paragraphs? (Common in chat/forum)
- No introduction/conclusion structure? (Just starts talking)
- Abrupt endings? (No wrap-up, just stops)

#### Architectural Patterns

Translate the linguistic architectures discovered in Step 3 into actionable rules for the voice skill. These go in a dedicated `## Architectural Patterns` section in the generated SKILL.md, between the identity rules and banned patterns.

For each documented architecture, write a rule:

```markdown
## Architectural Patterns

### Argument Flow
[Inductive/Deductive/Mixed] — [one-sentence description]
Build arguments by [specific instruction]. The main claim should appear [position].
Example from samples: "[exact quote showing the pattern]"

### Concessions
Structure: [short admission → pivot / long qualification → reversal / never concedes]
Pivot markers: [list of words this voice uses]
Example: "[exact quote]"

### Analogy Domains
Primary: [domain1, domain2]
Deployment: [where analogies appear — openers? mid-section? closers?]
Density: [frequency]
**NEVER draw analogies from**: [domains this voice avoids]
Example: "[exact quote]"

### Bookends
Opening move: [pattern]
Closing move: [pattern]
Symmetry: [yes/no/sometimes]
Example opening: "[quote]"
Example closing: "[quote]"
```

Omit any architecture that wasn't documented in Step 3. A missing section is better than a fabricated one.

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

NEVER modify voice_analyzer.py, voice_validator.py, banned-patterns.json, voice-calibrator, voice-orchestrator, or any existing skill/script, because the existing tools work. This skill only creates new files in `skills/voice-{name}/`.

Before generating, show users any existing voice implementation in `skills/voice-*/` as a concrete example of "done", because reference implementations ground expectations.

Follow the template structure from voice-calibrator (lines 1063-1512 of `pipelines/voice-calibrator/SKILL.md`), because it was refined over 10 iterations and embeds prompt engineering best practices (attention anchoring, probability dampening, XML context tags, few-shot examples for prohibitions). Deviating from the template means losing those lessons.

#### Files to Create

1. **`skills/voice-{name}/SKILL.md`** -- The voice skill itself (2000+ lines)
2. **`skills/voice-{name}/config.json`** -- Validation configuration
3. **`skills/voice-{name}/profile.json`** -- Already created in Step 2

#### SKILL.md Structure

The sections, in order of importance by line count. Target 400+ lines of samples and ~200 lines of rules, because V7-V9 had 500+ lines of rules with 100 lines of samples and failed authorship matching -- V10 inverted that ratio and passed 5/5:

| Section | Target Lines | Why This Size |
|---------|-------------|---------------|
| Extensive Authentic Samples | 400+ | THIS IS WHAT MAKES AUTHORSHIP MATCHING WORK. V7-V9 failed with rules-only. V10 passed with 100+ samples. |
| Voice Metrics (from profile.json) | ~100 | Quantitative targets give the model measurable goals, not vague aspirations |
| Rules and Prohibitions | ~200 | Hard constraints prevent the worst AI tells |
| Phrase Fingerprints | ~50 | Exact phrases that roasters use to confirm identity |
| Generation Protocol | ~100 | Pre/During/Post checklists keep output consistent |
| Natural Typos | ~20 | Authenticity markers that signal human-ness |
| Contrastive Examples | ~50 | Shows the model what NOT to do with concrete alternatives |
| Thinking Patterns | ~80 | Cognitive architecture, not just surface style |

**Total: 2000+ lines minimum. Most should be SAMPLES, not rules.** Do NOT pad with verbose rules to hit the line count -- the goal is 2000+ lines of USEFUL content, primarily samples.

#### SKILL.md Frontmatter

```yaml
---
name: voice-{name}
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
description: |
  Apply {Name}'s voice profile for content generation: [2-3 key traits],
  and modal writing. Use when generating content that must match {Name}'s
  distinctive voice. Do NOT use for voice analysis, voice profile creation,
  or generating content in other voices.
version: 1.0.0
command: /voice-{name}
---
```

#### Sample Organization (THE MOST IMPORTANT SECTION)

Organize samples from Step 1 into the SKILL.md following this structure:

**By Response Length:**
- Very short (1 sentence, ~{X}% of responses): Include 10+ samples
- Short (2-3 sentences, ~{X}% of responses): Include 15+ samples
- Medium (4-6 sentences, ~{X}% of responses): Include 10+ samples
- Long (paragraph+, ~{X}% of responses): Include 5+ samples

**By Pattern Type:**
- Admitting Mistakes: 5+ samples
- Acknowledging Limits: 5+ samples
- Respectful Disagreement: 5+ samples
- Technical Expertise (delivered casually): 5+ samples
- Strong Opinions (unhedged): 5+ samples
- Casual Closers: 5+ samples
- Sarcasm/Wit (if applicable): examples

#### Voice Metrics Section

Transfer the profile.json data into human-readable tables with targets and tolerances:

```markdown
| Metric | Target | Tolerance | Notes |
|--------|--------|-----------|-------|
| Average sentence length | {X} words | +/- 2 words | Primary rhythm indicator |
| Short sentences (3-10 words) | {X}% | +/- 5% | For emphasis and pacing |
```

#### Two-Layer Architecture

Design the skill with two layers:

- **Layer A (Always-On Base Voice)**: Core traits, sentence rhythm, punctuation signature, contraction rate, function word signature. These apply to ALL content regardless of mode.
- **Layer B (Mode-Specific Overlays)**: Different modes (e.g., technical, casual, opinion, review) that adjust tone, formality, and structure while keeping Layer A constant.

#### Prompt Engineering Techniques (Apply Throughout)

These techniques were validated over 10 iterations of a reference voice:

1. **Probability Dampening**: Use "**subtly**", "**slightly**", "**generally**" before traits. Without dampening, the model cranks traits to 100%
2. **Attention Anchoring**: **Bold** all negative constraints. The model pays more attention to formatted text
3. **XML Context Tags**: Use `<context type="static-instructions">` for directives and `<context type="safety-guardrails">` for prohibitions. Structured tags signal instruction priority to the model
4. **Few-Shot Examples**: Include 3+ examples for every prohibition (especially "It's not X. It's Y"). Rules without examples are abstract; examples are concrete
5. **Contrastive Pairs**: For every "DO" include a "DON'T" with concrete text. The model needs to see both sides of the boundary

#### config.json

Create the validation configuration:

```json
{
  "name": "{Name}",
  "version": "1.0.0",
  "description": "{Brief voice description}",
  "modes": ["technical", "casual", "opinion"],
  "validation": {
    "strict_banned_patterns": true,
    "em_dash_forbidden": true,
    "metric_tolerance": 0.20,
    "required_checks": ["banned_phrases", "punctuation", "rhythm"],
    "optional_checks": ["metrics", "sentence_starters", "opening_pattern"]
  },
  "thresholds": {
    "pass_score": 70,
    "error_max": 0,
    "warning_max": 3
  },
  "voice_specific_patterns": []
}
```

Adjust `em_dash_forbidden`, `modes`, and `pass_score` based on the specific voice's characteristics.

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

**Goal**: Test the voice against human judgment through authorship matching, because metrics measure surface features but humans detect deeper patterns -- the "feel" of a voice. A piece can pass all metrics and still feel synthetic. Do not treat validation passing as completion.

Maximum 3 iterations in this step before escalating to user.

#### The Authorship Matching Test

1. Select 3-5 original writing samples that were NOT included in the SKILL.md (hold-out samples)
2. Generate 3-5 new pieces using the voice skill on similar topics
3. Present both sets (mixed, unlabeled) to 5 "roasters" (people familiar with the original voice)
4. Ask each roaster: "Were these written by the same person?"
5. Target: 4/5 roasters say "SAME AUTHOR"

#### If Authorship Matching Fails

The answer is almost always MORE SAMPLES, not more rules, because adding "just one more rule" was tried through V7-V9 and never worked -- what worked was adding 100+ categorized samples in V10.

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
- [ ] Content does NOT read like polished professional writing (unless the original voice IS polished)
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
3. Do NOT proceed past Step 1. The system does not work with fewer than 50 samples.

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
4. Do NOT pad with verbose rules. The goal is 2000+ lines of USEFUL content, primarily samples.

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
