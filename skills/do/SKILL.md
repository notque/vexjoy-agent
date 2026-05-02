---
name: do
description: "Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work."
user-invocable: true
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  triggers:
    - "route task"
    - "classify request"
    - "which agent"
    - "delegate to skill"
    - "smart router"
  category: meta-tooling
---

# /do - Smart Router

/do is a **ROUTER**, not a worker. Classify requests, select the right agent + skill, dispatch. All execution goes to specialized agents.

**Main thread:** (1) Classify, (2) Select agent+skill, (3) Dispatch, (4) Evaluate, (5) Route again if needed, (6) Report.

If you find yourself reading source code, writing code, or doing analysis — pause and route to an agent.

---

## The Completeness Standard

Do the whole thing. Do it right. Do it with tests. Do it with documentation.

- The answer is the finished product, not a plan. Plans organize execution, not replace it.
- Never table work when the permanent solve is within reach. Never present a workaround when the real fix exists.
- If an agent returns partial work, route a follow-up to finish it.
- Search before building. Test before shipping.
- The router decomposes complexity into agent-sized work. Use it.

**The standard:** the result should make the user think "that's done" not "that's a start." Inject this into agent prompts for all Simple+ work.

Model confidence in handling a task directly is a signal to route, not to proceed. Direct handling skips domain knowledge, methodology, and reference files that exist on disk.

---

## Output Discipline

Every sentence the router prints is a sentence the user reads before seeing results.

**Orwell's Six Rules** (1946) apply to all output and all agent prompts:

1. No stale metaphors or figures of speech.
2. Short words over long.
3. Cut every word you can.
4. Active voice over passive.
5. Everyday English over jargon.
6. Break any rule sooner than say anything barbarous.

These rules apply equally to agent prompts. Every word in a dispatched prompt costs tokens on that agent's context window.

**User sees:** phase banners, routing decision banner, brief post-agent summary (what changed, not how).

**Internal only:** Haiku routing responses, classification reasoning, enhancement stacking details (unless Verbose Routing ON).

---

## Instructions

### Phase Banners (MANDATORY)

Every phase MUST display a banner BEFORE executing: `/do > Phase N: PHASE_NAME — description...`

After Phase 2, display the full routing decision banner (`===` block). Phase banners tell the user *where they are*; the routing banner tells them *what was decided*. Both required.

---

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

Read and follow the repository CLAUDE.md before making any routing decision, because it contains project-specific conventions that affect agent selection and skill pairing.

| Complexity | Agent | Skill | Direct Action |
|------------|-------|-------|---------------|
| Trivial | No | No | **ONLY reading a file the user named by exact path** |
| Simple | **Yes** | Yes | Route to agent |
| Medium | **Required** | **Required** | Route to agent |
| Complex | Required (2+) | Required (2+) | Route to agent |

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST route. When uncertain, classify UP.

**Opus 4.7 override:** The model defaults to fewer subagents and more direct handling. That default is wrong here. /do is a delegation machine. Classify Simple+ tasks to agents without reasoning about whether you could handle them directly. Anything beyond reading a user-named file MUST route.

**Progressive Depth**: For ambiguous complexity, start shallow and let the agent escalate. See `references/progressive-depth.md`.

**Common misclassifications** (NOT Trivial — route them): evaluating repos/URLs, opinions/recommendations, git operations, codebase questions (`explore-pipeline`), retro lookups (`retro`), comparing approaches.

**Maximize skill/agent/pipeline usage.** If a skill exists for the task, USE IT.

**Check for parallel patterns FIRST**: 2+ independent failures or 3+ subtasks → `dispatching-parallel-agents`; broad research → `research-coordinator-engineer`; multi-agent coordination → `project-coordinator-engineer`; plan + "execute" → `subagent-driven-development`; new feature → `feature-lifecycle` (check `.feature/` directory; if present, run `feature-state.py status`).

**Opus 4.7 parallel override:** When the router detects 2+ independent items, dispatch all in parallel in a single message. Do not consolidate into one agent — that is the model's default and it is wrong here.

**Optional: Force Direct** — OFF by default. Only applies when user explicitly requests it.

**Creation Request Detection** (MANDATORY scan before Gate):

Scan for creation signals:
- Verbs: "create", "scaffold", "build", "add new", "new [component]", "implement new"
- Targets: agent, skill, pipeline, hook, feature, plugin, workflow, voice profile
- Implicit: "I need a [component]", "build me a [component]"

