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

ROUTER, not worker. Classify → agent+skill → dispatch. All execution goes to agents. Catching yourself reading/writing code or analyzing — pause and route to an agent. Main: Classify→Select→Dispatch→Evaluate→Re-route→Report.

Do the whole thing (tests+docs). Product, not plan. Permanent solve over workaround. Search before building; test before shipping. Decompose into agent-sized tasks. The result reads as "that's done," not "that's a start." Partial → follow-up. Inject Simple+. Confidence in handling directly is a signal to route.

Dense-Complete Writing (`build-dispatch.py` injects; `skills/shared-patterns/dense-complete-writing.md`). User: banners+summary. Internal: JSON/reasoning/stacking (Verbose overrides).

## Instructions

### Phase Banners (MANDATORY)

Every phase: `/do > Phase N: PHASE_NAME — description...`
After Phase 2: `===` routing banner. Both required.

---

### Phase 1: CLASSIFY

Read CLAUDE.md first.

| Complexity | Agent | Skill | Direct |
|---|---|---|---|
| Trivial | No | No | ONLY user-named file by path |
| Simple | Yes | Yes | Route |
| Medium | Required | Required | Route |
| Complex | 2+ | 2+ | Route |

Beyond user-named file = Simple+, MUST route. Uncertain → UP. Depth: `references/progressive-depth.md`. NOT Trivial: repos/URLs, opinions, git, codebase Qs, retro, comparisons.

Parallel FIRST: 2+ failures / 3+ subtasks → multiple Agent tools. Research→research-coordinator-engineer; coord→project-coordinator-engineer; plan+exec→subagent-driven-development; feature→feature-lifecycle (.feature/→feature-state.py status). Force Direct: OFF.

**Creation Detection** (MANDATORY): create/scaffold/build/"add new"/"new [component]" targeting agent/skill/pipeline/hook/feature/plugin/workflow/voice. ANY + Simple+ → `is_creation=true`, Phase 4 Step 0. Not: debug/review/fix/refactor/explain/audit.

**Gate**: Complexity set. Creation → `[CREATION REQUEST DETECTED]`. Trivial: direct. Simple+: Phase 2.

---

### Phase 2: ROUTE

Semantic intent. Prefer FORCE. Keywords hint, never gate. "send my commits to the server" = "git push".

**Pre-route (ONCE, before fast-path)**

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

→`PRE_ROUTE_RESULT` (once).

**Fast path:** PRE_ROUTE_RESULT high-conf force_route + pr-workflow/security → skip 0/1.5/1, dispatch direct. Keep banner+overrides+P3+P4. `[do-route]` `health=-`. Agent: pre-route→domain→general-purpose.

**Step 0: Self-route**

Read the manifest (hash-gated cache or regenerate): `"$SDIR/get-routing-manifest.sh"` (SDIR from pre-route).

Internal JSON; `[do-route]` = sole trace.

**Routing rules (ALL apply):**

```
SECTION-INTEGRITY (HARD — never violate):
agent∈AGENTS|null, skill∈SKILLS|null, pipeline∈PIPELINES|null.
No fit→null→general-purpose. Never skill→agent. FORCE skills: skill slot only.

FORCE-ROUTE — select when domain matches SEMANTICALLY (meaning, not words):
- "push my changes" → pr-workflow (FORCE) ✓ (git push)
- "push back on this design" → NOT pr-workflow (resist/argue)
- "configure my fish shell" → fish-shell-config (FORCE) ✓
- "fish for bugs" → NOT fish-shell-config (search for bugs)
- "quick fix to the login page" → quick (FORCE) ✓
- "quick overview of the architecture" → NOT quick (exploration)

PIPELINE — both: triggers match + multi-phase benefit. Mostly null.
"vexjoy voice article"→voice-writer ✓ | "research+sources"→research-pipeline ✓ | "fix typo"→null
Comprehensive-review outranked by right-size-review when real diff exists.

GENERAL: most specific. Agent=domain, skill=method. Git→pr-workflow; metaphor→never.
```

