# Voice System

Create AI writing profiles that match a specific person's style. Analyzes writing samples, extracts measurable patterns, validates generated content against them. No pre-built voices included — bring your own samples.

---

## Quick Start

### 1. Collect Writing Samples

Gather 3-5 pieces of writing (blog posts, articles, emails). More samples = better calibration. Save as markdown.

### 2. Analyze the Samples

```bash
python3 scripts/voice-analyzer.py analyze --samples your-samples.md
```

Produces a voice profile: sentence length distribution, opening patterns, distinctive elements (comma density, contraction rate, fragment usage).

### 3. Create a Voice Profile

```
/create-voice
```

7-phase pipeline: Collect → Extract → Pattern → Rule → Generate → Validate → Iterate.

### 4. Generate Content

```
/do write a blog post about [topic]
```

### 5. Validate the Output

```bash
python3 scripts/voice-validator.py validate --content draft.md --profile your-voice-profile.json --voice your-voice-name
```

Checks: banned patterns, rhetorical pivots, sentence rhythm monotony, metric deviations from profile, architectural patterns, overall score (pass threshold: 60/100).

---

## How It Works

### Voice Analyzer (`scripts/voice-analyzer.py`)

| Metric | What It Measures |
|--------|-----------------|
| Sentence length distribution | Short/medium/long/very-long ratios |
| Opening patterns | How paragraphs begin (fact, question, story, conjunction) |
| Comma density | Punctuation style fingerprint |
| Contraction rate | Formality level |
| Fragment rate | Use of intentional sentence fragments |
| Em-dash usage | Punctuation preferences |
| Function word signature | Word frequency fingerprint |

### Voice Validator (`scripts/voice-validator.py`)

```bash
python3 scripts/voice-validator.py validate --content draft.md --profile your-voice-profile.json --voice your-voice-name
python3 scripts/voice-validator.py check-banned --content draft.md
python3 scripts/voice-validator.py check-rhythm --content draft.md --profile your-voice-profile.json
python3 scripts/voice-analyzer.py compare --profile1 voice1.json --profile2 voice2.json
```

### Voice Calibrator (`skills/workflow/references/voice-calibrator.md`)

Advanced calibration reference. Key insight: getting the **rules** right isn't enough — you need **100+ real samples categorized by pattern** for authorship matching.

### Wabi-Sabi Principle

Natural imperfections (run-ons, fragments, casual punctuation) are **features**, not bugs. Sterile grammatical perfection is an AI tell.

---

## Creating a Voice from Scratch

### Step 1: Sample Selection

Pick writing that is: recent, natural (not ghostwritten), varied topics, 500+ words per sample. Exclude corporate copy, co-authored pieces, and transcripts.

### Step 2: Initial Calibration

```
/create-voice
```

Reads samples, extracts metrics, identifies distinctive patterns, generates test content, validates against profile.

### Step 3: Iterative Refinement

```bash
python3 scripts/voice-validator.py validate --content draft.md --profile your-voice-profile.json --format text --verbose
/do refine voice your-voice with additional samples
```

### Step 4: Integration

Once calibrated, available to: `voice-writer`, `anti-ai-editor`, `workflow` (via `references/article-evaluation-pipeline.md`).

---

## File Structure

```
scripts/
  voice-analyzer.py      # Extract metrics from writing samples
  voice-validator.py     # Validate content against voice profiles
  data/
    banned-patterns.json # AI writing patterns to avoid

skills/
  create-voice/          # Interactive voice creation (7 phases)
  voice-validator/       # Validation methodology
  voice-writer/          # Unified 8-phase content generation
  anti-ai-editor/        # AI tell detection and removal
  workflow/
    references/
      voice-calibrator.md   # Advanced calibration and refinement (workflow reference)
```

---

## Tips

- **More samples beat better rules.** 10 mediocre samples outperform 3 perfect ones.
- **Test with blind reads.** If readers can tell it's AI, more calibration needed.
- **Voice profiles are portable.** Export JSON across projects.
- **Validator is strict by design.** 60/100 = right patterns. 90+ usually means over-fitting.
