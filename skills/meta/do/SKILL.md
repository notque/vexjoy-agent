---
name: do
description: "Classify user requests and route to the correct skill, pipeline, and stack. Primary entry point for all delegated work."
user-invocable: true
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Agent
routing:
  triggers:
    - "route task"
    - "classify request"
    - "which skill"
    - "delegate to skill"
    - "smart router"
  category: meta-tooling
---

# /do - Smart Router

ROUTER first, worker when dispatch does not pay. Classify → skill (+pipeline, stack) → execute or dispatch. No specialist agents: when dispatch pays, the worker is the built-in `general-purpose` agent and the skill carries the domain. Exception: a private overlay agent from the manifest's `AGENTS:` section that fits the request is the worker, and that pick alone makes dispatch pay (its file carries domain the main thread lacks). Trivial and Simple on the Anthropic lane: the main thread loads the skill and does the work itself, because a dispatched worker cold-reloads about 20k tokens of instructions and re-reads files this thread already holds. Dispatch only when it pays: parallel fan-out (independent parts), long lanes (about 5+ files, or work that would bloat this thread's context), worktree isolation, read-only Haiku gathering, or an overlay agent pick. Medium and Complex dispatch to `general-purpose` workers. Exception: reading to fill the Task Spec is routing work — up to 5 files as excerpts; more → one read-only Explore dispatch whose deliverable is the excerpt list. Main: Classify→Select→Execute or Dispatch→Evaluate→Re-route→Report.

Do the whole thing (tests+docs). Product, not plan. Permanent solve over workaround. Search before building; test before shipping. Decompose into worker-sized tasks. The result reads as "that's done," not "that's a start." Partial → follow-up. Inject Simple+. Confidence in handling Medium+ directly is a signal to route.

Dense-Complete Writing (`build-dispatch.py` injects; `skills/shared-patterns/dense-complete-writing.md`). User: banners+summary. Internal: JSON/reasoning/stacking (Verbose overrides).

Google Developer Documentation Style (`build-dispatch.py` injects; `skills/shared-patterns/google-devdocs-style.md`), alongside Dense-Complete. Precedence: completeness floor (never drop a required point) > Google construction (active voice, second person, context-before-instruction, formatting) > Dense-Complete length.

## Instructions

### Phase Banners

Every phase: `/do > Phase N: PHASE_NAME — description...`
After Phase 2: `===` routing banner. Both required.

---

### Phase 1: CLASSIFY

Read CLAUDE.md (or GEMINI.md on Antigravity CLI) first.

| Complexity | Worker | Skill | Direct |
|---|---|---|---|
| Trivial | No | No | Main thread; ONLY user-named file by path |
| Simple | Only when dispatch pays | Yes | Main thread (Anthropic lane); dispatch when it pays |
| Medium | `general-purpose` | Required | Route |
| Complex | 2+ `general-purpose` | 2+ | Route |

Beyond user-named file = Simple+: pick and load a skill, emit the marker, then execute or route. Uncertain → UP. Depth: `references/progressive-depth.md`. NOT Trivial: repos/URLs, opinions, git, codebase Qs, process, comparisons.

Parallel FIRST: 2+ failures / 3+ subtasks → multiple Agent tools. Research→`research` workers; coordination→`workflow`; plan+exec→process; feature→workflow (.feature/→feature-state.py status). Force Direct: OFF.

**Creation Detection**: create/scaffold/build/"add new"/"new [component]" targeting skill/pipeline/hook/feature/plugin/workflow/voice. Any of these + Simple+ → `is_creation=true`, Phase 4 Step 0. Not: debug/review/fix/refactor/explain/audit.

**Gate**: Complexity set. Creation → `[CREATION REQUEST DETECTED]`. Trivial: direct. Simple+: Phase 2.

---

### Phase 2: ROUTE

**Goal**: fill every slot the request earns — skill, pipeline, fan-out workers. The semantic self-route is PRIMARY and runs FIRST — the orchestrator reads the manifest in-session and decides for itself, with no routing sub-dispatch (self-route beat the Haiku hop by +8.1 accuracy points, zero new safety misses: `scripts/routing-ab-results/self-route-v1/VERDICT.md`). `pre-route.py` is a guardrail that runs AFTER the semantic decision and never short-circuits it.

