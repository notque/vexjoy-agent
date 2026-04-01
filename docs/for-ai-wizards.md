# Architecture Deep-Dive

You know Claude Code. You've written agents, maybe built a skill or two. This doc is about how *this specific toolkit* wires everything together -- the routing decisions, the hook lifecycle, the learning database that gets smarter across sessions. Skip what you know. Dig into what you don't.

## The Router

Every `/do` request hits the `skill-evaluator` hook on `UserPromptSubmit`. It doesn't route -- it *injects routing context* so Claude picks the right agent and skill. The actual dispatch happens when Claude reads the injected `<skill-evaluation-protocol>` block and decides to invoke `Task` or `Skill`.

### Complexity Classification

The evaluator classifies every prompt into four tiers:

| Tier | Heuristic | What Gets Injected |
|------|-----------|-------------------|
| **Trivial** | <10 words + has `?` | Nothing. No routing. |
| **Simple** | 1 complex signal or 20+ words | `UNDERSTAND -> EXECUTE -> VERIFY` |
| **Medium** | 1+ signal + 20-50 words | `UNDERSTAND -> PLAN -> EXECUTE -> VERIFY` |
| **Complex** | 2+ signals or 50+ words | Full 4-phase with requirements, risks, criteria |

Complex signals are verbs like `implement`, `create`, `refactor`, `debug`, plus multi-step indicators like `and also`, `first`, `after that`. Word count is a rough proxy for scope.

The `auto-plan-detector` hook runs in parallel on the same event. When it sees code modification verbs, research intent, or multi-step patterns, it injects `<auto-plan-required>` -- a Manus-style directive to create `task_plan.md` before doing anything. This fires independently from the skill evaluator.

### Agent Selection

Agents are matched by keyword triggers from `routing.triggers` in their frontmatter:

```yaml
routing:
  triggers:
    - go
    - golang
    - ".go files"
    - goroutine
    - gopls
  retro-topics:
    - go-patterns
    - concurrency
```

The `skill-evaluator` maintains a hardcoded `AGENT_ROUTING` dict that maps agent names to one-line descriptions. When injected, it's grouped by domain -- Go, Python, TypeScript, Infra, Data, Meta, Critique. Claude reads the list, matches the request, and dispatches via `Task` tool with `subagent_type`.

### Force-Route Triggers

Some skills MUST be invoked when their triggers appear. These aren't suggestions -- CLAUDE.md declares them as mandatory:

- Go test, `_test.go`, table-driven, goroutine, channel, `sync.Mutex`, error handling, `fmt.Errorf`, sapcc, make check -> `go-patterns`

Force-routes override the evaluator's recommendation. If someone says "add a goroutine pool" and the evaluator would have suggested `workflow`, the force-route to `go-patterns` wins.

## Agent Architecture

An agent is a markdown file in `agents/` with YAML frontmatter. Here's what the full schema looks like in practice:

```yaml
---
name: golang-general-engineer
version: 3.0.0
description: |
  Use this agent when you need expert assistance with Go development...
color: blue
memory: project
hooks:
  PostToolUse:
    - type: command
      command: |
        python3 -c "
        import sys, json
        data = json.loads(sys.stdin.read())
        # agent-specific hook logic
        "
      timeout: 3000
routing:
  triggers: [go, golang, goroutine, gopls]
  retro-topics: [go-patterns, concurrency]
---
```

Key fields: `name` identifies it in routing. `hooks` lets agents register their own PostToolUse handlers -- the Go agent reminds you to run `gofmt` after editing `.go` files. `routing.triggers` feeds the evaluator. `routing.retro-topics` tells the dream system which learning DB topics are relevant when this agent runs (used during nightly auto-dream curation, ADR-147). `memory: project` scopes learned context to the current project.

### The Operator Context Pattern

Every agent body follows the same three-tier structure:

1. **Hardcoded Behaviors** -- always apply, no exceptions. "Read CLAUDE.md before starting." "Never commit to main."
2. **Default Behaviors** -- on unless explicitly disabled. "Use conventional commits." "Run tests after changes."
3. **Optional Behaviors** -- off unless enabled. "Multi-language examples." "Interactive playground."

This isn't decorative. The pattern gives Claude a clear decision framework. Hardcoded behaviors can't be argued with. Defaults can be overridden by the user. Optionals need explicit activation. It prevents the rationalization problem where Claude talks itself into skipping steps.

### Reviewer Agents

Reviewer agents -- `reviewer-code`, `reviewer-system`, `reviewer-domain`, `reviewer-perspectives` -- get dispatched by the `parallel-code-review` and `roast` skills. Each umbrella agent loads the relevant reference file for its review dimension. They never modify code.

## Skill System

A skill is `skills/{name}/SKILL.md` -- a workflow methodology, not a domain expert. Where agents know *what*, skills know *how*.

