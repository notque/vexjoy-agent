# Sync and PR creation

Read repository instructions and classify any protected-organization rules before mutation. Inspect current branch, working tree, upstream, unpushed commits, remote, and any existing PR. A clean tree may still have commits that need pushing.

If on a protected base branch, create a focused branch before committing. Stage only intended paths and follow [commit.md](commit.md). On a personal repository, run the risk-selected review before PR creation and reuse a current review.

Push the actual current branch with upstream tracking and verify `origin/<branch>..HEAD` is empty. `CLAUDE_GATE_BYPASS=1` is reserved for this skill’s submission path when the repository hook explicitly expects it; it is not a general bypass.

Create or update the PR with a body file. If `.adr-session.json` exists, run ADR coverage before push; only after an authorized merge, mark the ADR accepted, move it to the repository’s completed location, and clear the session according to repo tooling.

After push, bind CI observation to branch plus HEAD SHA. Protected-organization repositories stop after reporting the PR URL unless merge authority and repository policy clearly allow more. A rejected push should be reconciled with fetch/rebase; never overwrite a remote branch silently.
