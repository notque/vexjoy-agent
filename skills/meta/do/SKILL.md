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

Classify the request, pick skill + pipeline + stack, then run in-thread or dispatch `general-purpose` workers (or an `AGENTS:` overlay agent). `/d` is `/do`'s Jev-gated main-loop mode sharing the exact same manifest (`get-routing-manifest.sh`), rule text (`print-route-rules.py`), `build-dispatch.py`, and `d-preflight.py`.

Run Trivial/Simple in-thread across Claude Code and Antigravity unless dispatch pays (fan-out, ~5+ files, worktree, read-only gather, or overlay agent). Medium/Complex dispatch workers (`general-purpose` on Claude Code; `self`/`research` on Antigravity); reading ≤5 files for Task Spec is routing work (more → Explore/research). Deliver tested, documented work in Dense-Complete + Google DevDocs style (`build-dispatch.py` injects both).

## Instructions

### Phase Banners

Emit `/do > Phase N: PHASE_NAME — ...` each phase and the `===` routing banner after Phase 2 (pure Q&A / zero-edit turns may use a 1-line header).

---

### Phase 1: CLASSIFY

Read `AGENTS.md` first (`CLAUDE.md` imports it for Claude Code).

| Complexity | Worker | Skill | Direct |
|---|---|---|---|
| Trivial | No | No | Main thread; ONLY named file path |
| Simple | When dispatch pays | Yes | Main thread; dispatch only when it pays |
| Medium | `general-purpose` | Required | Route |
| Complex | 2+ `general-purpose` | 2+ | Route |

Beyond a named file = Simple+ (uncertain → UP; `references/progressive-depth.md`). Never Trivial: repos/URLs, opinions, git, codebase Qs, process, comparisons. Parallel FIRST for 2+ failures or 3+ subtasks (`research`, `workflow`, `process`).

**Creation Detection**: create/scaffold/build/"add new"/"new [component]" targeting skill/pipeline/hook/feature/plugin/workflow/voice at Simple+ → `is_creation=true`, Phase 4 Step 0 (exclude debug/review/fix/refactor/explain/audit).

**Prompt shaping & presets**: `/prompt` or `--shape` → `references/prompt-compiler.md`. Standalone `--strict-scope`, `--spike`, `--review-only`, `--ship`, `--local-only` auto-inject via `build-dispatch.py` (`prompt_presets.py`).

**Gate**: Complexity set. Creation → `[CREATION REQUEST DETECTED]`. Trivial: direct. Simple+: Phase 2.

---

### Phase 2: ROUTE

**Goal**: fill every earned slot (`skill`, `pipeline`, `workers`). Semantic self-route runs FIRST against the manifest; `pre-route.py` runs AFTER as guardrail. Route on INTENT (`references/routing-examples.md`).

**Step 0: Semantic self-route (PRIMARY)**

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.gemini/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
bash "$SDIR/get-routing-manifest.sh" --request-file "$REQUEST_FILE"; rm -f "$REQUEST_FILE"
```

Hold unprinted JSON (`[do-route]` is the external trace):
`{"skill":"<SKILLS:|null>","pipeline":"<PIPELINES:|null>","workers":[{"skill":"<SKILLS:>","scope":"..."}],"reasoning":"...","confidence":"high|medium|low"}` (`workers`: extra fan-out or `[]`; add `"agent":"<AGENTS:>"` only for a matching overlay agent, keeping `skill`).

**Routing rules (ALL apply):**

```
SECTION-INTEGRITY RULE (HARD — never violate):
- `skill` and `workers[].skill` come from SKILLS: or null; `pipeline` from PIPELINES: or null.
- FORCE skills fill `skill` only; FORCE pipelines fill `pipeline` only (run still needs `skill`).
- `agent` comes from AGENTS: or is absent; never name retired specialist agents.

FORCE-ROUTE RULE: FORCE entries match semantically on user intent, never idioms/metaphors (`references/routing-examples.md`). A FORCE pipeline (6 of the 26) binds `pipeline` the same way; `pre-route.py` enforces guards while semantic routing owns intent.

PIPELINE-SELECTION RULE: 26 pipelines are available in PIPELINES:. Pick one when:
(1) intent semantically matches a pipeline, OR
(2) work has 3+ steps, gather-then-synthesize, mixed script+LLM, or durable artifacts, OR
(3) Phase 1 classified Complex.
Return null for single-step single-worker tasks (`references/routing-examples.md`).

FAN-OUT RULE: `workers` holds EXTRA `general-purpose` workers (`skill` + `scope`), `[]` if one suffices. Fan out for independent parallel parts on separate files (2+ failures, 3+ subtasks, per-language review, multi-domain gather); stay single when files overlap or stages depend sequentially. Complex starts from fan-out. Approved multi-subagent plans/specs must dispatch every defined subagent individually — never collapse them.

