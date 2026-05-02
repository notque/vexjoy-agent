---
name: github-notification-triage
description: "Triage GitHub notifications and report actions needed."
user-invocable: false
context: fork
allowed-tools:
  - Bash
  - Read
  - Write
routing:
  triggers:
    - github notifications
    - triage notifications
    - check notifications
    - notification cleanup
    - github inbox
  pairs_with: []
  complexity: Simple
  category: github
---

# GitHub Notification Triage Skill

Fetch, classify, and report on GitHub notifications. The script does the heavy lifting — this skill orchestrates invocation and presents results.

## Commands

```bash
# Report-only (default)
python3 scripts/github-notification-triage.py

# Mark informational notifications as read after reporting
python3 scripts/github-notification-triage.py --mark-read

# Save report to ~/.claude/reports/notifications/
python3 scripts/github-notification-triage.py --save

# Cron/scheduled mode: auto-clear noise and save report
python3 scripts/github-notification-triage.py --mark-read --save
```

## Instructions

### Step 1: Run the triage script

```bash
python3 scripts/github-notification-triage.py
```

### Step 2: Present the report

Display script output directly. Classifications:
- **Action required** — PRs awaiting review, mentions, assigned issues
- **Informational** — CI results, bot comments, automated updates (safe to clear)

### Step 3: Handle follow-up

If user says "clean them up", "mark read", "clear the noise", or "yes" to clearing:

```bash
python3 scripts/github-notification-triage.py --mark-read
```

Confirm how many notifications were marked read.

### Cron/scheduled mode

When invoked on a schedule (no interactive user):

```bash
python3 scripts/github-notification-triage.py --mark-read --save
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Error (auth failure, API error, script not found) |
