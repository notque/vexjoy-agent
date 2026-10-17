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

Judge before and after in one request, and score the anchor (the reference) in the same rubric and state form as the candidates as a calibration check. Paired scores in one request agreed within 0.18 over two runs; do not trust a gap under about 0.2.

Use code to expose probabilities, constraints, regressions, variance, cost, and Pareto tradeoffs. Do not hide a severe failure in one average. Treat contradictions as possible construct differences, poor wording, thin evidence, or variance.

Before each image round, hash-diff the kept and candidate renders (prove the pixels changed), include a byte-identical control pair (its `better` and `worse` reads are the noise floor, 0.11 to 0.17 in one run), and check by looking that the number you optimize is the visual cause Jev named. A measured gain (eye-window luma +4 and +7) that did not register as better (0.19 to 0.32) was a proxy that agreed with Jev by accident.

Freeze the question set across rounds. A Noul's answer on identical images can move with the sibling questions in the same request: 0.33 became 0.49 to 0.55 when only the other wordings changed, while repeating the identical request varied by 0.03 or less. Keep the same questions in the same request across rounds, or ask `worse` in its own request. Prefer a Choice when a decision must be stable across rounds: in one field run Choices stayed order-stable (margins 1.6 to 2.7) while Noul reads drifted.

## 6. Select and stop

Choose the smallest change that produces a material, repeatable improvement while all protected dimensions remain within their allowed regression. Stop broad iteration when the same candidate or disposition wins across frozen repeats, material-revision probability is low, and remaining issues are targeted polish or missing external evidence. More self-evaluation is not progress after convergence.

### Gating a change with a decided trade-off

Some changes carry a cost you decided on before the round from measured facts, such as an additive block that pushes content down. A plain `worse` Noul fires on that displacement and stays at 0.5 to 0.65 even when `better` is 0.92 or more, an A/B Choice reads 1.0 in both orders, and the task Noul is up 0.65 (3 builds). Telling Jev to ignore the trade-off does not work: plain and excluded wordings read the same when asked alone (0.61 and 0.64, 0.52 and 0.52, 0.65 and 0.74). Do not write an exclusion. Gate the change instead, and decide the gate and its thresholds before the round:

1. A measured guard on the displaced content (for example it stays in the first viewport, by bounding box).
2. A task Noul that the displaced content still serves its purpose (0.7 or more).
3. A `worse` Noul that names what to check (overlap, clipped text, lost controls, confusing repeats) instead of what to ignore, asked alone, under 0.4.
4. A DOM diff of features present before and after decides lost features (`question-design.md`).

Validate the gate before you trust it. The unchanged kept page must pass, and at least 2 known-bad variants (displaced content pushed out, a planted overlap) must fail. If not, fix the wording once and re-validate. Pre-register the thresholds in a commit, and report the plain `worse` beside the gated answers. When an exclusion seems needed, use this gate instead.

Fixing one diagnosed regression moves the judge to the next (0.29 to 0.01, then 0.40 to 0.59), so budget a round per diagnosed cause. If a gated `worse` stays at 0.4 to 0.6, stop and diagnose with a what-got-worse Choice instead of rewording (one field case: the diagnostic read `season_pushed` 0.52, `cramped` 0.23).

If `better` sits near 0.6 over several rounds (0.56, 0.65, 0.66) while the existing UI already serves the job, the change is redundant on that viewport; it is not a wording problem. Park it. A mockup that passes can fail once built: it idealises omitted content (`worse` 0.17 and 0.38 on the mockup against 0.69 and 0.75 on the build), so re-judge the real build before you rank ideas by mockup scores. Put a build hash in the state and assert that it matches the rendered build before you spend a round: a silent failed edit once sent stale state text. Worked example: idea 1 was parked after three unkept rounds; Jev picked "park and build idea 2" at 0.60/0.69 (order-averaged margin about 2.5) and "drop desktop" at 0.73/0.74.

Jev agreement validates the judge-facing rubric, not the real-world outcome. Before promoting a durable rule, test the selected artifact on representative held-out tasks or human-confirmed labels and measure the downstream action. Record unresolved disagreement and the rejected alternatives; do not describe model consensus as proof.

## Minimum report

Report the baseline, candidates, question version, per-dimension probabilities, relative choices, variance, regressions, cost, stopping decision, rejected alternatives, unresolved disagreement, external-validation status, and evidence that would reverse the decision.