```yaml
---
name: workflow
version: 2.0.0
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Write
  - Bash
  - Task
  - Skill
routing:
  triggers: [research then write, article with research]
  pairs_with: [voice-writer]
  complexity: complex
  category: content-pipeline
---
```

`context: fork` means the skill runs in an isolated sub-agent context -- it can't accidentally corrupt the parent's state. `user-invocable: false` hides it from the slash menu; it gets invoked by the router or other skills. `allowed-tools` is a whitelist -- if a skill doesn't list `Edit`, it can't edit files.

### Progressive Disclosure

Skills can have a `references/` directory with supporting files. The main SKILL.md stays focused -- instructions, phases, gates. Heavy reference material (step menus, spec formats, voice profiles) lives in `references/` and gets loaded on demand. This keeps the primary file parseable without bloating context.

### Gate Enforcement

Every skill phase ends with a gate -- a condition that must be true before proceeding. The learn skill's gates:

- Phase 1 (PARSE): "Both error_pattern and solution are non-empty strings"
- Phase 2 (CLASSIFY): "fix_type and fix_action are determined"
- Phase 3 (STORE): "Script exits 0 and prints confirmation"
- Phase 4 (CONFIRM): "User sees confirmation"

Gates prevent the LLM from racing ahead. Without them, Claude will happily "complete" Phase 3 by assuming the script worked without checking exit codes.

## Hook System

Hooks are Python scripts registered in `~/.claude/settings.json` under event type keys. They fire on lifecycle events and can inject context, block tools, or stay silent.

### Event Types

Eight event types, registered in settings.json:

| Event | When | Hooks Registered |
|-------|------|-----------------|
| `SessionStart` | Session begins | sync-to-user-claude, session-context, cross-repo-agents, fish-shell-detector, sapcc-go-detector, operator-context-detector |
| `UserPromptSubmit` | Before processing each prompt | skill-evaluator, auto-plan-detector, instruction-reminder, adr-context-injector, pipeline-context-detector, capability-catalog-injector |
| `PreToolUse` | Before tool execution | pretool-learning-injector, block-attribution |
| `PostToolUse` | After tool execution | post-tool-lint-hint, error-learner, agent-grade-on-change, adr-enforcement, routing-gap-recorder, retro-graduation-gate |
| `PreCompact` | Before context compression | precompact-archive |
| `TaskCompleted` | After a Task tool finishes | task-completed-learner |
| `SubagentStop` | When a subagent exits | subagent-completion-guard |
| `Stop` | Session ends | session-summary, confidence-decay |

### Execution Model

Every hook receives JSON on stdin, emits JSON on stdout. The contract:

**Input** (varies by event):
```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_result": {"output": "..."},
  "cwd": "/path/to/project"
}
```

