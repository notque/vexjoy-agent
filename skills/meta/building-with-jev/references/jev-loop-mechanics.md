# Jev Loop Mechanics and Answer Reading

Reference for using Jev as a decision and quality map during development.

## Run the loop

1. **Fix the destination.** Write a Score ladder: 3-5 levels, each with a `summary` and observable `signals` (counts, sizes, latencies, what a user sees), instead of adjectives. Score the current state as the baseline.
2. **Find the structural cause first.** Ask a Choice over approaches before tuning parameters.
3. **Describe output, rather than code.** Put measured observations in the state: text as shown, p95 from a timed run. For a visual goal, send the rendered output as an image with the measured pixels beside it; describing pixels in text is the fallback (`skills/meta/building-with-jev/references/images.md`). A state of settings or intent gets intent judged.
4. **Add a reference:** a known-good example or the last kept version, described like the candidate. For a visual goal, send it as an image too. Without one, Jev scores against its memory.
5. **Pair each judgment with a measured number.** If they disagree, stop and find out why. Drop a metric that agrees only by chance.
6. **Judge before/after** on one state, with the keep bar set first. Default: `better` >= 0.7, `worse` < 0.4, every measured guard intact. Keep or revert, and log both.
7. **Ask one judgment per question.** Split by trait and group, and add a separate "anything worse or blocking?" Noul. A combined score hides one group's regression.
8. **Let the owner recalibrate.** Write the owner's observation into the ladder as a signal, re-score the baseline, and continue. Treat owner observations as authoritative over prior scores.
9. **Stop** at the target level, or after two rounds with no kept step, and report the blocker.

## Read answers honestly

- A Noul in 0.4-0.6, or a split Choice or Score, is unsettled. Report the split, then split the question, sharpen criteria, or add evidence. If it stays split after one sharpening, escalate the decision to a stronger model instead of looping (`building-with-jev`, Escalate when Jev is unsure).
- Re-ask only after the state or the question set changes, and record the change.
- Before a deploy, merge, migration, or deletion, require every `ready`, `gap`, and `worse` answer to be decisive.
- `confidence` measures distribution shape, rather than correctness. Treat owner approval as separate from any Jev answer.

## Mechanics

Call `evaluate_packed(state, questions, timeout=90)` in `scripts/jev_transport.py`. Keep requests near 3.5k tokens and runs under 50k. `questions` is a dict. Choice uses `criteria` (`what`, `not_for`, `examples`; field names inside are conventions, up to 255 options); Score uses a `criteria` list of `{summary, signals}` (2-10 levels); Noul uses `criteria.true`/`criteria.false`. The client pins `jev-1.14.0` (Gateway: `typesafe-ai/jev-1.14.0`) so thresholds stay stable instead of tracking the moving `jev-latest` alias. Send scrubbed text only.

## Report the climb

Per round, report the ladder level before and after with probabilities, measured numbers, what was kept and reverted, and open gaps ranked by Jev.
