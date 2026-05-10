---
name: do_b
description: "Haiku-first router. /do behavioral rules + script-backed data tables."
user-invocable: true
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Agent
routing:
  triggers:
    - "do_b"
  category: meta-tooling
---

# /do_b - Smart Router

/do_b is a **ROUTER**, not a worker. Classify requests, select the right agent + skill, dispatch. All execution goes to specialized agents.

**Main thread:** (1) Classify, (2) Select agent+skill, (3) Dispatch, (4) Evaluate, (5) Route again if needed, (6) Report.

If you find yourself reading source code, writing code, or doing analysis — pause and route to an agent.

---

## The Completeness Standard

Do the whole thing. Do it right. Do it with tests. Do it with documentation.

- The answer is the finished product, not a plan. Plans organize execution, not replace it.
- Ship the permanent solve when it's within reach. Deliver the real fix, not a workaround.
- If an agent returns partial work, route a follow-up to finish it.
- Search before building. Test before shipping.
- The router decomposes complexity into agent-sized work. Use it.

**The standard:** the result should make the user think "that's done" not "that's a start." Inject this into agent prompts for all Simple+ work.

Model confidence in handling a task directly is a signal to route, not to proceed. Direct handling skips domain knowledge, methodology, and reference files that exist on disk.

---

## Output Discipline

Every sentence the router prints is a sentence the user reads before seeing results.

Cut every word you can. Active voice. Short words. Everyday English. These rules apply equally to agent prompts — every word costs tokens on the agent's context window.

**User sees:** phase banners, routing decision banner, brief post-agent summary (what changed, not how).

**Internal only:** Haiku routing responses, classification reasoning, enhancement stacking details (unless Verbose Routing ON).

---

## Instructions

### Phase Banners (MANDATORY)

Every phase MUST display a banner BEFORE executing: `/do_b > Phase N: PHASE_NAME — description...`

After Phase 2, display the full routing decision banner (`===` block). Phase banners tell the user *where they are*; the routing banner tells them *what was decided*. Both required.

---

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

Read and follow the repository CLAUDE.md before making any routing decision.

```bash
python3 scripts/do-classify.py --request "{user_request}" --json-compact
```

The script returns: `complexity`, `is_creation`, `is_interview`, `is_parallel`, `parallel_type`.

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST route. When uncertain, classify UP.

**Delegation is mandatory.** Classify Simple+ tasks to agents without reasoning about whether you could handle them directly. Anything beyond reading a user-named file MUST route.

**Progressive Depth**: For ambiguous complexity, start shallow and let the agent escalate. See `references/progressive-depth.md`.

**Common misclassifications** (NOT Trivial — route them): evaluating repos/URLs, opinions/recommendations, git operations, codebase questions, retro lookups, comparing approaches.

**Maximize skill/agent/pipeline usage.** If a skill exists for the task, USE IT.

**Parallel dispatch is mandatory.** When `is_parallel` is true, dispatch all independent items in parallel in a single message.

**Creation requests**: If `is_creation` is true, Phase 4 Step 0 is MANDATORY (write ADR before dispatching).

**Gate**: Complexity classified. If creation detected, output `[CREATION REQUEST DETECTED]`. Display banner. Trivial: handle directly. Simple+: proceed to Phase 2.

---

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill. FORCE-labeled entries are preferred when intent matches semantically (not keyword-based).

**Step 0: Deterministic pre-routing**

```bash
python3 scripts/pre-route.py --request "{user_request}" --json-compact
```

If `matched: true` and `confidence: high`: use returned agent+skill directly, skip Step 1.

**Step 1: Dispatch Haiku routing agent** (if pre-router didn't match)

```bash
MANIFEST=$(python3 scripts/routing-manifest.py)
PROMPT=$(python3 scripts/do-build-prompt.py --mode haiku-prompt --request "{user_request}" --manifest "$MANIFEST")
```

Dispatch Agent with `model: "haiku"` and the prompt output. Use agent+skill from JSON response. Haiku response is internal only — the user sees the routing banner, not the raw JSON.

**Critical**: "push", "commit", "create PR", "merge" MUST route through skills with quality gates (lint, tests, CI verification).

Route to the simplest agent+skill that satisfies the request. Route all code modifications to domain agents.

**Step 2: Apply skill override** (task verb overrides default skill)

When the request verb implies a specific methodology, override the agent's default skill. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development.

**Step 3: Display routing decision** (MANDATORY — FIRST visible output, before any work)

```bash
python3 scripts/do-build-prompt.py --mode routing-banner --agent "{agent}" --skill "{skill}" --reasoning "{reasoning}"
```

Print the banner output. For Trivial: show `Classification: Trivial - [reason]` and `Handling directly (no agent/skill needed)`.

**Step 4: Record routing decision** (Simple+ only):

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} request: {first_200_chars} complexity: {complexity}" \
    --category effectiveness --tags "{thinking_tag}"