**Contract: read for INTENT.** Route on what the user MEANS. Trigger keywords are hints, never gates. Plain or non-native phrasing routes as well as jargon: "send my commits to the server" routes like "git push". Cost: one manifest read per request — measured and accepted.

**Step 0: Semantic self-route (PRIMARY — runs first)**

The routing manifest (`scripts/routing-manifest.py`) is the runtime form; `docs/routing-map.md` is the human-readable committed form of the same data. Both are generated from frontmatter, so frontmatter is the single source of truth. CI checks staleness via `scripts/generate-routing-map.py --check`.

Resolve SDIR to locate installed scripts, then read the manifest for this request (hash-gated cache or regenerate). This probe does not identify the active session model or provider:

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.gemini/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
bash "$SDIR/get-routing-manifest.sh" --request-file "$REQUEST_FILE"
rm -f "$REQUEST_FILE"
```

Use `bash` explicitly so routing does not depend on the script's executable bit. Pass the request: private overlay skills appear in the manifest only when the request names their domain, the same gate `pre-route.py` and `/d` apply.

Hold the decision internally as JSON. It stays unprinted; the `[do-route]` marker is its sole external trace:

```
{
  "skill": "skill-name or null",
  "pipeline": "pipeline-name or null",
  "workers": [{"skill": "<SKILLS: name>", "scope": "files or part this worker owns"}],
  "reasoning": "one sentence why",
  "confidence": "high/medium/low"
}
```

`workers` holds EXTRA fan-out workers beyond the primary; `[]` when one worker covers it. Every worker is `general-purpose`. Add `"agent": "<AGENTS: name>"` only when the manifest has an `AGENTS:` section (private overlay agents, shown only when the request names their domain) and one of its agents fits the request better than `general-purpose` with the skill; keep a `skill` too. `build-dispatch.py` validates it and coerces any other name.

**Routing rules (ALL apply):**

```
SECTION-INTEGRITY RULE (HARD CONSTRAINT — never violate):
- `skill` and every `workers[].skill` must be names listed in the SKILLS: section, or null.
- `pipeline` must be a name listed in the PIPELINES: section, or null.
- Skills marked FORCE fill the `skill` slot only. Pipelines marked FORCE fill the `pipeline` slot only, and the run still needs its own `skill`.
- `agent` must be a name listed in the AGENTS: section, or absent. The public manifest has no AGENTS: section; it appears only for private overlay agents. Never put a retired specialist agent name (e.g. `golang-general-engineer`) anywhere; name the skill that now holds its content.

FORCE-ROUTE RULE: manifest entries marked FORCE — in SKILLS: or in PIPELINES: — are selected when their domain clearly matches the user's intent. FORCE matching is semantic, not keyword-based — match what the user means, not individual words:
- "push my changes" → pr-workflow ✓ (git push) | "push back on this design" → NOT pr-workflow (means resist)
- "configure my fish shell" → deploy ✓ (the Fish shell) | "fish for bugs" → NOT deploy (means search)
- "quick fix to the login page" → quick ✓ (small edit) | "quick overview of the architecture" → NOT quick (means explore)
A FORCE pipeline (6 of the 26) binds the `pipeline` slot exactly as a FORCE skill binds `skill`. `pre-route.py` reads FORCE pipelines and applies their semantic guard policy; the semantic route still owns intent and must apply the same MEANS-not-words test above.

PIPELINE-SELECTION RULE: pick a pipeline whenever the work has REAL PHASES. The PIPELINES: section ships in every manifest and 26 pipelines are available; reach for one on ANY of:
(1) the intent semantically matches a pipeline's description or its `t:` triggers, OR
(2) the shape is multi-phase — 3+ distinct steps, gather-then-synthesize, mixed script+LLM work, or intermediate artifacts worth keeping, OR
(3) Phase 1 classified the request Complex.
The user saying the word "pipeline" is one signal among these, never the gate. Examples:
- "write an article in vexjoy voice about X" → writing ✓ | "write structured docs for X from the source" → doc-pipeline ✓
- "comprehensive review of these 8 files" → comprehensive-review ✓ (outranked by `right-size-review.py` when a real diff exists: `tier_signal: true`)
- "add caching to the API and update the docs" → quality-loop ✓ (implement → review → document; nobody said "pipeline")
- "help me understand how auth works across this repo" → explore-pipeline ✓ (parallel exploration; a plain pipeline earns the pick on shape, no FORCE flag needed)
Return null when the whole job is one step for one worker: "fix the typo on line 42 of foo.py", "debug this failing test", "review this 10-line function".

