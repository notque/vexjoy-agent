# Claude Code Toolkit

<img src="docs/repo-hero.png" alt="Claude Code Toolkit - /do routes to specialized agents" width="100%">

A collection of 60+ agents, 115+ skills, and 30+ hooks for Claude Code. Built over a year of daily use.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/notque/claude-code-toolkit.git ~/claude-code-toolkit
cd ~/claude-code-toolkit

./install.sh --symlink        # recommended: updates with git pull
```

Then start Claude Code and run the health check:

```bash
claude
```

```
/install
```

This verifies your installation, shows what's available, and walks you through first-time setup. Run it again anytime to diagnose issues.

<details>
<summary>Install options</summary>

```bash
./install.sh --dry-run        # preview changes
./install.sh --symlink        # recommended: updates with git pull
./install.sh --copy           # alternative: stable snapshot
./install.sh --uninstall      # remove installation
./install.sh --force          # replace existing dirs without prompting
```

The installer places agents, skills, hooks, commands, and scripts in `~/.claude/`. It configures hooks in `settings.json`. Symlink mode replaces directories — back up any existing Claude Code customizations before installing.

Update with `cd ~/claude-code-toolkit && git pull` in symlink mode.

</details>

## The problem and the fix

Claude Code gives you one general-purpose model for all tasks. Claude Code Toolkit gives you a router (`/do`) that classifies your request by domain and action, picks a specialized agent, and loads a workflow skill to enforce methodology. The agent knows domain idioms. The skill structures the work into gated phases. Python scripts handle deterministic validation.

```
Router -> Agent -> Skill -> Script
```

Example: `/do debug this Go test` routes to `golang-general-engineer` + `systematic-debugging` + `go-testing`. The agent loads Go-specific context. The skill enforces REPRODUCE, ISOLATE, IDENTIFY, FIX, VERIFY. Each phase has a gate.

## /do router and force-routing

`/do` is the single entry point. Describe what you want, and the router matches you to an agent and skill.

Force-routing overrides normal selection for specific triggers:

| Trigger | Skill |
|---------|-------|
| goroutine, channel, sync.Mutex | `go-concurrency` |
| _test.go, t.Run, benchmark | `go-testing` |
| fmt.Errorf, error handling | `go-error-handling` |
| "create voice", "voice from samples" | `create-voice` |
| "design feature", "plan feature" | `feature-design` / `feature-plan` |

These overrides exist because the corresponding domains require very specific patterns. Generic advice about Go concurrency or error wrapping produces broken code.

## Code review in 3 waves

`/comprehensive-review` runs 20+ specialist reviewers across 3 waves.

**Wave 0:** Package discovery. Per-package language specialists dispatch automatically.

**Wave 1:** Parallel foundation review. Security, concurrency, silent failures, performance, dead code, API contracts, naming consistency, and others run simultaneously.

**Wave 2:** Cross-cutting analysis. Reviewers in this wave read all Wave 1 findings. A security reviewer flagged a swallowed error in Wave 1? The concurrency reviewer in Wave 2 can trace that swallowed error to a concurrent code path.

Result: unified BLOCK/FIX/APPROVE verdict, severity-ranked.

## Cross-session knowledge (learning system)

Hooks automatically capture learnings into a SQLite database (learning.db) during normal work:

- **error-learner**: captures tool errors and their solutions
- **review-capture**: extracts findings from reviewer agents
- **session-context**: loads high-confidence patterns at session start

On your next session, the `retro-knowledge-injector` hook queries the database via FTS5 search and injects relevant knowledge before the agent starts. Use `/retro graduate` to permanently embed mature learnings into specific agents.

## ADR coordination

When you create agents, skills, or pipelines, the system writes an Architecture Decision Record and registers a session. The `adr-context-injector` hook feeds role-targeted sections to each sub-agent. A skill-creator gets step-menu and type-matrix sections. An agent-creator gets architecture-rules. All agents involved in a creation task read from the same architectural decisions.

## Voice cloning with deterministic validation

Provide writing samples. `voice_analyzer.py` extracts measurable style patterns: sentence length distribution, comma density, contraction rate, fragment usage. `voice_validator.py` validates generated content against those measurements and flags AI tells. Both scripts are deterministic Python, not self-assessment.

```
/create-voice              # build a profile from samples
/do write in voice [name]  # generate matching content
```

No voices are pre-built. The measurement infrastructure ships; you build your profiles.

## Feature lifecycle

| Command | Output |
|---------|--------|
| `/feature-design` | Design doc from collaborative exploration |
| `/feature-plan` | Wave-ordered tasks with agent assignments |
| `/feature-implement` | Dispatched execution by domain agents |
| `/feature-validate` | Quality gates: tests, lint, type checks |
| `/feature-release` | PR, merge, tag, cleanup |

Each phase produces saved artifacts. Learnings are captured to learning.db at each checkpoint.

## More features

**Pipeline generator.** Describe the domain, and the system discovers subdomains and scaffolds agents, skills, and routing through a 7-phase flow (ADR, Domain Research, Chain Composition, Scaffold, Integrate, Test, Retro).

**PR workflow.** `/pr-sync` stages, commits, pushes, and creates a PR. On personal repos, it runs up to 3 automated review-and-fix iterations before opening the PR.

**.local/ overlay.** Put custom agents, skills, and hooks in `.local/`. They survive `git pull` without modifying the toolkit.

## FAQ

**How do I start?** Install, then use `/do` for all requests. Try `/do review this file` or `/do debug this test`. The router handles agent and skill selection.

**Can I use part of it?** Delete agents and skills you do not need. The router adapts. Disable individual hooks in `settings.json`.

**How does this differ from Superpowers?** Superpowers provides a workflow system (brainstorm, plan, build, review, ship) with single-command install across platforms. This toolkit provides specialist routing, multi-wave review, cross-session knowledge, and voice cloning. Different purposes.

**Performance impact?** Hooks add ~200ms at session start. Agents load on demand. An unused agent is a markdown file on disk and costs nothing to have around.

## License

MIT License. See [LICENSE](LICENSE) for details.
