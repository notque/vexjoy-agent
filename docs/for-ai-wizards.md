---
summary: "Architecture deep-dive: router internals, hook lifecycle, telemetry database."
read_when:
  - "studying how routing, hooks, and telemetry wire together"
---

# Architecture Deep-Dive

This guide traces a request through routing, agents, skills, hooks, and telemetry, then covers the supporting pipeline, ADR, and quality systems.

## The Router

`skills/meta/do/SKILL.md` is the routing source of truth. It classifies request complexity, reads the cached or generated manifest from `scripts/routing-manifest.py`, and selects an agent and skill by intent. `scripts/pre-route.py` checks that selection. A high-confidence PR or security force-route can override the semantic skill choice.

The router matches intent against agent and skill descriptions; frontmatter triggers are hints:

```yaml
routing:
  triggers:
    - go
    - golang
    - ".go files"
    - goroutine
    - gopls
  process-topics:
    - programming
    - concurrency
    - debugging
```

Force-route entries bind when their domain matches the request's meaning. If PR or security intent owns the primary skill, the router retains that skill and stacks relevant domain guidance. `scripts/build-dispatch.py` prepares the resulting agent dispatch.

A dispatch should preserve both the selected route and the evidence used to select it. That distinction powers later evaluation: a route can be syntactically valid yet semantically wrong, and a successful task does not prove every stacked enhancement helped. The feedback loop therefore records the agent, primary skill, enhancements, and eventual outcome separately. Health-aware reranking can adjust future choices without rewriting the routing taxonomy after one anecdote.

The former `skill-evaluator` and `auto-plan-detector` hooks are disabled or removed. Their routing and planning responsibilities now live in `/do`, whose plan rule is an instruction. The one hook check is narrower: `pretool-plan-gate` blocks Write and Edit under the project root's `agents/` and `skills/` directories until a `task_plan.md` modified in the last 24 hours exists there.

## Agent Architecture

An agent is a Markdown file in `agents/` with YAML frontmatter. A representative schema:

```yaml
---
name: golang-general-engineer
description: "Go development: features, debugging, code review, performance."
color: blue
memory: project
hooks:
  PostToolUse:
    - type: command
      command: |
        python3 -c "
        import sys, json
        data = json.loads(sys.stdin.read())
        tool = data.get('tool_name', '')
        command = data.get('tool_input', {}).get('command', '')
        # agent-specific hook logic
        "
      timeout: 5  # seconds
routing:
  triggers: [go, golang, goroutine, gopls]
  process-topics: [programming, concurrency, debugging]
  pairs_with: [programming]
allowed-tools: [Read, Edit, Write, Bash, Glob, Grep, Agent, Skill]
---
```

`name` identifies the agent in routing. `hooks` registers agent-specific handlers; they read the same JSON payload as settings hooks (see Hook System), and `timeout` is in seconds. `routing.triggers` supplies routing hints. `routing.process-topics` names knowledge areas; no script reads it today (`scripts/feature-state.py` still matches features on the older `retro-topics` key, which no agent carries). `memory: project` scopes remembered context to the project.

`allowed-tools` is advisory for agents. Claude Code restricts a subagent's tools through its `tools:` field, which no toolkit agent sets, so every agent runs with all tools. The list documents intent and feeds `scripts/audit-tool-restrictions.py`.

Agent bodies distinguish hardcoded behaviors, overridable defaults, and opt-in behaviors. Repository and user instructions determine which defaults and options apply.

Reviewer agents (`reviewer-code`, `reviewer-system`, `reviewer-domain`, and `reviewer-perspectives`) are dispatched by review skills. They inspect and report; they do not modify code. That read-only rule is an instruction in their prompts, not a tool restriction: their `allowed-tools` lists are advisory, and no hook stops a reviewer from editing files.

## Skill System

A skill is `skills/{category}/{name}/SKILL.md`. Agents supply domain expertise; skills define execution methods.

