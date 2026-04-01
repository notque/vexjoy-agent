---
name: kairos-lite
description: Proactive monitoring — checks GitHub, CI, and toolkit health, produces briefings.
version: 1.0.0
user-invocable: true
command: kairos
context: fork
model: sonnet
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - WebFetch
routing:
  triggers:
    - morning briefing
    - what happened
    - check notifications
    - check CI
    - project status
    - what's new
    - monitoring
    - health check
    - kairos
  category: meta-tooling
  pairs_with:
    - auto-dream
---

Proactive monitoring and briefing agent. Runs between sessions via `cron + claude -p`, checks GitHub (PRs, CI, issues, dependabot), local repo state (stale branches, uncommitted changes), and toolkit health (hook errors, stale memories, state files). Produces structured briefings injected at session start.

## When to invoke

- User says "morning briefing", "what happened", "project status", "check notifications", "health check", "kairos"
- Invoked automatically by cron every 4 hours during business hours (quick scan — Category A only)
- Nightly deep scan at 2:30 AM (all categories)

## Instructions

When invoked interactively, read `skills/kairos-lite/monitor-prompt.md` and execute its phases directly. The prompt is self-contained — it describes the full monitoring cycle including check categories, output format, and file paths.

For cron invocation: the monitor prompt is passed directly to `claude -p` and runs as a standalone headless session with no CLAUDE.md, no hooks, no project context. All instructions are embedded in the prompt.

Requires `CLAUDE_KAIROS_ENABLED=true` environment variable. If not set, exit silently.

## Monitoring Categories

**Category A — Action Required** (quick and deep scans):
- PRs assigned to @me with open state
- Review requests pending for @me
- CI failures on watched branches
- Dependabot security alerts (critical and high severity)

**Category B — FYI** (deep scan only):
- New issues opened since last check
- Dependency updates available (non-security)
- Stale branches (> 7 days since last commit)
- Uncommitted changes on feature branches

**Category C — Toolkit Health** (deep scan only):
- Hook error rate from learning.db
- Stale memory files (> 14 days since last update)
- ADR backlog count (local `adr/` directory)
- State file accumulation in `~/.claude/state/`

## Phases

1. **LOAD CONFIG** — Read `~/.claude/config/kairos.json` for watched repos, branches, and thresholds. Determine scan mode from `KAIROS_MODE` env var.
2. **GITHUB CHECKS** — Run `gh` queries in parallel. Category A always; Category B added for deep scans.
3. **REPO CHECKS** — Check local repo state: stale branches, uncommitted changes. Deep scan only.
4. **TOOLKIT HEALTH** — Query learning.db for hook error rates, scan memory file mtimes, count state directory files. Deep scan only.
5. **COMPILE BRIEFING** — Aggregate findings into structured sections. Empty categories get explicit "all clear" entries.
6. **WRITE OUTPUT** — Write briefing atomically (write to `.tmp`, then rename) to `~/.claude/state/briefing-{project-hash}-{date}.md`.

## Output

Briefing written to `~/.claude/state/briefing-{project-hash}-{date}.md`.

The project hash uses the same encoding as `~/.claude/projects/` directory names (URL-encode the project path, replace `/` with `-`).

## Config

Read from `~/.claude/config/kairos.json`. Example structure:

```json
{
  "repos": [
    {"owner": "notque", "repo": "claude-code-toolkit", "branches": ["main"]}
  ],
  "thresholds": {
    "stale_branch_days": 7,
    "stale_memory_days": 14,
    "state_file_warn_count": 50
  }
}
```

## Quick vs Deep scan

| Mode | Trigger | Categories | Frequency |
|------|---------|------------|-----------|
| Quick | Default / every 4 hours business hours | A only | Every 4h (8 AM–6 PM) |
| Deep | `KAIROS_MODE=deep` / nightly | A + B + C | 2:30 AM nightly |

Set `KAIROS_MODE=deep` to force a deep scan interactively.

## Opt-in requirement

`CLAUDE_KAIROS_ENABLED=true` must be set in the environment. If absent, the skill exits 0 silently — no output, no error. This prevents accidental runs during toolkit development.

## Cost estimate

~$0.04 per quick run (Category A only, ~8-12K input tokens at Sonnet pricing).
~$0.08 per deep run (all categories, ~18-25K input tokens).
~$14/year for full automated operation (4h quick + nightly deep, 5-day business week).

## Cron setup

Use `crontab-manager.py` (not raw `crontab -e`) to install both schedules.

```bash
# Quick scan every 4 hours, 8 AM–6 PM business hours
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "kairos-quick" \
  --schedule "0 8,12,16 * * 1-5" \
  --command "CLAUDE_KAIROS_ENABLED=true /home/feedgen/claude-code-toolkit/scripts/kairos-cron.sh >> /home/feedgen/claude-code-toolkit/cron-logs/kairos/quick.log 2>&1"

# Deep scan nightly at 2:30 AM
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "kairos-deep" \
  --schedule "30 2 * * *" \
  --command "CLAUDE_KAIROS_ENABLED=true KAIROS_MODE=deep /home/feedgen/claude-code-toolkit/scripts/kairos-cron.sh >> /home/feedgen/claude-code-toolkit/cron-logs/kairos/deep.log 2>&1"

# Verify
python3 ~/.claude/scripts/crontab-manager.py verify --tag kairos-quick
python3 ~/.claude/scripts/crontab-manager.py verify --tag kairos-deep
```

## Testing

```bash
# Verify opt-in guard (should exit silently)
./scripts/kairos-cron.sh
echo "Exit: $?"

# Quick scan dry-run
CLAUDE_KAIROS_ENABLED=true ./scripts/kairos-cron.sh --dry-run

# Deep scan dry-run
CLAUDE_KAIROS_ENABLED=true KAIROS_MODE=deep ./scripts/kairos-cron.sh --dry-run

# Check output
ls ~/.claude/state/briefing-*.md | tail -1 | xargs cat

# Interactive invocation (reads monitor-prompt.md and executes directly)
# Just invoke this skill — it reads and runs the prompt inline
```

## Pairs with auto-dream

kairos-lite and auto-dream are complementary. auto-dream runs nightly at 2:07 AM and consolidates memories. kairos-lite runs at 2:30 AM and checks external state. The nightly deep scan can incorporate the dream report into the toolkit health section.

Session-start injection: if both `dream-injection-{project-hash}.md` and `briefing-{project-hash}-{date}.md` exist, load both. Briefing takes precedence for action items; dream injection takes precedence for memory context.
