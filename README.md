# VexJoy Agent

<img src="docs/repo-hero.png" alt="VexJoy Agent" width="100%">

AI agents skip steps.

"Looks correct" replaces running tests. "Trivial change" replaces verification. The agent confidently ships broken code because nothing structurally prevented it from skipping the work.

This toolkit prevents that. 44 domain agents, 106 workflow skills, 71 hooks, 93 scripts. Agents carry knowledge, skills enforce methodology, hooks block incomplete work, scripts handle determinism. The pipeline has gates. Gates require evidence. Evidence means exit codes, not assertions.

Works across Claude Code (`/do`), Codex (`$do`), Gemini CLI (`/do`), Factory (`/do`).

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

The router reads intent, picks a Go agent paired with a debugging skill, and runs the full lifecycle. You typed one sentence. The system did the rest.

## The Pipeline

```
  ROUTE        PLAN         EXECUTE      VERIFY       DELIVER      LEARN
 ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
 │ /do  │───▶│ Task │───▶│Agent │───▶│Tests │───▶│  PR  │───▶│Record│
 │Router│    │ Plan │    │+Skill│    │Gates │    │Branch│    │Evolve│
 └──────┘    └──────┘    └──────┘    └──────┘    └──────┘    └──────┘
```

## Anti-Rationalization

This is the single thing that separates it from "agent with a system prompt."

| Agent Says | What Happens |
|---|---|
| "Code looks correct, skip tests" | Exit gate requires test output. Blocked. |
| "Trivial change, no verification" | Hook blocks completion without evidence. |
| "Similar to before" | Skill demands case-specific proof. |
| "User is in a hurry" | Protocol overrides time pressure. |
| "I'm confident" | Gate demands exit code, not assertion. |

Hooks fire automatically. Gates block completion. Skills encode counter-arguments at every skip-worthy step. The agent verifies or it doesn't finish.

For what I do, the difference is enormous. If you're doing simple single-file edits, maybe less so.

## Installation

```bash
git clone https://github.com/notque/vexjoy-agent.git ~/vexjoy-agent
cd ~/vexjoy-agent
./install.sh --symlink
```

Links into `~/.claude/` and mirrors into `~/.codex/`, `~/.gemini/`, `~/.factory/`. Use `--symlink` for live updates via `git pull`.

| CLI | Entry Point |
|-----|-------------|
| Claude Code | `/do` |
| Codex | `$do` |
| Gemini CLI | `/do` |
| Factory | `/do` |

**Full setup:** [docs/start-here.md](docs/start-here.md)

<details>
<summary><b>Codex CLI Parity</b></summary>

Mirrors agents, skills, and 6 allowlisted hooks into `~/.codex/`. Requires Codex CLI v0.114.0+.

**Blocked upstream:** Edit/Write interceptors waiting on [openai/codex#16732](https://github.com/openai/codex/issues/16732). PreCompact, SubagentStop, Notification, SessionEnd events stay Claude Code only.

</details>

<details>
<summary><b>Gemini CLI Support</b></summary>

Mirrors agents, skills, and Phase 1 hooks into `~/.gemini/`. Translates event names (`Stop` → `SessionEnd`, `PostToolUse` → `AfterTool`, `PreToolUse` → `BeforeTool`). Tool mapping: `Bash` → `run_shell_command`. Hook config merges into `~/.gemini/settings.json`.

</details>

<details>
<summary><b>Factory CLI Support</b></summary>

Mirrors agents (as "droids"), skills, and all hooks into `~/.factory/`. Hook config merges into `~/.factory/settings.json` with paths rewritten.

</details>

<details>
<summary><b>Token-saving mode</b></summary>

The toolkit supplies its own routing, domain knowledge, methodology, and enforcement. The default system prompt duplicates most of that.

```bash
claude --system-prompt "."
```

Strips built-in tool-use instructions. The toolkit's agents, skills, hooks, and CLAUDE.md provide equivalent coverage.

</details>

## Four Layers

| Layer | Count | Does |
|---|---|---|
| Agents | 44 | Domain knowledge: idiom tables, anti-pattern catalogs, error-to-fix mappings |
| Skills | 106 | Phased methodology with gates. Can't skip steps. Each phase has exit criteria requiring evidence. |
| Hooks | 71 | Fire on lifecycle events. Block incomplete work. Zero LLM cost. |
| Scripts | 93 | Determinism: test runners, linters, validators. No LLM judgment. |

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

**[I do knowledge work](docs/for-knowledge-workers.md)** Content pipelines, research, moderation. No code.

**[I'm a developer](docs/for-developers.md)** Architecture, extension points, adding agents and skills.

**[I'm an AI power user](docs/for-ai-wizards.md)** Routing tables, pipelines, hooks, learning DB.

**[I'm an AI agent](docs/for-claude-code.md)** Machine-dense inventory. Tables, paths, schemas.

**[I'm on LinkedIn](docs/for-linkedin.md)** 🚀 Thought leadership. Agree? 👇

## Philosophy

- **Zero-expertise operation.** Say what you want. The system classifies, dispatches, enforces, delivers.
- **LLMs orchestrate, programs execute.** Deterministic work belongs to scripts. LLM judgment handles design decisions, diagnosis, review.
- **Density.** Every word carries instruction, rule, or decision. Cut everything else.
- **Breadth over depth.** Right context ensures correctness. Unfocused context adds cost.
- **Structural enforcement.** Exit codes enforce what instructions can't. Quality gates are automated, not advisory.
- **Everything pipelines.** Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

Full design philosophy: **[PHILOSOPHY.md](docs/PHILOSOPHY.md)**

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