SPECIFICITY RULES:
- Most specific match ("Go tests" → `testing` + stack `programming`).
- Domain skills hold domain rules; methodology skills (`testing`, `review`, `debugging`) set method — put one in `skill`, the other in Phase 3 `stack`.
- Prefer semantic match and task verbs (review, debug, refactor, test) over bare keyword overlap.
- Genuine git/PR operations (push, commit, open/merge PR) select `pr-workflow`; metaphors do not.
- `skill` is one string, never an array.
```

**COMBINATION DOCTRINE.** Four surfaces compose (`workers` for fan-out, `skill`, `pipeline`, Phase 3 `stack`); fill every slot earned (`references/routing-examples.md`). Floor = one real surface: Simple = `skill`; Medium = `skill` + `stack`; Complex = 2+ workers + 2+ skills + `pipeline` when staged. A pipeline structures phases while `skill` fills its slot; `anti-rationalization-core` always rides in `stack`; FORCE skill + FORCE pipeline compose. Contradictions keep one: `quick` drops pipeline; `right-size-review.py` (`tier_signal: true`) beats `comprehensive-review`; domain skill beats `workflow` fallback; two pipelines pick outer, nest inner via Step 1c.

**Step 0b: Apply the routing decision** — use `skill`, `pipeline`, `workers`; verify low confidence in `skills/INDEX.json`.

**Skill-greediness gate (HARD — non-negotiable for Simple+).** Null skill → review→review, debug→workflow (systematic-debugging pipeline), refactor→workflow (systematic-refactoring pipeline), audit→review (whole-repo→review), explain→assessment, compare→assessment (component A/Bs→toolkit), plan→workflow, loop→workflow, TDD→testing. Fallback: `workflow`.

**Section validator (before dispatch):**

```
agents = tokens(manifest, "AGENTS:", "SKILLS:")
skills = tokens(manifest, "SKILLS:", "PIPELINES:")
pipelines = tokens(manifest, "PIPELINES:", END)
if route.agent not in agents: route.agent = None
if route.skill not in skills: route.skill = None; record_misroute(...)
route.workers = [w for w in route.workers if w.skill in skills]
if route.pipeline not in pipelines: route.pipeline = None
route.skill ||= "workflow"
```

No skill→`workflow`. `[cross-repo]`→`.claude/agents/`. Code→domain skill.

**Step 1: Deterministic safety-net** (`pre-route.py`, AFTER semantic decision; Phase 3 reads its `stack`):

```bash
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact; rm -f "$REQUEST_FILE"
```

→ `PRE_ROUTE_RESULT`. **(a) Safety override**: `"confidence":"high"` `force_route` for `pr-workflow` or `security` overrides a disagreeing semantic pick (record `match_type`; keep Step 0 `workers`). **(b) Else**: keep Step 0.

**Step 2: Apply skill override** — task verbs ("review", "debug", "refactor", "TDD") set the skill from Step 0b's gate.

**Step 3: Routing banner** (first visible output)

```
=== ROUTING: [summary] ===
  -> Worker: [main | general-purpose] - [why]
  -> Skill: [name] - [why]
  -> Pipeline: PHASE1 → PHASE2 (if set; pipeline-index.json)
  -> Extra Rigor: [patterns if needed]
