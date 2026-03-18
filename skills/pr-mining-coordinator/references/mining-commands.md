# PR Mining Command Reference

## Basic Mining Patterns

### Mine Last 100 PRs from Single Repo
```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py \
    your-org/go-libs \
    mined_data/go_bits_all_2025-11-29.json \
    --limit 100 --summary" &
```

### Mine Specific Reviewer
```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py \
    your-org/go-libs \
    mined_data/senior-reviewer_go_bits_2025-11-29.json \
    --reviewer senior-reviewer --all-comments --limit 100 --summary" &
```

### Mine Multiple Repos
```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py \
    your-org/go-libs,your-org/service-a,your-org/service-b \
    mined_data/go_repos_all_2025-11-29.json \
    --limit 100 --summary" &
```

## Advanced Mining Patterns

### Date Range Mining
```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py \
    your-org/service-a \
    mined_data/api_server_2025_q4.json \
    --since 2025-10-01 --until 2025-12-31 --limit 200 --summary" &
```

### Comprehensive Team Analysis (All Reviewers, Multiple Repos)
```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py \
    your-org/go-libs,your-org/service-a,your-org/service-b,your-org/service-c \
    mined_data/go_team_2025-11-29.json \
    --limit 150 --summary" &
```

### Senior Reviewer Deep Dive (All Comments, Multiple Repos)
```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py \
    your-org/go-libs,your-org/service-a \
    mined_data/senior-reviewer_patterns_2025-11-29.json \
    --reviewer senior-reviewer --all-comments --limit 200 --summary" &
```

## Command Flag Reference

### Required Arguments
- `repos`: Repository list (comma-separated, format: `owner/repo`)
- `output`: Output JSON file path (relative to pr-miner directory)

### Optional Flags
| Flag | Description | Default |
|------|-------------|---------|
| `--reviewer {username}` | Filter to specific reviewer's comments | All reviewers |
| `--all-comments` | Include all comment types (not just imperative) | Imperative only |
| `--limit {number}` | Maximum PRs to analyze | 100 |
| `--since {YYYY-MM-DD}` | Start date for PR range | No limit |
| `--until {YYYY-MM-DD}` | End date for PR range | No limit |
| `--summary` | Print mining summary statistics | Off |

## Output Naming Conventions

### Reviewer-Specific Mining
Format: `{reviewer}_{repos}_{date}.json`

Examples:
- `senior-reviewer_go_libs_2025-11-29.json`
- `senior-reviewer_go_all_2025-11-29.json`

### Team/All Reviewers Mining
Format: `{repos}_all_{date}.json`

Examples:
- `go_libs_all_2025-11-29.json`
- `api_server_metrics_service_all_2025-11-29.json`

### Multiple Repos Naming
Use underscores to separate repo names:
- `go_libs_api_server` for go-libs + api-server
- `go_libs_api_server_metrics_service` for three repos

### Date Ranges
Use descriptive date names for periodic analysis:
- `go_libs_2025_q1.json` for Q1 2025
- `api_server_2025_q4.json` for Q4 2025

## Directory Structure

All mining operations use fixed paths under `~/.claude/skills/pr-miner/`:

```
~/.claude/skills/pr-miner/
  scripts/miner.py          # Mining tool
  venv/                     # Python virtual environment
  mined_data/               # Mining output (JSON)
  rules/                    # Generated coding rules (markdown)
```

## Concurrent Mining Management

**Strategy**: Run jobs sequentially to avoid GitHub API rate limits (5000 requests/hour shared).

**Pattern**:
1. Start job 1, wait for completion
2. Start job 2, wait for completion
3. Generate combined rules from all results

**Never**: Run 3+ mining jobs in parallel (causes rate limit exhaustion).

## Typical Mining Session Workflow

1. Validate prerequisites (token, miner script, reviewer username)
2. Start mining job in background
3. Track progress with BashOutput (every 30-60 seconds)
4. When complete, verify output file has valid interactions
5. Generate categorized coding rules from mined data
6. Save rules to rules/ directory
7. Report results to user

Total time: 2-5 minutes for 100 PRs (depending on repo size and API response time).
