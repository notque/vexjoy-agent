# SPEC: /d — Jev-first router

Maintenance contract. Load only when creating, evaluating, or redesigning
this skill — not during ordinary routing (SKILL.md's phases are the runtime
contract).

## Purpose
Alternate entry point to `/do` that replaces the in-context routing-manifest
read with one external Jev classification call, cutting per-dispatch router
context cost when TypeSafe is available and confident.

## Scope
- Classify agent/skill/pipeline/complexity/stack-signals for one user
  request, via `scripts/jev-route.py`.
- Defer entirely to `/do`'s Phase 1-4 when TypeSafe is unavailable, a Jev
  call errors, or Jev names an invalid/off-manifest pick.
- Execute Phase 4 (Task Spec + `build-dispatch.py`) identically to `/do`.

## Non-goals
- Not a replacement for `/do` in this pass — `/do` stays the default,
  unedited baseline. Current eval results do not support promotion (see
  `scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT.md`, the
  current design's measured numbers; `jev-router-v1-2026-09-16/VERDICT.md`
  is the superseded single-call baseline).
- Not a new manifest format, INDEX schema, or `build-dispatch.py` contract
  change.
- Not a new telemetry/marker schema — dispatches still emit `[do-route]` via
  the shared `build-dispatch.py`.
- Does not reimplement `/do`'s Phase 1-3 semantic reasoning in Python; it
  replaces that reasoning with an external classifier plus a Python-side
  validation/floor layer, not a rules rewrite.

## Invariants
1. `scripts/pre-route.py`'s deterministic force-route guard always runs
   first and is never overridden by Jev.
2. Every agent/skill/pipeline name returned to the caller is validated
   against the live `AGENTS:`/`SKILLS:`/`PIPELINES:` manifest membership
   before use.
3. Manifest-membership validation is the ONLY thing that can invalidate a
   primary agent/skill/pipeline pick (2026-09-16, fits-threshold removal):
   every name returned to the caller must be a real, shortlisted manifest
   entry, or that dimension is rejected to `null` -> fallback, never a
   guess. Jev's top-ranked Choice pick is otherwise always used, with no
   minimum fit score required — the earlier `--fits-threshold`-gated
   rejection on primary selection (default 0.30) was removed per the
   owner's explicit instruction ("it picks the most relevant option instead
   of having some .7 requirement... I don't want there to be any artificial
   limit"; see `scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT_no_threshold.md`).
   `--fits-threshold` still exists, scoped down to gating optional
   fan-out-candidate inclusion only — it no longer gates primary selection.
   `--confidence-floor` remains accepted on the CLI for backward
   compatibility but has no effect on routing (superseded since the v1-to-v2
   redesign, unchanged by this removal). A stage-1 gate score below
   `--gate-threshold` (default 0.30) is a distinct terminal state
   (`jev-trivial-bypass`), not a fallback, and is completely unaffected by
   this invariant's rewrite — it decides whether routing is needed at all,
   not which candidate wins among real options.
4. `TYPESAFE_API_KEY` value is never logged, printed, or persisted.
5. `skills/meta/do/SKILL.md` and `commands/do.md` are never modified by this
   skill or its scripts.
6. On any fallback signal, `/d` executes `/do`'s full Phase 1-4 instructions
   unmodified — never a partial/degraded `/d`-only path. `jev-trivial-bypass`
   is not a fallback signal; it is handled directly (Phase 1T), matching
   `/do`'s own Trivial contract.
7. `jev-route.py` has zero third-party HTTP dependencies (stdlib
   `urllib.request` only) — a missing package must never crash `/d` instead
   of it falling back to `/do`.
8. Exactly 2 TypeSafe HTTP round trips per routing decision that reaches Jev
   at all (0 on force-route/unavailable, 1 on trivial-bypass, 2 otherwise) —
   never per-dimension, never proliferating.

## Dependencies
- `scripts/jev-route.py`, `scripts/jev_router_common.py` (classification)
- `scripts/pre-route.py`, `scripts/routing-manifest.py` (reused, unmodified)
- `scripts/build-dispatch.py` (reused, unmodified — Phase 4)
- TypeSafe API (`https://api.typesafe.ai/v1/systemone`),
  `TYPESAFE_API_KEY` env var, `enabledPlugins["typesafe@typesafe-ai"]` in
  settings

