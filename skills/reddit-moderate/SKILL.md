---
name: reddit-moderate
description: |
  Reddit community moderation via PRAW: fetch modqueue, classify content against
  subreddit rules, and take mod actions (approve, remove, lock). Supports interactive
  and auto modes. Use for "moderate reddit", "check modqueue", "reddit moderation",
  "mod queue", "reddit reports", "check subreddit".
version: 1.0.0
user-invocable: true
agent: python-general-engineer
allowed-tools:
  - Bash
  - Read
---

# Reddit Moderate

On-demand Reddit community moderation powered by PRAW. Fetches your modqueue,
classifies content against subreddit rules, and executes mod actions you confirm.

## Modes

| Mode | Invocation | Behavior |
|------|-----------|----------|
| **Interactive** | `/reddit-moderate` | Fetch queue → present with analysis → you confirm actions |
| **Auto** | `/loop 10m /reddit-moderate --auto` | Fetch queue → auto-remove high-confidence spam → flag rest |

## Prerequisites

```fish
# Required env vars (add to ~/.config/fish/conf.d/reddit.fish)
set -gx REDDIT_CLIENT_ID "your_client_id"
set -gx REDDIT_CLIENT_SECRET "your_secret"
set -gx REDDIT_USERNAME "your_username"
set -gx REDDIT_PASSWORD "your_password"
set -gx REDDIT_SUBREDDIT "your_subreddit"
```

Also: `pip install praw`

## Script Commands

```bash
# Fetch modqueue (items awaiting review)
python3 scripts/reddit_mod.py queue --limit 20

# Fetch reported items
python3 scripts/reddit_mod.py reports --limit 20

# Fetch unmoderated submissions
python3 scripts/reddit_mod.py unmoderated --limit 20

# Approve an item
python3 scripts/reddit_mod.py approve --id t3_abc123

# Remove an item with reason
python3 scripts/reddit_mod.py remove --id t3_abc123 --reason "Rule 3: No spam"

# Remove as spam
python3 scripts/reddit_mod.py remove --id t3_abc123 --reason "Spam" --spam

# Lock a thread
python3 scripts/reddit_mod.py lock --id t3_abc123

# Check user history
python3 scripts/reddit_mod.py user-history --username someuser --limit 10

# Fetch subreddit rules (for classification context)
python3 scripts/reddit_mod.py rules

# Fetch modmail
python3 scripts/reddit_mod.py modmail --limit 10

# Auto mode (for /loop): JSON output, recent items only
python3 scripts/reddit_mod.py queue --auto --since-minutes 15
```

## Instructions

### Interactive Mode (default)

**Phase 1: FETCH** — Get the modqueue and subreddit rules for context.

```bash
python3 scripts/reddit_mod.py rules
python3 scripts/reddit_mod.py queue --limit 25
```

Read both outputs. The rules define what's allowed in this community.

**Phase 2: PRESENT** — For each modqueue item, present a summary:

```
Item 1: [t3_abc123] "Post title here"
  Author: u/username (score: 5, reports: 2)
  Report reasons: "spam", "off-topic"
  Body: [first 200 chars of content]
  Analysis: Likely violates Rule 3 (self-promotion) — author history shows
            5 promotional posts in 7 days with no community engagement.
  Recommendation: REMOVE (reason: Rule 3)

Item 2: [t1_def456] "Comment text here"
  Author: u/other_user (score: 12, reports: 1)
  Report reason: "rude"
  Analysis: Sarcastic but within community norms. Report appears frivolous.
  Recommendation: APPROVE
```

If user history would help classify an item, fetch it:
```bash
python3 scripts/reddit_mod.py user-history --username suspicious_user --limit 10
```

**Phase 3: CONFIRM** — Ask the user to confirm or override recommendations.
Wait for user input. Do not proceed without explicit confirmation.

**Phase 4: ACT** — Execute confirmed actions:

```bash
python3 scripts/reddit_mod.py approve --id t1_def456
python3 scripts/reddit_mod.py remove --id t3_abc123 --reason "Rule 3: Self-promotion"
```

Report results after each action.

### Auto Mode (for /loop)

When invoked with `--auto` argument or when the user says "auto mode":

1. Fetch queue with auto flag:
   ```bash
   python3 scripts/reddit_mod.py queue --auto --since-minutes 15
   ```

2. Parse the JSON output. For each item, classify:
   - **CLEAR SPAM** (confidence >95%): obvious spam, scam links, gibberish → auto-remove
   - **CLEAR VIOLATION** (confidence >90%): unambiguous rule violation → auto-remove
   - **CLEAR SAFE** (confidence >90%): obviously fine content, frivolous report → auto-approve
   - **UNCERTAIN**: anything else → skip (leave for human review)

3. Execute auto-actions:
   ```bash
   python3 scripts/reddit_mod.py remove --id ID --reason "Auto-mod: spam" --spam
   python3 scripts/reddit_mod.py approve --id ID
   ```

4. Output a summary of actions taken and items skipped.

**Critical auto-mode rules:**
- NEVER auto-ban users — bans always require human review
- NEVER auto-lock threads — locks always require human review
- When in doubt, SKIP — false negatives are better than false positives
- Log every auto-action for the user to review later

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime error (network, API, invalid ID) |
| 2 | Configuration error (missing credentials, missing praw) |
