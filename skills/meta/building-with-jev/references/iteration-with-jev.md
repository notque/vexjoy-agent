# Iterating on artifacts with Jev

Use this method to improve a skill, rubric, prompt, policy, decision card, or other artifact whose quality can be judged from supplied evidence. Jev supplies cheap parallel judgments; it does not supply ground truth. The surrounding program owns candidate construction, comparison, selection, and stopping.

## 1. Define the decision

Name the artifact, its reader or consumer, the action it must improve, and what would justify changing it. Preserve the original artifact as the baseline. Write the policy before asking questions: which dimensions are constraints, which may trade off, how large a regression is acceptable, and what result means stop.

## 2. Build a wide battery

Ask every independent question that could change the edit, selection, or stopping decision, up to the request budget. Do not pursue a question-count maximum: omit heads whose answers cannot affect an action. Before running, estimate the fixed question-token floor, total input tokens, sends, repeats, and worst-case retries; compare the receipt afterward. Decompose vague goals such as “concise,” “safe,” or “clear” into observable dimensions. Include positive qualities, failure modes, boundary cases, omissions, redundancy, local fit, and likely misuse. Use the same wording and criteria for every candidate.

Use absolute Nouls for bars and relative Choices for comparisons when each changes policy. They are separate evidence, not algebraic checks. Add an overall disposition only after the component questions exist.

## 3. Supply fair evidence

Send complete candidates and the context in which they will be used. Compare like with like: same evidence window, question battery, model, and policy. If the full context does not fit, create one bounded shared evidence pack rather than truncating candidates differently. Keep candidate identities neutral when presentation order could bias selection.

## 4. Establish the baseline

Run the original before editing. Store probabilities, question and payload versions, usage, and latency. Repeat the frozen request to measure decision flips and the judge’s noise floor; changes within that noise are not improvements.

## 5. Iterate controlled candidates

Change one structural hypothesis or a small related set per round. Prefer complete candidates over independently optimizing fragments: locally preferred sentences can compose into a repetitive or incoherent artifact. Carry prior results as labeled history only when they help interpret the next comparison; do not coach Jev toward the prior winner. Re-run the unchanged battery against the baseline and every candidate.

Judge before and after in one request, and score the anchor (the reference) in the same rubric and state form as the candidates as a calibration check. Paired scores in one request agreed within 0.18 over two runs; do not trust a gap under about 0.2 (`field-learnings.md`).

Use code to expose probabilities, constraints, regressions, variance, cost, and Pareto tradeoffs. Do not hide a severe failure in one average. Treat contradictions as possible construct differences, poor wording, thin evidence, or variance.

Before each image round, hash-diff the kept and candidate renders (prove the pixels changed), include a byte-identical control pair (its `better` and `worse` reads are the noise floor, 0.11 to 0.17 in MMR's run), and check by looking that the number you optimize is the visual cause Jev named. A measured gain (eye-window luma +4 and +7) that did not register as better (0.19 to 0.32) was a proxy that agreed with Jev by accident (`field-learnings.md`).

## 6. Select and stop

Choose the smallest change that produces a material, repeatable improvement while all protected dimensions remain within their allowed regression. Stop broad iteration when the same candidate or disposition wins across frozen repeats, material-revision probability is low, and remaining issues are targeted polish or missing external evidence. More self-evaluation is not progress after convergence.

When a trade-off was decided before the round from measured facts (additive layout work pushes content below the fold), `worse` fires on that cost and stays high even after the specific losses are fixed (DeepRoute: 0.66 after `lost_info` 0.90 to 0.78 and `hero_small` 0.65 to 0.38). Ask `worse` twice: plain, and "anything worse other than <the named trade-off>". Report both and keep only if the excluded answer is under 0.4. Never add "this is decided" to the state of the plain question: that argues the bar away silently (`field-learnings.md`). If the excluded `worse` stays at 0.4 to 0.6, the trade-off is not the whole cause: stop and diagnose with a what-got-worse Choice instead of rewording (DeepRoute: desktop 0.50 to 0.33, mobile 0.58 to 0.53; the diagnostic read `season_pushed` 0.52, `cramped` 0.23). If `better` sits near 0.6 over several rounds (0.56, 0.65, 0.66) while the existing UI already serves the job, the change is redundant on that viewport; it is not a wording problem. Park it. Worked example: idea 1 was parked after three unkept rounds; Jev picked "park and build idea 2" at 0.60/0.69 (order-averaged margin about 2.5) and "drop desktop" at 0.73/0.74.

Jev agreement validates the judge-facing rubric, not the real-world outcome. Before promoting a durable rule, test the selected artifact on representative held-out tasks or human-confirmed labels and measure the downstream action. Record unresolved disagreement and the rejected alternatives; do not describe model consensus as proof.

## Minimum report

Report the baseline, candidates, question version, per-dimension probabilities, relative choices, variance, regressions, cost, stopping decision, rejected alternatives, unresolved disagreement, external-validation status, and evidence that would reverse the decision.