## Known limitations (not blocking, tracked)
- Hidden prose coupling: `jev-route.py`'s classifier instructions
  hand-paraphrase `/do`'s Phase 1-3 text with no automated drift check (see
  `references/jev-classifier-design.md` "Hidden coupling").
- No independent verification beyond Jev's own self-reported fit scores
  (`/do`'s Step 0 has the orchestrator's live reasoning as an implicit
  check; `/d` does not have an equivalent for a confident-but-wrong pick).
  Since the 2026-09-16 fits-threshold removal, this is more relevant, not
  less: a low-fit pick is no longer deferred to `/do`, it is dispatched
  as-is. Monitored via the eval and the promotion-review checkpoint, not
  solved structurally in this pass — see `references/jev-classifier-design.md`
  "Confident-wrong risk," strengthened (not softened) by that change.
- Fallback rate dropped from v1's flat confidence-floor 62.1% (corpus v1.4)
  to v2-with-fits-threshold's 26.0% (corpus v1.5), and, after the
  2026-09-16 fits-threshold removal from primary selection, to ~0.0% per a
  derived recompute (`scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT_no_threshold.md`
  — not a fresh full-corpus run; see that file for methodology and caveats).
  The token-savings claim now applies to essentially every dispatch that
  reaches Jev, not the ~3-in-4 figure that held under the removed threshold.
  Removed as a limitation of note; see the "No independent verification"
  item above for the corresponding new consideration (fallback no longer
  acts as an uncertainty backstop on a low-fit pick).
- v2's two-stage design roughly doubles measured mean latency versus v1's
  single call (v2 mean 285.0 ms vs v1 mean 201.5 ms) in exchange for the
  accuracy and fallback-rate gains above — still far below any interactive-
  latency concern, but not free.

## Success criteria
- Accuracy on `scripts/routing-ab-corpus.json` >= the documented self-route
  baseline, measured on a paired same-corpus run. Not yet done at full scale
  (an 80-case stratified paired sample exists, see `jev-classifier-design.md`);
  the corpus's own labels were found to be unreliable for several buckets
  (near-synonym skills scored as hard misses, labels reflecting aspirational
  policy real `/do` traffic doesn't follow either) — treat any accuracy
  percentage from this corpus as a rough signal, not a promotion gate.
- Zero regression in `SAFETY_BUCKETS`, checked per bucket (met in the v1
  2026-09-16 run AND the v2 2026-09-16 redesign run).
- Decision JSON materially smaller than the ~15,700-token manifest read
  (met: median 1191 bytes, ~1/53rd, in the v2 2026-09-16 run — larger than
  v1's 825 bytes/~1/76th due to v2's new `agents`/`gate_score`/
  `fits_scores`/`stage1_shortlist` fields and itemized `latency_ms`/`usage`,
  still tiny against the manifest baseline).
- Fallback path exercised and confirmed equivalent to `/do` (met — force-route,
  trivial-bypass, and unavailable/error/invalid-pick paths all verified to
  defer or resolve correctly; `low-confidence` is no longer a reachable
  fallback source as of the 2026-09-16 fits-threshold removal).

Current status against these criteria: 3 of 4 met; accuracy vs. a paired
same-corpus self-route baseline is the open item, tracked for the 4-week
promotion review. v2's own measured accuracy with the 0.30 fits-threshold
still in place was 113/269 (42.0%, corpus v1.5), a large improvement over
v1's (45/269, 16.7%, corpus v1.4); after the 2026-09-16 fits-threshold
removal, a derived recompute reports 149/269 (55.4%) full-corpus and 54/80
(67.5%) on the paired 80-case subset against `/do`'s own 68.8% on that
subset — a 1.3-point gap, down from 12.6 points pre-removal (see
`scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT_no_threshold.md`,
cited here as its source: a derived recompute, not a fresh full-corpus API
run). Neither figure is itself the paired same-corpus self-route baseline
this criterion is tracking — see
`scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT.md`.
