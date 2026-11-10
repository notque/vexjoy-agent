---
summary: "Quick reference: slash commands, where the generated catalogs live, file layout, and the settings the installer adds."
read_when:
  - "scanning the full command list"
  - "checking which env settings the installer adds"
---

# Quick Reference Card

**Everything in one place. Scan in 2 minutes.**

---

## Slash Commands

The primary entry point is `/do`, which routes your request to the appropriate agent and skill.

### Core Entry Points
| Command | Purpose | Example |
|---------|---------|---------|
| `/do` | **Smart router** - figures out what you need | `/do debug this failing test` |
| `/d` | Jev-validated router: picks the route with `/do`'s rules, then checks the restated intent with Jev | `/d fix the flaky payments test` |

### Other Slash Commands
These are the files in `commands/`:

| Command | Purpose |
|---------|---------|
| `/install` | Plan, then apply, the install with the vexinstall engine |
| `/pr-review` | Comprehensive PR review, recording reusable findings to learning.db |
| `/retro` | Routing and review telemetry from learning.db: route health, route stats, errors, evidence, review false positives |
| `/reddit-moderate` | Reddit moderation: modqueue, classification, actions |
| `/generate-claudemd` | Generate project-specific CLAUDE.md from repo analysis |
| `/github-notifications` | Triage GitHub notifications: fetch, classify, report |
| `/create-pipeline` | Create a new pipeline from a task description |
| `/system-upgrade` | Systematic upgrade of agents, skills, hooks |
| `/github-profile-rules` | Extract coding conventions from GitHub profiles |
| `/gm-brilliant-implementation` | The staged implementation workflow for a large 5 Star Booker GM program |

Every skill marked user-invocable is also a slash command under its own name (for example `/frontend`, `/review`, `/workflow`).

### Available via `/do` Routing
These workflows are activated through `/do` with natural language:

| Want This? | Try This | Routes to |
|------------|----------|-----------|
| Test-driven development | `/do write tests using TDD` | `testing` |
| Systematic debugging | `/do debug authentication failure` | `workflow` (systematic-debugging) |
| Verification | `/do verify before marking done` | `testing` |
| Code linting | `/do lint src/` | `code-quality` |
| Multi-step task planning | `/do plan the payment system` | `workflow` |
| Go code review | `/do review this Go code` | `review` with `golang-general-engineer` |
| Check CI status | `/do check CI status` | `pr-workflow` |
| Comment quality | `/do check comment quality` | `comment-quality` |

The router decides by meaning, so the right column is the usual route, not a guarantee.

---

## Agents, Skills, and Triggers

The catalogs are generated from frontmatter, so they stay current:

- [routing-map.md](routing-map.md): every agent, skill, and pipeline with its triggers, force-route flag, `not_for`, and `pairs_with`.
- [skills.md](skills.md): every routed skill by category.

Ask for an agent by name ("Use the golang-general-engineer agent"), or let `/do` pick one.

---

## Claude Code Frontmatter Features

| Feature | In Frontmatter | Purpose |
|---------|----------------|---------|
| `once: true` | Hook config | Run hook only once per session |
| `user-invocable: false` | Skill | Hide from slash menu |
| `context: fork` | Skill | Run in isolated sub-agent |
| `agent: name` | Skill | Declare executor agent |
| `hooks:` | Agent | Define agent-specific lifecycle hooks |
| `allowed-tools` | Skill | Tools the skill may use without a permission prompt. On an agent the toolkit's `allowed-tools` lists are advisory: Claude Code limits a subagent's tools only through `tools:`, which no toolkit agent sets. |

---

## Decision Cheat Sheet

```
What do you need?
│
├─ "Just get it done" ──────────► /do [describe task]
│
├─ Specific workflow ───────────► /do [describe workflow]
│   ├─ TDD ─────────────────────► /do write tests using TDD
│   ├─ Debug ───────────────────► /do debug this failure
│   ├─ Lint ────────────────────► /do lint this project
│   └─ Verify ──────────────────► /do verify this is correct
│
├─ Deep domain expertise ───────► "Use the [X] agent"
│   ├─ Go code ─────────────────► golang-general-engineer
│   ├─ Kubernetes ──────────────► kubernetes-helm-engineer
│   └─ React ───────────────────► react-portfolio-engineer
│
├─ Complex multi-step task ─────► /do plans first
│   └─ Writes task_plan.md for Simple+ work
│
└─ Don't know ──────────────────► Just describe what you want
                                  Claude figures it out
```

---

