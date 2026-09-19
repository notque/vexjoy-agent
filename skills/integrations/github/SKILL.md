---
name: github
description: "GitHub: notification triage, profile rule extraction."
user-invocable: false
context: fork
allowed-tools:
  - Bash
  - Read
  - Write
routing:
  not_for: "git commit/push/PR operations (use pr-workflow)"
  triggers:
    - github notifications
    - triage notifications
    - check notifications
    - notification cleanup
    - github inbox
    - triage issues
    - triage pull requests
    - pr queue
    - github profile rules
    - profile conventions
  pairs_with: []
  complexity: Simple
  category: github
---

# GitHub Skill

GitHub notification triage and issue/PR queue classification.

## Mode Selection

| Request | Mode |
|---|---|
| Notifications, inbox, cleanup | **Notification Triage** |
| Issue or PR queue, review items | **Queue Triage** |

---

## Notification Triage

Fetch, classify, and report GitHub notifications via the triage script.

### Commands

```bash
# Report-only (default)
python3 scripts/github-notification-triage.py

# Mark informational notifications as read
python3 scripts/github-notification-triage.py --mark-read

# Save report to ~/.claude/reports/notifications/
python3 scripts/github-notification-triage.py --save

# Cron/scheduled: auto-clear noise and save
python3 scripts/github-notification-triage.py --mark-read --save
```

### Steps

1. Run report-only: `python3 scripts/github-notification-triage.py`.
2. Display the output. The report classifies notifications as:
   - **Action required** -- PRs awaiting review, mentions, assigned issues.
   - **Informational** -- CI results, bot comments, automated updates.
3. If the user says "clean them up", "mark read", "clear the noise", or "yes"
   to clearing informational items, re-run with `--mark-read`. Confirm how many
   were marked read.

Scheduled (no interactive user): run with `--mark-read --save`.

Exit codes: 0 = success, 1 = error (auth, API, script not found).

---

## Queue Triage

When triaging a queue of issues or PRs (not just notifications), produce one
card per item.

### Card Format

Open each card with the item's full GitHub URL on its own line, then these
fields in order:

| Field | Content |
|---|---|
| What | One sentence: what the issue/PR asks or changes. |
| Why | Motivation or problem it addresses. |
| Author trust | Maintainer, known contributor, first-timer, or bot. Cite prior merged PRs. |
| Fit | Match to project scope and conventions. |
| Risk | Blast radius: files touched, API/behavior changes, security or data paths. |
| Proof state | CI status, tests added, repro steps, screenshots. "Unverified" when none. |
| Blocker | Single thing stopping progress, or "None". |
| Next action | One concrete step with named actor. Label **Autonomous** or **Needs-owner**. |

Example:

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

### Autonomous vs Needs-owner

- **Autonomous** -- the agent can complete the action alone: reply with a
  question, label, close an obvious duplicate, merge a green PR within granted
  authority, rebase.
- **Needs-owner** -- requires owner judgment: scope decisions, breaking changes,
  security-sensitive merges, releases, money, or access.

When in doubt, label Needs-owner and state the decision the owner must make.

### Clean-Checkout Gate

Before any local work on an item (checkout, tests, repro):

1. Run `git status --short`.
2. Proceed only when output is empty.
3. If dirty, mark the card Needs-owner with blocker "dirty working tree in
   `<repo>`" and continue triaging from API data only.
