# Voice Triad Eval

Test a voice skill against the author's real pieces.  A described voice skill
is a set of guesses until it wins a held-out comparison.

Design record: ADR-voice-triad-eval (local-only).

Source: "How I Finally Got AI to Write Like Me", Mike Taylor, Every
(https://every.to), 2026-11-16.  Measured numbers below are the author's,
not this toolkit's.

---

## Why test

A voice skill built by reading samples is a list of guesses about what makes
the author's writing distinctive.  In the source article's test, such a skill
lost to an optimized skill on 80-95% of held-out posts.  For one model the
guess-based skill lost to no skill at all 61% of the time.

The only way to know whether a skill helps is to measure it on pieces the
skill has never seen.

---

## The six steps

### 1. Corpus and held-out split

Collect 12-25 pieces of one format from the author (blog posts, newsletters,
essays -- not a mix of formats).  Split into train and holdout sets.  Put the
newest pieces in holdout when the author's style is changing over time.

```bash
python3 scripts/voice-triad-eval.py split \
  --corpus CORPUS_DIR --out manifest.json \
  --holdout-frac 0.3 --min-holdout 5 --recent-first --seed 0
```

The script refuses a corpus with fewer than 8 pieces and warns below 12.

### 2. Substance-only briefs

For each holdout piece, extract a brief that holds the thesis, outline, every
fact, source, anecdote, and exact quote -- and none of the style, phrasing,
hooks, or jokes.  Draft from briefs, not from topics.

```bash
python3 scripts/voice-triad-eval.py brief-jobs \
  --manifest manifest.json --corpus CORPUS_DIR --out brief-jobs/
```

Run each job file through the drafting model.  Save the brief output for the
next step.

### 3. Two arms, always including a no-skill baseline

Generate two drafts per holdout brief:

- **Arm A**: the voice skill under test.
- **Arm B**: a no-skill baseline (same model, same brief, no voice skill).

Always include a no-skill baseline.  A skill that loses to no skill is worse
than useless.

Save drafts at `DRAFTS/<arm>/<piece-id>.md`.

### 4. Pairwise judge, both orders

A judge model sees the real piece as REFERENCE and the two drafts as Draft 1
and Draft 2 (never named by arm).  It picks the draft closer to the reference
in voice, rhythm, and word choice.  Run each comparison twice with the
presentation order swapped.

```bash
python3 scripts/voice-triad-eval.py judge-jobs \
  --manifest manifest.json --corpus CORPUS_DIR \
  --drafts DRAFTS/ --arms skill-v1 baseline --out judge-jobs/
```

This writes two job files per holdout piece (one AB, one BA).  Run each
through the judge model.  Collect results as JSONL.

### 5. Score and check order-swap consistency

```bash
python3 scripts/voice-triad-eval.py score \
  --jobs judge-jobs/ --judgments results.jsonl --json
```

Read these numbers before trusting any result:

| Metric | Meaning |
|---|---|
| order-swap consistency | Share of pieces where both orders picked the same arm.  Below 0.7, the judge is unreliable for this comparison. |
| first-position rate | Share of judgments that picked Draft 1.  Near 0.5 is healthy; near 1.0 means the judge has a position bias. |
| consistent win rate | Per-arm win rate with split pieces excluded. |
| split count | Pieces where the two orders disagreed.  High splits mean the drafts are hard to tell apart or the judge is noisy. |

Compare judges on the same jobs before standardizing on one.

### 6. Keep only what wins

Keep a voice skill change only when it wins on held-out pieces.  Stop after
three rounds without a kept change -- the skill is at its local optimum for
this model and corpus.

---

## Rules

- **Skills are tuned per model.**  Re-run the eval when the drafting model
  changes.  A skill that wins on one model may lose on another.
- **Draft from a brief, not a topic.**  A one-line topic forces the model to
  invent substance and style at the same time.  The brief isolates the style
  dimension.
- **Feed edits back.**  Save the author's edits to a draft as evidence for the
  next round's skill revision.
- **The eval rewards resemblance only.**  It measures how close a draft reads
  to past writing, not whether the writing is good.  A bad habit in the corpus
  becomes a target.

---

## Distillation ratio

After generating briefs and final drafts, measure how much substance the
brief captures relative to the final:

```bash
python3 scripts/voice-triad-eval.py distill \
  --briefs briefs/ --finals finals/ --json
```

A ratio below 1.0 means the brief is shorter than the final it describes and
may be missing substance.

---

## Cost shape

Per held-out piece, one eval round costs:

| Step | Jobs |
|---|---|
| Brief extraction | 1 |
| Drafts | 1 per arm |
| Judge | 2 per arm pair (one per order) |

For 5 held-out pieces and 2 arms: 5 briefs + 10 drafts + 10 judge calls = 25
model calls per round.
