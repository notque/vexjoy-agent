---
description: "Extract programming rules and coding conventions from a GitHub user's public profile via API."
argument-hint: "<github-username>"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Skill"]
---

# GitHub Profile Rules Pipeline

Extract programming rules and coding conventions from a GitHub user's public profile via API.

## Instructions

Call the Skill tool with `toolkit`, then read `skills/meta/toolkit/references/github-profile-rules.md` and `skills/meta/toolkit/references/github-profile-rules/rule-categories.md`.

## Phases

7-phase pipeline: `PROFILE SCAN -> CODE ANALYSIS -> REVIEW MINING -> PATTERN SYNTHESIS -> RULES GENERATION -> VALIDATION -> OUTPUT`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/github-api-fetcher.py` | GitHub REST API client: repos, file contents, PR reviews |
| `scripts/rules-compiler.py` | Deduplication, confidence scoring, markdown/JSON formatting |

## Usage

```
/do extract programming rules from github user {username}
/do analyze coding style of github profile {username}
/do generate CLAUDE.md rules from {username}'s github
```

ARGUMENTS: $ARGUMENTS
