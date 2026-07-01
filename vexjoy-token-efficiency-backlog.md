Based on the structured opportunities provided, here is the prioritized backlog.

---

# VexJoy Token-Efficiency Backlog

## Status: All 4 Shipped

All four ranked items shipped 2026-05-28, three days before this backlog was
committed (2026-05-31, `f4d10928`). The plan below is kept as the design
record; treat "ship first" / "ship it ahead of" language in it as historical,
not as open work.

| Rank | Area | Shipped in |
|------|------|------------|
| 1 | Resume / interruption caching | PR [#687](https://github.com/notque/vexjoy-agent/pull/687) (`133d6d1d`) |
| 2 | Agent-count sizing heuristic | PR [#688](https://github.com/notque/vexjoy-agent/pull/688) (`f3fcf716`) |
| 3 | Schema-enforced review gates | PR [#687](https://github.com/notque/vexjoy-agent/pull/687) (`133d6d1d`) |
| 4 | Native Workflow for comprehensive-review | PR [#688](https://github.com/notque/vexjoy-agent/pull/688) (`f3fcf716`) |

## Framing

The single biggest lever is **work-proportional dispatch**: VexJoy currently hard-codes large fixed agent counts (12+10+4-5 waves, 10 perspectives) regardless of how small the change is, so a 3-file PR pays the same multi-agent tax as a 50-file one. Right-sizing agent counts to actual file/package scope — backed by a token-budget primitive and a feedback loop — is where the "use 4 where native used 8" goal is won. Everything else (caching completed agents, schema gates that fail cheap, native Workflow replacing disk-roundtrips) compounds on top: stop paying for work you already did, work you don't need, or work that has to be re-run because output was malformed.

## Ranked Table

All four items below are shipped; see Status section above for PR references.

| Rank | Area | Change (short) | Token impact | Effort | Value |
|------|------|----------------|--------------|--------|-------|
| 1 | Resume / interruption caching | Cache per-agent outputs in HANDOFF.json by input hash; skip re-execution of completed agents | saves-tokens | small | high |
| 2 | Agent-count sizing heuristic | Right-size wave/perspective counts by file+package scope; add token-budget env var | saves-tokens | medium | high |
| 3 | Schema-enforced review gates | Wire existing validate-review-output.py + schemas into dispatch; fail cheap, retry once | saves-tokens | medium | high |
| 4 | Native Workflow for comprehensive-review | Replace 4 prose waves + disk state with Workflow JS (cached-prefix replay, barriers) | saves-tokens | medium | high |

All four are `value: high` and `saves-tokens`; rank breaks on effort (small before medium). The three medium items are co-ranked by value+token-saving; ordered to put the lowest-risk, highest-coverage change (sizing) before the gate, before the largest structural rewrite (Workflow).

## Opportunities

### 1. Resume / interruption caching (small effort, highest ROI)
- **Change:** Extend `HANDOFF.json` schema with `agent_outputs: {agent_id: {input_hash, output, timestamp}}`. On resume, hash each wave agent's prompt+code; cache hit → reuse output, no dispatch.
- **Files:** `scripts/feature-state.py` (add deterministic SHA256 normalizer + cache load/save, currently lines 111-129 store no outputs), `skills/process/planning/references/resume.md` (Phase 4 Step 1: "check agent output cache before re-dispatching"), `skills/meta/do/references/parallel-analysis.md`, `agents/project-coordinator-engineer.md`.
- **Why it pays:** Today resume re-sends every agent in a wave (~2000 tokens prompt + input each) even for ones that already finished. Quote: HANDOFF stores `completed_agents` but "stores no per-agent cached outputs."
- **Token trade-off:** Saves ~8,000+ tokens per interrupted wave; cached hits cost zero tokens. Storage cost only (HANDOFF.json grows). No runtime needed — stays prose-driven. Best effort-to-save ratio in the set; do first.

### 2. Agent-count sizing heuristic (the core lever)
- **Change:** In `/do` Phase 3 ENHANCE, derive `FILE_SCOPE_TIER` (1-4) from git-diff file + package counts (computed in Phase 1), then dispatch proportionally:
  - 1-5 files / 1 pkg → parallel-code-review (3 agents)
  - 6-20 / 1-2 pkg → Wave 1 only (12)
  - 21-50 / 3-5 pkg → Wave 1 + Wave 2 subset (12+5); Wave 3 only on CRITICAL
  - 50+ / 5+ pkg → full (12+10+4-5)
  - parallel-analysis: 10→5 perspectives if source <2000 words.
- Add `BUDGET_MAX` env from `.claude/settings.json orchestration.token_budget` (default 500k); prepend "~{budget_remaining} tokens available; prioritize" to agent prompts. Record actual agent count + scope + tokens to learning.db (Phase 5) for heuristic refinement.
- **Files:** `skills/workflow/references/comprehensive-review.md` (Phase 1 Step 3 compute tier; Phase 2a/3a conditional wave includes), `skills/meta/do/SKILL.md` (Phase 3 table row + Phase 4 Step 2 budget injection), `skills/meta/do/references/parallel-analysis.md`.
- **Why it pays:** Counts are currently fixed "regardless of file count." A narrow PR drops from 25+ agents to 3 — the headline "4 not 8" win.
- **Token trade-off:** Saves the most in aggregate (largest multiplier on common small PRs). Risk: tier mis-classification under-reviews a high-risk small diff — mitigate by escalating to next tier on any CRITICAL finding (already built into tier 3 rule). Feedback loop adds tiny per-run logging cost.

### 3. Schema-enforced review gates (cheap-on-success, robust)
- **Change:** Wire the unused, working assets into dispatch. After each review agent returns, capture markdown to temp file, run `scripts/validate-review-output.py --type {review_type}` (exit 0/1/2). On failure, retry that ONE agent with specific schema errors; if still failing, report + stop (no partial data). Convert the 4-level goal-backward audit (EXISTS/SUBSTANTIVE/WIRED/DATA-FLOW) into schema predicates instead of prose.
- **Files:** `skills/review/parallel-code-review/SKILL.md`, `skills/review/systematic-code-review/SKILL.md`, `skills/process/verification-before-completion/SKILL.md`, `private-voices/vexjoy/shared-patterns/fan-out-dispatch.md`, plus existing `scripts/validate-review-output.py` (922 lines, working) and the 3 schemas.
- **Why it pays:** `validate-review-output.py` is "never referenced anywhere." Prose gates let executors rationalize past any level; mechanical gates can't be talked around.
- **Token trade-off:** Validation is ~10ms / 0 tokens. Costs ~1 agent re-run per ~50 batches (failure-only). Net save vs today's protocol, which re-runs all 3 agents on a BLOCK. Cheapest failure mode in the set.

### 4. Native Workflow for comprehensive-review (largest structural change)
- **Change:** Create `skills/workflow/references/comprehensive-review-workflow.js`. Replace 4 manual waves + `$REVIEW_DIR/wave-N-findings.md` disk round-trips with `parallel()` / `pipeline()` + schema-validated `agent({schema})` typed returns + true barriers. Phase 4 Fix uses `while(budget.remaining() > threshold)` native budget loop. `/do` Phase 4 Step 1b escalates to the JS workflow when comprehensive review or 5+ files / 2+ categories.
- **Files:** new `skills/workflow/references/comprehensive-review-workflow.js`, `skills/meta/do/SKILL.md`.
- **Why it pays:** Today findings are written to disk then "re-read and re-parsed into agent prompts" on every compaction/resume. Cached-prefix replay eliminates that re-parse tax.
- **Token trade-off:** Saves wave-to-wave context re-injection and survives compaction without re-reading state files. Highest implementation risk (new runtime surface, must keep markdown path as fallback); do last so #1-3 land the easy wins first. Overlaps with #1 (caching) and #3 (schema returns) — sequence after them to reuse their primitives.

## Quick Wins This Week (shipped — see Status)
- **#1 Resume caching** — small effort, saves ~8k tokens/interruption, zero runtime. Ship first. Shipped PR #687.
- **#3 validation wiring (partial)** — the script and schemas already exist and work; wiring `validate-review-output.py` into one skill (parallel-code-review) is a same-week subset that immediately stops malformed-output re-runs. Shipped PR #687.
- **#2 budget env var (partial)** — injecting `BUDGET_MAX` + the prompt string is a small, isolated slice of the medium #2 item; ship it ahead of the full tiering logic. Shipped PR #688.

## Watch Out (token COSTS)
- **#2 feedback logging** to learning.db — small recurring write cost per run; worth it (enables tiering refinement, pays back quickly).
- **#3 retry-on-failure** — a failed validation triggers a full agent re-run (~2k+ tokens). Worth it: rare (~1/50 batches) and cheaper than today's full 3-agent re-review on BLOCK. Cap at one retry (already specified) so a persistently-malformed agent can't loop.
- **#4 native Workflow** — build/maintenance cost of a new JS runtime surface; net-positive on tokens but only if the markdown fallback is retained. If maintenance bandwidth is thin, defer #4 and capture ~80% of its savings via #1 + #3, which remove the same disk re-parse and re-run costs without the new surface.