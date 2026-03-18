# AI Overkill

**This is probably not for you.**

And that's fine. Most people don't need specialized domain agents, multi-wave parallel code review, or a self-improving knowledge system that remembers what it learned last Tuesday. Most people are fine with Claude Code out of the box. It's good.

But if you've ever:
- Asked Claude to review your PR and gotten back "the code looks good and is well-structured"
- Watched it give you generic concurrency advice when you needed Go-specific concurrency patterns
- Started a new session and realized it forgot everything from the last one
- Wanted to throw more agents at a problem instead of writing a better prompt

Then maybe this is for you. I built it for me. I've been using it for a year. It's called AI Overkill because I know it's overkill. The approach to most problems here is "what if we just threw more tokens at it?" and honestly, that works better than it should.

**It works.** The multi-wave review catches things. The error-learner remembers solutions. Force-routing stops the generic advice. The retro system means session 50 is better than session 1. I ship better code with this than without it, and the gap widens over time as the system accumulates knowledge. The `/do` router alone makes the whole experience vastly better. High-context agents with deep domain expertise (more tokens, yes) produce different results than "you are a helpful Go engineer."

**Here's the thing.** This system is built for me, around the work I do. The agents reflect my domains. The skills reflect my workflows. The hooks solve problems I've hit. You'll get some value installing it. The real value is studying the patterns and building your own. Write agents for your domains. Write skills for your workflows. The infrastructure (the router, the hooks, the retro system, the voice tools) is general. The content is mine. Make yours.

---

## The philosophy (such as it is)

The solution to most AI coding problems is not "write a better prompt." It's "dispatch more specialized agents and let them argue about it."

Code review? Don't ask one agent to review everything. Dispatch a wave of specialists (security, concurrency, performance, dead code, naming) and have each one focus on exactly one thing. Then dispatch a second wave that reads the first wave's findings and goes deeper. Yes, this uses a lot of tokens. The tokens are cheaper than the bugs.

Debugging? Don't let the AI skip straight to "let me try this fix." Force it through REPRODUCE, ISOLATE, IDENTIFY, then FIX, with gates between each phase. It can't skip steps because the skill literally checks.

Knowledge? Don't start every session from zero. Record what worked, inject it next time, track confidence, decay what's stale. The system gets smarter the more you use it.

Is this efficient? No. Is it effective? Unreasonably.

---

## Who this is for

**You'll probably get value if you:**
- Want to build your own agents, skills, and pipelines and need patterns to learn from
- Work primarily in Go, Python, or TypeScript and want to see what domain-specific agent expertise looks like in practice
- Have hit the ceiling of what a good CLAUDE.md gives you and want to understand what's beyond it
- Want your AI to remember what it learned across sessions
- Think "what if I dispatched 20 parallel review agents" is a reasonable sentence