**Output** (via `hook_utils.py`):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "injected text for Claude's system prompt",
    "userMessage": "text that MUST be shown to the user verbatim"
  }
}
```

**Exit codes**: `0` = pass (always for non-blocking hooks). `2` = block the tool (PreToolUse only). The `block-attribution` hook exits 2 when it detects "Generated with Claude Code" or "Co-Authored-By: Claude" in a git command -- physically preventing the tool call.

All hooks target sub-50ms execution. `once: true` in settings means the hook fires only on the first event of that type per session. Every hook wraps its main logic in try/except and exits 0 in `finally` -- a crashed hook must never block Claude.

### Key Hooks

**error-learner** (PostToolUse): Detects errors in tool output by scanning for indicators like "permission denied", "not found", "traceback". Classifies the error type, generates a signature, checks learning.db for known solutions. If found, emits `[auto-fix]`, `[fix-with-skill]`, or `[fix-with-agent]` directives. Sets pending feedback so the *next* PostToolUse can check whether the fix worked -- automatic reinforcement learning without human intervention.

**session-context** (SessionStart, ADR-147): At session start, reads the pre-built dream payload from `~/.claude/state/dream-injection-{project-hash}.md` and injects it as a `<retro-knowledge>` block. The payload was LLM-curated during the nightly auto-dream cycle — top memories selected by relevance, ~2000 token budget. Also loads high-confidence patterns directly from learning.db as fallback. Win rate: 67% in A/B testing when retro knowledge is relevant.

**block-attribution** (PreToolUse): Scans Bash commands for AI attribution patterns. Exits 2 to block. This enforces the CLAUDE.md rule that commits carry no AI watermarks.

**retro-graduation-gate** (PostToolUse): Fires after `gh pr create`. Checks learning.db for ungraduated high-confidence entries from the current session. Emits an advisory warning -- doesn't block, but nags you to graduate findings before merging.

## Learning System

The learning database is a SQLite file at `~/.claude/learning/learning.db`. WAL mode for concurrent reads across sessions. FTS5 for full-text search. One table does everything.

### Schema

```sql
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL,        -- error, pivot, review, design, debug, gotcha, effectiveness
    confidence REAL DEFAULT 0.5,
    source TEXT NOT NULL,           -- hook:error-learner, hook:review-capture, skill:learn
    source_detail TEXT,             -- e.g. "Bash:golang-general-engineer"
    project_path TEXT,
    observation_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    graduated_to TEXT,              -- NULL until embedded in an agent/skill file
    error_signature TEXT,
    error_type TEXT,
    fix_type TEXT,                  -- auto, skill, agent, manual
    fix_action TEXT,                -- create_file, systematic-debugging, use_replace_all, etc.
    UNIQUE(topic, key)
);
```

Additional tables: activations (learning activation tracking),
session_stats (per-session ROI cohort data), learning_archive (archived stale entries).

### Confidence Scoring

Entries start at category-specific defaults (errors: 0.55, reviews: 0.70, gotchas: 0.70). The error-learner boosts confidence by 0.15 when a fix works, decays by 0.10 when it doesn't. The `confidence-decay` hook runs at session end -- entries untouched for 30+ days decay by 0.05, entries below 0.3 and older than 90 days get pruned.

Manually taught patterns (via `/learn`) enter at 0.9 confidence. The dream system only surfaces entries above 0.5 confidence and excludes graduated entries when building the nightly injection payload.

### The Retro Cycle

1. **Capture**: Hooks record learnings automatically. `error-learner` captures error patterns. `review-capture` captures PR review findings. `task-completed-learner` records effectiveness data. `user-correction-capture` records when you correct Claude.
2. **Accumulate**: Entries gain confidence through repeated observation and successful fixes.
3. **Inject**: `session-context` injects the pre-built dream payload at session start (ADR-147). Falls back to direct learning.db queries for high-confidence patterns.
4. **Graduate**: When an entry is mature (high confidence, multiple observations), the `/retro graduate` command embeds it directly into an agent or skill file. The `graduated_to` column records where it went.
5. **Decay**: Unused knowledge fades. The confidence-decay hook ensures the DB doesn't fill with stale advice.

### The /learn Command

`/learn "Edit tool fails with 'found N matches'" -> "Use replace_all=True"` parses the input, classifies the fix type (auto/skill/agent/manual), and stores it at 0.9 confidence via `scripts/learning-db.py record`. It's for pre-loading knowledge you already have, not for debugging live issues.

### CLI

```bash
# ROI report — cohort comparison of sessions with/without retro knowledge
python3 scripts/learning-db.py roi [--json]

# Show stale entries (low confidence, old, not graduated)
python3 scripts/learning-db.py stale [--min-age-days 30]

# Archive stale entries
python3 scripts/learning-db.py stale-prune --dry-run
python3 scripts/learning-db.py stale-prune --confirm
```

## Pipeline Architecture

Pipeline skills follow a standard template. Not all use every phase, but the shape is consistent:

```
PHASE 1: GATHER    -> Launch parallel agents for research/analysis
PHASE 2: COMPILE   -> Structure findings into coherent format
PHASE 3: GROUND    -> Establish context (audience, tone, mode)
PHASE 4: GENERATE  -> Load skill/agent, create content
PHASE 5: VALIDATE  -> Run deterministic validation scripts
PHASE 6: REFINE    -> Fix validation errors (max 3 iterations)
PHASE 7: OUTPUT    -> Final content with validation report
```

The `research-to-article` workflow reference (now in `skills/workflow/references/`) uses all seven phases. It launches 5 parallel research agents in GATHER (primary domain, narrative arcs, external context, community reaction, business context), compiles findings with story arc emphasis in COMPILE, selects voice mode in GROUND, generates via voice-writer in GENERATE, validates with `voice-validator.py` in VALIDATE, iterates in REFINE, and outputs with a validation report.

`parallel-code-review` uses a compressed version: IDENTIFY SCOPE -> DISPATCH (3 reviewers in parallel) -> AGGREGATE -> VERDICT. The fan-out/fan-in pattern -- dispatch independent subagents, collect results, merge by severity.

Pipeline skills differ from standard skills in that they:
- Almost always set `context: fork` to isolate execution
- List `Task` in `allowed-tools` because they dispatch subagents
- Enforce timeouts per phase (5 minutes default per agent)
- Save artifacts to disk at each phase boundary -- context is ephemeral, files persist

## ADR System

Architectural Decision Records live in `adr/`. They're numbered markdown files tracking major design decisions -- why the learning system uses SQLite instead of markdown files, why hooks replace L1/L2 retro files, how graduation works.

### The adr-context-injector Hook

When you start a pipeline session, you create `.adr-session.json` in the project root:

```json
{
  "adr_path": "adr/011-choose-your-adventure-docs.md",
  "adr_hash": "abc123",
  "domain": "documentation"
}
```

The `adr-context-injector` hook (UserPromptSubmit) detects this file and injects ADR compliance context into every prompt. It checks for relevance keywords -- "pipeline", "skill", "agent", "create", "build" -- and only injects when the prompt looks like it's doing pipeline work. The injection includes:

- Mandatory `adr-query.py context` command before creating components
- Compliance check command after writing files
- ADR integrity verification via hash

This ensures every subagent in a pipeline session knows about the governing ADR, even if the orchestrator forgot to mention it.

### ADR Enforcement

The `adr-enforcement` hook (PostToolUse) verifies that written files comply with the active ADR after every Write/Edit. Advisory, not blocking -- but it's in your face about compliance failures.

## MCP Integration

Four MCP servers are configured:

| Server | Purpose | Key Tools |
|--------|---------|-----------|
| **gopls** | Go workspace intelligence | `go_diagnostics`, `go_search`, `go_file_context`, `go_symbol_references`, `go_vulncheck` |
| **Context7** | Library documentation lookup | `resolve-library-id`, `query-docs` |
| **Playwright** | Browser automation | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form` |
| **Chrome DevTools** | Chrome debugging | Network inspection, console access |