Invoking...
```

Trivial: `Classification: Trivial - [reason]`, `Handling directly`. Main-thread Simple: `-> Worker: main - main thread, dispatch does not pay`. Pure Q&A (no edits/mutating tools): compact 1-line route header (`ROUTING: main | <skill> - <why>`).

**Gate**: Worker and skill set, banner shown. Phase 3.

---

### Phase 3: ENHANCE

| Signal | Enhancement |
|---|---|
| Substantive | Retro knowledge when material |
| "with tests"/"production ready" | `testing` |
| "research needed"/"investigate first" | `research`; fan out per source group |
| Full review or 5+ files, no diff | `review` (Security, BizLogic, Arch) |
| Multi-file review, real diff | `right-size-review.py`; pass tier only if `tier_signal: true` (else all waves). Outranks `comprehensive-review`. |
| Complex implementation | Offer `process` |
| "local only"/"no push"/"stay local" | Inject `shared-patterns/local-only.md` |
| Voice profile (e.g. voice-example-profile) | Stack `writing`; voice-*=profile |
| Knowledge/approval with another person | `workflow` (`skills/process/workflow/references/pl-human-source-elicitation.md`) |
| Observation settles high impact uncertainty | `workflow` (`skills/process/workflow/references/pl-empirical-prototype.md`) |
| Objective with done-criteria / "loop until done" | Stack `workflow` |
| Protected PR/security + Go source operand | Keep `pr-workflow`/`security` primary; stack `programming` |

Review overlap: real-diff row wins; fallback only without diff. Unresolved decisions, triage, or interviews: `references/interview-and-triage.md`. Check `pairs_with` before stacking; skills with built-in verification gates may suffice.

**Step G: GATHER (Simple+)** — populate Task Spec: unchanged `request_verbatim`, `intent`, `constraints`, verified `files`, `ownership`, `acceptance`, relevant `decisions`/`prior_results`/`gaps`, and `context_mode` (`"summary"`/`"files"`/`"none"`; `references/routing-examples.md`).

**Gate**: Enhancements applied, Task Spec filled. Phase 4.

---

### Phase 4: EXECUTE

- **Step 0: Creation** — ADR `adr/{name}.md`, `adr-query.py register`, plan.
- **Step 1: Plan** (Simple+) — `task_plan.md`; skip Trivial.
- **Step 1b: Quality-loop** (Medium+ code mod) — `references/quality-loop.md` 14 phases (`general-purpose` + implementation skill; skip non-code/Trivial/Simple).
- **Step 1c: Workflow** — Pipeline pick, Complex without pick, or explicit → `${CLAUDE_SKILL_DIR}/references/workflow-dispatch.md` (with 1b: quality-loop OUTER, workflow in IMPLEMENT).

**Step 2: Invoke worker**

- **Main thread (Trivial; Simple when dispatch does not pay):** `build-dispatch.py` with `{"execution":"main","skill":"<skill|->","complexity":"<trivial|simple>","task_spec":{"intent":"..."}}` (no model fields; `--no-record` skips telemetry). Load and run the printed skill in-thread.
- **Dispatched workers:** always build `[do-route]` (sole telemetry signal), Skill-tool calls, injections, and budget via `build-dispatch.py` (`references/routing-examples.md`):

```bash
DISPATCH_JSON=$(mktemp); cat > "$DISPATCH_JSON" << 'EOF'
{"skill":"<skill>","pipeline":"<omit if null>","complexity":"<trivial|simple|medium|complex>",
 "model":"<haiku|opus|fable|gemini-*>","context_mode":"summary","provider":"<anthropic|openai|google|antigravity|other>",
 "manual_model_override":false,"health":"-","stack":["s1"],
 "task_spec":{"request_verbatim":"<unchanged>","intent":"...","constraints":"...","decisions":"...","prior_results":"...","gaps":"...","acceptance":"<cmd> -> <expected>","files":"<paths>","ownership":"<scope>"},
 "flags":{"worktree":false,"local_only":false,"thinking_override":null},"token_remaining":480000}
EOF
python3 "$SDIR/build-dispatch.py" --json-file "$DISPATCH_JSON"; rm -f "$DISPATCH_JSON"
```

**PR work briefs:** put in `constraints`: commit locally, report SHA, never push/open PR without coordinator go-ahead. **Fallback:** `[do-route] agent=general-purpose skill={s|-} complexity={c}[ pipeline={p}] health=- model={m|-}` + inline Task Spec.

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

**Antigravity (`agy`) / Google AI:** if `detect-workflow-capability.py` reports `harness="antigravity"`, load `${CLAUDE_SKILL_DIR}/references/antigravity-execution.md`, set `provider="google"` (`gemini-3.8-flash`/`gemini-4-argon`/`gemini-4-argon-high`), run Trivial/Simple in-thread unless dispatch pays, and dispatch Medium+ or parallel work via `invoke_subagent` or `run_workflow`.

Marker records requested selection, not observed identity; use scripts for deterministic work; keep Codex prompts read-only/public unless required. Complex (3+ sources) matrix: `references/routing-examples.md`.

**Step 3: Multi-part / fan-out** — deps sequential; independent parallel (`references/workflow-dispatch.md`). One `build-dispatch.py` call + one `general-purpose` dispatch per worker in one message (`references/routing-examples.md`). Complex 2+ worker report → one self-review pass (`skills/shared-patterns/report-self-review.md`, `model: opus`, no marker).

**Step 4: Auto-Pipeline Fallback** (no match, Simple+) — `workflow` + `auto-pipeline`. None → closest+`workflow`. Never empty skill.

**Lazy-completion check.** "Done" on enumerable scope → compare; short → reject, re-dispatch (`references/lazy-completion-detector.md`). Re-dispatch → route failure.

**Gate**: Work executed or dispatched, results delivered.

---

### Routing telemetry (automatic)

Hooks record routing; on route failure or figure re-derivation → `${CLAUDE_SKILL_DIR}/references/routing-telemetry.md`.

## Error Handling

On routing error → `${CLAUDE_SKILL_DIR}/references/error-handling.md`.

## References

- `${CLAUDE_SKILL_DIR}/references/{interview-and-triage,prompt-compiler,routing-examples,progressive-depth,antigravity-execution}.md`
- `skills/INDEX.json`, `skills/process/workflow/references/pipeline-index.json`, `scripts/routing-manifest.py`
