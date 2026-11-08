# Writing blind A/B tests

Use this guide when you compare two agents, prompts, reviewers, or routers and the result decides whether a change ships. Each rule comes from a run in this repo that cost money and still had to be judged by hand, or that nearly reported a wrong answer. The code checks live in `scripts/routing-ab-test.py` (`--pilot-check`, and the `--gate` CEILING/FLOOR verdict). The routing procedure is in `docs/router-ab-runbook.md`.

## 1. Prove the corpus can discriminate first

A test that every arm passes, or every arm fails, judges the corpus, not the arms. fix-strategy-v1 scored 8/8 against 8/8 (`scripts/routing-ab-results/fix-strategy-v1/VERDICT.md`), so it could never have shown a difference.

- Run a pilot on about 20% of cases before the main run, with four arms: the baseline, a degraded control, a second baseline run (the A/A arm), and a reference arm of different quality, such as a stronger model. The reference arm is required: a case the baseline fails discriminates only when another arm passes it, and the degraded control rarely does. Without it, a stable 60%/60%/0% pilot fails as NON-DISCRIMINATING, and guarding every baseline failure leaves the baseline at 100% (CEILING).
- Keep baseline accuracy or recall within 30-70% on the analysis set. Guard cases count toward neither accuracy nor the control gap, so they cannot pad a ceiling baseline into the band. Above 70%, harden the cases. Below 30%, check the grader before you blame the cases.
- Require every case to discriminate: baseline and A/A agree on it, and the control or the reference arm gets the other result. A flip between baseline and A/A is noise, not discrimination. A case every arm passes is a ceiling case; one every arm fails is a floor case. Rework or drop each one, or keep it as a guard outside the analysis set and report it as non-discriminating. Log each guard and its reason in the change log. Guards may be at most 20% of cases, and the analysis set keeps at least 8; past that the pilot fails as TOO-MANY-GUARDS, so harden the corpus instead.
- Gate it: `python3 scripts/routing-ab-test.py --pilot-check --control-arm NAME --aa-arm NAME --extra-arm NAME`, or pass `--per-case FILE` for a review A/B outside the routing harness. Name every arm in the pilot data; name the reference arm with `--extra-arm NAME` and each guard with `--guard-case ID`. Leave the candidate arm out of the pilot data: the check rejects unnamed arms. Per-case values must be JSON `true`/`false`, not strings. On FAIL, rework the cases. Do not start the main run.
- If the main run still ends with both arms at 95% or above (or 5% or below) and fewer than 6 discordant pairs, `--gate` returns CEILING or FLOOR (exit 3). Report that the run judged nothing. Never report it as "no difference".
- For a lower-is-better metric, such as false positives per review, record a case as passing when it shows the good outcome, and declare that direction before the pilot.

In the reviewer-isolation pilot, 6 of 11 cases failed that protocol's per-defect version of this rule (among A1, A2, and C, at least one run misses a seeded defect and at least one catches one). Three replacement cases, all real bugs, hit the ceiling in the re-pilot and were dropped. Expect to lose cases here, and budget for it.

## 2. Build cases from real defects

- Take seeded defects from real bugs in git history: a fix commit names the bug, its pre-fix state is the case, and the fix is the answer key. Of 21 defects in the final reviewer corpus, 18 came from history.
- Add distractors: code that looks wrong but is correct. A finding that matches a distractor is a false positive you can count without judging.
- Add clean cases with no defect, to measure noise findings.
- Write synthetic cases only to fill a gap, and report results with and without them. In the reviewer run, one synthetic plan drove the largest share of the gap.
- Record each case's origin (commit or synthetic) in the key.

## 3. Keep the corpus author blind to the candidate

Freeze the corpus and the answer key before anyone reads the candidate arm's text. An author who has seen the treatment picks defects it is built to catch. Exclude the candidate arm from the pilot, so pilot hardening cannot tune cases toward it.

## 4. Make the arms differ in one thing

- Keep the same model, tools, dispatch text, output format, and verdict vocabulary in every arm. Measure total prompt length and keep each arm within 15% of the baseline.
- Strip anything that tells an arm it is the experiment, such as a source credit or a hook name.
- When a candidate bundles several changes, add an ablation arm for each part. The reviewer run's goldfish arm carried both isolation and a rubric. The no-rubric arm (BR) showed that the rubric caused most of the loss (B minus BR was -11.9 points).
- Give every run a fresh workspace, and delete it afterwards.

## 5. Validate the grader before you trust it

- **Agreement gate.** Hand-label a fresh set (20 to 30 items) before the grader sees it, and require at least 90% agreement. Write the matching rule down before you label. Check every grader revision on a set it has never seen; a rule fitted on the set that exposed it is untested. In the reviewer run, two matcher rounds failed (80.0%, 76.7%) before a third passed (93.3%), and both real-defect graders failed (50%, 75%). FP was therefore counted from distractor matches only, and the verdict said so.
- **A/A control.** Run the baseline twice. The gap between the two runs is your noise. A pairwise judge on an A/A pair should read near 0.5. In the reviewer run, one read 0.333 with n = 9, so treat any pairwise read within about 0.17 of that as noise.
- **Degraded-arm control.** Run an arm built to lose, such as a style-only reviewer or a manifest with stripped descriptions. It must lose by at least 30 points (the reviewer-isolation positive-control bar) and by more than twice the A/A gap. If it does not, the grader or the corpus cannot see quality.
- Spot-check about 5 main-run grader answers against the key.

## 6. Cancel position bias

Pairwise judges favor one slot. Jev favored the second-listed review by about 0.12. Ask every pairwise question in both orders, swapping the state and the option order, and average the two reads. Report both order reads beside the mean. A single-order number is not a result.

## 7. Size the run from measured noise

- Use the A/A gap or the bootstrap band from the pilot to choose repeats. With a pilot band of ±8.2 points, 2 repeats give 8.2/√2 = 5.8, under half of a 15-point keep bar.
- Report the run-to-run spread beside every contrast. A contrast inside one arm's own rep-to-rep spread (14.3 points for one reviewer arm) is not an effect, in either direction.
- For a paired pass/fail metric, use McNemar with at least 6 discordant pairs. Fewer is UNDERPOWERED, not a null.

## 8. Pre-register, then freeze

- Before the main run, write the question, metrics, keep bar, analysis script, and stopping rules. Hash the protocol, corpus, key, and arm files, and store the hashes.
- Log every change after a pilot in a dated change log, with the numbers that drove it, before you run the change.
- Re-verify every hash at the end. A changed gate after the results invalidates the run.

## 9. Audit with an independent recompute

Before you report, recompute the headline numbers from the raw outputs with a separate script, keyed by run id. Grep every prompt and system file for answer-key text, to prove the key did not leak. Re-hash the frozen inputs. In the reviewer run, the recompute matched for every arm and repeat, the key grep found 0 hits, and the re-hash found 0 mismatches.

## Report

Report the verdict against each keep-bar line, the per-case hit table, every control result, grader agreement numbers, both pairwise orders, run-to-run spread, cost, and a threats list with the residual risk of each threat. State what a null result does and does not rule out.
