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

/do is a **ROUTER**, not a worker. Classify, select agent+skill, dispatch. All execution goes to agents.

**Main thread:** (1) Classify, (2) Select, (3) Dispatch, (4) Evaluate, (5) Re-route if needed, (6) Report.

Catching yourself reading/writing code or analyzing — pause and route to an agent.

## The Completeness Standard

Do the whole thing — with tests and documentation. The answer is the finished product, not a plan. Prefer the permanent solve over a workaround. If an agent returns partial work, route a follow-up. Search before building. Test before shipping. Decompose into agent-sized tasks. The standard: the result reads as "that's done," not "that's a start." Inject for Simple+ work. Confidence in handling directly is a signal to route: direct handling skips domain knowledge, methodology, and references.

## Output Discipline

Every word follows **Dense-Complete Writing** (injected by `scripts/build-dispatch.py`). Full rules: `skills/shared-patterns/dense-complete-writing.md`.

**User sees:** phase banners, routing banner, brief post-agent summary (what changed, not how).
**Internal only:** routing JSON, classification reasoning, enhancement stacking (unless Verbose Routing ON).

## Instructions

### Phase Banners (MANDATORY)

Every phase displays: `/do > Phase N: PHASE_NAME — description...`
After Phase 2, display the `===` routing decision banner. Both required.

---

### Phase 1: CLASSIFY

Read and follow repository CLAUDE.md first.

| Complexity | Agent | Skill | Direct Action |
|------------|-------|-------|---------------|
| Trivial | No | No | **ONLY reading a file the user named by exact path** |
| Simple | **Yes** | Yes | Route to agent |
| Medium | **Required** | **Required** | Route to agent |
| Complex | Required (2+) | Required (2+) | Route to agent |

Everything beyond reading a user-named file is Simple+ and MUST route — without reasoning about whether you could handle it directly. When uncertain, classify UP.

**Progressive Depth**: Start shallow; let the agent escalate. See `references/progressive-depth.md`.

**NOT Trivial** (route them): evaluating repos/URLs, opinions, git operations, codebase questions (`explore-pipeline`), retro lookups (`retro`), comparisons.

Maximize skill/agent/pipeline usage. Named-pattern guide: `skills/workflow/references/workflow-patterns.md`.

**Parallel FIRST**: 2+ independent failures or 3+ subtasks → multiple Agent tools in one message. `fan-out-workflow.js` for Workflow. Research → `research-coordinator-engineer`; coordination → `project-coordinator-engineer`; plan+"execute" → `subagent-driven-development`; new feature → `feature-lifecycle` (`.feature/` present → `feature-state.py status`).

**Force Direct** — OFF by default; explicit request only.

**Creation Request Detection** (MANDATORY before Gate):

Creation signals: verbs ("create", "scaffold", "build", "add new", "new [component]", "implement new"), targets (agent, skill, pipeline, hook, feature, plugin, workflow, voice profile), implicit ("I need/build me a [component]"). If ANY signal AND Simple+: `is_creation = true`; Phase 4 Step 0 mandatory. Not creation: debugging, reviewing, fixing, refactoring, explaining, auditing existing. When ambiguous, check whether output is a NEW file.

**Gate**: Complexity classified. Creation → output `[CREATION REQUEST DETECTED]`. Display banner. Trivial: handle directly. Simple+: Phase 2.

---

### Phase 2: ROUTE

Select the correct agent+skill. Semantic intent routing is primary; the orchestrator does it itself. Prefer FORCE-labeled entries when intent matches.

**Read for INTENT.** Keywords are hints, never gates. Plain/non-native-English routes as well as jargon ("send my commits to the server" = "git push").

**Pre-route (run ONCE, before fast-path)**

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

Store as `PRE_ROUTE_RESULT`. Never call pre-route.py again.

**Fast path:** If `PRE_ROUTE_RESULT` has `"confidence": "high"` AND `"match_type": "force_route"` AND skill is `pr-workflow` or a security skill: dispatch directly. Skip Steps 0/1.5/1. Keep mandatory: routing banner (Step 3), Step 2 overrides, Phase 3, ALL Phase 4 injections — stamp `[do-route]` marker with `health=-`. Agent: pre-route's `agent` when non-null, else domain agent, else `general-purpose`. The full flow lands on the same route (Step 1a would force-override to it anyway); fast path changes cost, not behavior.

**Step 0: Semantic intent routing (self-route)**

