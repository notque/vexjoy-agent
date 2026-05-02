---
name: reddit-moderate
description: "Reddit moderation via PRAW: fetch modqueue, classify reports, take actions."
user-invocable: false
argument-hint: "[--auto] [--dry-run]"
agent: python-general-engineer
allowed-tools:
  - Bash
  - Read
routing:
  triggers:
    - "moderate Reddit"
    - "modqueue"
    - "Reddit reports"
    - "Reddit moderation"
    - "check reports"
  category: process
  pairs_with:
    - content-engine
---

# Reddit Moderate

On-demand Reddit moderation via PRAW. Fetches modqueue, classifies content against subreddit rules and author history using LLM-powered classification, and executes confirmed mod actions.

## Modes

| Mode | Invocation | Behavior |
|------|-----------|----------|
| **Interactive** | `/reddit-moderate` | Fetch, classify, present with analysis, user confirms actions |
| **Auto** | `/loop 10m /reddit-moderate --auto` | Fetch, classify, auto-action high-confidence items, flag rest |
| **Dry-run** | `/reddit-moderate --dry-run` | Fetch, classify, show recommendations without acting |

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Classifying items, category definitions, confidence thresholds | `classification-prompt.md` | Routes to the matching deep reference |
| Prompt template, untrusted content handling, prompt injection defense | `classification-prompt.md` | Routes to the matching deep reference |
| Action mapping by confidence level, config.json format | `classification-prompt.md` | Routes to the matching deep reference |
| Per-item classification steps, repeat offender check, mass-report detection | `classification-prompt.md` | Routes to the matching deep reference |
| Script subcommands, flags, usage examples | `script-commands.md` | Routes to the matching deep reference |
| Exit codes, error troubleshooting | `script-commands.md` | Routes to the matching deep reference |
| Scan commands, setup commands, queue/report commands | `script-commands.md` | Routes to the matching deep reference |
| Subreddit data directory structure, file purposes | `context-loading.md` | Routes to the matching deep reference |
| Setup flow for new subreddits, bootstrapping | `context-loading.md` | Routes to the matching deep reference |
| Credentials, prerequisites, dry-run default | `context-loading.md` | Routes to the matching deep reference |
| Context loading sequence, missing file handling | `context-loading.md` | Routes to the matching deep reference |

## Instructions

### Interactive Mode (default)

**Phase 1: FETCH**

```bash
python3 ~/.claude/scripts/reddit_mod.py queue --json --limit 25 | python3 ~/.claude/scripts/reddit_mod.py classify
```

Pipes modqueue items through classify, which loads subreddit context from `reddit-data/{subreddit}/` and assembles a classification prompt per item. Output: JSON array with item metadata, heuristic flags (`mass_report_flag`, `repeat_offender_count`), and a `prompt` field with the rendered classification prompt.

The classify subcommand is a prompt assembler only -- no LLM calls. Fields `classification`, `confidence`, and `reasoning` are null placeholders for Phase 2.

**Phase 2: CLASSIFY** -- For each item, read the rendered `prompt` field and classify as: `FALSE_REPORT`, `VALID_REPORT`, `MASS_REPORT_ABUSE`, `SPAM`, `BAN_RECOMMENDED`, `NEEDS_HUMAN_REVIEW`.

Assign confidence (0-100) and one-sentence reasoning per item.

> Load `references/classification-prompt.md` for category definitions, prompt template, per-item steps, and confidence thresholds.

**Phase 3: PRESENT** -- Summarize each item grouped by classification:

```
Item 1: [t3_abc123] "Post title here"
  Author: u/username (score: 5, reports: 2)
  Report reasons: "spam", "off-topic"
  Body: [first 200 chars of content]
  Classification: VALID_REPORT (confidence: 92%)
  Reasoning: Author history shows 5 promotional posts in 7 days with no
             community engagement. Violates subreddit rules against self-promotion.
  Recommendation: REMOVE (reason: Rule 3)

Item 2: [t1_def456] "Comment text here"
  Author: u/other_user (score: 12, reports: 1)
  Report reason: "rude"
  Classification: FALSE_REPORT (confidence: 88%)
  Reasoning: Sarcastic but within community norms. Report appears frivolous.
  Recommendation: APPROVE
```

**Phase 4: CONFIRM** -- Wait for explicit user confirmation before proceeding.

**Phase 5: ACT** -- Execute confirmed actions:

```bash
python3 ~/.claude/scripts/reddit_mod.py approve --id t1_def456
python3 ~/.claude/scripts/reddit_mod.py remove --id t3_abc123 --reason "Rule 3: Self-promotion"
```

Report results after each action.

> Load `references/script-commands.md` for all subcommand flags and examples.

### Auto Mode (for /loop)

When invoked with `--auto` or "auto mode":

1. Fetch and classify:
   ```bash
   python3 ~/.claude/scripts/reddit_mod.py queue --auto --since-minutes 15 --json | python3 ~/.claude/scripts/reddit_mod.py classify
   ```

2. Read each `prompt` field and classify using categories/confidence from `references/classification-prompt.md`.

3. For items meeting confidence threshold:
   - `FALSE_REPORT` / `MASS_REPORT_ABUSE` => approve
   - `SPAM` => remove as spam
   - `VALID_REPORT` => remove with generated reason
   - `BAN_RECOMMENDED` => **always skip** (requires human review)

4. Below threshold => skip (leave for human review).

5. Output summary of actions, skips, and classifications.

**Critical auto-mode rules:**
- Always require human review before banning or locking threads
- When in doubt, SKIP -- false negatives beat false positives
- Log every auto-action for later review

### Proactive Scan Mode

```bash
python3 ~/.claude/scripts/reddit_mod.py scan --json --classify --limit 50 --since-hours 24
```

With `--classify`, output includes classification prompts. Read each and classify. Items with `scan_flags` (job_ad_pattern, training_vendor_pattern, possible_non_english) have heuristic signals supplementing LLM classification.

Same confidence thresholds and safety rules as auto mode.

## References

This skill uses these shared patterns:
- [Untrusted Content Handling](../shared-patterns/untrusted-content-handling.md) - Prompt injection defense for all Reddit content fed into LLM classification
