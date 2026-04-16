# Script Commands Reference

> **Scope**: All reddit_mod.py subcommands, flags, usage examples, and exit codes. Does NOT cover classification logic or workflow phases.
> **Version range**: All toolkit versions using `~/.claude/scripts/reddit_mod.py`
> **Generated**: 2026-04-16

---

## Overview

`reddit_mod.py` is the deterministic backbone of reddit-moderate. It handles Reddit API calls via PRAW, outputs structured data for LLM classification, and executes mod actions. The script never calls an LLM itself; all classification happens in the Claude session that invokes this skill.

---

## Queue and Report Commands

```bash
# Fetch modqueue (items awaiting review)
python3 ~/.claude/scripts/reddit_mod.py queue --limit 20

# Fetch reported items
python3 ~/.claude/scripts/reddit_mod.py reports --limit 20

# Fetch unmoderated submissions
python3 ~/.claude/scripts/reddit_mod.py unmoderated --limit 20

# Auto mode (for /loop): JSON output, recent items only
python3 ~/.claude/scripts/reddit_mod.py queue --auto --since-minutes 15

# Pipe queue through classify for LLM-ready prompts
python3 ~/.claude/scripts/reddit_mod.py queue --json --limit 25 | python3 ~/.claude/scripts/reddit_mod.py classify

# Auto mode with classify
python3 ~/.claude/scripts/reddit_mod.py queue --auto --since-minutes 15 --json | python3 ~/.claude/scripts/reddit_mod.py classify
```

---

## Mod Action Commands

```bash
# Approve an item
python3 ~/.claude/scripts/reddit_mod.py approve --id t3_abc123

# Remove an item with reason
python3 ~/.claude/scripts/reddit_mod.py remove --id t3_abc123 --reason "Rule 3: No spam"

# Remove as spam
python3 ~/.claude/scripts/reddit_mod.py remove --id t3_abc123 --reason "Spam" --spam

# Lock a thread
python3 ~/.claude/scripts/reddit_mod.py lock --id t3_abc123
```

---

## Information Commands

```bash
# Check user history
python3 ~/.claude/scripts/reddit_mod.py user-history --username someuser --limit 10

# Fetch subreddit rules (for classification context)
python3 ~/.claude/scripts/reddit_mod.py rules

# Fetch modmail
python3 ~/.claude/scripts/reddit_mod.py modmail --limit 10

# View subreddit info (sidebar rules, subscribers, etc.)
python3 ~/.claude/scripts/reddit_mod.py subreddit-info

# Generate mod log analysis
python3 ~/.claude/scripts/reddit_mod.py mod-log-summary --limit 500
```

---

## Setup and Scan Commands

```bash
# Bootstrap subreddit data directory
python3 ~/.claude/scripts/reddit_mod.py setup

# Scan recent posts for unreported violations (heuristic flags only)
python3 ~/.claude/scripts/reddit_mod.py scan --limit 50 --since-hours 24

# Scan with classification prompts (JSON for LLM evaluation)
python3 ~/.claude/scripts/reddit_mod.py scan --json --classify --limit 50 --since-hours 24
```

The `--classify` flag on scan builds classification prompts internally (same `build_classification_prompt()` as the classify subcommand). Without `--json`, scan shows a summary with a note to use `--json` for full prompts.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime error (network, API, invalid ID) |
| 2 | Configuration error (missing credentials, missing praw) |
