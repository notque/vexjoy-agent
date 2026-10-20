# PR Fix Loop: Review Checklist

Load in Phase 1. Every applicable item is tested or marked N/A with a reason. A domain overlay adds its own items to the end of each list.

## Comment collection

Comments live on the PR's base repo. Resolve it from the PR URL, so the commands work from a fork checkout too:

```bash
REPO=$(gh pr view "$PR" --json url -q .url | cut -d/ -f4-5)   # owner/name of the base repo
gh api --paginate "repos/$REPO/pulls/$PR/reviews"          # bot overview and review bodies
gh api --paginate "repos/$REPO/pulls/$PR/comments"         # inline comments, with commit_id and path:line
gh api --paginate "repos/$REPO/issues/$PR/comments"        # conversation comments
```

On a GitHub Enterprise Server host, add `--hostname <host>` (the third field of the PR URL).

Write one file per PR, for example `pr-<n>-comments.md`, with each comment's source, `commit_id`, `path:line`, and status: open, fixed in `<sha>`, or invalid (reason in a local file).

A comment made on an older commit may already be fixed. Check it against the current head before acting.

## Render check

Judge what users see, not the config that produces it.

**Any change**

Run the changed output the way a user meets it: CLI output, API responses, rendered docs, generated config, or UI. Record the before and after output for the same input.

**Observability changes (dashboards, alerts, metrics)**

Dashboards:

1. Load the dashboard in the real UI against live data.
2. Screenshot every panel.
3. Compare each panel's value to an independent source, such as a direct query or the system's own counter.
4. Record per panel: shown value, independent value, match or mismatch.

Alerts:

1. Run the rule unit-test tool (for Prometheus, `promtool test rules`) against real label sets, including extra labels the series carries in production.
2. Evaluate each expression on the last 24h of live data.
3. Per alert, record: would it fire now, and would that be noise.

## Edge cases

**Generic (every PR)**

| # | Case | What to check |
|---|------|---------------|
| G1 | Upgrade path | Existing installs and configs keep working after the change; defaults did not shift silently |
| G2 | Other consumers | Other users of the same module, chart, or API see no unintended change |
| G3 | Error paths | Failure and empty-input paths behave as before or better |
| G4 | Alternate paths | Every code or data path that reaches the change behaves the same; paused paths count as live |

**Observability changes**

| # | Case | What to check |
|---|------|---------------|
| O1 | Rollout and restart | Terminated pods still inside rate windows; counter resets on restart or OOM |
| O2 | Multiple installs | Two or more installs in one metrics backend; selectors and aggregation keep them apart |
| O3 | Absent series | Series missing at start; counters that only appear after the first failure |
| O4 | Failover-level failure | Every failover level failing at once, not just the primary |
| O5 | Shared charts | Other teams' installs use the same chart; defaults and value changes affect them |
| O6 | Peak shape | Message size and batch shape at peak volume, including volume from paused paths |

## Re-review rules

- Re-verify each claim in the PR body and in review comments against live data, read-only.
- Use paused-path data as the baseline, not today's reduced traffic.
- Quote the query and the number for every claim you confirm or reject.