The catch: MCP tools are **deferred** in subagent contexts. When a pipeline dispatches a subagent via `Task`, that subagent can't call `mcp__gopls__go_diagnostics` directly. It has to use `ToolSearch` first to fetch the schema:

```
ToolSearch(query: "select:mcp__gopls__go_diagnostics")
```

Only after ToolSearch returns the full schema definition can the subagent invoke the tool. This is easy to miss and causes silent failures when subagents try MCP tools without the fetch step.

## Quality Gates

### The Wave Review Pattern

The `roast` skill dispatches 5 parallel reviewer personas -- Contrarian, Newcomer, Pragmatic Builder, Skeptical Senior, Pedant. Each reads the same target from a different critical angle. The coordinator validates every claim against actual evidence (file contents, line numbers) and categorizes findings as VALID, PARTIAL, UNFOUNDED, or SUBJECTIVE. Only VALID and PARTIAL findings make the final report.

`parallel-code-review` does something similar with 3 reviewers: Security, Business Logic, Architecture. Each runs in a separate subagent. Findings are aggregated by severity into a BLOCK/FIX/APPROVE verdict.

### The Retro Graduation Cycle

This is the quality feedback loop that makes the toolkit self-improving:

1. Work happens. Hooks capture learnings.
2. PR gets created. `retro-graduation-gate` fires, warns about ungraduated entries.
3. Before merge, you run `/retro graduate`. The skill queries learning.db for high-confidence entries, proposes where to embed them (which agent or skill file), and waits for confirmation.
4. Approved entries get written into the actual agent/skill markdown. The `graduated_to` column in learning.db records the target file.
5. Next session, those patterns are baked into the agent itself instead of being injected from the DB.

### Anti-AI Validation

The `de-ai-pipeline` skill runs a scan-fix-verify loop on documentation. `scripts/scan-ai-patterns.py` checks against 323 banned patterns across 24 categories (pulled from `scripts/data/banned-patterns.json`). The `anti-ai-editor` skill fixes flagged patterns. Loop repeats until clean, max 3 iterations.

Banned words include the usual suspects: "delve", "leverage", "streamline", "foster", "spearheaded". But also structural patterns -- the list-of-three, the "In conclusion" wrapper, the "It's important to note" throat-clearing.

## Anti-Rationalization

This is the toolkit's immune system against LLM self-deception. Claude doesn't lie on purpose -- it constructs plausible-sounding reasons to skip steps. "The code looks correct" (looking != being correct). "Simple change" (simple changes cause complex bugs). "Should work" (should != does).

The anti-rationalization system has three layers:

**CLAUDE.md table**: A hardcoded lookup of common rationalizations mapped to required actions. "Already done" -> "Actually verify." "I'm confident" -> "Verify regardless." These are in the global CLAUDE.md that every session reads.

**Auto-injection via hooks**: The `instruction-reminder` hook (UserPromptSubmit) re-injects CLAUDE.md snippets to combat context drift. As conversations get long, early instructions fade from attention. The hook brings them back.

**Skill-level embedding**: Every agent and skill embeds anti-rationalization in its operator context. The `with-anti-rationalization` skill can be composed with other skills to add an extra verification layer. Gate enforcement in skills is itself an anti-rationalization mechanism -- you can't skip Phase 3 by claiming Phase 2 "probably" passed.

The pattern works because it doesn't trust the LLM to police itself. It uses structural enforcement (gates, hooks, exit codes) instead of behavioral instructions alone.