FAN-OUT RULE: `workers` holds EXTRA `general-purpose` workers beyond the primary, each with its own `skill` and `scope`; `[]` when one worker covers the work. Fan out when the parts run at once against separate files: 2+ independent failures, 3+ independent subtasks, per-package or per-language review, gather from several domains. Keep a single worker when the parts touch the same files or each step consumes the previous step's output. Complex (Phase 1) starts from fan-out and justifies staying single. When an approved plan, job package, or specification defines multiple subagents (e.g. Subagents A/B/C/D), all defined subagents must be dispatched individually; collapsing them into a single monolithic subagent dispatch is strictly prohibited.

SPECIFICITY RULES:
- Pick the most specific match. "Go tests" → skill testing + stack programming.
- The domain skill (programming, frontend, kubernetes, data, ...) carries what the retired specialist agents held; a methodology skill (testing, review, debugging) sets the method. When both apply, one is `skill` and the other rides in Phase 3 `stack`.
- Prefer entries whose description semantically matches the request, not just keyword overlap.
- A task verb in the request (review, debug, refactor, test) prefers the skill matching that verb.
- GENUINE git / version-control operations — actually pushing code, committing files, opening or merging a pull request — select pr-workflow. Metaphorical uses ("commit to a decision", "merge ideas in your head", "push back on a proposal") do not route to pr-workflow.
- Return a single skill name as a string, not an array. Multiple candidates → pick the primary one.
```

**COMBINATION DOCTRINE.** Four surfaces compose; they do not compete. Fill every slot the request earns.

| Surface | Answers | Slot |
|---|---|---|
| Workers | parallel `general-purpose` dispatches for fan-out, each with its own skill and scope | `workers` |
| Skill | which domain or methodology runs | `skill` |
| Pipeline | which phase structure holds the work | `pipeline` |
| Stack | which extra rigor rides along | Phase 3 `stack` |

One surface filled is the FLOOR, not the ceiling (a fallback skill counts as unfilled). Combine upward: Simple = skill. Medium = skill+stack (domain skill plus methodology). Complex = 2+ workers (primary plus `workers`), 2+ skills (`skill` plus Phase 3 `stack`), and a pipeline unless one phase truly covers the work — which is how Phase 1's "2+/2+" row is satisfied with one `skill` string.

Composition rules:
- A pipeline names the phases; the skill still fills its slot and runs inside those phases. Picking a pipeline does not replace it.
- Stack always composes: anti-rationalization-core rides every route, and Phase 3 adds the rest.
- A FORCE skill and a FORCE pipeline matching together is legal — different slots, both get filled.
- Contradictory pairs, keep one: `quick` with any pipeline (quick means one step — drop the pipeline); comprehensive-review with `right-size-review.py` (a real diff, `tier_signal: true`, wins); `workflow` as fallback beside a real domain skill (the fallback yields); two pipelines (pick the outer one, nest the other through Step 1c).

**Step 0b: Apply the routing decision**

Use the `skill`, `pipeline`, and `workers` fields directly. Low confidence → verify against `skills/INDEX.json`.

**Skill-greediness gate (HARD — non-negotiable for Simple+).** Null skill → pick: review→review, debug→workflow (systematic-debugging pipeline), refactor→workflow (systematic-refactoring pipeline), audit→review (whole-repo→review), explain→assessment, compare→assessment (component A/Bs→toolkit), plan→workflow, loop→workflow, TDD→testing. Fallback: `workflow`.

**Section validator (before dispatch):**

```
agents = tokens(manifest, "AGENTS:", "SKILLS:")   # empty when no AGENTS: section
skills = tokens(manifest, "SKILLS:", "PIPELINES:")
pipelines = tokens(manifest, "PIPELINES:", END)
if route.agent not in agents: route.agent = None    # general-purpose worker
if route.skill not in skills: route.skill = None; record_misroute(...)
route.workers = [w for w in route.workers if w.skill in skills]
if route.pipeline not in pipelines: route.pipeline = None
route.skill ||= "workflow"
```

No skill→`workflow`. `[cross-repo]`→`.claude/agents/` (that repo's own agents). Code→the domain skill.

**Step 1: Deterministic safety-net** (`pre-route.py` — runs AFTER the semantic decision, never short-circuits it)

Use its result ONLY as a guardrail. Run once per /do; Phase 3 reads its `stack`:

```bash
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