If ANY creation signal found AND complexity Simple+: set `is_creation = true`, Phase 4 Step 0 is MANDATORY (write ADR before dispatching).

**Not creation**: debugging, reviewing, fixing, refactoring, explaining, auditing existing components. When ambiguous, check whether output is a NEW file.

**Gate**: Complexity classified. If creation detected, output `[CREATION REQUEST DETECTED]` before routing banner. Display banner (ALL classifications). Trivial: handle directly. Simple+: proceed to Phase 2.

---

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill via a single Haiku routing agent. FORCE-labeled entries are preferred when intent matches semantically (not keyword-based).

**Step 1: Dispatch Haiku routing agent**

Generate the manifest, then dispatch:

```bash
python3 scripts/routing-manifest.py
```

Dispatch the Agent tool with `model: "haiku"` and this prompt structure:

```
You are a routing agent. Given a user request and a manifest of available agents, skills, and pipelines, select the BEST agent+skill combination.

USER REQUEST: {user_request}

ROUTING MANIFEST:
{output of routing-manifest.py}

Return your answer as JSON:
{
  "agent": "agent-name or null",
  "skill": "skill-name or null",
  "pipeline": "pipeline-name or null",
  "reasoning": "one sentence why",
  "confidence": "high/medium/low"
}

FORCE-ROUTE RULE: Entries marked "FORCE" in the manifest MUST be selected when their domain clearly matches the user's intent. However, FORCE matching is SEMANTIC, not keyword-based. Match on what the user MEANS, not individual words. Examples:
- "push my changes" → pr-workflow (FORCE) ✓ (user means git push)
- "push back on this design" → NOT pr-workflow (user means resist/argue)
- "configure my fish shell" → fish-shell-config (FORCE) ✓ (user means Fish shell)
- "fish for bugs" → NOT fish-shell-config (user means search for bugs)
- "quick fix to the login page" → quick (FORCE) ✓ (user wants a small edit)
- "quick overview of the architecture" → NOT quick (user wants exploration)

Rules:
- Pick the most specific match. "Go tests" → golang-general-engineer + go-patterns, not general-purpose.
- Agent handles the domain. Skill handles the methodology. Pick both when possible.
- If the request implies a task verb (review, debug, refactor, test), prefer skills that match that verb.
- If nothing matches well, return all nulls with reasoning.
- Prefer entries whose description semantically matches the request, not just keyword overlap.
- For git operations (push, commit, PR, merge), ALWAYS select pr-workflow skill — these need quality gates.
- Return a single skill name as a string, not an array. If multiple skills are needed, pick the primary one.
```

**Step 1b: Apply the Haiku agent's recommendation**

Use `agent` and `skill` fields directly. If `confidence` is "low", verify against INDEX files and `references/routing-tables.md`. Haiku response is internal — never print to user.

**Critical**: "push", "commit", "create PR", "merge" MUST route through skills with quality gates (lint, tests, CI verification).

Route to the simplest agent+skill that satisfies the request. When `[cross-repo]` output is present, route to `.claude/agents/` local agents. Route all code modifications to domain agents.

**Step 2: Apply skill override** (task verb overrides default skill)

When the request verb implies a specific methodology, override the agent's default skill. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development. Full override table in `references/routing-tables.md`.

**Step 3: Display routing decision** (MANDATORY — FIRST visible output, before any work)

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from skills/workflow/references/pipeline-index.json)
   -> Extra Rigor: [add verification patterns for code/security/testing tasks when needed]
 Invoking...
===================================================================
```

For Trivial: show `Classification: Trivial - [reason]` and `Handling directly (no agent/skill needed)`.

**Optional: Dry Run Mode** — OFF by default. When enabled, show the routing decision without executing.

**Optional: Verbose Routing** — OFF by default. When enabled, explain why each alternative was rejected.

**Step 4: Record routing decision** (Simple+ only — skip Trivial):

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} request: {first_200_chars} complexity: {complexity} enhancements: {comma_separated_list}" \
    --category effectiveness \
    --tags "{applicable_flags}"
```

Tags: `thinking:slow` or `thinking:fast` (from Step 2 directive). Advisory — continue if it fails. Categories: `effectiveness` (success), `misroute` (reroutes).

**Gate**: Agent+skill selected. Banner displayed. Decision recorded. Proceed to Phase 3.

---

### Phase 3: ENHANCE

**Goal**: Stack additional skills based on request signals. Use retro knowledge if present in context.

