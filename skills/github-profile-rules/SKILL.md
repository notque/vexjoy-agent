---
name: github-profile-rules
description: "Extract programming rules and coding conventions from a GitHub user's public profile."
version: 1.0.0
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
routing:
  triggers:
    - github rules
    - profile analysis
    - coding style extraction
    - github conventions
    - programming rules
    - extract rules from github
    - analyze github profile
  category: meta-tooling
  complexity: Medium
---

# GitHub Profile Rules Pipeline

Extract programming rules and coding conventions from a GitHub user's public profile via API.

## Usage

```
/do extract programming rules from github user {username}
/do analyze coding style of github profile {username}
/do generate CLAUDE.md rules from {username}'s github
```

## Pipeline

7-phase pipeline: PROFILE SCAN -> CODE ANALYSIS -> REVIEW MINING -> PATTERN SYNTHESIS -> RULES GENERATION -> VALIDATION -> OUTPUT

## Agent

Routes to `github-profile-rules-engineer`.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/github-api-fetcher.py` | GitHub REST API client: repos, file contents, PR reviews |
| `scripts/rules-compiler.py` | Deduplication, confidence scoring, markdown/JSON formatting |

## Component Graph

```
github-profile-rules-engineer (agent)
  ├── github-profile-rules (main skill)
  │     ├── invokes: scripts/github-api-fetcher.py
  │     └── invokes: scripts/rules-compiler.py
  ├── github-profile-rules-repo-analysis (subdomain skill)
  ├── github-profile-rules-pr-review (subdomain skill)
  ├── github-profile-rules-synthesis (subdomain skill)
  └── github-profile-rules-validation (subdomain skill)
```