→ `PRE_ROUTE_RESULT`.

- **(a) Safety-critical force-route override — the one case that beats Step 0.** `"confidence": "high"` with a `force_route` match for `pr-workflow` or a security skill overrides a disagreeing semantic pick: genuine push, commit, create-PR, and merge work, and security work, must hit the quality gates (lint, tests, CI). Record `match_type`. The workers stay the Step 0 pick.
- **(b) Every other result keeps the Step 0 decision.** Phrase and unigram guards inside `pre-route.py` already suppress idiom false positives ("fish out", metaphorical commit/merge), so a guarded or non-matching result leaves the semantic pick standing. Matching only force-routes is by design — the semantic route owns the long tail.

**Step 2: Apply skill override** — a task verb in the request ("review", "debug", "refactor", "TDD") sets the skill from the Skill-greediness gate list in Step 0b.

**Step 3: Routing banner** (first visible output)

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Worker: [main | general-purpose] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from skills/process/workflow/references/pipeline-index.json)
   -> Extra Rigor: [verification patterns for code/security/testing when needed]
 Invoking...
===================================================================
```

Trivial: `Classification: Trivial - [reason]`, `Handling directly`. Main-thread Simple: the banner shows `-> Worker: main - main thread, dispatch does not pay`.

**Gate**: Worker (`main` or `general-purpose`) and skill set, banner shown. Phase 3.

---

### Phase 3: ENHANCE

Stack on signals.

| Signal | Enhancement |
|---|---|
| Substantive | Retro knowledge when material |
| "with tests"/"production ready" | testing |
| "research needed"/"investigate first" | `research` skill; fan out `research` workers per source group |
| Comprehensive/thorough/full review or 5+ files, no diff | review (Security, BizLogic, Arch) |
| Multi-file review, real diff | `right-size-review.py`; pass its tier only when `tier_signal: true` (else pass no tier: every wave). Prose T1→3,T2→12,T3→17,T4→27; native 4/4/7/13. CRITICAL+1. Outranks comprehensive-review. |
| Complex implementation | Offer process |
| "local only"/"no push"/"keep it local"/"stay local" | Inject `shared-patterns/local-only.md` |
| Voice profile (e.g. voice-example-profile) | Stack `writing`; voice-*=profile |
| Needed knowledge or approval exists with another person | `workflow` — `skills/process/workflow/references/pl-human-source-elicitation.md` |
| Observation can settle a high impact uncertainty | `workflow` — `skills/process/workflow/references/pl-empirical-prototype.md` |
| Objective with done-criteria / "loop until done" | Stack `workflow` |
| Protected PR/security intent with a Go source operand | Keep `pr-workflow`/`security` primary and stack `programming` from `PRE_ROUTE_RESULT.stack` or the skill's `pairs_with` |

Review overlap: real-diff row wins; fallback only without diff.


| Unresolved state | Action |
|---|---|
| Low impact, reversible, or covered by a safe convention | State the assumption and execute. |
| One high impact decision owned by the current user | Ask one question with a recommendation, then execute. |
| Two or more high impact decisions owned by the current user | Use `skills/process/workflow/references/pl-depth-first-interview.md`: batch the independent frontier, then traverse genuine dependencies. Caps: below. |
| Facts, constraints, preferences, or approval exist with another person | Use `skills/process/workflow/references/pl-human-source-elicitation.md`; draft the artifact and never send without authorization. |
| Evidence can settle the choice faster than discussion | Use `skills/process/workflow/references/pl-empirical-prototype.md`: Question → Evidence → Verdict → Next action. |

Explicit "interview me" or "grill me" opts into exhaustive material coverage until shared understanding or a user stop; it has no arbitrary question or round cap. An implicit interview must earn its interruption cost through likely avoided rework and remains bounded. "Just build it," "skip questions," and equivalents use recommended defaults and continue.

An interview is not terminal when it suspends an active delivery objective. Compile the decisions and automatically resume the originating build, fix, deploy, validation, or other execution flow; never report the decision artifact as completion of the original objective. Stop after compilation only when the user explicitly requested only an interview artifact or excluded implementation.

Ask the current independent frontier in one logical round. In Markdown, include the full frontier with a recommendation for each and wait once. A harness native structured question UI may chunk the frontier only at its capacity per call; do not recompute between chunks unless an answer invalidates a pending question. Single question turns are reserved for true dependency branches. Interviews initiated by the router cap at five questions and three decision rounds, plus at most one concise confirmation response. Do not add ceremonial questions. Answering the last frontier does not authorize execution by itself: ask one concise shared understanding confirmation. Skip that extra confirmation only when the same response explicitly says "proceed", "build it", "looks right, continue", or equivalent. Resume nested execution only after explicit proceed or confirmation; a request for only an interview stops at the artifact.


Check `pairs_with` before stacking. Skills with built-in verification gates may suffice.


**Step G: GATHER (Simple+)** — fill the Task Spec before the Gate.

1. Keep `request_verbatim` unchanged. State this worker's `intent`, `constraints` (including authority), `files`, ownership, and `acceptance`.
2. Include decisions, prior results, and gaps when they affect this assignment. Summarize findings and link durable evidence; quote exact text only when its wording matters. Do not copy the whole investigation into every handoff.
3. Verify named paths. Add excerpts only when they explain a decision or let the worker act; the builder validates paths even when gathering is off.
4. Use `context_mode: "summary"` for current git status, diff stat, and recent commits. Use `files` when initial excerpts help, or `none` when the worker already has valid context. The legacy default is `files`. Mode `none` retains a notice that no fresh state was gathered, so the handoff envelope stays complete. Legacy `--no-gather` removes that envelope too; use `none` for Medium+ handoffs. Context modes never omit the supplied Task Spec or required injections.

Reuse reads only while their source and task context remain unchanged; a fresh worker needs access to the relevant content or references. For worker transitions, use `process`. Verification evidence follows `testing`; repeat checks when their inputs or relevant environment change, not just because a new phase starts.

**Gate**: Enhancements applied, Task Spec filled. Phase 4.

---

### Phase 4: EXECUTE

**Step 0: Creation** — ADR at `adr/{name}.md`, `adr-query.py register`, plan.

**Step 1: Plan** (Simple+) — `task_plan.md`; skip Trivial.

**Step 1b: Quality-loop** (Medium+ code mod) — `references/quality-loop.md` 14 phases. P2 worker: `general-purpose` with the implementation skill. Force-route in loop. Skip non-code/Trivial/Simple.

**Step 1c: Workflow** — Pipeline pick or Complex no pick or explicit → `${CLAUDE_SKILL_DIR}/references/workflow-dispatch.md`. Both 1b+1c → quality-loop OUTER, workflow in IMPLEMENT.

**Step 2: Invoke worker**

**Main thread (Trivial, and Simple when dispatch does not pay; Anthropic lane):** run `build-dispatch.py` with `{"execution": "main", "skill": "<skill, or - for Trivial>", "complexity": "<trivial|simple>", "task_spec": {"intent": "..."}}` and no model fields. It prints `[do-route] agent=main skill={s} complexity={c} model=inherit health=- exec=main` plus the Skill-tool calls, and feeds the marker to `routing-decision-recorder`, so telemetry counts the route (`--no-record` skips that). Then call the Skill tool as printed and do the work in this thread. Do not dispatch an Agent for it.

**`build-dispatch.py`** — source for `[do-route]`, exact Skill-tool calls, thinking, budget, Task Spec, injections, worktree/local-only. Do not hand-assemble it.

```bash
DISPATCH_JSON=$(mktemp)
cat > "$DISPATCH_JSON" << 'DISPATCH_EOF'
{
  "skill": "<skill>",
  "pipeline": "<pipeline; omit when Phase 2 returned null>",
  "complexity": "<trivial|simple|medium|complex>",
  "model": "<haiku|opus|fable from Model choice, or gemini-3.8-flash|gemini-4-argon|gemini-4-argon-high>",
  "context_mode": "summary",
  "provider": "<anthropic|openai|google|antigravity|other>",
  "manual_model_override": false,
  "health": "-",
  "stack": ["s1","s2"],
  "task_spec": {"request_verbatim": "<user message, unchanged>", "intent": "...",
                "constraints": "<applicable rules, limits, and authorization>",
                "decisions": "...", "prior_results": "...", "gaps": "...",
                "acceptance": "<command> → <expected>",
                "files": "<owned paths; optional line ranges>", "ownership": "<worker scope>",
                "operator_context": "..."},
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}
DISPATCH_EOF
python3 "$SDIR/build-dispatch.py" --json-file "$DISPATCH_JSON"
rm -f "$DISPATCH_JSON"
```

`skill`/`complexity`: Phase 2 (null→`-`). `agent`: omit; the builder defaults it to `general-purpose`. Pass it only for a private overlay agent from the manifest's AGENTS: section; any other name (a retired specialist, a typo) becomes `general-purpose` with `fallback=invalid-agent:<name>` on the marker. `pipeline`: the Phase 2 pick, passed so the marker carries it; omit when null. The builder validates each name against its index, then emits this exact action contract once per callable skill, primary first with ordered stack de-duplication: `Call the Skill tool with \`skill-name\`.` Shared-pattern stack entries remain prompt injections. Pipelines stay out of Skill-tool calls. Fan-out: one call per worker, each with its own `skill` and `files`. `model`: **required Medium+**; pick from **Model choice** below. Override rules: `references/model-selection.md`. `provider` describes the active harness, not an installed directory. `health`: `-` (in-context weights read retired — `docs/route-loop-validation.md`). `stack`: Phase 3. `task_spec`: mandatory Simple+ (Phase 3 Step G); the script rejects an empty spec at Medium+; creation+"match ADR". `thinking_override`: slow=security/arch/5+files; fast=lookups.