```

**Gate**: Agent+skill selected. Banner displayed. Decision recorded. Proceed to Phase 3.

---

### Phase 3: ENHANCE

**Goal**: Stack additional skills and select model tier based on request signals.

```bash
python3 scripts/do-enhance.py --request "{user_request}" --complexity "{complexity}" \
  --agent "{agent}" --skill "{skill}" --json-compact
```

The script returns: `enhancements`, `anti_rationalization`, `thinking_directive`, `thinking_tag`, `worker_model`, `local_only`, `model_dispatch`.

Apply all returned values. For `local_only: true`, prepend to agent prompt: "**LOCAL-ONLY MODE.** All work stays on disk. Read-only git is fine."

If `is_interview` was true from Phase 1, load `planning` skill (depth-first-interview.md) as primary.

Before stacking, check `pairs_with` in `skills/INDEX.json`. Prefer listed pairs.

**Gate**: Enhancements applied. Proceed to Phase 4.

---

### Phase 4: EXECUTE

**Goal**: Invoke the selected agent + skill and deliver results.

**Step 0: Execute Creation Protocol** (creation requests ONLY)

If creation signal + Simple+: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan.

**Step 1: Create plan** (Simple+)

Create `task_plan.md` before execution. Skip for Trivial only.

**Step 1b: Apply quality-loop pipeline** (Medium+ code modifications)

For code modifications at Medium/Complex, load `references/quality-loop.md` as the outer orchestration wrapper. Does NOT apply when: Trivial/Simple (use `quick`), review-only/research/debugging/content creation, or user requests simpler flow.

**Step 2: Build and dispatch agent**

```bash
python3 scripts/do-build-prompt.py --mode agent-prompt \
  --agent "{agent}" --skill "{skill}" --complexity "{complexity}" \
  --request "{user_request}" --thinking "{thinking_directive}" \
  --enhancements "{enhancements}"
```

Dispatch Agent with `model: "{worker_model}"` and the prompt output. For `model_dispatch: "parallel-haiku"`, spawn Haiku readers per data source → Opus synthesizer.

Route to agents that create feature branches. Include "commit your changes on the branch" in agent prompts for file modifications.

For `isolation: "worktree"` agents, inject `worktree-agent` skill rules.

Non-org repos: up to 3 iterations of `/pr-review` → fix before PR creation. Org-gated repos (via `scripts/classify-repo.py`): require user confirmation before EACH git action.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple agents in single message. Max parallelism: 10.

**Step 4: Auto-Pipeline Fallback** (no match AND complexity >= Simple)

When uncertain: **ROUTE ANYWAY** with verification-before-completion as safety net.

**Gate**: Agent invoked, results delivered. Proceed to Phase 5.

---

### Phase 5: LEARN

**Goal**: Capture session insights to `learning.db`.

**Routing outcome** (MANDATORY for Simple+):

```bash
# On success:
python3 ~/.claude/scripts/learning-db.py record-routing-outcome \
    "{selected_agent}:{selected_skill}" --success

# On failure:
python3 ~/.claude/scripts/learning-db.py record-routing-outcome \
    "{selected_agent}:{selected_skill}" --failure --reason "{brief reason}"
```

Record every routing outcome — this feeds future routing accuracy.

**Immediate graduation for review findings** (MANDATORY): Issue found + fixed in same PR → (1) Record scoped, (2) Boost to 1.0, (3) Embed into pattern references, (4) Graduate, (5) Stage in same PR.

**Gate**: Record at least one routing outcome for Simple+ tasks.

---

## Error Handling

### Error: "No Agent Matches Request"
Solution: Check INDEX files for near-matches. Route to closest agent with verification-before-completion. Report the gap.

### Error: "Force-Route Conflict"
Solution: Apply most specific force-route first. Stack secondary routes as enhancements if compatible.

### Error: "Plan Required But Not Created"
Solution: Stop execution. Create `task_plan.md`. Resume routing after plan is in place.

---

## References

### Reference Files
- `skills/do/references/progressive-depth.md`: Progressive depth escalation protocol
- `skills/do/references/quality-loop.md`: Quality loop pipeline for Medium+ code modifications
- `agents/INDEX.json`: Agent triggers, metadata, and `not_for` disambiguation
- `skills/INDEX.json`: Skill triggers, force-route flags, pairs_with, and `not_for` disambiguation
- `scripts/routing-manifest.py`: Generates compact routing manifest from INDEX files
- `scripts/do-classify.py`: Deterministic request classification
- `scripts/do-enhance.py`: Deterministic enhancement/model selection
- `scripts/do-build-prompt.py`: Prompt templates (haiku-prompt, routing-banner, agent-prompt, task-spec)
