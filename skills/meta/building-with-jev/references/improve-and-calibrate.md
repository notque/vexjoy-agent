# Improve and calibrate

Read every miss with its exact state, questions, answer distribution, action, and label. First separate transport/schema/code failures from judgment errors. Classify judgment errors as missing evidence, ambiguous boundary, wrong primitive, label noise, or distribution shift.

Change one lever per variant, in order: evidence, decomposition, criteria, threshold, examples. Reuse stored probabilities for threshold sweeps. Compare against majority, strongest deterministic signal, and rules-only baselines; report slices, false positives, Brier/calibration, failures, cost, and repeated-request flips.

Score returns a weighted mean, not a level. Inspect distributions when bimodality changes the action. Confidence is concentration and can be high on a literal but wrong reading.

Freeze fixture/rubric hashes and label provenance. Tune on train/dev; use group-disjoint heldout once after selection. Invalid/unavailable answers stay outside quality metrics with separate failure receipts. A model, rubric, policy, or material data-distribution change triggers recalibration.