`[do-route]` = SOLE signal for `routing-decision-recorder`. Sub-agents excluded.

**PR work briefs:** put in `constraints`: commit locally, report the SHA, never push or open a PR without the coordinator's go-ahead.

**Fallback:** `[do-route] agent=general-purpose skill={s|-} complexity={c}[ pipeline={p}] health=- model={m|-}`, Task Spec inline, dispatch.

**Model choice.** Set `model` from the task type, not `inherit`. Pass the same `model` on every Agent call, including Explore and Plan.

| Task type | Model / effort |
|---|---|
| read-only gathering: locate, lookup, cite lines, excerpts, research fetch, log reading | haiku |
| code writing and edits, debugging, features, reviews that decide, decisions, no row fits | opus / medium, then high |
| high-risk: auth, data, security, concurrency, irreversible | opus / medium, then high |
| major refactor or migration, architecture planning, lead of a many-worker fan-out, deep research synthesis, quantitative analysis, long unattended run, or Opus at high fell short | fable / medium, then high |

Sonnet is no row's default. When the owner names a model for the task ("use fable for everything"), pass that model on every dispatch with `manual_model_override=true`.

Tiers (`model_policy`): low-risk = haiku/low (read-only gathering only), standard = opus/medium, high-risk = opus/medium, max-power = fable/high. Owner, 2026-11-09: "Also I prefer opus 5.5 medium over high". Opus starts at medium on every row and tier, high-risk included. opus/high is no tier's default: reach it as an explicit pick (`model: "opus"`, `model_effort: "high"`, no `model_policy`) or as the step after a failed opus/medium attempt. `max-power`, fable/max, opus/max, and explicit opus/xhigh need `manual_model_override=true`; test fable at high before opus/xhigh. Use `inherit` only when no row or tier fits and the session model is acceptable.

