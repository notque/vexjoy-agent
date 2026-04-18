---
name: github-notifications
description: "Triage GitHub notifications."
version: 1.0.0
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
routing:
  triggers:
    - github notifications
    - triage notifications
    - check notifications
    - gh notifications
  category: workflow
  complexity: Simple
---

# github-notifications

Triage GitHub notifications: fetch, classify, report actions needed.

## Usage

```
/do triage github notifications [--mark-read] [--save]
```

Default: report-only (shows what needs attention, doesn't modify anything)

- `--mark-read`: also mark informational notifications as read
- `--save`: save report to `~/.claude/reports/notifications/`

## Instructions

Parse any arguments from the user's request, then run:

```bash
python3 scripts/github-notification-triage.py $ARGUMENTS
```

Present the output to the user. If the report includes informational notifications and `--mark-read` was not passed, ask the user if they want to clear them.