**Step 0b: Apply the routing decision**

Low conf → verify INDEX.

**Skill-greediness gate (HARD — non-negotiable for Simple+).** Null skill → pick: review→systematic-code-review, debug→workflow (systematic-debugging), refactor→workflow (systematic-refactoring), audit→systematic-code-review (whole-repo→full-repo-review), explain→codebase-overview, compare→decision-helper (agent A/Bs→agent-comparison), plan→planning, loop→objective-loop. Fallback: `objective-loop`.

**Section validator (MANDATORY before dispatch):**

```
agents = tokens(manifest, "AGENTS:", "SKILLS:")
skills = tokens(manifest, "SKILLS:", "PIPELINES:")
if route.agent not in agents:
    if route.agent in skills: route.skill ||= route.agent
    route.agent = None; record_misroute(...)
route.agent ||= "general-purpose"
```

No pair→general-purpose+objective-loop. `[cross-repo]`→`.claude/agents/`. Code→domain agents.

**Step 1.5: Health (shadow-only)**

```bash
python3 "$SDIR/learning-db.py" route-weights --json
```

`health_adjust()` → keep|demote|tiebreak. **Recorded, never alters route.** Activation gated on first negative signal (`docs/route-loop-validation.md`). Demote: conf<0.30+fail>=3+n>=5. Tiebreak: conf<0.35+healthier alt. Force-route/security→keep. n<5→keep. `build-dispatch.py` emits marker on DECISION.

**Step 1: Safety-net** (reads PRE_ROUTE_RESULT)

(a) force_route pr-workflow/security disagrees → override. Git/security MUST hit quality gates. (b) Phrase guards suppress false matches → Step 0.

**Step 2: Apply skill override** — "review"→systematic-code-review, "debug"→workflow (systematic-debugging pipeline), "refactor"→workflow (systematic-refactoring pipeline), "TDD"→test-driven-development. Full table in INDEX.

**Step 3: Routing banner** (MANDATORY — first visible output)

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from skills/workflow/references/pipeline-index.json)
   -> Extra Rigor: [verification patterns for code/security/testing when needed]
 Invoking...
