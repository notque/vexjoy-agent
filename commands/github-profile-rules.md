# GitHub Profile Rules Pipeline

## Domain
`github-profile-rules` — extract programming rules and coding conventions from a GitHub user's public profile via API.

## Agent
`github-profile-rules-engineer` (new)
- Triggers: github rules, profile analysis, coding style extraction, github conventions, programming rules
- Category: meta
- Complexity: Medium

## Skills

### github-profile-rules (main orchestration)
- Triggers: github rules, profile analysis, coding style extraction, github conventions, programming rules extraction
- 7-phase pipeline: PROFILE SCAN -> CODE ANALYSIS -> REVIEW MINING -> PATTERN SYNTHESIS -> RULES GENERATION -> VALIDATION -> OUTPUT
- User-invocable: yes

### Subdomain Skills
| Skill | Triggers | Task Type |
|-------|----------|-----------|
| github-profile-rules-repo-analysis | github repo analysis, code pattern extraction, api repo scanning | analysis |
| github-profile-rules-pr-review | pr review mining, review pattern analysis, developer preference extraction | analysis |
| github-profile-rules-synthesis | rules compilation, pattern deduplication, confidence scoring | analysis |
| github-profile-rules-validation | rules validation, contradiction detection, rule quality check | analysis |

## Scripts
| Script | Purpose |
|--------|---------|
| `scripts/github-api-fetcher.py` | GitHub REST API client: repos, file contents, PR reviews |
| `scripts/rules-compiler.py` | Deduplication, confidence scoring, markdown/JSON formatting |

## Reference Files
| File | Location |
|------|----------|
| `rule-categories.md` | `skills/workflow/references/github-profile-rules/references/` |

## Component Graph
```
github-profile-rules-engineer (agent)
  ├── github-profile-rules (main skill)
  │     ├── references/rule-categories.md
  │     ├── invokes: scripts/github-api-fetcher.py
  │     └── invokes: scripts/rules-compiler.py
  ├── github-profile-rules-repo-analysis (subdomain skill)
  ├── github-profile-rules-pr-review (subdomain skill)
  ├── github-profile-rules-synthesis (subdomain skill)
  └── github-profile-rules-validation (subdomain skill)
```

## Usage
```
/do extract programming rules from github user {username}
/do analyze coding style of github profile {username}
/do generate CLAUDE.md rules from {username}'s github
```