## File Locations

```
agents/            ← Specialized agents (one .md per agent, optional references/)
skills/            ← skills/{category}/{name}/SKILL.md, each with optional references/
  └─ process/workflow/references/  ← Workflow definitions loaded on demand (formerly pipelines/)
commands/          ← Slash commands (one .md per command)
hooks/             ← Python hooks and utility scripts
  └─ lib/          ← Shared libraries
scripts/           ← Deterministic Python scripts
docs/              ← This documentation
```

---

## Recommended Settings

Environment variables set in `.claude/settings.json` under `"env"`. `install.sh` adds any that are missing from `~/.claude/settings.json`, keeps values you already set (except one still on an old shipped default, which it moves to the new value once), and removes retired variables it used to set (only when the value is still the one it shipped):

| Variable | Recommended Value | Why |
|----------|-------------------|-----|
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | `500000` | Every turn re-reads the whole conversation, and a cache miss after an idle gap rewrites all of it. Compacting at 500k caps that cost and the quality loss of very long context while compacting less often than 400k did. Installs still on the old shipped `400000` move to `500000` once; other values, and any value set after that, are kept. |
| `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` | `1` | Turns on Claude Code function hooks, which the optional Jev Auto-Compact plugin (`plugins/jev-auto-compact`) uses. Without a plugin that registers one it changes nothing. |
| `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION` | `false` | Turns off the greyed-out next-prompt suggestions, which cost tokens and add noise. |
| `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` | `1h` | Keeps a subagent's prompt cache for an hour instead of 5 minutes. Subagents that wait 5-15 minutes on a test or sim run rewrote their whole context once the 5-minute cache expired. A 1-hour cache write is billed at a higher rate than a 5-minute one, so this trades a dearer first write for fewer full rewrites. |

**Retired:** `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1`. It has no effect on Opus 5.5 and Fable, and on older models such as Opus 4.6 it forces the deprecated fixed thinking budget.

**Context on `AUTO_COMPACT_WINDOW`:** Claude supports a 1M token context window, but the model reads the full conversation on every turn. Cache hits bill those tokens at a fraction of the input price (0.05x on Opus 5.5), and a miss after the cache expires bills a full rewrite. Message threads, which Claude Code uses since about 2.1.316, send only new messages each turn and cut time to first token on long requests, but they do not reduce the tokens billed. Answers also degrade as context grows, while each compaction drops detail. 500k is the middle ground between those two costs; it was 400k before message threads. History: [anthropics/claude-code#45756](https://github.com/anthropics/claude-code/issues/45756#issuecomment-4231739206), credit [@bcherny](https://github.com/bcherny).

The installer merges only `hooks` and `env` from the repo settings. Keys such as `attribution`, `effortLevel`, and `autoMemoryEnabled` apply to sessions in this checkout only.

### Model choice

`/do` and `/d` set the model for each dispatched agent from the task type. To pick the model yourself, name it in the request ("use fable for everything").

| Task | Model / effort |
|------|----------------|
| read-only gathering: locate, lookup, cite lines, excerpts, research fetch, log reading | haiku |
| code writing and edits, debugging, features, reviews that decide, decisions, no row fits | opus / medium, then high |
| high-risk: auth, data, security, concurrency, irreversible | opus / medium, then high |
| major refactor or migration, architecture planning, lead of a many-agent fan-out, deep research synthesis, quantitative analysis, long unattended run, or Opus at high fell short | fable / medium, then high |

Sonnet is no task's default. Opus starts at medium on every row, high-risk included (owner, 2026-11-09: "Also I prefer opus 5.5 medium over high"); high is the step after a failed medium attempt. Prices, effort trade-offs, and the evidence: [model task fit](../skills/meta/d/references/model-task-fit.md).

### Orchestration (optional)

Keys under `"orchestration"` in `.claude/settings.json` tune how `/do` sizes dispatched work.

| Key | Default | Why |
|-----|---------|-----|
| `orchestration.token_budget` | `500000` | Advisory token budget for a single `/do` task. `/do` Phase 4 prepends "~{remaining} tokens available for this task; prioritize accordingly." to each dispatched agent prompt so agents right-size their own work. A documented signal, not a hard runtime cap — absent the key, the default applies and behavior is unchanged. |

---

## Getting Help

- **Don't know what to use?** → `/do [what you want]`
- **Want to see commands?** → Check this file
- **Building new tools?** → [../AGENTS.md](../AGENTS.md) and [../CONTRIBUTING.md](../CONTRIBUTING.md)