**You'll probably NOT get value if you:**
- Want to install something and have it work perfectly for your workflow out of the box (this is my workflow, not yours)
- Just started using Claude Code (try [Superpowers](https://github.com/obra/superpowers) first)
- Think "overkill" is a criticism rather than a feature
- Are looking for something production-hardened with a community and support (this is one person's toolkit, shared as-is)

---

## How to use this without installing

**The best use case for this repo isn't installing it.**

Point your AI coding assistant at the patterns. Read through the agents, skills, and hooks. The value is in the *structure*, not the `install.sh`.

Patterns worth stealing:

- **`agents/*.md`** How to write domain-expert system prompts with routing metadata, force-triggered skills, and phase gates. Pick one and read it. The pattern is: frontmatter declares triggers and capabilities, the body is deep domain expertise, and there's a quality gate at the end that prevents the agent from declaring victory without evidence.

- **`skills/*/SKILL.md`** Workflow methodologies that enforce process. The `systematic-debugging` skill has four phases (REPRODUCE, ISOLATE, IDENTIFY, FIX) with gates between them. You can't skip to "fix" because the skill literally checks. Steal this pattern for any multi-step workflow you want AI to follow without cutting corners.

- **`hooks/*.py`** Event-driven automation. The `error-learner.py` hook watches for tool errors, stores error-to-solution patterns in SQLite, and suggests fixes when it sees similar errors later. The system learns from its own mistakes.

- **`skills/comprehensive-review/SKILL.md`** The "throw tokens at it" pattern in its purest form. Wave 0 discovers packages, Wave 1 runs a wall of specialized reviewers in parallel, Wave 2 does cross-cutting analysis using Wave 1's findings. It's a template for "fan out, gather, synthesize."

- **The router (`skills/do/SKILL.md`)** How to build a natural-language routing layer. You describe what you want, it classifies domain + action + complexity, selects the right agent and skill, and handles force-routing for specific triggers.

You don't need to install anything. Read the patterns, then build your own agents for your domains, your own skills for your workflows, your own hooks for your pain points. The system includes tools to help: `/do create an agent for [your domain]` and `/do create a skill for [your workflow]` use the same patterns to scaffold new components. The `.local/` overlay lets you add private agents and skills that survive updates.

But if you *do* want to install it...

---

## Install

```bash
git clone https://github.com/notque/ai-overkill.git ~/ai-overkill
cd ~/ai-overkill

# See what would happen first (RECOMMENDED)
./install.sh --dry-run

# Then install for real
./install.sh --symlink    # symlink mode (updates via git pull)
# OR
./install.sh --copy       # copy mode (stable, re-run to update)
```

The installer links or copies agents, skills, hooks, commands, and scripts into `~/.claude/`, installs Python dependencies, and configures hooks in `settings.json`. It has `--dry-run`, `--uninstall`, and asks before overwriting anything.

**Back up first** if you have existing Claude Code customizations. Symlink mode replaces directories.

**Updating:** `cd ~/ai-overkill && git pull` (symlink mode updates automatically).

---

## Everything goes through `/do`

That's the entry point. You describe what you want, the router figures out the rest.

```
You: "/do debug this Go test"

  Router classifies: domain=Go, action=debug
  Selects agent: golang-general-engineer
  Selects skill: systematic-debugging
  Force-routes: go-testing (trigger match)

  Agent loads Go-specific context and idioms
  Skill enforces: REPRODUCE -> ISOLATE -> IDENTIFY -> FIX -> VERIFY
  Scripts run deterministic validation (go vet, gopls, gofmt)
```

You don't need to know which agent or skill exists. Just say what you want. The router alone makes the whole experience different. Instead of Claude guessing what approach to take, it gets matched to a domain expert with a methodology. That single change, routing to specialized agents instead of hoping the general model figures it out, is where most of the value comes from.

### Force-routing (why this exists)

Certain triggers always invoke specific skills:

| Trigger | Skill | Why |
|---------|-------|-----|
| goroutine, channel, sync.Mutex | `go-concurrency` | Generic concurrency advice is how you get data races |
| _test.go, t.Run, benchmark | `go-testing` | Test patterns need table-driven, t.Helper, race detection |
| error handling, fmt.Errorf | `go-error-handling` | Error wrapping chains have specific Go patterns |

Without force-routing, Claude gives you generic advice when you need specific patterns. That's how bugs happen.

---

## Throwing tokens at code review

`/comprehensive-review` is the headline feature and the most ridiculous thing in the repo.

It dispatches parallel specialist agents across 3 waves. Each wave's findings feed the next wave. The security reviewer finds a swallowed error. The concurrency reviewer reads that finding and realizes the swallowed error is on a concurrent path. Now you've found an invisible race condition that no single-pass review would catch.

**Wave 0** auto-discovers packages, dispatches per-package language specialists

**Wave 1** parallel foundation reviewers (security, concurrency, silent failures, performance, dead code, type design, API contracts, code quality, language idioms, docs)

**Wave 2** cross-cutting analysis using Wave 1 findings (deep concurrency, config safety, observability, error messages, naming consistency)

Final output: unified BLOCK/FIX/APPROVE verdict with severity-ranked findings.

Could one reviewer prompt do this? Some of it. But the cross-domain interactions, the "this swallowed error is on a concurrent path" insight, that's where the real bugs hide. So I threw tokens at it. And it finds things.

---

## The system remembers

Most AI coding sessions are stateless. This one isn't.

```
Feature completed
  -> retro-pipeline extracts learnings
  -> Saved to retro/L2/
  -> Next session, injected automatically when keywords match
  -> Agent receives context from prior work before starting
```

The `error-learner` hook does this automatically for errors: sees a tool error, records the pattern, suggests the fix next time, tracks whether the fix worked, adjusts confidence. It's a SQLite database with reinforcement learning characteristics. Tokens in, knowledge out.

---

## Voice system (bring your own)

Create AI writing profiles that match a specific person's style. Bring your own writing samples, the system extracts measurable patterns, validates generated content against those patterns, and flags AI tells. See [docs/VOICE-SYSTEM.md](docs/VOICE-SYSTEM.md).

No pre-built voices included. The infrastructure ships; your voice is yours to create.

---

## What else is in here

| Thing | What it does |
|-------|-------------|
| Domain agents | Specialized experts for Go, Python, TypeScript, Kubernetes, databases, and more |
| Workflow skills | TDD, debugging, refactoring, code review, PR pipelines, content creation |
| Event hooks | Error learning, auto-planning, retro injection, context archiving |
| Roast personas | Skeptical senior, pedant, pragmatic builder, contrarian, newcomer. They don't hold back |
| Pipeline generator | Say "I need a pipeline for X" and the system builds agents, skills, and routing for it |
| Voice system | Clone a writing style with deterministic validation |
| PR workflow | `/pr-sync` stages, commits, pushes, and creates PRs in one command |
| `.local/` overlay | Your private customizations that survive `git pull` |

---

## FAQ

**Q: This is probably not for me, right?**
A: Probably not. But if you've hit the ceiling and want to see what happens when you stop being conservative with tokens and start being aggressive with agents, it's a different experience. Things work better. Your code reviews find real bugs. Your debugging sessions don't skip steps. Your sessions compound knowledge. It's overkill, but it's effective overkill.

**Q: How many tokens does the comprehensive review use?**
A: A lot. Multiple waves of parallel agents, each reading your codebase independently. It's like hiring a consulting firm for every PR. The findings are worth it. Your wallet's opinion may vary.

**Q: Can I just steal patterns without installing?**
A: That's the recommended use case. Read `agents/golang-general-engineer.md` to see how to write a deep domain agent. Read `skills/systematic-debugging/SKILL.md` to see phase-gated workflows. Read `hooks/error-learner.py` to see cross-session learning. Adapt to your own setup.

**Q: Will this slow down my sessions?**
A: Hooks add ~200ms at session start. After that, agents only load when invoked. The comprehensive review is slow because you're running waves of parallel agents. That's the trade-off.

**Q: Can I use just parts of it?**
A: Yes. Delete what you don't want. The router adapts to what's available. Hooks can be individually disabled in settings.json.

**Q: I only write Python. Why are there Go agents?**
A: They're markdown files doing nothing until invoked. The cost of having them is zero. The cost of needing one and not having it is a bad session.

**Q: How is this different from Superpowers?**
A: Different tools for different stages. Superpowers is a great workflow system with a clean brainstorm, plan, build, review, ship pipeline. It installs in one command and works on multiple platforms. AI Overkill is a different bet: deep domain agents with high context, a router that matches you to the right specialist, multi-wave review that throws tokens at the problem, and a knowledge system that compounds over time. The router alone changes the experience. The high-context agents change it more. They're not really competing. One is a workflow. This is an arsenal.

**Q: The name is ridiculous.**
A: It's descriptive.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
