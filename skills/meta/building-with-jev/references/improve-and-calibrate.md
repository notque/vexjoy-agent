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
| Answer follows text inside the state | state steering | separate trusted policy from untrusted text; require source evidence in code; adversarial and self-reference tests; thresholds may abstain or refer, not authorize |
| Instruction and criteria point in different directions | contradictory question definition | rewrite both to ask the same condition in the same direction; a Noul's `true` side describes yes |
| Rewording one question trades errors | one question weighs several properties | split into atomic questions |
| Each answer right, decision wrong | policy | change weights or thresholds in code; leave questions alone |
| Slow or costly | sequential calls | merge into one request; keep a second only when it depends on the first |
| Findings unverifiable | whole-input judgment | judge per file or element; anchor to file:line |
| Severity all one band | levels not situations | rewrite levels; add a second-opinion Score in verification |
| `max_tokens_exceeded` mid-pipeline | a later stage skipped fitting | cap items per call at every stage; count `calls_failed` per stage |
| `calls_failed` nonzero, output looks fine | defaults masquerading as answers | surface failed calls; never default silently on a safety path |
| One query works; real use or an eval fails with 429, 529, or Gateway 503 | the run spends too much of the per-second limit; synchronized retries amplify it | price with `scripts/jev-budget-check.py`; cascade; cap in-flight requests; jittered backoff (see below) |

## Service failure or wrong design

HTTP errors and timeouts are not wrong answers; separate them before improving questions. Diagnose in this order, and do not change the payload format, request size, or model on a guess:

1. **Price the run.** `python3 scripts/jev-budget-check.py` on one run's requests at the real concurrency. A `fail` or `warn` on tokens per second or requests per minute explains 429/529/503 on its own. Fix the design (cascade, fewer tokens per run, a concurrency cap) first.
2. **Count retries.** Log retries and failed requests per run. Many retries per run with short fixed delays is a retry storm: the program keeps the limit tripped.
3. **Check what else is spending the account.** An eval, a benchmark, or another app on the same key shares the per-second limit. Stop it and retest.
4. **Send one small known-good request on the same transport** (Gateway through the Gateway, direct through the direct API). If an identical payload alternates between success and failure, the payload is valid; the cause is rate or capacity, not format.
5. **Measure failure against request shape.** Replay a few real requests of different sizes and question counts, round-robin and one at a time (`maxRetries: 0`), alongside a tiny control, for 8 to 12 rounds. Interleaving puts every variant in the same time windows, so drift in service health cannot pass for a size effect. On 2026-09-22 this showed that Gateway 503s tracked tokens per request (about 0% at 1.6k, 12% at 3k, 60 to 75% at 13k) while concurrency and question count did not matter. Because a retry resends the whole request, the cheapest request size minimizes `tokens / success_rate`; for us that was about 2.5 to 4k tokens. Record the curve and date in the project's AGENTS.md; it is service behavior, not a documented limit, and it can change.
6. **Only then suspect the service.** Check the provider status page, and ask the owner whether other apps on the same account are failing at the same time.

Do not infer the state of one transport from another: a direct-key 401 or 402 says nothing about a Gateway-routed app, and a working direct probe says nothing about the Gateway. Report what was measured and what is inferred.

## Revision rules

- Change one or two questions per revision. Probabilities shift in ways that are hard to predict; leave questions that discriminate well alone.
- Judge on labeled data. Higher confidence alone does not show a better question; two wordings of one scale behave differently on your data.
- Keep the answer space stable once code depends on it. Adding or removing a level or option changes what every earlier answer meant and invalidates stored calibration.
- General rules in instructions and criteria; specific names and values only in `examples`.
- Do not loosen criteria to remove a false positive. Sharpen the boundary by adding the misjudged case to `not_for` or the `false` side.
- Pin the model version when thresholds are tuned on measured behavior. Rerun the labeled set and reread the jaggedness page when the model changes.
- Treat state as a design lever only when it supplies evidence needed by the decision. More context is not a fix. Change one state, instruction, criterion, or policy lever at a time so a result remains attributable.
- Do not use a generic probability label, bundled cues, or a list of loosely related tells as a decision surface. Ask a narrow, observable question with `not_for` or restraint cases that protect valid exceptions, quoted input, domain-specific values, and already-supported conclusions.

## Labeled-example loop

1. Build a set with known labels, including adversarial and self-describing inputs and the cases that were misjudged in production.
2. Run every question; store answers with full `probabilities`.
3. For each miss, read the distribution: a near-tie means overlap; a confident miss means literal reading or a missing condition.
4. Revise one or two questions. Rerun the whole set, not just the miss.
5. Keep the set and the results under version control or in the assessment store so the next model version can be compared.

## Labels, holdouts, and failures

Hash frozen fixtures and the rubric that produced their labels. Record label provenance. Human-confirmed labels may evaluate or promote an action; agent or provisional labels are useful for finding cases but remain diagnostic until confirmed.

Keep one untouched, group-disjoint heldout split out of selection and tuning. Use it once for the final report. If work resumes after seeing it, create a new independent heldout before making another claim. This prevents repeated inspection from turning a test result into another dev signal.

Treat an unavailable service, malformed response, missing answer, or failed validation as `unknown`, not a negative label or passing score. Store a failure receipt (request identity, stage, error, timestamps, retry outcome) separately from quality metrics. Never let missingness improve an accuracy, pass, or action-rate metric.

For any action-changing selector, run the policy in shadow mode until human-confirmed, disjoint-heldout results show that the action helps. Confidence cannot authorize an action or override source evidence, permissions, or deterministic policy. Evidence quality is evaluated against a supplied source-evidence ledger; plausibility and stated intent do not substitute for that evidence.

`scripts/jev-compact-evidence.py` shows the measurement side: read the engine's own records, not the tool's claims.

## Baselines, data, and out-of-distribution holdouts

External reports below are directional, from a partial post; rerun them on your own data.

- **Baseline the untrained model first.** Before training or fine-tuning anything for a Jev-shaped decision, score plain Jev (questions only) on the same holdout. An external team's untrained decoder matched every trained small encoder out of distribution (0.567 vs 0.563, 0.541, 0.407). Train only when the trained model beats that baseline by more than run-to-run spread.
- **Grow data before changing architecture.** In the same report, 1,200 to 123,475 labeled examples moved the out-of-distribution score from 0.407 to 0.550. When a tuned component underperforms, add labeled cases first: production misses, and candidates mined from `hooks/routing-decision-recorder.py` logs. Mined labels stay diagnostic until a human confirms them.
- **Hold out out-of-distribution cases.** Hold out whole phrasings and request types, not random rows. Report in-distribution and out-of-distribution scores separately. Treat a small gap as noise until repeat runs on fresh splits show it holds; report the spread.

## Reading `score`

Jev's `score` is the probability-weighted mean of 0-based level numbers. Adding an offset or rounding is a bucketing step: say so in the code, and read `probabilities` when the decision hinges on which level won. Label levels with situations, and keep the 0-based numbering out of user-facing text.