```yaml
---
name: workflow
description: "Structured work: multi-phase tasks, feature builds, planning, objective loops, hill climbing."
user-invocable: true
context: fork
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Skill, Agent, Task]
routing:
  force_route: true
  not_for: "code review (use review), testing (use testing), security (use security)"
  triggers: [workflow, multi-phase task, write spec, keep working until, hill climb on this metric]
  category: process
  pairs_with: [review, testing, security, pr-workflow]
---
```

This is the real `skills/process/workflow/SKILL.md` frontmatter, with lists shortened.

`context: fork` isolates execution in a subagent context. `user-invocable: false` hides a skill from the slash menu while leaving it available to routers and other skills. On a skill, `allowed-tools` names the tools Claude Code may use without a permission prompt while the skill is active; it does not take other tools away.

Keep the core procedure in `SKILL.md`; put specialized formats and detailed references in `references/` for progressive loading. Skills use explicit exit gates so a phase advances only after its required condition is true.

## Hook System

Hooks are Python scripts registered by event type in `~/.claude/settings.json`. They receive JSON on stdin and emit JSON on stdout. A hook can inject context, block a tool, or remain silent.

### Execution contract

Input varies by event:

```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "..."},
  "tool_response": {"...": "tool-specific result"},
  "cwd": "/path/to/project"
}
```

`hook_utils.get_tool_result()` reads the result from `tool_response` or `tool_result`, whichever the runtime sends.

Output uses `hook_utils.py`:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "injected text for Claude's system prompt",
    "userMessage": "text that MUST be shown to the user verbatim"
  }
}
```

Exit `0` passes. What exit `2` does depends on the event in Claude Code:

| Event | Exit 2 |
|---|---|
| `PreToolUse` | Blocks the tool call and shows stderr to Claude. |
| `PostToolUse` | Shows stderr to Claude; the tool has already run. |
| `UserPromptSubmit` | Blocks the prompt. |
| `Stop`, `SubagentStop` | Blocks stopping, so the model keeps working. |
| `SessionStart`, `PreCompact` | Blocks nothing. |

A PreToolUse hook can also deny with `permissionDecision: "deny"` in JSON on exit 0; most toolkit gates do. A Stop or SubagentStop hook blocks only with exit 2 or `"decision": "block"`. A PreToolUse-style deny there is ignored, which is why `subagent-completion-guard` never blocks. Blocking hooks must preserve their denial code. `once: true` limits a hook to the first matching event in a session.

Hook output is part of the user-facing contract. `additionalContext` changes the model's working context; `userMessage` is text the user must see. A hook that has nothing actionable to add should stay silent. Blocking decisions must be deterministic enough to explain from the submitted tool call, because retries and alternate clients still need the same boundary.

### Lifecycle

The configured lifecycle includes `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, `Stop`, `StopFailure`, and `SessionEnd`. Inspect `~/.claude/settings.json` for the current hook list; registrations change more often than the execution contract.

| Event | Architectural role |
|---|---|
| `SessionStart` | Synchronize configuration and inject project, operator, ADR, and cached routing context. |
| `UserPromptSubmit` | Capture prompt-level evidence and resolve outcomes whose signal appears in the user's next message. |
| `PreToolUse` | Enforce safety, branch, planning, pipeline-phase, and creation constraints before mutation. |
| `PostToolUse` | Record usage and routing evidence, run advisory checks, and update generated indexes after successful work. |
| `PreCompact` / `PostCompact` | Preserve and restore durable session context across compression. |
| `SubagentStart` / `SubagentStop` | Give delegated work its operating context and close its routing records. |
| `Stop` / `StopFailure` | Record the turn's summary and failures; score errored or stale routing outcomes. |
| `SessionEnd` | Resolve every routing outcome still pending when the session ends. |

This split matters when adding a hook. A check that can deny an unsafe operation belongs before the tool; an observer that records what happened belongs after it. Prompt and stop hooks should not impersonate tool gates because they lack the same action boundary.