Escalate on a miss, when an objective check fails (tests, `tsc`, `ruff`, acceptance command) or a Jev blocker Noul is at least 0.6. In order: (1) give the agent a way to verify (test, build, script); (2) raise effort one level, up to high; (3) move to the next model up at a lower effort: haiku → opus/medium → opus/high → fable/medium → fable/high. Never raise opus past high before trying fable.

Evidence: Anthropic's 2026-11-09 model guide and the owner's 2026-11-01 and 2026-11-09 orders, which win where they differ. Prices, effort trade-offs, mixing rules, history, and the re-measure method: `skills/meta/d/references/model-task-fit.md`.

**Antigravity CLI (`agy`) & Google AI (Argon):** When `detect-workflow-capability.py` reports `harness="antigravity"`, load `${CLAUDE_SKILL_DIR}/references/antigravity-execution.md`. Set `provider="google"` in `build-dispatch.py` (`low-risk` = `gemini-3.8-flash` / `low`, `standard` = `gemini-4-argon` / `medium`, `high-risk` = `gemini-4-argon-high` / `high`, `max-power` = `gemini-4-argon-high` / `max` with `manual_model_override=true`). For all Simple+ tasks (Simple, Medium, Complex), dispatch subagents via native Antigravity primitives (register the worker persona via `define_subagent` from `build-subagent-spec.py --skill <skill>` if not already defined, dispatch via `invoke_subagent` with `Workspace="inherit"` for single-agent tasks, `Workspace="branch"|"share"` for parallel code isolation, `send_message` for stateful continuation, `manage_subagents` for 3-strike circuit breaking) or Python `run_workflow` (`skills/process/workflow/references/fan-out-workflow.py`). The FAN-OUT RULE (Phase 2) applies. Escalation order: `gemini-3.8-flash` → `gemini-4-argon` → `gemini-4-argon-high`. On Antigravity, only Trivial tasks execute directly in the main thread; the Anthropic-lane main-thread rule for Simple tasks does not apply here. For deep autonomous work (`/goal`), enforce Phase 4.5 verification before emitting `<!-- GOAL_COMPLETE -->`.

