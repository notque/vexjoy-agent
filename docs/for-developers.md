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

## Adding an Agent

Agents are markdown files with YAML frontmatter. The frontmatter tells the router when to use the agent. The body tells Claude *how to be* that agent.

### Step 1: Create the file

```bash
touch agents/my-domain-engineer.md
```

Naming convention: `{domain}-{function}-engineer.md`. The `-engineer` suffix isn't mandatory but it's what most agents use. Look at the existing ones -- `golang-general-engineer.md`, `python-general-engineer.md`, `kubernetes-helm-engineer.md`.

### Step 2: Write the frontmatter

Here's the minimum viable frontmatter:

```yaml
---
name: my-domain-engineer
version: 1.0.0
description: |
  Use this agent when you need help with [your domain].
  The agent specializes in [specific things].

  Examples:

  <example>
  Context: User wants to do X
  user: "Help me do X"
  assistant: "[Routes to my-domain-engineer] Doing X with proper patterns."
  <commentary>
  Routes here because: (1) X is a trigger keyword, (2) requires domain expertise.
  </commentary>
  </example>

color: blue
routing:
  triggers:
    - my-domain
    - relevant-keyword
    - .file-extension
  pairs_with:
    - verification-before-completion
  complexity: Medium
  category: language
---
```

The `color` field sets the accent in the Claude Code UI. Pick from: blue, green, orange, red, purple.

The `routing` block is what `/do` uses to match requests to your agent. Triggers are fuzzy-matched against the user's request. `pairs_with` lists skills that work well with this agent. `complexity` tells the planner how much scaffolding to set up. `category` groups agents for discovery.

### Step 3: Write the body

The body follows a pattern you'll see in every agent. Look at `agents/python-general-engineer.md` for a real example. The key sections:

1. **Operator context preamble** -- "You are an operator for X, configuring Claude's behavior for Y"
2. **Hardcoded behaviors** -- things this agent always does (CLAUDE.md compliance, over-engineering prevention, plus domain-specific rules)
3. **Default behaviors** -- on by default, can be turned off (communication style, cleanup habits, domain defaults)
4. **Optional behaviors** -- off by default (things users can enable)
5. **Capabilities and limitations** -- what the agent CAN and CANNOT do
6. **Anti-patterns** -- common mistakes with what-why-instead format
7. **Anti-rationalization table** -- domain-specific rationalization patterns to watch for

The full template lives at `AGENT_TEMPLATE_V2.md` in the repo root. It's worth reading -- it shows the complete structure including reference file organization.

### Step 4: Register in the index

```bash
python3 scripts/generate-agent-index.py
```

This reads all `agents/*.md` files, extracts routing metadata from frontmatter, and writes `agents/INDEX.json`. The `/do` router reads that index at runtime. Don't hand-edit INDEX.json -- it gets overwritten.

### Step 5: Test routing

Start a Claude Code session and try:

```
/do [request that should trigger your agent]
```

The routing banner should show your agent being selected. If it doesn't, check your triggers -- they might be too narrow, or another agent's triggers might be matching first.

### Optional: Reference files

For agents with deep domain knowledge, create a references subdirectory:

```
agents/my-domain-engineer/
  references/
    error-catalog.md
    anti-patterns.md
    code-examples.md
```

The agent can reference these when it needs detailed examples or error resolution steps. Keeps the main agent file under 10k words.

## Adding a Skill

Skills are workflow methodologies. Where agents know *what* to do, skills know *how* to structure the work. A skill might be "test-driven development" or "systematic debugging" or "PR pipeline."

### Step 1: Create the directory and SKILL.md

```bash
mkdir -p skills/my-workflow
touch skills/my-workflow/SKILL.md
```

### Step 2: Write the frontmatter

```yaml
---
name: my-workflow
description: |
  One-paragraph description of what this skill does and when to use it.
  Include trigger phrases so the router can match it.
version: 1.0.0
user-invocable: true
agent: python-general-engineer
allowed-tools:
  - Bash
  - Read
  - Edit
---
```

Key fields:

