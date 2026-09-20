---
summary: "Five-minute path from install to first /do."
read_when:
  - "onboarding a new user"
---

# Start Here

Install the toolkit, then describe your task with `/do`. The router selects the relevant agent, skill, and checks.

## What You Need

Install [Claude Code](https://docs.claude.com/en/docs/claude-code), then confirm it works:

```bash
claude --version
```

Codex CLI, Factory, and Reasonix are optional. The installer mirrors the components each runtime supports. Use `/do` in Claude Code, Factory, and Reasonix; use `$do` in Codex.

If you plan to use an optional runtime, verify it before installation with `codex --version`, `factory --version`, or `reasonix --version`. Claude Code has the broadest hook coverage; the other runtimes receive only the components and lifecycle events they support.

## Install

```bash
git clone https://github.com/notque/vexjoy-agent.git
cd vexjoy-agent
./install.sh
```

Choose symlinks if you want `git pull` updates to appear immediately, or copies for a stable snapshot. The installer puts the toolkit in `~/.claude/` and creates the supported mirrors for other installed runtimes.

Verify the result:

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/install-doctor.py inventory
```

`check` validates the installation, settings, hook paths, and local data access. `inventory` shows what each runtime can see. Rerun `./install.sh` after pulling changes if you chose copies.

### Codex users

Codex integration requires v0.144.1 or later. The current test suite covers 70 hook registrations: 29 run through native Codex events, 30 are adapter-backed, and 11 are unsupported. That is 59 supported registrations in total, but not full Claude Code parity.

After installation or a hook update, run `/hooks` in Codex and approve changed definitions. Codex does not run changed hook commands until they are trusted.

## Try It

Open a project directory and start Claude Code:

```bash
claude
```

Then ask for an overview or give it a concrete task:

```text
/do what can you do?
/do give me an overview of this codebase
/do debug why this test fails
/do write a blog post about [topic]
```

You do not need to choose an agent or skill. State the outcome you want; `/do` handles routing and applies the relevant workflow and verification.

If a check reports missing or stale mirrors, rerun `./install.sh`, then repeat the two verification commands. The inventory output is the authoritative view of what the installed runtimes can currently discover.

## What Was Installed

- **Agents** provide domain knowledge.
- **Skills** define reusable methods such as debugging, review, research, and writing.
- **Hooks** run checks at configured lifecycle events.
- **Commands** provide entry points such as `/do`.
- **Scripts** perform deterministic operations.

These components load when you start Claude Code in any directory. See the root README for architecture, runtime differences, and implementation details.

## Where Next

- [For Knowledge Workers](for-knowledge-workers.md): writing, research, data analysis, moderation, and HTML artifacts.
- [For Developers](for-developers.md): architecture, extension points, agents, and skills.
- [For AI Power Users](for-ai-wizards.md): routing, hooks, and pipeline internals.
- [For AI Agents](for-claude-code.md): machine-dense component inventory.