Acquire manifest cache-first. Hash-gated disk cache (`~/.claude/cache/routing-manifest.txt` + `.hash` sidecar), kept fresh by SessionStart hook and INDEX sync hooks. On cache miss/stale:

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
BASE="$(dirname "$SDIR")"; CACHE="${HOME}/.claude/cache/routing-manifest.txt"; CHASH="${HOME}/.claude/cache/routing-manifest.hash"
if [ -s "$CACHE" ] && [ -s "$CHASH" ] && [ "$(cat "$SDIR/routing-manifest.py" "$SDIR/routing_index_merge.py" "$BASE/skills/INDEX.json" "$BASE/skills/INDEX.local.json" "$BASE/agents/INDEX.json" "$BASE/agents/INDEX.local.json" "$BASE/skills/workflow/references/pipeline-index.json" 2>/dev/null | sha256sum | cut -d' ' -f1)" = "$(cat "$CHASH")" ]; then
  cat "$CACHE"    # cache hit: manifest read from disk, no Python start
else
  python3 "$SDIR/routing-manifest.py"
fi
```

Select BEST agent+skill+pipeline. Hold internally as JSON (never printed; `[do-route]` marker is its only external trace):

```
{
  "agent": "agent-name or null",
  "skill": "skill-name or null",
  "pipeline": "pipeline-name or null",
  "reasoning": "one sentence why",
  "confidence": "high/medium/low"
}
```

**Routing rules (ALL apply):**

```
SECTION-INTEGRITY (HARD — never violate):
- `agent` MUST be from the manifest's AGENTS section, or null. Never put a skill name in `agent`.
- `skill` MUST be from SKILLS section, or null. Never put an agent name in `skill`.
- `pipeline` MUST be from PIPELINES section, or null.
- No agent fit → `"agent": null` (router falls back to `general-purpose`). Never promote a skill into `agent`.
- FORCE (process) skills go in `skill` only. Example: `zsh-shell-config` → `"skill": "zsh-shell-config"`, separate agent.

FORCE-ROUTE: FORCE entries MUST be selected when domain matches SEMANTICALLY. Match MEANING, not words:
- "push my changes" → pr-workflow (FORCE) ✓ (git push)
- "push back on this design" → NOT pr-workflow (resist/argue)
- "configure my fish shell" → fish-shell-config (FORCE) ✓
- "fish for bugs" → NOT fish-shell-config (search for bugs)
- "quick fix to the login page" → quick (FORCE) ✓
- "quick overview of the architecture" → NOT quick (exploration)

PIPELINE: Optional, most null. Select ONLY when BOTH hold: (1) intent SEMANTICALLY matches a pipeline's triggers/description, AND (2) the request genuinely benefits from a multi-phase flow — not just a single skill task. Examples:
- "write an article in vexjoy voice about X" → pipeline: "voice-writer" ✓
- "research X with artifacts and sources" → pipeline: "research-pipeline" ✓
- "fix the typo on line 42 of foo.py" → pipeline: null
When in doubt, null. (A comprehensive-review pick is outranked by Phase 3 right-size-review tiering when a real diff exists.)

GENERAL:
- Most specific match. Agent = domain, skill = methodology; pick both.
- Task verbs → prefer matching skills. No match → all nulls with reasoning.
- GENUINE git ops (push, commit, PR, merge) → ALWAYS pr-workflow. Metaphorical ("commit to a decision") → never.
- Single skill string, not array.
```

**Step 0b: Apply the routing decision**

Use `agent`/`skill` directly; low confidence → verify against INDEX files. Routing JSON is internal.

**Skill-greediness gate (HARD — non-negotiable for Simple+).** Null/empty skill → pick one: review→systematic-code-review, debug→workflow (systematic-debugging), refactor→workflow (systematic-refactoring), audit→systematic-code-review (whole-repo→full-repo-review), explain→codebase-overview, compare→decision-helper (agent A/Bs→agent-comparison), plan→planning, loop→objective-loop. Fallback: `objective-loop`. Never leave skill empty on Simple+.

**Section validator (MANDATORY before `Agent(subagent_type=...)`):**

```
agents_section = grep_section(manifest, "AGENTS:", "SKILLS:")
skills_section = grep_section(manifest, "SKILLS:", "PIPELINES:")
agent_names = [first_token(line) for line in agents_section]
skill_names = [first_token(line) for line in skills_section]

if route.agent and route.agent not in agent_names:
    if route.agent in skill_names:
        route.skill = route.skill or route.agent
        route.agent = None
    record_misroute(reason="agent-slot held skill name", value=route.agent)

if route.agent is None:
    route.agent = "general-purpose"
