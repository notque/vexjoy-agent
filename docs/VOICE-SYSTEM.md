# Voice System

Create AI writing profiles that match a specific person's style. The system analyzes writing samples, extracts measurable patterns, and validates generated content against those patterns.

No pre-built voices are included. You bring your own writing samples and create your own.

---

## Quick Start

### 1. Collect Writing Samples

Gather 3-5 pieces of writing (blog posts, articles, emails) from the person whose voice you want to replicate. More samples = better calibration. Save them as markdown files.

### 2. Analyze the Samples

```bash
python3 scripts/voice_analyzer.py analyze --samples your-samples.md
```

This produces a voice profile: sentence length distribution, opening patterns, distinctive elements (comma density, contraction rate, fragment usage, etc.).

### 3. Create a Voice Profile

Use the interactive skill:

```
/create-voice
```

This walks you through a 7-phase pipeline:
1. **Collect**:gather and organize samples
2. **Extract**:pull measurable metrics from the writing
3. **Pattern**:identify distinctive stylistic patterns
4. **Rule**:create validation rules from patterns
5. **Generate**:produce test content using the voice
6. **Validate**:run the validator against generated content
7. **Iterate**:refine until the voice passes validation

### 4. Generate Content in That Voice

```
/do write a blog post about [topic]
```

The system loads the voice profile and generates content matching those patterns.

### 5. Validate the Output

```bash
python3 scripts/voice_validator.py validate --content draft.md --voice your-voice-name
```

The validator checks:
- Sentence length distribution matches the profile
- Opening patterns match (direct fact vs. question vs. story)
- Banned patterns are avoided (AI tells like "It's not X, it's Y")
- Voice-specific markers are present
- Overall score (pass threshold: 60/100)

---

## How It Works

### Voice Analyzer (`scripts/voice_analyzer.py`)

Extracts quantitative metrics from writing samples:

| Metric | What It Measures |
|--------|-----------------|
| Sentence length distribution | Short/medium/long/very-long ratios |
| Opening patterns | How paragraphs begin (fact, question, story, conjunction) |
| Comma density | Punctuation style fingerprint |
| Contraction rate | Formality level |
| Fragment rate | Use of intentional sentence fragments |
| Em-dash usage | Punctuation preferences |
| Function word signature | Word frequency fingerprint |

### Voice Validator (`scripts/voice_validator.py`)

Validates content against a voice profile:

```bash
# Basic validation
python3 scripts/voice_validator.py validate --content draft.md --voice your-voice

# Check for banned AI patterns only
python3 scripts/voice_validator.py check-banned --content draft.md

# Compare two voice profiles
python3 scripts/voice_analyzer.py compare --profile1 voice1.json --profile2 voice2.json
```

### Voice Calibrator (`pipelines/voice-calibrator/`)

Advanced calibration skill for iterative refinement. Key insight from development: getting the **rules** right isn't enough:you need **100+ real samples categorized by pattern** for the voice to pass authorship matching.

### Wabi-Sabi Principle

Natural imperfections (run-ons, fragments, casual punctuation) are **features**, not bugs. Sterile grammatical perfection is an AI tell. The system intentionally preserves these patterns from the original writing samples rather than "correcting" them.

---

## Creating a Voice from Scratch

### Step 1: Sample Selection

Pick writing that is:
- **Recent**:voice evolves over time
- **Natural**:not heavily edited or ghostwritten
- **Varied**:different topics, same author
- **Substantial**:at least 500 words per sample

Avoid:
- Heavily edited corporate copy
- Co-authored pieces
- Transcripts (speaking voice ≠ writing voice)

### Step 2: Initial Calibration

```
/create-voice
```

Follow the prompts. The skill will:
1. Read your samples
2. Extract metrics automatically
3. Ask you to identify distinctive patterns
4. Generate test content
5. Validate against the profile

### Step 3: Iterative Refinement

The first calibration is rarely perfect. Use:

```bash
# See what patterns the validator catches
python3 scripts/voice_validator.py validate --content draft.md --voice your-voice --verbose

# Refine with additional samples
/do refine voice your-voice with additional samples
```

### Step 4: Integration

Once calibrated, the voice is available to:
- `voice-writer`:unified 8-phase pipeline for blog posts and articles with mandatory validation
- `anti-ai-editor`:reviews content for AI tells relative to your voice
- `article-evaluation-pipeline`:evaluates articles for voice fidelity

---

## File Structure

```
scripts/
  voice_analyzer.py      # Extract metrics from writing samples
  voice_validator.py     # Validate content against voice profiles
  data/
    banned-patterns.json # AI writing patterns to avoid

skills/
  create-voice/          # Interactive voice creation (7 phases)
  voice-calibrator/      # Advanced calibration and refinement
  voice-validator/       # Validation methodology
  anti-ai-editor/        # AI tell detection and removal

pipelines/
  voice-writer/          # Unified 8-phase content generation pipeline
```

---

## Tips

- **More samples beat better rules.** 10 mediocre samples outperform 3 perfect ones.
- **Test with blind reads.** Have someone read generated content without knowing it's AI. If they can tell, the voice needs more calibration.
- **Voice profiles are portable.** Export the JSON profile and use it across projects.
- **The validator is strict by design.** A 60/100 pass score means the content has the right patterns. Scoring 90+ usually means over-fitting.
