# Reddit Moderation Templates

This directory contains template files for the `reddit-data/{subreddit}/` local data directory. The `reddit-data/` directory is gitignored because it contains subreddit-specific context, audit logs, and potentially sensitive moderator notes that should not be committed to the repository.

## How setup works

When you run the setup command for a new subreddit:

```bash
python3 scripts/reddit_mod.py setup --subreddit mysubreddit
```

The script:

1. Creates the `reddit-data/mysubreddit/` directory
2. Auto-generates `rules.md` by fetching sidebar and formal rules from Reddit
3. Auto-generates `mod-log-summary.md` by analyzing the last 500 mod log entries
4. Auto-generates `repeat-offenders.json` from mod log removal patterns
5. Creates a minimal `moderator-notes.md` stub for you to fill in manually (the full 7-section template is available at `templates/reddit/moderator-notes.md.template`)
6. Creates `config.json` with default settings from the template below

## Template files

### `moderator-notes.md.template`

**Purpose:** Template for the human-written moderator notes file. This is the only file in `reddit-data/{subreddit}/` that requires manual input -- everything else is auto-generated or has sensible defaults.

**What it contains:** Sections for documenting spam patterns, community norms, content redirection rules, false-report patterns, trusted domains, and known bad actors. The classifier reads this file to understand context that cannot be auto-detected from the Reddit API.

**Usage:** After running `setup`, open `reddit-data/{subreddit}/moderator-notes.md` and replace the example entries with real patterns from your community. Sections left empty are ignored by the classifier.

### `config.json.template`

**Purpose:** Template for per-subreddit configuration. Controls confidence thresholds, auto-action limits, language enforcement, and proactive scanning defaults.

**What each field does:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `confidence_auto_approve` | int (0-100) | 95 | Minimum confidence to auto-approve false/abusive reports |
| `confidence_auto_remove` | int (0-100) | 90 | Minimum confidence to auto-remove rule-violating content |
| `trust_reporters` | bool | true | Default to trusting community reports |
| `community_type` | string | "professional-technical" | Community tone for classifier calibration |
| `max_auto_actions_per_run` | int | 25 | Safety cap on auto-actions per run |
| `required_language` | string or null | null | ISO 639-1 code for required language, or null for any (planned — not yet implemented) |
| `scan_recent_hours` | int | 24 | Default time window for proactive scanning (planned — not yet implemented) |
| `scan_limit` | int | 50 | Default item limit for proactive scanning (planned — not yet implemented) |

**Note:** The template file uses `_comment_*` keys to document each field inline. These comment keys are ignored by the scripts -- only the actual config keys are read. When the `setup` command generates `config.json`, it produces a clean file without the comment keys.

## Directory structure after setup

```
reddit-data/
  {subreddit}/
    rules.md                  # Auto-generated: sidebar + formal rules from Reddit API
    mod-log-summary.md        # Auto-generated: mod log pattern analysis (500 entries)
    moderator-notes.md        # Manual: human-written context (from template)
    repeat-offenders.json     # Auto-generated: authors with repeat removals
    config.json               # Configuration: thresholds, language, scan settings
    audit.jsonl               # Runtime: classification decisions and action log
```

## Multi-subreddit support

Each subreddit gets its own directory under `reddit-data/`. Run `setup` once per subreddit:

```bash
python3 scripts/reddit_mod.py setup --subreddit subreddit_one
python3 scripts/reddit_mod.py setup --subreddit subreddit_two
```

Switch between subreddits via the `REDDIT_SUBREDDIT` environment variable or the `--subreddit` CLI flag.
