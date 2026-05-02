---
name: kairos-lite
description: Proactive monitoring — checks GitHub, CI, and toolkit health, produces briefings.
user-invocable: true
command: kairos
context: fork
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
- Cron every 4 hours during business hours (quick scan — Category A only)
- Nightly deep scan at 2:30 AM (all categories)

## Instructions

When invoked interactively, read `skills/kairos-lite/monitor-prompt.md` and execute its phases directly. The prompt is self-contained.

For cron: the monitor prompt is passed directly to `claude -p` as a standalone headless session (no CLAUDE.md, no hooks, no project context).

Requires `CLAUDE_KAIROS_ENABLED=true`. If not set, exit silently.

## Monitoring Categories

**Category A — Action Required** (quick and deep):
- PRs assigned to @me (open)
- Review requests pending for @me
- CI failures on watched branches
- Dependabot security alerts (critical/high)

**Category B — FYI** (deep only):
- New issues since last check
- Non-security dependency updates
- Stale branches (> 7 days)
- Uncommitted changes on feature branches

**Category C — Toolkit Health** (deep only):
- Hook error rate from learning.db
- Stale memory files (> 14 days)
- ADR backlog count (local `adr/`)
- State file accumulation in `~/.claude/state/`

## Phases

1. **LOAD CONFIG** — Read `~/.claude/config/kairos.json` for watched repos, branches, thresholds. Determine scan mode from `KAIROS_MODE`.
2. **GITHUB CHECKS** — `gh` queries in parallel. Category A always; Category B for deep scans.
3. **REPO CHECKS** — Stale branches, uncommitted changes. Deep only.
4. **TOOLKIT HEALTH** — Hook error rates, memory file mtimes, state directory counts. Deep only.
5. **COMPILE BRIEFING** — Aggregate findings. Empty categories get "all clear" entries.
6. **WRITE OUTPUT** — Write atomically (`.tmp` then rename) to `~/.claude/state/briefing-{project-hash}-{date}.md`.

## Output

Briefing at `~/.claude/state/briefing-{project-hash}-{date}.md`. Project hash uses same encoding as `~/.claude/projects/` directory names (URL-encode path, replace `/` with `-`).

## Config

`~/.claude/config/kairos.json`:

```json
{
  "repos": [
    {"owner": "notque", "repo": "vexjoy-agent", "branches": ["main"]}
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
| Quick | Default / every 4 hours business hours | A only | Every 4h (8 AM-6 PM) |
| Deep | `KAIROS_MODE=deep` / nightly | A + B + C | 2:30 AM nightly |

Set `KAIROS_MODE=deep` to force deep scan interactively.

## Opt-in requirement

`CLAUDE_KAIROS_ENABLED=true` must be set. If absent, exits 0 silently — no output, no error.

## Cost estimate

~$0.04 per quick run (~8-12K input tokens at Sonnet pricing).
~$0.08 per deep run (~18-25K input tokens).
~$14/year for full automated operation (4h quick + nightly deep, 5-day business week).

## Cron setup

Use `crontab-manager.py` (not raw `crontab -e`):

```bash
# Quick scan every 4 hours, 8 AM-6 PM business hours
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "kairos-quick" \
  --schedule "0 8,12,16 * * 1-5" \
  --command "CLAUDE_KAIROS_ENABLED=true /home/feedgen/vexjoy-agent/scripts/kairos-cron.sh >> /home/feedgen/vexjoy-agent/cron-logs/kairos/quick.log 2>&1"

# Deep scan nightly at 2:30 AM
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "kairos-deep" \
  --schedule "30 2 * * *" \
  --command "CLAUDE_KAIROS_ENABLED=true KAIROS_MODE=deep /home/feedgen/vexjoy-agent/scripts/kairos-cron.sh >> /home/feedgen/vexjoy-agent/cron-logs/kairos/deep.log 2>&1"

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

# Interactive: just invoke this skill — it reads and runs the prompt inline
```

## Pairs with auto-dream

auto-dream runs at 2:07 AM (memory consolidation), kairos-lite at 2:30 AM (external state). Nightly deep scan can incorporate dream report into toolkit health.

Session-start injection: if both `dream-injection-{project-hash}.md` and `briefing-{project-hash}-{date}.md` exist, load both. Briefing takes precedence for action items; dream injection for memory context.
