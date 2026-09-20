# Search-quality experiment contract

Choose metrics by task: MRR/P@1 for one-answer navigation, nDCG for graded ranked lists, and high-k recall for compliance/discovery. Report the cutoff.

Judgment rules:

- version labels and guidelines; separate development from untouched test queries;
- stratify head/torso/tail and intent; include known failure queries;
- track unjudged top results because treating them as irrelevant versus ignoring them changes metrics;
- click labels have position/presentation bias; use expert judgments or debiasing for evaluation;
- compare rankers on the same queries with paired confidence intervals or a paired test.

Online tests randomize by user, precompute sample size, run across day-of-week cycles, and guard latency, zero-result rate, and errors. Team-draft interleaving is useful when ranking sensitivity matters more than absolute conversion.

Do not promote a relevance change from aggregate improvement if an important slice regresses materially.
