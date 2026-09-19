# Improve and calibrate

Find the failing question before changing anything. Collect labeled examples, run them, and compare each question's answers and probabilities against the labels. Rewording on intuition trades one error for another.

## Symptom table

| Symptom | Likely cause | Fix |
|---|---|---|
| Wrong answers with high confidence | literal reading of the instruction | state the exact condition; put the boundary case in criteria |
| Low confidence on a Choice | options overlap, or none fits | add `what`, `not_for`, `examples`; add `other` |
| Low confidence on a Score | levels overlap, two dimensions, or thin state | rewrite levels as distinct situations; split; add the missing field |
| Scores cluster in the middle | levels are degrees or numerals | one concrete situation per level; remove numerals |
| Top-of-scale cases look alike | the extreme has no level | add a level for it |
| Noul hovers near 0.5 | vague condition | define it; add `true`/`false` criteria with examples |
| Accuracy falls as inputs grow | irrelevant state | filter in code; send only needed fields; judge per unit |
| Errors on counts, sums, dates, nearness | Jev doing arithmetic | move it to code; per-item Nouls; Choice per date part |
| Errors on nested or negated questions | indirection | ask directly; name the path; two literal questions combined in code |
| Answer follows text inside the state | state steering | tighten criteria; adversarial and self-reference tests; confidence gate |
| Rewording one question trades errors | one question weighs several properties | split into atomic questions |
| Each answer right, decision wrong | policy | change weights or thresholds in code; leave questions alone |
| Slow or costly | sequential calls | merge into one request; keep a second only when it depends on the first |
| Findings unverifiable | whole-input judgment | judge per file or element; anchor to file:line |
| Severity all one band | levels not situations | rewrite levels; add a second-opinion Score in verification |
| `max_tokens_exceeded` mid-pipeline | a later stage skipped fitting | cap items per call at every stage; count `calls_failed` per stage |
| `calls_failed` nonzero, output looks fine | defaults masquerading as answers | surface failed calls; never default silently on a safety path |

## Revision rules

- Change one or two questions per revision. Probabilities shift in ways that are hard to predict; leave questions that discriminate well alone.
- Judge on labeled data. Higher confidence alone does not show a better question; two wordings of one scale behave differently on your data.
- Keep the answer space stable once code depends on it. Adding or removing a level or option changes what every earlier answer meant and invalidates stored calibration.
- General rules in instructions and criteria; specific names and values only in `examples`.
- Do not loosen criteria to remove a false positive. Sharpen the boundary by adding the misjudged case to `not_for` or the `false` side.
- Pin the model version when thresholds are tuned on measured behavior. Rerun the labeled set and reread the jaggedness page when the model changes.

## Labeled-example loop

1. Build a set with known labels, including adversarial and self-describing inputs and the cases that were misjudged in production.
2. Run every question; store answers with full `probabilities`.
3. For each miss, read the distribution: a near-tie means overlap; a confident miss means literal reading or a missing condition.
4. Revise one or two questions. Rerun the whole set, not just the miss.
5. Keep the set and the results under version control or in the assessment store so the next model version can be compared.

`scripts/jev-compact-evidence.py` shows the measurement side: read the engine's own records, not the tool's claims.

## Reading `score`

Jev's `score` is the probability-weighted mean of 0-based level numbers. Adding an offset or rounding is a bucketing step: say so in the code, and read `probabilities` when the decision hinges on which level won. Label levels with situations, and keep the 0-based numbering out of user-facing text.

