# SPEC: /d — session-pick router with Jev validation

Maintenance contract. Load only when creating, evaluating, or redesigning
this skill — not during ordinary routing (SKILL.md's phases are the runtime
contract).

## Purpose
Alternate entry point to `/do`. The session model picks the agent, skill, and
pipeline from the full routing manifest with `/do`'s own rule text. Jev
validates that the restated outcome survives the route and answers the
attachment questions. Intent preservation is production behavior: the router
must return the requested apple, not expand it into an orchard.

## Scope
- Run the force-route guard and one Jev attachment evaluation before the pick,
  via `scripts/jev-route.py` (prepare).
- Validate the pick against the live manifest and compute `attach` after it,
  via `scripts/jev-route.py --finalize`.
- Print `/do`'s Phase 2 rule text for the pick, via `scripts/print-route-rules.py`.
- Execute Phase 5 (Task Spec + `build-dispatch.py`) identically to `/do`.

## Intent alignment
Every `/d` route receives a required runtime intent restatement. One batched
Jev judgment checks that the intended outcome and constraints survive routing;
it reports scope loss, added work, route mismatch, and essential ambiguity
without fabricating a task. The receipt for the agent's actual `PROPOSED_INTENT`
satisfies the instruction gate. There is no hook-time baseline: the route does
not exist until the session model picks it, so a baseline would judge an empty
route. This is not hook enforcement, so the user remains the final backstop if
an agent violates the contract.

This is a production requirement grounded in repeated daily use: preventing
unrequested scope expansion is the feature's primary value.

## Non-goals
- Not a replacement for `/do`: `/d` shares `/do`'s rule text and manifest, and
  adds Jev's attachment answers and outcome validation.
- Not a new manifest format, INDEX schema, or `build-dispatch.py` contract
  change.
- Not a new telemetry/marker schema — dispatches still emit `[do-route]` via
  the shared `build-dispatch.py`.
- Jev does not pick the agent, skill, or pipeline. A 2026-10 paired
  measurement showed the session model with `/do`'s rule text beating Jev's
  two-stage pick (`references/jev-classifier-design.md`).

## Invariants
1. `scripts/pre-route.py`'s deterministic force-route guard always runs
   first. Its pr-workflow, pr-pipeline, and security matches override the
   picked skill and pipeline in `--finalize` (`/do` Phase 2 Step 1(a)). Other
   force matches are not carried into `JEV_RESULT`, matching `/do` Step 1(b).
2. Every agent, skill, and pipeline name in the route is validated against the
   live `AGENTS:`/`SKILLS:`/`PIPELINES:` manifest membership in `--finalize`.
   A name outside it is dropped and listed in `problems`. `d` and `do` are
   never valid skills.
3. The rule text is single-sourced. `/d` prints `/do`'s Phase 2 span with
   `print-route-rules.py` and never copies it.
   `scripts/tests/test_print_route_rules.py` fails when an anchor or a rule
   leaves `/do`'s SKILL.md.
4. `JEV_TRANSPORT=auto|vercel|direct` selects the transport. Auto prefers
   `AI_GATEWAY_API_KEY`, then `TYPESAFE_API_KEY`. Credential values are never
   passed as arguments, logged, printed, or persisted.
5. `skills/meta/do/SKILL.md` and `commands/do.md` are never modified by this
   skill or its scripts.
6. Jev failure never blocks routing. Without attachment evidence the route
   keeps the pre-route stack and the agent domain floor. The Phase 2 validator
   reports `unavailable`, and the request continues.
7. `jev-route.py` uses the shared transport selector. A missing Gateway bridge
   or unavailable direct API must never crash `/d`.
8. `/d` uses at most two Vercel AI Gateway Jev evaluations per request: one
   for the attachment questions (prepare) and one batched intent-alignment
   evaluation (Phase 2). Neither makes one request per question. `--finalize`
   never calls Jev. The Vercel transport is a supported production dependency.
9. Every route carries `attach`: manifest-valid extra skills from code policy
   (`_attachments` in `jev-route.py`), at most three. `/d` passes it as the
   dispatch `stack` unchanged. A route with no domain agent takes the primary
   or attached skill's owning agent. An empty skill takes `workflow`.

## Dependencies
- `scripts/jev-route.py`, `scripts/print-route-rules.py`, `scripts/jev_intent_align.py`
- `scripts/pre-route.py`, `scripts/routing-manifest.py`, `scripts/get-routing-manifest.sh` (reused, unmodified)
- `scripts/build-dispatch.py` (reused, unmodified — Phase 5)
- Jev transport selector (`scripts/jev_transport.py`), Vercel AI Gateway bridge
  (`scripts/jev_vercel.py` and `scripts/jev_gateway/jev_vercel_gateway.mjs`),
  direct client (`scripts/jev_router_common.py`), and their credentials
- Eval drivers: `scripts/d_route_model.py`, `scripts/jev-eval.py`,
  `scripts/jev-eval-live.py`, `scripts/router_attachment/run_eval.py`

## Known limitations (not blocking, tracked)
- The pick is one model reply. A rerun with unchanged code changes the pick on
  about 11% of corpus rows, so compare arms only with two runs each and count a
  row as changed when both runs agree.
- Route classification has no independent verification beyond the session
  model's own reasoning and the manifest-membership check. A confident wrong
  pick is dispatched as-is. Monitored via the corpus run, not solved
  structurally — see `references/jev-classifier-design.md` "Confident-wrong risk".
- The pick reads the whole manifest (about 10k tokens) and `/do`'s rule text
  (about 2k tokens) in the session. Jev's two-stage pick kept them out of the
  session; `/d` now spends that context for a higher pair accuracy.
- The Jev attachment call adds network latency. Vercel is preferred in `auto`
  mode because it is the required, currently cost-free production path; direct
  Jev remains the explicit alternative.

## Release criteria
- The instructions require a runtime receipt for the exact proposed intent
  before acting, unless validation is explicitly reported unavailable and the
  fail-open contract is followed.
- Added work, lost scope, route mismatch, and essential ambiguity exercise the
  alignment gates in `EVAL.md`.
- Vercel `auto` preference, explicit transport isolation, retry bounds,
  credential redaction, and direct-transport parity remain covered.
- Force-route, unavailable, error, and invalid-pick paths resolve according to
  their documented contracts.
- `scripts/tests/test_router_attachment_eval.py` passes, and a live run of
  `scripts/router_attachment/` does not drop below the last recorded run in
  `EVAL.md`.
- `SAFETY_BUCKETS` have no critical regressions in any new full-corpus run.

Historical percentages are not release criteria. Only results present in the
repository and reproducible with the current corpus and manifest may be cited;
missing or superseded verdict files are not evidence against production use.