The marker records the requested selection, not an observed worker model. Report actual identity only from harness metadata. Use scripts for deterministic work. Session configuration stays under the user's control. Codex prompts stay read-only and public unless the task requires otherwise.

**Complex (3+ sources):**

| Verbs | Mode |
|---|---|
| list/count/extract/inventory/search/check/find/grep | Scripts when deterministic; otherwise readers → synthesis, model per **Model choice** |
| review/audit/assess/analyze/debug/investigate/evaluate | Single worker, model per **Model choice** |

Simple: main thread unless dispatch pays (Phase 1). Medium: one direct dispatch. Feature-branch; mods commit. `isolation:"worktree"`→`flags.worktree`. Non-org: 3 reviews→fix→PR. Org: confirm git.

**Step 3: Multi-part / fan-out** — deps sequential; independent parallel (worker count: the roster rule in `references/workflow-dispatch.md`). Phase 2 `workers` → ONE `build-dispatch.py` call and ONE `general-purpose` Agent dispatch per worker, each with its own `skill`: N workers = N calls = N markers, one marker each. Emit the parallel Agent calls in a single message. Each worker gets its own `files` and scope. Sequential stages pass relevant prior results and evidence locations; synthesis receives the findings and access to evidence from every required stage. Packing several markers into one Bash/Workflow script keeps them recorded but forfeits route-fit scoring, which reads a lone marker per event.

**Complex fan-in report** — when 2+ workers feed one synthesized report, run one self-review pass on the draft before delivery: `skills/shared-patterns/report-self-review.md` (one separate dispatch, no marker, `model: opus`). Not for Trivial, Simple, or Medium routes.

**Step 4: Auto-Pipeline Fallback** (no match, Simple+) — skill `workflow` with pipeline `auto-pipeline`. None → closest+`workflow`. Never empty skill.

**Lazy-completion check.** "Done" on enumerable → compare scope; short → reject, re-dispatch (`references/lazy-completion-detector.md`). Re-dispatch → route failure.

**Gate**: Work executed or worker dispatched, results delivered.

---

### Routing telemetry (automatic)

Hooks record routing. On an observed route failure, or to re-derive a quoted telemetry figure → load `${CLAUDE_SKILL_DIR}/references/routing-telemetry.md` (hooks table, outcome fidelity, route-failure protocol, figure queries).

---

## Error Handling

On any routing error → load `${CLAUDE_SKILL_DIR}/references/error-handling.md`.

## References

- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`
- `${CLAUDE_SKILL_DIR}/references/antigravity-execution.md`
- `skills/INDEX.json`
- `skills/process/workflow/SKILL.md`, `skills/process/workflow/references/pipeline-index.json`
- `scripts/routing-manifest.py`
