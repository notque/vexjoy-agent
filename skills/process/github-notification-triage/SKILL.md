---
name: github-notification-triage
description: "Triage GitHub notifications and issue/PR queues."
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
    - triage issues
    - triage pull requests
    - pr queue
  pairs_with: []
  complexity: Simple
  category: github
---

# GitHub Notification Triage Skill

Fetch, classify, and report on GitHub notifications. The script does the heavy lifting — this skill orchestrates invocation and presents results.

## Commands

```bash
# Report-only (default): show what needs attention, no modifications
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

Run report-only by default:

```bash
python3 scripts/github-notification-triage.py
```

### Step 2: Present the report

Display the script output directly to the user. The report classifies notifications into:
- **Action required** — PRs awaiting review, mentions, assigned issues
- **Informational** — CI results, bot comments, automated updates (safe to clear)

### Step 3: Handle follow-up

If the user responds with any of the following, re-run with `--mark-read`:
- "clean them up"
- "mark read"
- "clear the noise"
- "yes" (in response to a prompt about clearing informational items)

```bash
python3 scripts/github-notification-triage.py --mark-read
```

Confirm how many notifications were marked read after the run completes.

### Cron/scheduled mode

When invoked on a schedule (no interactive user), use both flags to auto-clear and persist the report:

```bash
python3 scripts/github-notification-triage.py --mark-read --save
```

## Issue/PR Queue Triage

When the task is triaging a queue of issues or PRs (not just notifications), report one card per item using the contract in [references/item-card-contract.md](references/item-card-contract.md):

- URL-first card with fields: what, why, author trust, fit, risk, proof state, blocker, next action.
- Label each next action **Autonomous** or **Needs-owner**.
- Pass the clean-checkout gate (`git status --short` empty) before any local work on an item.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Error (auth failure, API error, script not found) |