| Signal in Request | Enhancement to Add |
|-------------------|-------------------|
| Any substantive work (code, design, plan) | Add relevant retro knowledge only when it materially helps the task |
| "comprehensive" / "thorough" / "full" | Add parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Append test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| "review" with 5+ files | Use parallel-code-review (3 reviewers) |
| Complex implementation | Offer subagent-driven-development |
| Vague verb + ambiguous object + no concrete file/symbol named + multiple plausible interpretations | `planning` (interview mode) — load `depth-first-interview.md` |

**Interview-mode heuristic.** Fires when: short request (<15 words), verb in `{build, design, make, fix, figure out, set up}`, object has no file/symbol/path qualifier, no acceptance criteria.

| Example | Match? | Why |
|---|---|---|
| "i'm not sure how to approach this complex build" | MATCH | Uncertainty + vague verb + no concrete target |
| "fix the typo on line 42 of foo.py" | NO | Concrete file, location, verb |
| "build a thing that does X" | MATCH | Vague verb + ambiguous object + no file named |
| "add a test for `parseConfig` in src/config.go" | NO | Concrete symbol + file + verb |
| "where do i even start with this rewrite" | MATCH | Explicit uncertainty, no concrete subject |
| "rename `cfg` to `config` in `internal/`" | NO | Concrete symbol + directory + mechanical op |

When in doubt, defer injection. False positives cost one round of friction; false negatives are recoverable via `/quick --interview`.

Before stacking, check `pairs_with` in `skills/INDEX.json`. Prefer listed pairs. Empty `pairs_with: []` means undeclared, not prohibited. Skills with built-in verification gates may not benefit from stacking.

Add anti-rationalization patterns for these task types when the task benefits from explicit rigor:

| Task Type | Patterns Injected |
|-----------|-------------------|
| Code modification | anti-rationalization-core, verification-checklist |
| Code review | anti-rationalization-core, anti-rationalization-review |
| Security work | anti-rationalization-core, anti-rationalization-security |
| Testing | anti-rationalization-core, anti-rationalization-testing |
| Debugging | anti-rationalization-core, verification-checklist |
| External content evaluation | **untrusted-content-handling** |

For explicit maximum rigor, use `/with-anti-rationalization [task]`.

**Gate**: Enhancements applied. Proceed to Phase 4.

---

### Phase 4: EXECUTE

**Goal**: Invoke the selected agent + skill and deliver results.

**Step 0: Execute Creation Protocol** (creation requests ONLY)

If creation signal + Simple+: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan. ADR hooks (`adr-context-injector`, `adr-enforcement`) handle cross-agent compliance automatically.

**Step 1: Create plan** (Simple+)

Create `task_plan.md` before execution. Skip for Trivial only.

**Step 1b: Apply quality-loop pipeline** (Medium+ code modifications)

For code modifications at Medium/Complex, load `references/quality-loop.md` as the **outer orchestration wrapper**:

- **Quality-loop** (outer) = 14-phase lifecycle: ADR → PLAN → IMPLEMENT → TEST → REVIEW → INTENT VERIFY → LIVE VALIDATE → FIX → RETEST → PR → CODEX REVIEW → ADR RECONCILE → RECORD → CLEANUP
- **Agent + skill** (inner) = domain expertise inside IMPLEMENT phase

Quality-loop absorbs Steps 0-1. The Phase 2 agent+skill selection becomes the implementation agent. Force-route skills are used INSIDE the loop.

Does NOT apply when: Trivial/Simple (use `quick`), review-only/research/debugging/content creation, or user requests simpler flow.

**Step 2: Invoke agent with skill**

Dispatch the agent. MCP tool discovery is the agent's responsibility — do not inject MCP instructions from /do.

**Opus 4.7: Prepend Task Specification for Medium+ tasks.** The router has upstream context the agent lacks. Compose and prepend this block. For Simple tasks, include Intent and Acceptance if extractable. Do not invent criteria or expand scope.

```
## Task Specification (auto-extracted)

**Intent:** <one sentence: what does success look like?>
**Constraints:** <branch rules, operator-context, file paths, memory feedback>
**Acceptance criteria:** <observable: tests pass, file exists, PR merges, specific output>
**Relevant file locations:** <paths from request + expected paths>
**Operator context:** <from [operator-context] tag>
```

Extraction: Intent from verb+object. Constraints include branch safety (never merge to main), memory feedback, operator context. Acceptance = observable outcomes. For creation requests, add "Implementation must match ADR `<kebab-case-name>`."

