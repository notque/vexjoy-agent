# SPEC: /d — Jev-first router

Maintenance contract. Load only when creating, evaluating, or redesigning
this skill — not during ordinary routing (SKILL.md's phases are the runtime
contract).

## Purpose
Alternate entry point to `/do` that replaces the in-context routing-manifest
read with bounded external Jev classification calls, cutting per-dispatch router
context cost when Jev is available.

## Scope
- Classify agent/skill/pipeline/complexity/stack-signals for one user
  request, via `scripts/jev-route.py`.
- Defer entirely to `/do`'s Phase 1-4 when Jev is unavailable, a Jev
  call errors, or Jev names an invalid/off-manifest pick.
- Execute Phase 4 (Task Spec + `build-dispatch.py`) identically to `/do`.

## Non-goals
- Not a replacement for `/do`: `/d` is a production Jev-backed entry point,
  while `/do` remains the manifest-based fallback and separate default route.
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
   limit").
   `--fits-threshold` still exists, scoped down to gating optional
   fan-out-candidate inclusion only — it no longer gates primary selection.
   `--confidence-floor` remains accepted on the CLI for backward
   compatibility but has no effect on routing (superseded since the v1-to-v2
   redesign, unchanged by this removal). A stage-1 gate score below
   `--gate-threshold` (default 0.30) is a distinct terminal state
   (`jev-trivial-bypass`), not a fallback, and is completely unaffected by
   this invariant's rewrite — it decides whether routing is needed at all,
   not which candidate wins among real options.
4. `JEV_TRANSPORT=auto|vercel|direct` selects the transport. Auto prefers
   `TYPESAFE_API_KEY`, then `AI_GATEWAY_API_KEY`. Credential values are never
   passed as arguments, logged, printed, or persisted.
5. `skills/meta/do/SKILL.md` and `commands/do.md` are never modified by this
   skill or its scripts.
6. On any fallback signal, `/d` executes `/do`'s full Phase 1-4 instructions
   unmodified — never a partial/degraded `/d`-only path. `jev-trivial-bypass`
   is not a fallback signal; it is handled directly during classification, matching
   `/do`'s own Trivial contract.
7. `jev-route.py` uses the shared transport selector. A missing Gateway bridge
   or unavailable direct API must never crash `/d`; it must fail open to `/do`.
8. Classification uses at most two Jev evaluations through the selected
   transport: none for force routes, one for a trivial bypass, and two for a
   routed request. Routing does not call the intent-alignment validator.

## Dependencies
- `scripts/jev-route.py` (classification)
- `scripts/pre-route.py`, `scripts/routing-manifest.py` (reused, unmodified)
- `scripts/build-dispatch.py` (reused, unmodified — Phase 4)
- Jev transport selector (`scripts/jev_transport.py`), Vercel AI Gateway bridge
  (`scripts/jev_vercel.py` and `scripts/jev_gateway/jev_vercel_gateway.mjs`),
  direct client (`scripts/jev_router_common.py`), and their credentials

## Known limitations (not blocking, tracked)
- Hidden prose coupling: `jev-route.py`'s classifier instructions
  hand-paraphrase `/do`'s Phase 1-3 text with no automated drift check (see
  `references/jev-classifier-design.md` "Known risk and coupling").
- Route classification has no independent verification beyond Jev's own
  self-reported fit scores
  (`/do`'s Step 0 has the orchestrator's live reasoning as an implicit
  check; `/d` does not have an equivalent for a confident-but-wrong pick).
  Since the 2026-09-16 fits-threshold removal, this is more relevant, not
  less: a low-fit pick is no longer deferred to `/do`, it is dispatched
  as-is. Monitored via regression evaluation, not solved structurally in this
  pass — see `references/jev-classifier-design.md`
  "Known risk and coupling," strengthened (not softened) by that change.
- Removing the primary fits threshold means fallback no longer acts as an
  uncertainty backstop for a low-fit but manifest-valid pick.
- The two-stage classifier adds network latency. `auto` prefers direct Jev
  when configured; explicit Vercel and gateway-only setups remain supported.

## Release criteria
- Matched routes proceed to dispatch or direct trivial handling without an
  extra baseline or proposed-intent Jev call.
- Direct Jev `auto` preference, explicit transport isolation, retry bounds,
  credential redaction, and direct-transport parity remain covered.
- Force-route, trivial-bypass, unavailable, error, and invalid-pick paths
  resolve according to their documented contracts.
- `SAFETY_BUCKETS` have no critical regressions in any new full-corpus run.

Historical percentages are not release criteria. Only results present in the
repository and reproducible with the current corpus and manifest may be cited;
missing or superseded verdict files are not evidence against production use.
