# VexJoy Agent

<img src="docs/repo-hero.png" alt="VexJoy Agent" width="100%">

Essays and writing behind this toolkit live at [vexjoy.com](https://vexjoy.com).

VexJoy Agent connects plain-English requests to specialist agents, skills, and workflows. `/do` selects the knowledge and tools needed for your task. Hooks enforce specific checks, and scripts handle repeatable work.

The aim is to give capable models useful domain knowledge without making you learn the toolkit's catalog.

<!-- Counts here must match the Four Layers table (~line 143). Verify both: python3 scripts/validate-doc-counts.py -->
43 agents, 61 skills, 78 hooks, 160 scripts. Agents carry domain knowledge, skills provide reusable methods, hooks enforce selected checks, and scripts handle repeatable plumbing.

Works across Claude Code (`/do`), Codex (`$do`), Factory (`/do`), Reasonix (`/do`).

## What It Looks Like

```
$ claude

> /do debug this Go test

  Routing: go-engineer + systematic-debugging
  Phase 1/4: Reproduce: running test, capturing failure...
  Phase 2/4: Hypothesize: 3 candidates from stack trace...
  Phase 3/4: Verify: isolated root cause in connection pool timeout
  Phase 4/4: Fix: patch applied, test passing, PR opened

  ✓ Delivered: PR #847, fix connection pool timeout in health check
```

The router pairs a Go agent with a debugging skill, then follows the task through verification and delivery.

## The Pipeline

```
  ROUTE        PLAN         EXECUTE      VERIFY       DELIVER      RECORD
 ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
 │ /do  │───▶│ Task │───▶│Agent │───▶│Tests │───▶│  PR  │───▶│Route │
 │Router│    │ Plan │    │+Skill│    │Gates │    │Branch│    │Result│
 └──────┘    └──────┘    └──────┘    └──────┘    └──────┘    └──────┘
```

## /d — Jev-Powered Router

`/d` requires [TypeSafe's Jev](https://docs.typesafe.ai). Jev classifies the
request, checks that the selected route preserves the requested outcome, and
then dispatches the agent, skill, and pipeline.

Intent preservation is production behavior: `/d` restates the requested
outcome and gates dispatch on a Jev receipt for that exact proposed intent,
preventing an agent from quietly expanding an apple into an orchard.

Choose either transport:

```bash
# Preferred: Jev through Vercel AI Gateway
export JEV_TRANSPORT=vercel
export AI_GATEWAY_API_KEY=...

# Alternative: Jev's direct API
export JEV_TRANSPORT=direct
export TYPESAFE_API_KEY=...
```

`JEV_TRANSPORT=auto` is the default. It prefers Vercel when
`AI_GATEWAY_API_KEY` is set, then uses the direct API when only
`TYPESAFE_API_KEY` is set. An explicit transport never silently switches to
the other one. The TypeSafe MCP plugin is not required for `/d`.

Intent-alignment judgments are recorded in `learning.db` without raw request
text. Receipts keep the Jev judge model separate from the executing agent's
configured model and effort level. View proposed-intent difference rates by
agent profile, judge model, and transport:

```bash
python3 scripts/jev-intent-stats.py --days 30
```

Example:

```
> /d fix the flaky test in the payments module

  Intent alignment (/d):
    -> Restated outcome: Fix the flaky payments test without changing unrelated behavior.
    -> Jev: aligned

  ROUTING (/d): testing-automation-engineer + testing-preferred-patterns
  Source: jev (confidence: medium)
  Invoking...
```

## Anti-Rationalization

Checks require evidence rather than confidence.

| Agent Says | What Happens |
|---|---|
| "Code looks correct, skip tests" | Exit gate requires test output. Blocked. |
| "Trivial change, no verification" | Hook blocks completion without evidence. |
| "Similar to before" | Skill demands case-specific proof. |
| "User is in a hurry" | Protocol overrides time pressure. |
| "I'm confident" | Gate demands exit code, not assertion. |

Hooks run at configured events. Skills state what to verify; blocking hooks enforce the checks they cover. Coverage depends on the runtime and tool path.

## Knowledge Work Is First-Class

The content engine researches, drafts in a calibrated voice, checks 397 writing patterns, and adapts finished pieces for each platform. `/html` produces a self-contained report, deck, prototype, chart, or diagram.

## It Proves Its Own Changes

Toolkit changes use direct review and relevant checks. Model comparisons can settle specific uncertainties; they are not required for every edit. [PHILOSOPHY.md](docs/PHILOSOPHY.md) explains the validation policy. [what-didnt-work.md](docs/what-didnt-work.md) records failed experiments, routing reversals, unvalidated A/B citations, disabled lint rules, and program refutations.

The automated nightly evolution loop (`/evolve`, writes to `evolution-reports/`) ran regularly through mid-May 2026. It is currently dormant; recent evidence has come from manual PRs instead.

## Installation

```bash
git clone https://github.com/notque/vexjoy-agent.git ~/vexjoy-agent
cd ~/vexjoy-agent
./install.sh
```

Installs into `~/.claude/` and into `~/.codex/`, `~/.factory/`, `~/.hermes/`, and `~/.reasonix/` when the runtime command is on PATH or its home directory exists. `install.sh` wraps the `vexinstall` engine (`scripts/vexinstall/`). Each SessionStart in the repo re-syncs through the same engine. Symlinks (default in a git checkout) follow `git pull`; `--copy` gives a stable snapshot.

| Flag | Effect |
|---|---|
| `--dry-run` | Print the plan; write nothing |
| `--target <t>` | Only `claude`, `codex`, `factory`, `hermes`, `reasonix`, or `all` |
| `--no-takeover` | Leave old unowned copies in place (default: move them to trash and replace) |
| `--uninstall` / `--rollback` | Remove owned entries / restore the newest trash and settings backup |

Layout and safety rules: [docs/installer-layout.md](docs/installer-layout.md).

Want only part of the toolkit? Run `./install.sh --configure`, or copy `.local.example/profile.yaml` to `.local/profile.yaml` and edit it. Without a profile, the full toolkit installs. Details: [.local.example/README.md](.local.example/README.md).

| CLI | Entry Point |
|-----|-------------|
| Claude Code | `/do` |
| Codex | `$do` |
| Factory | `/do` |
| Reasonix | `/do` |

**Jev Auto-Compact plugin** (optional, requires `TYPESAFE_API_KEY`):

```bash
claude plugin marketplace add ./plugins/jev-auto-compact
claude plugin install jev-auto-compact@jev-auto-compact -y
```

Replaces generated compaction summaries with Jev-judged verbatim pruning after context reaches 60%. Inspect recorded before/after tokens and duration with `python3 scripts/jev-compact-evidence.py`.

**Full setup:** [docs/start-here.md](docs/start-here.md)

<details>
<summary><b>Codex CLI Parity</b></summary>

Mirrors agents, skills, and supported hooks into `~/.codex/`. Codex v0.144.1+ supports 59 of the 70 unique Claude hook registrations: **29 native, 30 adapter-backed, and 11 unsupported**. These are registrations, not unique hook files.

The adapter converts `apply_patch` operations into the Write/Edit payload expected by existing guards. It cannot intercept writes through `unified_exec`, unmatched MCP tools, WebSearch, or other unsupported paths. PreCompact and Stop receive less telemetry than in Claude Code. This is expanded compatibility, not full parity.

After install or any hook-definition change, run `/hooks` in Codex and review the new definitions before trusting them. Codex hash-trusts hook commands and skips changed, unreviewed definitions.

</details>

<details>
<summary><b>Factory CLI Support</b></summary>

Mirrors agents (as "droids"), skills, and hooks into `~/.factory/`. Hook config merges into `~/.factory/settings.json` with paths rewritten.

</details>

<details>
<summary><b>Reasonix Support</b></summary>

Mirrors skills, 160 scripts, and 10 allowlisted hook registrations into `~/.reasonix/`. Reasonix has no agent or custom-command surface; `/do` arrives as a skill. It exposes four events: PreToolUse, PostToolUse, UserPromptSubmit, and Stop. MCP, model, and permissions in `~/.reasonix/config.json` remain user-owned.

</details>

<details>
<summary><b>Token-saving mode</b></summary>

The toolkit supplies its own routing, domain knowledge, methodology, and enforcement. The default system prompt duplicates most of that.

```bash
claude --system-prompt "."
```

Strips built-in tool-use instructions. The toolkit's agents, skills, hooks, and CLAUDE.md provide the project-specific guidance.

</details>

## Four Layers

<!-- Counts here must match the intro line (~line 13). Verify both: python3 scripts/validate-doc-counts.py -->

| Layer | Count | Does |
|---|---|---|
| Agents | 43 | Domain knowledge: idiom tables, failure mode catalogs, error-to-fix mappings |
| Skills | 61 | Reusable guidance and methodology for recurring work. |
| Hooks | 78 | Lifecycle checks, context injection, and telemetry. |
| Scripts | 160 | Repeatable validation, orchestration, and plumbing. |

Full skill catalog: [docs/skills.md](docs/skills.md).

```
┌─────────────────────────────────────────────────┐
│  SKILL.md                                       │
│  ┌─ Frontmatter ─────────────────────────────┐  │
│  │ triggers, pairs_with, success-criteria     │  │
│  └────────────────────────────────────────────┘  │
│  Reference Loading Table (conditional imports)   │
│  Phased Instructions (numbered, with gates)      │
│  Verification (evidence requirements)            │
└─────────────────────────────────────────────────┘
```

## Built with the Toolkit

A game built entirely by Claude Code using these agents, skills, and pipelines:

<div align="center">
<video src="https://github.com/user-attachments/assets/0e74abeb-dc7e-42ba-8239-a7a98cb1ab09" width="100%" autoplay loop muted playsinline></video>
</div>

## Choose Your Path

**[I just want to use it](docs/start-here.md)** Install, learn `/do`, done.

**[I do knowledge work](docs/for-knowledge-workers.md)** Writing, research, data analysis, moderation, HTML artifacts. No code.

**[I'm a developer](docs/for-developers.md)** Architecture, extension points, adding agents and skills.

**[I'm an AI power user](docs/for-ai-wizards.md)** Routing tables, pipelines, hooks, telemetry DB.

**[I'm an AI agent](docs/for-claude-code.md)** Machine-dense inventory. Tables, paths, schemas.

## Philosophy

- **Outcome-first operation.** Describe the result; routing selects the relevant catalog entries.
- **Programs compute; models judge and generate.** Use deterministic code where the answer is computable.
- **Density.** Every word carries instruction, rule, or decision. Cut everything else.
- **Breadth over depth.** Right context ensures correctness. Unfocused context adds cost.
- **Structural enforcement.** Exit codes enforce what instructions can't. Quality gates are automated, not advisory.
- **Everything pipelines.** Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

Full design philosophy: **[PHILOSOPHY.md](docs/PHILOSOPHY.md)**

## Maintenance

One report-only script surfaces upkeep work; it prints a digest and never edits, deletes, or blocks.

- `python3 scripts/stale-skill-scan.py --top 20` ranks stale skills and agents as pruning candidates. Run it quarterly; see [docs/deprecation-template.md](docs/deprecation-template.md).

Scheduled work follows the same boundary as everything else: judgment uses models; repeatable plumbing uses 160 scripts.

| Need | Use |
|---|---|
| Run a deterministic command on a schedule | `scripts/agent-scheduler.py` with `runner: "command"` |
| Run an agent judgment on a schedule, webhook, or file change | `scripts/agent-scheduler.py` with the default `runner: "claude"` |
| Install or remove a user crontab entry safely | `scripts/crontab-manager.py` |
| Audit shell cron reliability | `cron-automation` |
| Keep one interactive objective moving until criteria verify | `objective-loop` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
