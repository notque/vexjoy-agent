---
description: "Reddit moderation: fetch modqueue, classify content, take mod actions"
argument-hint: "[--auto]"
allowed-tools: ["Read", "Bash"]
---

# /reddit-moderate

Moderate your Reddit community. Fetches the modqueue, classifies each item against
subreddit rules, and recommends actions for your approval.

## Usage

```
/reddit-moderate           # Interactive: fetch, analyze, confirm, act
/reddit-moderate --auto    # Auto mode: remove clear spam, skip uncertain
```

## Loop Mode

```
/loop 10m /reddit-moderate --auto
```

When invoked, load and follow the skill at `skills/reddit-moderate/SKILL.md`.

Parse the argument:
- No argument → run interactive mode (Phase 1-4)
- "--auto" → run auto mode
