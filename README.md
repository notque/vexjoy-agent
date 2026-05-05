# VexJoy Agent

<img src="docs/repo-hero.png" alt="VexJoy Agent" width="100%">

Agents, skills, hooks, and scripts for [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex](https://github.com/openai/codex), [Gemini CLI](https://github.com/google-gemini/gemini-cli), and [Factory](https://factory.ai). You type what you want. A router picks a specialist, pairs it with a methodology, and runs the whole lifecycle (plan, execute, test, PR) without you picking agents or learning internals.

## How It Works

```
/do debug this Go test
```

The router (`/do` in Claude Code/Gemini/Factory, `$do` in Codex) reads your intent, picks a Go agent + debugging skill, and runs:

```
  ROUTE        PLAN         EXECUTE      VERIFY       DELIVER      LEARN
 ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐
 │ /do  │───▶│ Task │───▶│Agent │───▶│Tests │───▶│  PR  │───▶│Record│
 │Router│    │ Plan │    │+Skill│    │Gates │    │Branch│    │Evolve│
 └──────┘    └──────┘    └──────┘    └──────┘    └──────┘    └──────┘
```

The agent creates a branch, gathers evidence, diagnoses in phases, fixes, tests, reviews its own work, and opens a PR. The system records what worked so routing improves over time.

Four layers make this go:
- Agents carry domain knowledge (Go idioms, K8s patterns, Python conventions)
- Skills enforce methodology (TDD cycles, debugging phases, review waves)
- Hooks automate gates (fire on lifecycle events, block incomplete work)
- Scripts handle determinism (test runners, linters, validators, no LLM judgment)

## Built with the Toolkit

A game built entirely by Claude Code using these agents, skills, and pipelines:

<div align="center">
<video src="https://github.com/user-attachments/assets/0e74abeb-dc7e-42ba-8239-a7a98cb1ab09" width="100%" autoplay loop muted playsinline></video>
</div>

## Installation

```bash
git clone https://github.com/notque/vexjoy-agent.git ~/vexjoy-agent
cd ~/vexjoy-agent
./install.sh --symlink
```

Links everything into `~/.claude/` and mirrors into `~/.codex/`, `~/.gemini/`, `~/.factory/`. Use `--symlink` for live updates via `git pull`.

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/install-doctor.py inventory
```

| CLI | Entry Point |
|-----|-------------|
| Claude Code | `/do` |
| Codex | `$do` |
| Gemini CLI | `/do` |
| Factory | `/do` |

**Full setup:** [docs/start-here.md](docs/start-here.md)

<details>
<summary><b>Codex CLI Parity</b></summary>

Mirrors agents, skills, and 6 allowlisted hooks into `~/.codex/`. Runs on every `install.sh`.

**Mirrors:** agents, skills, SessionStart injectors, Stop recorder, PostToolUse Bash scanner. Sets `[features] codex_hooks = true` in `~/.codex/config.toml`.

**Blocked upstream:** Edit/Write interceptors waiting on [openai/codex#16732](https://github.com/openai/codex/issues/16732). PreCompact, SubagentStop, Notification, SessionEnd events stay Claude Code only. Windows hook support disabled upstream.

Requires Codex CLI v0.114.0+. Harmless when Codex isn't installed — `~/.codex/` sits unused.

</details>

<details>
<summary><b>Gemini CLI Support</b></summary>

Mirrors agents, skills, and Phase 1 hooks into `~/.gemini/`. Translates event names:

| Claude/Codex | Gemini |
|---|---|
| SessionStart | SessionStart |
| Stop | SessionEnd |
| PostToolUse | AfterTool |
| PreToolUse | BeforeTool |

Tool mapping: `Bash` → `run_shell_command`. Hook config merges into `~/.gemini/settings.json` (only the `hooks` key, other settings preserved).

Harmless when Gemini CLI isn't installed.

</details>

<details>
<summary><b>Factory CLI Support</b></summary>

Mirrors agents (as "droids"), skills, and all hooks into `~/.factory/`. Hook config merges into `~/.factory/settings.json` with paths rewritten from `$HOME/.claude/` to `$HOME/.factory/`.

Harmless when Factory isn't installed.

</details>

<details>
<summary><b>Token-saving mode</b></summary>

The toolkit supplies its own routing, domain knowledge, methodology, and enforcement. The default Claude Code system prompt duplicates most of that. Override it:

```bash
claude --system-prompt "."
```

Trade-off: strips built-in tool-use instructions. The toolkit's agents, skills, hooks, and CLAUDE.md provide equivalent coverage. On a bare install without the toolkit, use `--append-system-prompt` instead.

</details>

<details>
<summary><b>The Core Workflow</b></summary>

1. **Route.** `/do` classifies intent, picks agent + skill, dispatches.
2. **Plan.** Creates task plan with phases and gates before touching code.
3. **Execute.** Domain agent works using the skill's methodology.
4. **Verify.** Tests run. Scripts validate. Hooks block incomplete work.
5. **Deliver.** Feature branch, PR, lint, CI.
6. **Learn.** Records routing outcome, captures errors, feeds self-improvement.

</details>

## What's Inside

<details>
<summary><b>44 Domain Agents</b></summary>

Concrete domain knowledge: idiom tables, anti-pattern catalogs with detection commands, error-to-fix mappings from real incidents.

| Category | Agents | Covers |
|---|---|---|
| Software Engineering | Go, Python, TypeScript, PHP, Kotlin, Swift, Node.js, React Native | Languages, DB design, data pipelines, K8s, Ansible, Prometheus/Grafana, OpenSearch, RabbitMQ, OpenStack |
| Code Review | Multi-perspective, domain-specific, playbook-enhanced | 5 reviewer personas, ADR compliance, adversarial verification |
| Frontend & Creative | React, Next.js, UI/UX, PixiJS, Rive, VFX | Portfolios, e-commerce, combat rendering, skeletal animation |
| Infrastructure | Pipeline, project, research coordination | System upgrades, governance, tech docs, MCP servers, Perses |

</details>

<details>
<summary><b>106 Workflow Skills</b></summary>

Phased methodologies with gates. You can't skip steps — each phase has exit criteria requiring evidence.

| Category | Key Skills | Use When |
|---|---|---|
| Development | TDD, systematic debugging, feature lifecycle, subagent-driven dev | Building, fixing, testing |
| Code Quality | Parallel review (3 simultaneous), systematic review, quality gates | Before any merge |
| Content & Research | Voice-validated writing, research pipelines, content calendars | Writing, researching |
| Operations | PR workflow, GitHub Actions, service health, K8s debugging | Shipping, monitoring |
| Meta | Skill evaluation, A/B testing, toolkit evolution | Improving the toolkit |

</details>

<details>
<summary><b>71 Hooks</b></summary>

Fire on SessionStart, PreToolUse, PostToolUse, PreCompact, Stop, UserPromptSubmit, SubagentStop. Handle error learning, context injection, quality enforcement, anti-rationalization. Zero LLM cost — pure automation.

</details>

<details>
<summary><b>93 Scripts</b></summary>

Python utilities for what should never be improvised: INDEX generation, learning DB management, voice validation, routing manifests, reference validation.

</details>

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

## Anti-Rationalization

AI agents skip steps. "Looks correct" replaces running tests. "Trivial change" replaces verification. Every skill here has counter-arguments baked in:

| Agent Says | What Happens |
|---|---|
| "Code looks correct, skip tests" | Exit gate requires test output — blocked |
| "Trivial change, no verification" | Hook blocks completion without evidence |
| "Similar to before" | Skill demands case-specific proof |
| "User is in a hurry" | Protocol overrides time pressure |
| "I'm confident" | Gate demands exit code, not assertion |

Hooks fire automatically. Gates block completion. Skills encode counter-arguments at every skip-worthy step. Agents verify or they don't finish.

## Choose Your Path

**[I just want to use it](docs/start-here.md)** — Install, learn `/do`, done.

**[I do knowledge work](docs/for-knowledge-workers.md)** — Content pipelines, research, moderation. No code.

**[I'm a developer](docs/for-developers.md)** — Architecture, extension points, adding agents and skills.

**[I'm an AI power user](docs/for-ai-wizards.md)** — Routing tables, pipelines, hooks, learning DB.

**[I'm an AI agent](docs/for-claude-code.md)** — Machine-dense inventory. Tables, paths, schemas.

**[I'm on LinkedIn](docs/for-linkedin.md)** — 🚀 Thought leadership. Agree? 👇

## Philosophy

Tested principles. The toolkit absorbs complexity so you don't.

- **Zero-expertise operation.** Say what you want. The system classifies, dispatches specialists, enforces quality, delivers.
- **LLMs orchestrate, programs execute.** Deterministic work belongs to scripts. LLM judgment handles design decisions, diagnosis, and review.
- **Density.** Every word carries instruction, rule, or decision. Cut everything else.
- **Breadth over depth.** Tokens buy more specialists in parallel, not longer prompts. Right context ensures correctness; unfocused context adds cost.
- **Knowledge lives in agents.** Agent quality tracks specificity of attached knowledge. Domain expertise and methodology beat motivational preambles — A/B tested.
- **Structural enforcement.** Exit codes enforce what instructions can't. Quality gates are automated, not advisory.
- **Everything pipelines.** Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

Full design philosophy: **[PHILOSOPHY.md](docs/PHILOSOPHY.md)**

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — skill anatomy, agent format, quality gates, PR process.

## License

MIT. See [LICENSE](LICENSE).
