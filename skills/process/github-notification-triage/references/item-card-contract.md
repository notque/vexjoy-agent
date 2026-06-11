# Item-Card Triage Contract

Output contract for triaging a queue of issues and PRs. Each item gets one card. Cards make the queue scannable: the owner reads URL + verdict first, detail only when needed.

## Card format

URL first. Every card opens with the item's full GitHub URL on its own line, then the fields below in order.

| Field | Content |
|-------|---------|
| What | One sentence: what the issue/PR asks or changes. |
| Why | The motivation or problem it addresses. |
| Author trust | Maintainer, known contributor, first-timer, or bot. Cite prior merged PRs when known. |
| Fit | How it matches project scope and conventions. |
| Risk | Blast radius: files touched, API/behavior changes, security or data paths. |
| Proof state | Evidence it works: CI status, tests added, repro steps, screenshots. State "unverified" when none. |
| Blocker | The single thing stopping progress (failing CI, missing review, unanswered question, conflict). "None" when clear. |
| Next action | One concrete step, named actor ("reply asking for repro", "merge", "close as duplicate"). |

Example card:

```
https://github.com/owner/repo/pull/123
What: Adds retry with backoff to the webhook sender.
Why: Webhooks drop on transient 5xx from receivers.
Author trust: Known contributor, 4 merged PRs.
Fit: Matches existing client retry pattern in net/client.go.
Risk: Low — one module, behavior gated behind config flag.
Proof state: CI green; unit tests cover backoff schedule.
Blocker: None.
Next action: Autonomous — review and merge.
```

## Classification: Autonomous vs Needs-owner

Every card ends with one of two labels inside Next action:

- **Autonomous** — the agent can complete the next action alone: replying with a question, labeling, closing an obvious duplicate, merging a green PR within granted authority, rebasing.
- **Needs-owner** — the action requires owner judgment or authority: scope decisions, breaking changes, security-sensitive merges, anything touching releases, money, or access.

When in doubt, label Needs-owner and state the decision the owner must make.

## Clean-checkout gate

Before any local work on an item (checking out a PR branch, running its tests, reproducing a bug):

1. Run `git status --short` in the target repo.
2. Proceed only when output is empty.
3. When the tree is dirty, stop local work for that item, mark its card Needs-owner with blocker "dirty working tree in `<repo>`", and continue triaging remaining items from API data only.

The gate keeps in-progress owner work safe from checkouts and test runs.