===================================================================
```

Trivial: `Classification: Trivial - [reason]`, `Handling directly`.

Learning: hooks below.

**Gate**: Agent+skill set, banner shown. Phase 3.

---

### Phase 3: ENHANCE

Stack on signals.

| Signal | Enhancement |
|---|---|
| Substantive | Retro knowledge when material |
| "with tests"/"production ready" | test-driven-development+verification-before-completion |
| "research needed"/"investigate first" | research-coordinator-engineer |
| Comprehensive/thorough/full review or 5+ files, no diff | parallel-code-review (Security, BizLogic, Arch) |
| Multi-file review, real diff | `right-size-review.py`; T1→3,T2→12,T3→17,T4→27. CRITICAL+1. Outranks comprehensive-review. |
| Complex implementation | Offer subagent-driven-development |
| "local only"/"no push"/"keep it local"/"stay local" | Inject `shared-patterns/local-only.md` |
| Voice profile (e.g. voice-example-profile) | Stack `voice-writer`; voice-*=profile |
| Interview-mode heuristic | `planning` — `depth-first-interview.md` |
| Objective with done-criteria / "loop until done" | Stack `objective-loop` |

Review overlap: real-diff row wins; fallback only without diff.

**Interview heuristic.** Short, no file/symbol, ambiguous. Spec:

| Example | ? | Why |
|---|---|---|
| "i'm not sure how to approach this complex build" | Y | Vague+no target |
| "fix the typo on line 42 of foo.py" | N | File+loc |
| "build a thing that does X" | Y | No file |
| "add a test for `parseConfig` in src/config.go" | N | Symbol+file |
| "where do i even start with this rewrite" | Y | No subject |
| "rename `cfg` to `config` in `internal/`" | N | Mechanical |

Check `pairs_with` before stacking. Skills with built-in verification gates may suffice.

anti-rationalization-core always + verification-checklist (code/debug) + anti-rationalization-review + anti-rationalization-security + anti-rationalization-testing; external: **untrusted-content-handling**. Max: `/with-anti-rationalization`.

**Gate**: Enhancements applied. Phase 4.

---

### Phase 4: EXECUTE

**Step 0: Creation** — ADR at `adr/{name}.md`, `adr-query.py register`, plan.

**Step 1: Plan** (Simple+) — `task_plan.md`; skip Trivial.

**Step 1b: Quality-loop** (Medium+ code mod) — `references/quality-loop.md` 14 phases. P2 agent=implementation. Force-route in loop. Skip non-code/Trivial/Simple.

**Step 1c: Workflow** — Pipeline pick or Complex no pick or explicit → `${CLAUDE_SKILL_DIR}/references/workflow-dispatch.md`. Both 1b+1c → quality-loop OUTER, workflow in IMPLEMENT.

**Step 2: Invoke agent**

**`build-dispatch.py` (MANDATORY)** — source for `[do-route]`, thinking, budget, Task Spec, injections, worktree/local-only. Never hand-assemble.

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

`agent`/`skill`/`complexity`: Phase 2 (null→`-`). `model`: **required Medium+** (`-` trivial/simple). `health`: 1.5 (`-` if none). `stack`: Phase 3. `task_spec`: mandatory Medium+; creation+"match ADR". `thinking_override`: slow=security/arch/5+files; fast=lookups.

`[do-route]` = SOLE signal for `routing-decision-recorder`. Sub-agents excluded.

**Fallback:** `[do-route] agent={a} skill={s|-} complexity={c} health=- model={m|-}`, Task Spec inline, dispatch.

**Model Selection (ADR `model-selection-policy`).**

| model | cost | int | taste | role |
|---|---|---|---|---|
| gpt-5.5 | 9 | 8 | 5 | Bulk/mechanical via codex |
| sonnet-5 | 5 | 5 | 7 | Fan-out, lighter. `"sonnet"` |
| opus-4.8 | 4 | 7 | 8 | Reviews, deep. `"opus"` |
| fable-5 | 2 | 9 | 9 | Escalation only |

**Medium+ MUST set model**. Cheaper misses→smarter (sonnet→opus→gpt-5.5→spec). intelligence>taste>cost. Bulk→gpt-5.5, taste>=7 user-facing, reviews→opus. Haiku retired. Codex: read-only; public only.

**Complex (3+ sources):**

| Verbs | Mode |
|---|---|
| list/count/extract/inventory/search/check/find/grep | Fan-out gpt-5.5/sonnet → opus synth |
| review/audit/assess/analyze/debug/investigate/evaluate | Single opus |

Simple/Medium: direct. Feature-branch; mods commit. `isolation:"worktree"`→`flags.worktree`. Non-org: 3 reviews→fix→PR. Org: confirm git.

**Step 3: Multi-part** — deps sequential; independent parallel (max 10).

**Step 4: Auto-Pipeline Fallback** (no match, Simple+) — `auto-pipeline`. None → closest+`objective-loop`. Never empty skill.

**Lazy-completion check.** "Done" on enumerable → compare scope; short → reject, re-dispatch (`references/lazy-completion-detector.md`). Re-dispatch → route failure.

**Gate**: Agent invoked, results delivered.

---

### Learning Capture (automatic)

Hooks capture all. On observed route failure or learning question → load `${CLAUDE_SKILL_DIR}/references/learning-capture.md` (hooks table, outcome fidelity, route-failure protocol).

---

## Error Handling

On any routing error → load `${CLAUDE_SKILL_DIR}/references/error-handling.md`.

## References

- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`
- `agents/INDEX.json`, `skills/INDEX.json`
- `skills/workflow/SKILL.md`, `skills/workflow/references/pipeline-index.json`
- `scripts/routing-manifest.py`