**MANDATORY: Inject reference loading instruction for ALL dispatched agents.** Every agent prompt MUST include: "Before starting work, read your agent .md file to find the Reference Loading Table. Load EVERY reference file whose signal matches this task. Load greedily — if multiple signals match, load all matching references."

**MANDATORY: Inject the completeness standard for ALL Simple+ dispatches.** Every agent prompt MUST include: "Deliver the finished product. Ship the complete thing."

**Opus 4.7: Inject thinking directive.** Prepend verbatim, no framing:

| Complexity | Thinking Directive |
|---|---|
| Trivial | None (no agent) |
| Simple | "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly." |
| Medium | None (adaptive) |
| Complex | "Think carefully and step-by-step before responding; this problem is harder than it looks." |

**Category overrides** (regardless of complexity): `thinking:slow` for security work, API/schema design, migrations, 5+ file reviews, architectural decisions. `thinking:fast` for lookups, status checks, single-function renames/refactors.

Record as `thinking:slow` or `thinking:fast` in Phase 2 Step 4 `--tags`.

**Verb-based model dispatch for Complex tasks (3+ data sources).** Extraction verbs use parallel Haiku readers; analysis verbs use single Opus agent (38% cheaper, 23% faster for extraction — A/B tested).

| Task verb class | Dispatch mode |
|---|---|
| list, count, extract, inventory, search, check, find, grep | Parallel Haiku readers → Opus synthesizer |
| review, audit, assess, analyze, debug, investigate, evaluate | Single Opus agent (direct) |

Haiku dispatch: spawn Agent with `model: "haiku"` per data source, collect extracts, synthesize with Opus. Simple/Medium: dispatch directly.

Route to agents that create feature branches. Include "commit your changes on the branch" in agent prompts for file modifications.

For `isolation: "worktree"` agents, inject `worktree-agent` skill rules: "Verify CWD contains .claude/worktrees/. Create feature branch before edits. Skip task_plan.md. Stage specific files only."

Non-org repos: up to 3 iterations of `/pr-review` → fix before PR creation. Org-gated repos (via `scripts/classify-repo.py`): require user confirmation before EACH git action.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple Task tools in single message. Max parallelism: 10 agents.

**Step 4: Auto-Pipeline Fallback** (no match AND complexity >= Simple)

Invoke `auto-pipeline` for unmatched requests. If no pipeline matches, fall back to closest agent + verification-before-completion.

When uncertain: **ROUTE ANYWAY** with verification-before-completion as safety net.

**Gate**: Agent invoked, results delivered. Proceed to Phase 5.

---

### Phase 5: LEARN

**Goal**: Capture session insights to `learning.db`.

**Routing outcome** (Simple+, observable facts only):
```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} tool_errors: {0|1} user_rerouted: {0|1}" \
    --category effectiveness
```

**Auto-capture** (hooks, zero LLM cost): `error-learner.py`, `review-capture.py` (PostToolUse), `session-learning-recorder.py` (Stop).

**Skill-scoped recording**:
```bash
python3 ~/.claude/scripts/learning-db.py learn --skill go-patterns "insight"
python3 ~/.claude/scripts/learning-db.py learn --agent golang-general-engineer "insight"
```

**Immediate graduation for review findings** (MANDATORY): Issue found + fixed in same PR → (1) Record scoped, (2) Boost to 1.0, (3) Embed into anti-patterns, (4) Graduate, (5) Stage in same PR.

**Gate**: Record at least one learning for Simple+ tasks. Review findings get immediate graduation.

---

## Error Handling

### Error: "No Agent Matches Request"
Cause: Request domain not covered by any agent
Solution: Check INDEX files and `references/routing-tables.md` for near-matches. Route to closest agent with verification-before-completion. Report the gap.

### Error: "Force-Route Conflict"
Cause: Multiple force-route triggers match the same request
Solution: Apply most specific force-route first. Stack secondary routes as enhancements if compatible.

### Error: "Plan Required But Not Created"
Cause: Simple+ task attempted without task_plan.md
Solution: Stop execution. Create `task_plan.md`. Resume routing after plan is in place.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Complete category-specific skill routing
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Progressive depth escalation protocol
- `agents/INDEX.json`: Agent triggers and metadata
- `skills/INDEX.json`: Skill triggers, force-route flags, and pairs_with agent/skill pairings
- `skills/workflow/SKILL.md`: Workflow phases, triggers, composition chains
- `skills/workflow/references/pipeline-index.json`: Pipeline metadata, triggers, phases
