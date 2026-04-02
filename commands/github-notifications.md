---
description: "Triage GitHub notifications: fetch, classify, report actions needed."
argument-hint: "[--mark-read] [--save]"
allowed-tools: ["Bash", "Read", "Write"]
---

Triage GitHub notifications: fetch, classify, report actions needed.

Usage: /github-notifications [--mark-read] [--save]

Default: report-only (shows what needs attention, doesn't modify anything)
--mark-read: also mark informational notifications as read
--save: save report to ~/.claude/reports/notifications/

Invokes: scripts/github-notification-triage.py

## Instructions for Claude

**Arguments:** "$ARGUMENTS"

Parse arguments from `$ARGUMENTS`, then run:

```bash
python3 scripts/github-notification-triage.py $ARGUMENTS
```

Present the output to the user. If the report includes informational notifications and `--mark-read` was not passed, ask the user if they want to clear them.
