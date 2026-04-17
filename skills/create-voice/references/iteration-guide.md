# Create Voice — Iteration Guide (Step 6 + 7 details)

## Step 6 Details: Validation Procedure

### Generate Test Content

Using the new voice skill, generate 3 test pieces:
1. A short response (2-3 sentences) to a casual prompt
2. A medium response (paragraph) to a technical question
3. A long response (multi-paragraph) to an opinion question

Save each to a temp file.

### Run Validation

For each test piece:

```bash
python3 ~/.claude/scripts/voice-validator.py validate \
  --content /tmp/voice-test-{name}-{N}.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text \
  --verbose
```

### Run Banned Pattern Check

```bash
python3 ~/.claude/scripts/voice-validator.py check-banned \
  --content /tmp/voice-test-{name}-{N}.md \
  --voice {name}
```

### Interpret Results

| Score | Status | Action |
|-------|--------|--------|
| 60+ with 0 errors | PASS | Proceed to Step 7. The script's pass threshold is 60 (calibrated against real human writing which scored ~66). 70+ is ideal but not required. |
| 50-59 with warnings only | MARGINAL | Review warnings, fix if simple, or proceed |
| < 50 or errors present | FAIL | Identify top 3 violations, fix in SKILL.md, regenerate, revalidate |

**Wabi-sabi check**: If validation flags natural imperfections as errors (run-on sentences, fragments, loose punctuation that match the samples), adjust the validator threshold in config.json, NOT the content, because the authentic writing scored what it scored and synthetic content should match it, not exceed it. If the original writing "fails" validation, the validator is wrong, not the writing.

### If Validation Fails

1. Read the violation report carefully
2. Identify the top 3 violations by severity
3. For each violation, determine if it's:
   - A **real problem** (AI phrase, wrong structure) -- fix in SKILL.md rules or add more samples
   - A **false positive** (natural imperfection flagged as error) -- adjust config.json thresholds
4. Make targeted fixes (one at a time, not wholesale rewrites)
5. Regenerate test content and revalidate
6. Maximum 3 validation/refinement iterations before escalating to user

---

## Step 7 Details: Authorship Matching

### The Authorship Matching Test

1. Select 3-5 original writing samples that were NOT included in the SKILL.md (hold-out samples)
2. Generate 3-5 new pieces using the voice skill on similar topics
3. Present both sets (mixed, unlabeled) to 5 "roasters" (people familiar with the original voice)
4. Ask each roaster: "Were these written by the same person?"
5. Target: 4/5 roasters say "SAME AUTHOR"

### If Authorship Matching Fails

The answer is almost always MORE SAMPLES, not more rules, because adding "just one more rule" was tried through V7-V9 and produced zero improvement -- what worked was adding 100+ categorized samples in V10.

| Failure Pattern | Diagnosis | Fix |
|----------------|-----------|-----|
| "Ideas match but style doesn't" | Insufficient samples in SKILL.md | Add 20-50 more samples, especially short responses |
| "Too polished, too perfect" | Wabi-sabi not applied strongly enough | Increase fragment rate target, add more typos, loosen punctuation rules |
| "Phrases feel generic" | Phrase fingerprints not prominent enough | Bold the fingerprints, add more examples of each |
| "Wrong rhythm" | Sentence length distribution off | Check profile.json targets against generated metrics |
| "Right voice, wrong length" | Response length distribution wrong | Adjust default mode or add stronger length constraints |

### The V10 Lesson

One voice went through 10 versions during development:
- V1-V6: Incremental rule improvement. Modest gains.
- V7-V9: Rules were correct but authorship matching failed 0/5. The voice had the right CONSTRAINTS but not enough EXAMPLES.
- V10: Added 100+ samples organized by pattern. Passed 5/5.

**The breakthrough was not better rules. It was more samples.**

If you find yourself tweaking rules and not improving, step back and ask: "Do I need more samples in the SKILL.md?" The answer is almost certainly yes.

### Wabi-Sabi Final Check

Before declaring the voice complete, verify:

- [ ] Generated content contains natural imperfections from the samples (not manufactured imperfections)
- [ ] Run-on sentences appear at approximately the same rate as in the original samples
- [ ] Fragments appear for emphasis, matching sample patterns
- [ ] Typos from the natural typos list appear occasionally (not forced)
- [ ] Content reads with the same level of polish as the original samples (unless the original voice IS polished)
- [ ] If content is too perfect, the skill needs MORE samples and LOOSER constraints, not fewer
- [ ] If generated content "feels too rough," compare against original samples before adjusting -- if it matches the samples' roughness, it's correct
