# Authorization Tiers and Owner Decision Briefs

Three contracts for agents that drive PRs on the owner's behalf: how far you may act, what a question to the owner must contain, and when you may ask it.

---

## Contract 1: Authorization Tiers

Every PR task carries an authorization tier. Act up to the last tier the owner granted, then stop and report.

| Tier | Granted by phrases like | You may |
|---|---|---|
| **Triage** | "look at", "assess", "what's the state of" | Read code, PRs, CI, reviews. Report findings. No edits. |
| **Implement** | "fix", "build", "address the feedback" | Edit files, commit on a branch, run tests locally. |
| **Push** | "push", "open a PR", "send for review" | Push the branch, open or update the PR, watch CI. |
| **Merge** | "merge", "land it", "ship it" | Merge the approved, green PR. |
| **Release** | "release", "deploy", "publish the version" | Tag, publish, deploy per project release process. |

Rules:

- Tiers nest. A merge grant includes implement and push for that task.
- Grants are per task. "Ship it" on one PR authorizes merging that PR only.
- When the grant is ambiguous, take the lower tier and ask before crossing the boundary.
- Stopping at the boundary means: finish all work the tier allows, then hand the owner a Decision Brief for the next step.

## Contract 2: Owner Decision Brief

A bare "here's the URL — land or delete?" ask wastes the owner's time. Every question to the owner about a PR's fate uses this format:

```
**Decision: <one-line subject>**
- URL: <PR link>
- Change: <what it does, in plain language a non-reader of the diff understands>
- Proof: <what was verified and how — tests run, CI green, behavior observed>
- Tradeoffs: <what the change costs or risks; "none found" only after looking>
- Recommendation: <the single option you would pick, and why in one sentence>
- Choices: <exact options, e.g. "merge / merge after X / close">
```

Rules:

- Choices are concrete actions the owner can grant verbatim, never "thoughts?".
- Proof cites evidence, not intent: "CI green, 14 tests added, manual check of /login" rather than "should work".
- One brief per decision. Several pending PRs means several briefs, each self-contained.

## Contract 3: Decision-Ready Rule

Drive every item to **mergeable and proven** before asking the owner anything about it.

Decision-ready means:

- Branch rebased or merge-clean against the target.
- CI green, or the failure explained and shown to be pre-existing.
- Review comments addressed or answered.
- The claimed behavior verified, with the evidence named in the brief's Proof line.

Rules:

- Ask about a non-ready item only when the blocker itself needs an owner decision (scope change, conflicting requirement, missing access). Say so in the brief.
- Batch ready items. Present briefs together instead of interrupting per PR.
- The owner's time goes to choosing between finished options, not to project management.
