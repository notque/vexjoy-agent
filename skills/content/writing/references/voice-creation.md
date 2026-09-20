# Evidence-backed voice creation

## Artifacts

- Raw samples remain unchanged and retain source/context provenance.
- `profile.json` stores measured ranges and tolerances.
- The voice `SKILL.md` stores corpus-backed behaviors, boundaries, and representative excerpts.
- Validation configuration stores thresholds separately from the source evidence.

Run the repository analyzers when available:

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json
python3 scripts/voice-stylometry.py band \
  --samples skills/voice-{name}/references/samples/*.md
```

## Admission test for a qualitative pattern

Keep a pattern only when it:

1. recurs across at least two distinct contexts;
2. changes generated language or reasoning, rather than merely describing it; and
3. distinguishes this writer from competent generic prose.

Record exact excerpts and counts. Mark context-limited patterns as such. Put common contractions, punctuation frequency, and sentence length in measured fields rather than inflating them into “voice rules.” Never manufacture typos or roughness; preserve only irregularities supported by samples.

## Validation

Reserve real samples before analysis. Generate short, medium, and long probes in several modes, then run:

```bash
python3 ~/.claude/scripts/voice-validator.py validate \
  --content <probe> --profile skills/voice-{name}/profile.json \
  --voice {name} --format text --verbose
python3 ~/.claude/scripts/voice-validator.py check-banned \
  --content <probe> --voice {name}
```

Also test blind authorship discrimination against held-out originals. Historical iterations here improved when representative examples replaced piles of rules: if ideas match but rhythm does not, add missing sample modes before adding prohibitions. If real held-out writing fails a threshold, recalibrate the validator from the corpus instead of polishing the source.
