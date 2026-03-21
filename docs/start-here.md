# Start Here

Claude Code is powerful on its own. This toolkit makes it *much* better -- specialized agents for every domain, workflow skills that enforce methodology, and hooks that automate the boring parts. You install it once and it works everywhere.

## What You Need

One thing: [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and working. Open a terminal and run:

```bash
claude --version
```

If that prints a version number, you're good. If not, install Claude Code first and come back.

## Install

Three commands. Copy-paste them.

```bash
git clone https://github.com/notque/claude-code-toolkit.git
```

```bash
cd claude-code-toolkit
```

```bash
./install.sh
```

The installer asks one question -- symlink or copy -- then sets everything up. Pick symlink if you want updates via `git pull`, copy if you want a stable snapshot. Either works fine.

What just happened: the installer linked agents, skills, hooks, and scripts into `~/.claude/`, which is where Claude Code looks for extensions. It also configured hooks in your settings so they activate automatically.

## Your First Commands

Open any project folder. Start Claude Code.

```bash
claude
```

Now try these.

### See what's available

```
/do what can you do?
```

The `/do` command is the front door. It reads your request, picks the right agent and skill, and runs it. This one shows you the full routing system -- every domain it handles, every workflow it knows.

### Explore a codebase

```
/do give me an overview of this codebase
```

Try this in any project you're working on. It'll read the code structure, identify patterns, and explain what the project does. Works with Go, Python, TypeScript, Kubernetes configs, whatever's in the repo.

### Write something

```
/do write a blog post about [topic you care about]
```

This kicks off a multi-phase pipeline -- research, outline, draft, voice validation. Replace the topic with something real. The output lands in a file you can edit.

### Debug a problem

```
/do debug why [describe the problem]
```

Routes to a systematic debugging skill. It'll gather evidence before guessing, which is the whole point.

## What You Just Installed

Four kinds of things got copied to `~/.claude/`:

- **Agents** -- domain experts for Go, Python, Kubernetes, data engineering, content, and more
- **Skills** -- reusable workflows like TDD, debugging, code review, article writing, research pipelines
- **Hooks** -- automation that fires on session start, after errors, before context compression
- **Scripts** -- Python utilities the agents call for deterministic operations

These load automatically when you start Claude Code in any directory. You don't need to configure anything else.

## Where Next?

Depends on what you're here for.

**[For Developers](for-developers.md)** -- Architecture, extension points, how to build your own agents and skills.

**[For Knowledge Workers](for-knowledge-workers.md)** -- Content pipelines, research workflows, moderation, data analysis. No code required.

**[For AI Power Users](for-ai-wizards.md)** -- Routing internals, hook lifecycle, pipeline architecture. The deep stuff.

**[For AI Agents](for-claude-code.md)** -- Machine-dense component inventory. If you're an LLM operating in this repo, start there instead.
