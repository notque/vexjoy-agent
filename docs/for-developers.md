# For Developers

You cloned the repo. You want to add an agent, write a skill, build a hook, or just understand how the pieces fit. This guide gets you there.

## Architecture in 60 Seconds

Everything flows through a four-layer dispatch:

```
User request
     |
     v
  Router (/do)          -- classifies intent, picks agent + skill
     |
     v
  Agent (*.md)          -- domain expert (Go, Python, K8s, review...)
     |
     v
  Skill (SKILL.md)      -- workflow methodology (TDD, debugging, PR pipeline...)
     |
     v
  Script (*.py)         -- deterministic operations (no LLM judgment)
```

The router parses your request, matches triggers to find the right agent, pairs it with a skill if the task type calls for one, and the agent executes using that skill's methodology. Hooks fire at lifecycle events (session start, before/after tool use, compaction, stop) to inject context, learn from errors, and enforce quality gates. Scripts do the mechanical work -- index generation, voice validation, learning database queries -- where you want deterministic behavior, not LLM judgment calls.

## Directory Structure

```
agents/              Domain experts. One .md per agent, optional references/ subdirectory
  INDEX.json         Generated routing index (don't hand-edit -- run the script)

skills/              Workflow methodologies. One directory per skill, each with SKILL.md
  INDEX.json         Generated skill index

hooks/               Event-driven Python scripts. Fire on lifecycle events
  lib/               Shared utilities (hook_utils.py, learning_db_v2.py, feedback_tracker.py)
  tests/             Hook-specific tests

scripts/             Deterministic CLI tools. Python scripts for mechanical operations
  tests/             Script-specific tests

commands/            Slash command definitions (markdown files that wire up user-facing commands)

templates/           Template directories for scaffolding (e.g., reddit data templates)

evals/               Evaluation harness -- task definitions, rubrics, fixtures, results

adr/                 Architecture Decision Records. Numbered markdown files tracking why decisions were made
```

A few things that aren't obvious from the listing: `agents/` and `skills/` both have INDEX.json files that are *generated* by scripts (`scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`). The `hooks/lib/` directory is where shared code lives -- hooks import from there, not from each other. And the `services/` directory exists for optional service integrations.

## Creating Components

The toolkit has specialized creator agents for each component type. Tell `/do` what you want, describe the domain and purpose in your prompt, and the creator agent handles structure, registration, and routing integration.

### Creating an Agent

```
/do create an agent for [your domain]
```

Describe what the agent should specialize in, what triggers should route to it, and what patterns it should enforce. The `skill-creator` handles the rest: file creation, frontmatter, operator context, anti-patterns, index registration, and routing table integration.

**Example prompts:**
- `/do create an agent for Terraform infrastructure management that knows HCL, state management, and module patterns`
- `/do create an agent for Redis caching that specializes in data structures, eviction policies, and cluster management`

The agent creator uses the `AGENT_TEMPLATE_V2.md` template and produces a complete agent with operator context, hardcoded/default/optional behaviors, anti-patterns, and reference files.

### Creating a Skill

```
/do create a skill for [your workflow]
```

Describe the methodology, phases, and quality gates. The `skill-creator` builds the skill directory, SKILL.md with frontmatter, phase definitions, and updates the index.

**Example prompts:**
- `/do create a skill for database migration safety with pre-migration checks, rollback validation, and post-migration verification`
- `/do create a skill for API contract testing that validates OpenAPI specs against implementation`

### Creating a Hook

```
/do create a hook for [your purpose]
```

Describe the event type, what it should detect or inject, and any performance constraints. The `hook-development-engineer` creates the hook with proper event handling, `hooks/lib/` integration, and settings.json registration.

**Example prompts:**
- `/do create a hook that warns when test files are modified without updating test fixtures`
- `/do create a PostToolUse hook that detects when a git merge conflict marker is written to a file`

Hooks must meet a **50ms performance target** since they fire on every tool call or prompt.

### Creating a Pipeline

```
/do create a pipeline for [your domain]
```

The `pipeline-orchestrator-engineer` decomposes the domain into subdomains, composes pipeline chains, scaffolds skills, and wires routing. See `commands/create-pipeline.md` for details.

### Key Architecture Points

- **Agents** (`agents/*.md`) know *what* to do -- domain expertise, patterns, anti-patterns
- **Skills** (`skills/*/SKILL.md`) know *how* to structure work -- phases, gates, methodology
- **Hooks** (`hooks/*.py`) fire on lifecycle events -- JSON in, JSON out, 50ms budget
- **Scripts** (`scripts/*.py`) do deterministic work -- linting, indexing, validation