- `user-invocable`: set to `true` if users can call it directly as `/my-workflow`. Set to `false` for skills that only get invoked by the router or other skills.
- `agent`: declares which agent should execute this skill. Optional -- some skills are agent-agnostic.
- `allowed-tools`: restricts which tools the skill can use. Good for security (a read-only skill shouldn't need Write).
- `context: fork` -- add this if the skill should run in an isolated sub-agent context. Used for skills that do heavy work and shouldn't pollute the main conversation.

### Step 3: Write the body

The body is the methodology. It tells the agent *how* to work through the task. Look at `skills/reddit-moderate/SKILL.md` for a concrete example -- it defines modes, prerequisites, commands, and a step-by-step workflow.

Skills often include:
- Operator context (hardcoded/default/optional behaviors)
- Phase definitions (if it's a pipeline)
- Quality gates between phases
- Commands or scripts to invoke
- Error handling and troubleshooting

### Step 4: Update the index

```bash
python3 scripts/generate-skill-index.py
```

Same idea as the agent index. Reads all `skills/*/SKILL.md` files, extracts frontmatter, writes `skills/INDEX.json`.

### Step 5: Force-route triggers (optional)

Some skills need to be invoked whenever certain keywords appear, regardless of what agent is selected. These go in the `/do` skill's routing table. For example, Go test files *always* trigger the `go-testing` skill. If your skill has that kind of mandatory coupling, you'll need to add it to the force-route list in `skills/do/SKILL.md`.

## Writing a Hook

Hooks are Python scripts that fire on Claude Code lifecycle events. They read JSON from stdin and print JSON to stdout. That's the whole contract.

### The event types

| Event | When it fires | Typical use |
|-------|--------------|-------------|
| `SessionStart` | Session begins | Load context, sync files, detect environment |
| `UserPromptSubmit` | Before processing a prompt | Inject skills, detect task complexity |
| `PreToolUse` | Before a tool runs | Gate tool calls, inject learning hints |
| `PostToolUse` | After a tool runs | Detect errors, suggest fixes, capture learnings |
| `PreCompact` | Before context compression | Archive important state |
| `TaskCompleted` | After a task finishes | Record learnings, cleanup |
| `SubagentStop` | Sub-agent finishes | Guard completion quality |
| `Stop` | Session ends | Generate summary, save state |

### The contract

Your hook receives JSON on stdin describing the event. The shape varies by event type but always includes the event name and relevant context. Your hook prints JSON to stdout. The output format uses the `HookOutput` structure from `hooks/lib/hook_utils.py`:

```python
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output

def main():
    event = json.loads(sys.stdin.read())

    # Your logic here
    if should_inject_context(event):
        output = context_output("PostToolUse", "Context to inject into Claude's next response")
        output.print_and_exit()
    else:
        empty_output("PostToolUse").print_and_exit()

if __name__ == "__main__":
    main()
```

Three output modes:
- `empty_output(event_name)` -- nothing to say, no injection
- `context_output(event_name, text)` -- inject system context (Claude sees it, user doesn't)
- `user_message_output(event_name, message)` -- message displayed verbatim to the user

### Performance budget

Hooks have a **50ms target**. They fire on every tool call (PostToolUse) or every prompt (UserPromptSubmit), so slow hooks add up fast. The settings.json registration supports a `timeout` field (in milliseconds) -- default varies but keep it tight. If your hook needs to do anything heavy, do it asynchronously or cache aggressively.

### The lib directory

Don't reinvent the wheel. `hooks/lib/` has:

- `hook_utils.py` -- output formatting, JSON escaping, environment helpers, frontmatter parsing, file discovery, cascading fallbacks
- `learning_db_v2.py` -- SQLite-backed learning database for cross-session pattern storage
- `feedback_tracker.py` -- automatic feedback loop for error-learning confidence tracking
- `quality_gate.py` -- shared quality gate logic
- `usage_db.py` -- usage tracking database

Import from lib by adding it to your path:

```python
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, get_project_dir
```

### Registration

Hooks are registered in `settings.json` under the `hooks` key. Each event type has an array of hook groups, each group containing an array of hooks:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/my-hook.py\"",
            "description": "What my hook does",
            "timeout": 3000
          }
        ]
      }
    ]
  }
}
```

Note the path uses `$HOME/.claude/hooks/` -- that's where the sync hook deploys files at session start. You write your hook in the repo's `hooks/` directory. The `sync-to-user-claude.py` hook (which runs on SessionStart) copies it to `~/.claude/hooks/`. The settings.json in the repo is the source of truth for hook registration -- sync replaces the hooks section entirely.

Add `"once": true` for hooks that should only fire once per session (like SessionStart hooks that load initial context).

### Testing hooks

Hook tests live in `hooks/tests/`. Use pytest:

```bash
pytest hooks/tests/test_my_hook.py -v
```

Feed your hook test JSON via stdin and assert on the stdout JSON. Look at `hooks/tests/test_feedback_tracker.py` or `hooks/tests/test_learning_system.py` for patterns.

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