```

No defensible pair → `general-purpose` + `objective-loop`. Route simplest satisfying pair. `[cross-repo]` → `.claude/agents/` local agents. Code changes → domain agents.

**Step 1.5: Health evaluation (shadow-only)**

After Step 0/0b, before Step 1. Read weights, score the pick:

```bash
python3 "$SDIR/learning-db.py" route-weights --json
```

Call `health_adjust()` (`scripts/lib/route_policy.py`). Returns `{final_pick, action, reason}`, action in `keep|demote|tiebreak`. **Shadow-only: recorded, never alters route.** Activation gated on first negative signal (`docs/route-loop-validation.md`).

Thresholds: demote floor `confidence<0.30 AND failure>=3 AND n>=5`; tiebreak `confidence<0.35` with healthier alternate `n>=5`; force-route/security always `keep`; `n<5` or no row → `keep`.

Log to T3: `health_at_decision` (float/null), `n`, `failure` as separate fields on the DECISION event in `route-events.jsonl`. Pass as `health` field in routing JSON; `build-dispatch.py` emits the marker.

**Step 1: Deterministic safety-net** (reads `PRE_ROUTE_RESULT`, after semantic decision)

Guardrail only. No second pre-route invocation.

- **(a)** If pre-route has high-confidence force_route for pr-workflow/security and semantic pick disagrees → override. Git/security work MUST hit quality gates. Record `match_type`.
- **(b)** Phrase/unigram guards suppress false matches ("fish out", metaphorical commit). Guarded requests stay with Step 0.

**Step 2: Apply skill override** — "review"→systematic-code-review, "debug"→workflow (systematic-debugging pipeline), "refactor"→workflow (systematic-refactoring pipeline), "TDD"→test-driven-development. Full table in INDEX files.

**Step 3: Display routing decision** (MANDATORY — FIRST visible output)

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

Trivial: `Classification: Trivial - [reason]` and `Handling directly (no agent/skill)`.

**Dry Run Mode** / **Verbose Routing** — both OFF by default.

Learning capture is automatic via hooks (table in Learning Capture section).

**Gate**: Agent+skill selected. Banner displayed. Phase 3.

---

### Phase 3: ENHANCE

Stack skills based on request signals.

| Signal | Enhancement |
|--------|-------------|
| Substantive work | Retro knowledge when it materially helps |
| "with tests" / "production ready" | test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| "comprehensive"/"thorough"/"full" review, or "review" with 5+ files — no diff | Fallback: parallel-code-review (3: Security, BizLogic, Architecture) |
| Multi-file/comprehensive review, real diff | `python3 "$SDIR/right-size-review.py" --base {base} --head {head}` (or `--files N --packages M`); Tier 1→3, 2→12, 3→17, 4→27 reviewers. Escalate one tier on CRITICAL; no tier signal → full behavior. Outranks Phase 2 `comprehensive-review` pipeline pick. |
| Complex implementation | Offer subagent-driven-development |
| "local only" / "no push" / "keep it local" / "don't commit" / "stay local" | Inject local-only (`shared-patterns/local-only.md`): "**LOCAL-ONLY MODE.** Do not push, commit, create PRs, or deploy. All work stays on disk. Read-only git is fine." |
| Voice profile skill selected (any voice-* profile, e.g. voice-example-profile) | Stack `voice-writer` (13-phase pipeline); voice-* loads as profile in Phase 1. |
| Interview-mode heuristic fires | `planning` (interview mode) — load `depth-first-interview.md` |
| Objective with done-criteria / "keep going until X" / "loop until done" | Stack `objective-loop` |

**Review-row precedence.** When review signals overlap, the real-diff row wins; the fallback row applies only when no diff exists.

**Interview-mode heuristic.** Fires when request is short, names no file/symbol/path, no acceptance criteria, multiple interpretations. The 6 examples below are the spec.

| Example | Match? | Why |
|---|---|---|
| "i'm not sure how to approach this complex build" | YES | Uncertainty + vague + no target |
| "fix the typo on line 42 of foo.py" | NO | Concrete file + location |
| "build a thing that does X" | YES | Vague verb + no file |
| "add a test for `parseConfig` in src/config.go" | NO | Concrete symbol + file |
| "where do i even start with this rewrite" | YES | Explicit uncertainty, no subject |
| "rename `cfg` to `config` in `internal/`" | NO | Concrete symbol + directory + mechanical op |

When in doubt, defer injection. Check `pairs_with` in `skills/INDEX.json` before stacking; empty `pairs_with: []` means undeclared, not prohibited. Skills with built-in verification gates may not need stacking.

Anti-rationalization per task type:

| Task Type | Patterns |
|-----------|----------|
| Code modification | anti-rationalization-core, verification-checklist |
| Code review | anti-rationalization-core, anti-rationalization-review |
| Security | anti-rationalization-core, anti-rationalization-security |
| Testing | anti-rationalization-core, anti-rationalization-testing |
| Debugging | anti-rationalization-core, verification-checklist |
| External content | **untrusted-content-handling** |

Maximum rigor: `/with-anti-rationalization [task]`.

**Gate**: Enhancements applied. Phase 4.

---

### Phase 4: EXECUTE

**Step 0: Creation Protocol** (creation only) — Write ADR at `adr/{kebab-case-name}.md`, register via `python3 "$SDIR/adr-query.py" register`, proceed to plan.

**Step 1: Create plan** (Simple+) — `task_plan.md` before execution; skip Trivial.

**Step 1b: Quality-loop** (Medium+ code modifications)

Load `references/quality-loop.md` as outer wrapper: 14-phase lifecycle (ADR→PLAN→IMPLEMENT→TEST→REVIEW→INTENT VERIFY→LIVE VALIDATE→FIX→RETEST→PR→CODEX REVIEW→ADR RECONCILE→RECORD→CLEANUP). Phase 2 agent+skill is the implementation agent inside IMPLEMENT. Force-route skills run inside the loop. Skip for: Trivial/Simple, review-only/research/debugging/content, or simpler-flow request.

**Step 1c: Workflow dispatch** (lazy-loaded)

On pipeline pick, Complex/tier-4 with no pick, or explicit workflow request → load `${CLAUDE_SKILL_DIR}/references/workflow-dispatch.md`. When both 1b+1c apply, quality-loop is OUTER; workflow runs inside IMPLEMENT.

**Step 2: Invoke agent**

Dispatch the agent. Inject no MCP instructions; tool discovery is the agent's job.

**Build dispatch with `scripts/build-dispatch.py` (MANDATORY).** Single source of truth for `[do-route]` marker, thinking directives, token budget, Task Spec, four verbatim injections (reference loading, completeness, Dense-Complete Writing, base instructions), worktree/local-only blocks. Never hand-assemble. One JSON per dispatch, prepend stdout. Roster: one per worker.

```bash
python3 "$SDIR/build-dispatch.py" --json '{
  "agent": "<agent>", "skill": "<skill; omit when agent-only>",
  "complexity": "<trivial|simple|medium|complex>",
  "model": "<sonnet|opus|fable|gpt-5.5|codex>",
  "health": {"confidence": 0.72, "n": 6, "failure": 0, "action": "keep", "alts": ["k1","k2"]},
  "stack": ["s1","s2"],
  "task_spec": {"intent": "...", "constraints": "...", "acceptance": "...",
                "files": "...", "operator_context": "..."},
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}'
```

Fields (omit optional; script degrades): `agent`/`skill`/`complexity` from Phase 2 (no skill→`skill=-`). `model` from Model Selection (**required Medium+**, script errors; values: sonnet/opus/fable/gpt-5.5/codex; trivial/simple→`model=-`). `health` from Step 1.5 (no row→omit→`health=-`). `stack` from Phase 3 (instrumentation). `task_spec` mandatory Medium+, Simple include intent+acceptance when extractable; intent=verb+object, constraints=branch safety+operator-context+memory, acceptance=observable outcomes; creation adds "must match ADR"; invent nothing. `flags.worktree` for worktree agents. `flags.local_only` on local-only signals. `flags.thinking_override`: "slow" for security/API design/migrations/5+ files/arch; "fast" for lookups/renames; else omit. `token_remaining` advisory budget minus spend.

The `[do-route]` marker is the SOLE signal `routing-decision-recorder` reads. Dispatches without it (sub-agents, nested fan-out) are excluded from route-health.

**Fallback (script failed).** Hand-stamp: `[do-route] agent={agent} skill={skill|-} complexity={complexity} health=- model={model|-}` at prompt head, add Task Specification inline, dispatch, report failure.

**Model Selection (canonical table — ADR `model-selection-policy`).**

| model | cost | intelligence | taste | role |
|---|---|---|---|---|
| gpt-5.5 | 9 | 8 | 5 | Bulk/mechanical via codex wrapper. Dispatch target. |
| sonnet-5 | 5 | 5 | 7 | Mechanical fan-out, lighter work. `model: "sonnet"`. Dispatch target. |
| opus-4.8 | 4 | 7 | 8 | Reviews, audits, analysis, deep work. `model: "opus"`. Dispatch target. |
| fable-5 | 2 | 9 | 9 | Highest requirements only — deliberate escalation, never routine dispatch. |

Rules: Orchestrator = main thread model. **Medium+ MUST set model explicitly** (omission inherits — expensive propagation). Trivial/Simple: omission OK. Defaults, not limits — cheaper output misses bar → rerun smarter. Path: sonnet→opus→gpt-5.5→tighter spec. Ships: intelligence > taste > cost. Bulk→gpt-5.5. User-facing needs taste≥7. Reviews→opus. Haiku retired. Wrapper symmetry: wrapper serves model family NOT current harness. `codex exec -s read-only` for investigation. Codex prompts leave machine — public content only. Mechanics: `codex` skill.

**Complex tasks (3+ sources) verb dispatch:**

| Verb class | Mode |
|---|---|
| list, count, extract, inventory, search, check, find, grep | Fan-out: gpt-5.5/sonnet readers → opus synthesizer |
| review, audit, assess, analyze, debug, investigate, evaluate | Single opus agent |

Simple/Medium: dispatch directly. Route to feature-branch agents; for modifications, include "commit on the branch". `isolation: "worktree"` → set `flags.worktree`.

Non-org repos: up to 3 `/pr-review` → fix iterations before PR. Org-gated (`classify-repo.py`): confirm before each git action.

**Step 3: Multi-part requests** — "first...then", "and also", numbered lists, semicolons. Sequential dependencies in order; independent items in parallel (max 10).

**Step 4: Auto-Pipeline Fallback** (no match, Simple+) — `auto-pipeline`. Still no match → route closest agent + `objective-loop`. Never dispatch Simple+ with empty skill.

**Lazy-completion check.** Agent claims "done" on enumerable objective → compare claimed vs actual scope; if short, reject and re-dispatch remainder. See `references/lazy-completion-detector.md`. Re-dispatch → report route failure.

**Gate**: Agent invoked, results delivered.

---

### Learning Capture (automatic)

Hooks capture everything. Router records one case manually: observed route failures (below).

| Capture | Hook | Event |
|---------|------|-------|
| Routing decision (`{agent}:{skill}`) | `routing-decision-recorder` | PostToolUse:Agent |
| Outcome - validate pending | `routing-outcome-recorder` | SubagentStop |
| Outcome - finalize (boost/decay) | `routing-outcome-finalizer` | UserPromptSubmit |
| Outcome - session-end fallback | `session-learning-recorder` | Stop |
| Right-sizing feedback | `routing-decision-recorder` | PostToolUse:Agent |
| Tool errors | `error-learner` | PostToolUse |
| Review findings | `review-capture` | PostToolUse:Agent |

Feeds `learning-db.py route-health`. See ADR `learn-step-to-hook`.

**Outcome fidelity.** Deterministic on next user turn, zero LLM cost, THREE-WAY: failure on errors/rejection (decay); success on explicit acceptance (boost); neutral otherwise. No complaint ≠ acceptance. Stop fallback: errors→failure, clean→neutral.

**Report route failures** (HIGH-CONFIDENCE only):

```bash
REASON_FILE=$(mktemp); printf '%s' "<cause>" > "$REASON_FILE"
python3 ~/.claude/scripts/learning-db.py route-failure AGENT:SKILL --reason-file "$REASON_FILE" --routing-relevant yes --session $SESSION --marker $DISPATCH_ID
rm -f "$REASON_FILE"
```

Run for: re-route, lazy-completion re-dispatch, section-validator misroute, harness-rejected agent. Right route + bad execution → `--routing-relevant no`. Ambiguous → skip. Decays one per dispatch key. Temp file avoids shell-splicing.

**Optional:** curated insight via `retro` skill: `learning-db.py learn --skill <name> "insight"` or `--agent <name> "insight"`. Routing rows (`category=effectiveness`) excluded from `retro graduate`.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No Agent Matches | No agent covers domain | INDEX near-matches → closest agent + verification-before-completion. Report gap. |
| Force-Route Conflict | Multiple force-route triggers match | Most specific first; stack compatible secondaries. |
| Plan Required | Simple+ without task_plan.md | Create plan, resume. |
| Router Script Failed | Non-zero exit or non-JSON | No-match fallback: `general-purpose` + `verification-before-completion`. |

## References

- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Progressive depth escalation
- `agents/INDEX.json`: Agent triggers, metadata, `not_for`
- `skills/INDEX.json`: Skill triggers, force-route flags, pairs_with, `not_for`
- `skills/workflow/SKILL.md`: Workflow phases, triggers, composition
- `skills/workflow/references/pipeline-index.json`: Pipeline metadata, triggers, phases
- `scripts/routing-manifest.py`: Generates routing manifest from INDEX files