Four hooks carry most of the architecture:

- `routing-decision-recorder` reads the `[do-route]` marker after an agent or workflow dispatch and stores one idempotent routing decision per marker.
- `routing-outcome-finalizer` resolves pending dispatches on the next user prompt: explicit acceptance succeeds, recorded tool errors or clear rejection fail, and unrelated prompts remain neutral.
- `session-context` injects a fresh pre-built dream payload from `~/.claude/state/` without querying the database.
- `pretool-unified-gate` blocks `git add -f` on ignored paths, dangerous commands, unregistered component creation, sensitive-file writes, and dev servers bound to public interfaces. Its raw push and PR check runs only when `CLAUDE_OPERATOR_PROFILE` is not `personal`, the default. It fails open if it crashes. Branch safety, review-before-push, and CI merge gates add narrower checks; [Start Here](start-here.md#gates-in-every-repo) lists every blocking hook.

AI attribution is configured declaratively in `settings.json`, not by a hook.

## Telemetry Database

Telemetry lives in the WAL-mode SQLite database `~/.claude/learning/learning.db`; FTS5 provides full-text search. `hooks/lib/learning_db_v2.py` is the shared storage layer for routing telemetry, safety governance, and the voice corpus.

### Core schema

```sql
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL,        -- error, pivot, review, design, debug, gotcha, effectiveness, misroute (8 categories)
    confidence REAL DEFAULT 0.5,
    tags TEXT,
    source TEXT NOT NULL,           -- hook:routing-decision-recorder, hook:review-capture, hook:prompt-capture
    source_detail TEXT,             -- e.g. "Bash:golang-general-engineer"
    project_path TEXT,
    session_id TEXT,
    observation_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    graduated_to TEXT,              -- unused
    error_signature TEXT,
    error_type TEXT,
    fix_type TEXT,                  -- auto, skill, agent, manual
    fix_action TEXT,                -- create_file, systematic-debugging, use_replace_all, etc.
    UNIQUE(topic, key)
);
```

Supporting tables store run envelopes, routing outcome bases, evidence events and decisions, governance events, failure-deduplication keys, session metrics, FTS data, and migrations.

| Table group | What it preserves |
|---|---|
| `telemetry_runs` | Per-run envelope such as run ID, git SHA, model, token count, wall time, and tool errors. |
| `routing_outcome_basis` | Counters describing how route outcomes were decided, including the silent-success share. |
| `evidence_sessions`, `evidence_events`, `evidence_route_decisions` | The evidence read model used to reconstruct agent activity and routing decisions. |
| `governance_events` | Security and policy events emitted by branch, configuration, privacy, worktree, unified, and merge gates. |
| `route_failure_dedup` | Idempotency keys that prevent duplicate route-failure reporting. |
| `sessions`, `session_stats` | Session-level accounting and aggregate metrics. |
| `learnings_fts`, `schema_migrations` | Search support and database-version history. |
| `activations` | Learning activations (topic, key, outcome); nothing writes it today, and pruning drops rows after 90 days. |
| `evidence_events_fts` | Full-text search over evidence events. |
| `instruction_compliance` | Per-observation compliance with a named instruction. |
| `jev_calls`, `jev_intent_alignments` | Jev transport calls (latency, tokens, redactions) and `/d` intent-alignment receipts. |
| `compaction_events`, `session_usage` | Compaction before/after sizes and per-turn context and cost samples. |
| `harness_runs` | Hill-climbing rounds: lever, variant, metrics, and whether the variant was kept. |

The active `learnings` topics have separate ownership:

| Topic | Category | Writer | Reader |
|---|---|---|---|
| `routing` | `effectiveness` | `routing-decision-recorder`, then `routing-outcome-finalizer` | routing health, statistics, weights, and stack-usage commands |
| `voice-sample` | `voice` | `prompt-capture` | corpus consumers; no automated reader |

Review findings and false positives have dedicated, lightly used paths. Older categories are historical unless current code names them.

### Routing feedback loop

1. `/do` chooses an agent and skill and stamps a `[do-route]` marker into the dispatch.
2. `routing-decision-recorder` stores the decision and a pending outcome.
3. `routing-outcome-finalizer` scores it when the next prompt provides evidence. Subagent-stop handling validates pending records, the Stop fallback scores only errored or stale (over 6 hours) records, and the same hook resolves the rest on SessionEnd.
4. Reporting commands measure route health and compare cohorts.
5. `route-weights` exposes health-aware reranking weights as JSON.

```bash
# Loop health: pending vs resolved, outcome basis, silent-success share
python3 scripts/learning-db.py route-health

# Routing decisions aggregated by agent, skill, week, or day
python3 scripts/learning-db.py route-stats --by week

# Did that change help? Compare two git-SHA or date cohorts
python3 scripts/learning-db.py route-delta --from SHA --to SHA

# Enhancement skills seen stacked, with times stacked and last seen
python3 scripts/learning-db.py stack-usage
```

## Pipeline Architecture

Pipeline skills use a fan-out/fan-in shape: gather independent evidence, compile it, generate or act, validate deterministically, refine within a bound, and deliver the result. They commonly set `context: fork`, allow `Task` for subagent dispatch, bound each phase, and persist artifacts at phase boundaries so results survive ephemeral context.

The exact phase names vary. For example, a research-to-article workflow may use GATHER, COMPILE, GROUND, GENERATE, VALIDATE, REFINE, and OUTPUT, while parallel review compresses this to IDENTIFY SCOPE, DISPATCH, AGGREGATE, and VERDICT. The invariant is explicit boundaries with evidence saved before fan-in.

The coordinator, not an individual worker, owns fan-in. It resolves duplicated findings, checks source support, and applies the workflow's acceptance rule. Per-phase timeouts prevent one branch from holding the whole run open. Persisting intermediate outputs also makes a partial failure inspectable and lets a later phase restart from evidence instead of regenerating earlier work.

## ADR System

Architectural Decision Records in `adr/` (gitignored and local-only, so a fresh clone has none) explain consequential design choices and bind component creation to recorded decisions. A pipeline can identify its governing ADR in `.adr-session.json`:

```json
{
  "adr_path": "adr/011-choose-your-adventure-docs.md",
  "adr_hash": "abc123",
  "domain": "documentation"
}
```

At session start, `session-adr-health-check` surfaces this context. After writes, `adr-enforcement` checks that the session consulted ADR context, the written files comply, and the ADR hash remains intact. Its findings are advisory; creation gates can separately block unregistered components.

## MCP Integration

Configured MCP servers provide workspace intelligence, external documentation, browser automation, and browser debugging. Their exact inventory is environment-dependent. MCP tools may be deferred in subagent contexts; fetch a tool's schema before invoking it. For example:

```
ToolSearch("gopls")
```

Then call the returned tool using its declared schema.

## Quality Gates

Review skills fan out independent perspectives, then validate their claims against file contents and other concrete evidence before aggregation. Findings are classified by validity and severity; unsupported opinions do not become required fixes.

The `roast` pattern uses several reader perspectives—such as newcomer, contrarian, pragmatic builder, skeptical senior, and pedant—to expose different failure modes. Parallel code review instead separates security, business logic, and architecture. These are discovery roles, not independent authorities: the coordinator verifies file paths, line references, and claimed behavior before producing a verdict such as BLOCK, FIX, or APPROVE.

For prose, `scripts/scan-ai-patterns.py` checks documentation against `scripts/data/banned-patterns.json`. Treat it as a mechanical signal, not a substitute for editorial judgment.

## Evidence for Completion

Completion claims require current evidence: the relevant test, build, validator, exit code, or inspected artifact. Shared instructions establish that rule; lifecycle hooks re-inject durable context at session and compaction boundaries; individual skills define the checks their own work must pass. Written confidence does not replace an executed check.