The `/do` router connects everything. After creating any component, test it:

```
/do [request that should trigger your new component]
```

The routing banner shows which agent and skill were selected. If routing doesn't match, the creator agents handle trigger registration automatically.

## The PR Workflow

This repo uses a structured workflow for changes. It's more than "branch, commit, push" -- there's a review loop built in.

### The full cycle

1. **Branch** -- create a feature branch off main. Convention: `feature/description`, `fix/description`, `refactor/description`.
2. **Implement** -- make your changes. Agents, skills, hooks, scripts, whatever.
3. **Wave review** -- run `/pr-review` which dispatches parallel reviewer agents against your changes. They check code quality, naming, security, dead code, error handling, and more.
4. **Fix** -- address reviewer findings. The PR pipeline does up to 3 review-fix iterations automatically.
5. **Retro** -- after significant work, the system captures learnings into the learning database. These get injected into future sessions.
6. **Graduate** -- mature retro entries (high confidence, validated multiple times) get promoted into agent and skill files permanently.
7. **Commit** -- conventional commit format. No AI attribution lines. Focus on what and why.
8. **Push** -- push to remote with tracking.
9. **PR** -- create the pull request via `gh pr create`.
10. **CI** -- wait for CI checks to pass.
11. **Merge** -- after CI and any human review.

The `pr-pipeline` skill automates steps 3-10. You can invoke it with `/pr` or let `/do` route to it when you say "create a PR" or "submit changes."

For repos under protected organizations (configured in `scripts/classify-repo.py`), every git action requires user confirmation. The pipeline won't auto-commit, auto-push, or auto-create PRs for those repos.

## Testing

Tests use pytest. Two main test directories:

```
hooks/tests/       Hook-specific tests
scripts/tests/     Script-specific tests
```

### Running tests

```bash
# All tests
pytest -v

# Hook tests only
pytest hooks/tests/ -v

# Script tests only
pytest scripts/tests/ -v

# Single test file
pytest hooks/tests/test_learning_system.py -v

# With coverage
pytest --cov=hooks --cov=scripts -v
```

### What to test

- **Hooks**: Feed JSON input, assert JSON output. Test the happy path and the silent path (when the hook has nothing to say). Mock external dependencies like the learning database.
- **Scripts**: Test CLI interfaces. Scripts are deterministic -- given input X, they should always produce output Y. No LLM judgment to worry about.
- **Agents/Skills**: The `evals/` directory has an evaluation harness for testing agent quality. Task definitions live in `evals/tasks/`, rubrics in `evals/rubrics/`. This is more about quality assessment than unit testing.

### Test fixtures

`scripts/tests/fixtures/` contains test data. `hooks/tests/` has its own fixtures inlined in conftest or test files. The eval system has `evals/fixtures/` and `evals/calibration/`.

## Key Conventions

**Conventional commits.** Format: `type(scope): description`. Types: feat, fix, refactor, docs, test, chore. Scope is optional but helpful. Examples: `feat(reddit): add ban subcommand`, `fix(hooks): handle missing session ID`.

**No AI attribution.** Don't add "Generated with Claude Code" or "Co-Authored-By: Claude" to commits. The CLAUDE.md is explicit about this.

**Branch safety.** Never commit directly to main. Always work on a feature branch. The hooks and skills enforce this -- `pretool-git-submission-gate.py` will block commits to protected branches.

**Wabi-sabi in docs.** Documentation should read like a human wrote it. Contractions are fine. Sentence fragments where they're clear. Varied sentence length -- short punchy ones mixed with longer explanatory ones. Never use "delve", "leverage", "comprehensive", "robust", "streamline", or "empower." The `scripts/scan-ai-patterns.py` script catches these.

**INDEX.json is generated.** Don't hand-edit `agents/INDEX.json` or `skills/INDEX.json`. Run the generation scripts. They parse frontmatter and build the index.

**Hooks go in hooks/, sync deploys them.** Write your hook in the repo's `hooks/` directory. The sync hook copies it to `~/.claude/hooks/` on session start. Register it in `settings.json` using the `$HOME/.claude/hooks/` path.

**Scripts are deterministic.** If it involves LLM judgment, it's an agent or skill. If it's mechanical (parse files, query a database, validate patterns), it's a script. Don't blur the line.

**50ms hook budget.** Hooks fire frequently. Keep them fast. Profile if you're not sure. The `scripts/benchmark-hooks.py` script can help.
