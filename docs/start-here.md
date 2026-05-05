# Start Here

Claude Code is good on its own. This toolkit makes it structurally better. Specialized agents, workflow skills that enforce methodology, hooks that automate the boring parts. Install once, works everywhere.

## What You Need

One thing: [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed.

```bash
claude --version
```

If that prints a version number, you're good. If not, install Claude Code first and come back.

Optional: Codex CLI, Gemini CLI, or Factory. The toolkit mirrors skills and agents into their directories (`~/.codex/`, `~/.gemini/`, `~/.factory/`), so all four CLIs dispatch the same domain expertise. Claude Code remains the full runtime for hooks, commands, and scripts.

Verify optional tools: `codex --version` / `gemini --version` / `factory --version`.

Command entry points:

| CLI | Command |
|-----|---------|
| Claude Code | `/do` |
| Codex | `$do` |
| Gemini CLI | `/do` |
| Factory | `/do` |

## Install

```bash
git clone https://github.com/notque/vexjoy-agent.git
cd vexjoy-agent
./install.sh
```

The installer asks one question: symlink or copy. Symlink means updates via `git pull`. Copy means a stable snapshot. Either works.

What it does: links agents, skills, hooks, commands, and scripts into `~/.claude/`. Mirrors skills into `~/.codex/skills/` and `~/.gemini/skills/`, agents into `~/.codex/agents/` and `~/.gemini/agents/` and `~/.factory/droids/` (Factory calls agents "droids"). Configures hooks in settings so they activate automatically.

## Verify

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/install-doctor.py inventory
```

`check` verifies the install layout, settings, hook paths, learning DB access, and CLI mirrors. `inventory` lists what each CLI can currently see. If you pull new toolkit changes later and want the mirrors updated, rerun `./install.sh`.

## First Commands

Open any project folder. Start Claude Code.

```bash
claude
```

Then:

```
/do what can you do?
```

The router reads your request, picks the right agent and skill, runs it. This one shows you the full routing system.

```
/do give me an overview of this codebase
```

Works in any repo. Reads structure, identifies patterns, explains what the project does.

```
/do write a blog post about [topic]
```

Multi-phase pipeline: research, outline, draft, voice validation. Output lands in a file.

```
/do debug why [problem]
```

Systematic debugging. Gathers evidence before guessing.

## What Got Installed

Five kinds of things in `~/.claude/`:

- **Agents**: domain experts. Go, Python, Kubernetes, data engineering, content, more.
- **Skills**: reusable workflows. TDD, debugging, code review, article writing, research pipelines.
- **Hooks**: automation that fires on session start, after errors, before context compression.
- **Commands**: slash command definitions that wire up entry points like `/do`.
- **Scripts**: Python utilities agents call for deterministic operations.

These load automatically when you start Claude Code in any directory.

## Where Next

Depends on what you're here for.

**[For Developers](for-developers.md)** : Architecture, extension points, how to build your own agents and skills.

**[For Knowledge Workers](for-knowledge-workers.md)** : Content pipelines, research workflows, moderation, data analysis. No code required.

**[For AI Power Users](for-ai-wizards.md)** : Routing internals, hook lifecycle, pipeline architecture.

**[For AI Agents](for-claude-code.md)** : Machine-dense component inventory. If you're an LLM operating in this repo, start there.
