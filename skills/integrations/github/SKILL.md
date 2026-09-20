---
name: github
description: "Triage GitHub notifications and issue/PR queues; excludes commit, push, and PR lifecycle work."
user_invocable: false
context: fork
allowed-tools: [Bash, Read, Write]
routing:
  not_for: "git commit/push/PR operations (use pr-workflow)"
  triggers: [github notifications, triage notifications, notification cleanup, github inbox, triage issues, triage pull requests, pr queue, github profile rules]
  complexity: Simple
  category: github
---

# GitHub triage

## Notifications

Use the repository script; report-only is the interactive default:

```bash
python3 scripts/github-notification-triage.py
python3 scripts/github-notification-triage.py --mark-read   # only when clearing was requested
python3 scripts/github-notification-triage.py --save        # save under ~/.claude/reports/notifications/
```

For a scheduled run, use `--mark-read --save`. The script separates action-required items from informational noise. Report what it marked read. Exit `1` means auth/API/script failure.

## Issue/PR queues

Open each card with its full URL, then report: `What`, `Why`, `Author trust` (with prior merged-PR evidence), `Fit`, `Risk`, `Proof state`, one `Blocker`, and one named-actor `Next action`.

Label the action:

- `Autonomous`: action is both permitted and executable without owner judgment.
- `Needs-owner`: scope, breaking change, sensitive merge, release, money/access, or missing authority. Name the decision needed.

Before checkout, tests, or reproduction, run `git status --short`. If nonempty, do not disturb the tree; continue from API evidence and record `Needs-owner — dirty working tree in <repo>`.
