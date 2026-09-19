# Jev classifier design

Deep reference for `/d` (`skills/meta/d/SKILL.md`). Load this when explaining,
tuning, or extending the router; SKILL.md's phases are enough to run it.

**v2 redesign, 2026-09-16.** This document describes the CURRENT two-stage
design. v1 (single flat `Choice` call per dimension) is superseded; its
numbers are cited only as the documented before/after baseline
(`scripts/routing-ab-results/jev-router-v1-2026-09-16/VERDICT.md`).

## Presence contract

`scripts/jev_router_common.py: typesafe_available() -> (bool, str)`. Unchanged
by the v2 redesign. True only when both hold:

1. `TYPESAFE_API_KEY` is set and non-empty in the environment (value never
   read into logs, prints, or files — only its presence is checked).
2. `enabledPlugins["typesafe@typesafe-ai"] == true` in the merged settings:
   `~/.claude/settings.local.json` values win over `~/.claude/settings.json`
   for any key present in both; a missing file is `{}`, not an error.

Either condition false -> `/d` never attempts a network call. This is a
presence check, not a health check — a configured-but-down TypeSafe endpoint
still attempts the call and falls back on the resulting timeout/error, not on
this check.

## Why v1 was replaced

v1 asked ONE flat `Choice` question per dimension (agent, skill, pipeline,
complexity) over ALL manifest candidates at once, with descriptions truncated
to ~100 characters each — and never sent `not_for` disambiguation text to Jev
at all, at any point, for any dimension. Two independent problems, not one:

1. **Truncation cut real disambiguating content inside `description` itself**
   for any entry whose description ran past ~100 characters (several
   agent/skill descriptions do — see "Cookbook reuse and divergence" below
   for the measured effect).
2. **`not_for` was never in the payload, truncated or not.** Many entries
   carry an explicit `not_for` clause naming the exact sibling skill/agent a
   request is likely to be confused with (e.g. `reviewer-code`'s `not_for`
   says "business-logic correctness, ADR conformance... (use reviewer-domain)").
   v1's single pass had no way to show Jev that text, so Jev had no signal
   telling it "not this one, that one" beyond the short descriptions
   themselves.

Owner-mandated fix: a two-stage progressive-disclosure pattern (cheap wide
rank, then full-detail shortlist rerank), NOT the cookbook's shape
transplanted wholesale — see below for exactly what was kept and what
changed, and why.

## Request/response shape (v2, two calls)

Up to TWO `POST https://api.typesafe.ai/v1/systemone` calls per routing
decision that reaches Jev at all: 0 on force-route or TypeSafe-unavailable, 1
on trivial-bypass (stage 1 only), 2 otherwise (stage 1 + stage 2). Never
per-dimension, never more than 2 — this is a hard cost constraint, not a
default that grows with manifest size.

### Stage 1 (wide rank + trivial-bypass gate)

One call. Body:

```json
{
  "state": "<user request verbatim>",
  "model": "jev-latest",
  "questions": {
    "agent":    {"type": "choice", "instructions": "...", "criteria": {"<agent>": "<~100-char desc>", ..., "general-purpose": "..."}},
    "skill":    {"type": "choice", "instructions": "...", "criteria": {"<skill>": "<~100-char desc>", ...}},
    "pipeline": {"type": "choice", "instructions": "...", "criteria": {"<pipeline>": "<~100-char desc>", ..., "none": "..."}},
    "needs_skill":     {"type": "noul", "instructions": "..."},
    "needs_pipeline":  {"type": "noul", "instructions": "..."},
    "prose_suffices":  {"type": "noul", "instructions": "..."}
  }
}
```

`criteria` for `agent`/`skill`/`pipeline` are the SAME ~100-char truncated
descriptions v1 built (`_truncate_desc`, `_build_criteria_maps` — reused
unchanged; a cheap skim doesn't need full text, only stage 2 does). Response:
`{model, answers: {qid: Answer}, usage}`. Each `choice` answer carries
`{choice, probabilities, confidence}` — `jev-route.py` reads `probabilities`
(not just the single top `choice`) to build shortlists, since the whole point
of stage 1 is "who are the top ~3 contenders," not "who is the single best
guess from a cheap pass."

`jev-route.py` (`_parse_stage1`) computes, per single-select dimension:

- **agent, skill**: top `STAGE1_SHORTLIST_N` (3) names by `probabilities`,
  restricted to live manifest membership.
- **pipeline**: top 1 REAL (non-`"none"`) candidate by `probabilities`,
  computed unconditionally — even when `"none"` won stage 1's own `choice`.
  Rationale: with only ~29 pipeline candidates and a cheap truncated pass,
  "none" can win narrowly on a genuinely ambiguous case; forwarding the
  best real candidate anyway gives stage 2's full-detail rerank a real
  chance to confirm or reject it, rather than letting the cheap pass
  foreclose the pipeline slot before the precise pass ever runs. This is
  the same "don't let cheap-pass noise be final" reasoning behind giving
  agent/skill a 3-wide shortlist instead of trusting stage 1's single top
  pick outright — pipeline gets a 1-wide shortlist only because there are
  far fewer real candidates to protect against, not because the reasoning
  differs.

`gate_score` = mean of the three oriented gate `Noul`s: `needs_skill`,
`needs_pipeline`, and `1 - prose_suffices` (prose_suffices is inverted before
averaging, so a HIGH gate_score always means "routing is needed," matching
the other two nouls' orientation). Below `--gate-threshold` (default 0.30):
**trivial-bypass** — `source: "jev-trivial-bypass"`, `complexity: "trivial"`,
`agent`/`skill`/`pipeline` all `null`, `matched: true`, `fallback: false`.
Stage 2's HTTP call is skipped entirely; this is the one case with only one
round trip. This maps directly onto `/do`'s own Trivial classification
(`skills/meta/do/SKILL.md` Phase 1: "Trivial: ONLY user-named file by
path... never dispatches, handled directly") — `/d`'s SKILL.md Phase 1T
handles it the same way: direct, no Phase 4.

### State and shortlist size

`state` is the bare request string when no project facts exist. When the hook
passes `--cwd`, `detect_project_context()` reads marker files (for example
`pyproject.toml`, `package.json`, `go.mod`) and dependency manifests in that
directory, and `state` becomes `{"request": ..., "project": {"languages":
[...], "frameworks": [...], "datastores": [...]}}`. The project block holds
names only, never paths or file contents. The agent instructions gain one
sentence that tells Jev to use `project` when the request names no language.

The stage-1 shortlist is 6 agents and 6 skills (`STAGE1_SHORTLIST_N`,
`--shortlist`). Stage 2 cannot pick outside the shortlist, so its size caps
accuracy. Measure coverage offline from the stored stage-1 probabilities in
`jev_calls` before changing it.

Score the router with `scripts/jev-eval.py --split dev` while tuning and
`--split test` once at the end. `--workload-dir NAME=PATH` supplies the
repository for corpus cases that record a workload.

### Stage 2 (shortlist rerank + fits + multi-select), only when gate clears

One call, only reached when `gate_score >= gate_threshold`. Body (shape,
candidate counts vary per request):

```json
{
  "state": "<user request verbatim>",
  "model": "jev-latest",
  "questions": {
    "agent":                 {"type": "choice", "instructions": "...", "criteria": {"<top-6 agent shortlist>": "<full desc NOT: not_for>"}},
    "agent_fit__<name>":     {"type": "noul", "instructions": "..."},
    "skill":                 {"type": "choice", "instructions": "...", "criteria": {"<top-6 skill shortlist>": "<full desc NOT: not_for>"}},
    "skill_fit__<name>":     {"type": "noul", "instructions": "..."},
    "pipeline":              {"type": "choice", "instructions": "...", "criteria": {"<top-1 pipeline>": "...", "none": "..."}},
    "pipeline_fit__<name>":  {"type": "noul", "instructions": "..."},
    "tests_requested":       {"type": "noul", "instructions": "..."},
    "research_needed":       {"type": "noul", "instructions": "..."},
    "comprehensive_review":  {"type": "noul", "instructions": "..."},
    "local_only":            {"type": "noul", "instructions": "..."},
    "objective_loop_worthy": {"type": "noul", "instructions": "..."},
    "fanout__<name>":        {"type": "noul", "instructions": "..."}
  }
}
```

Criteria text for every stage-2 candidate is `description + (" NOT: " +
not_for if present)`, sourced straight from `routing-manifest.py`'s live
`load_entries()` output — already untruncated, no filesystem reads of
SKILL.md/agent.md files added. Question keys for per-candidate `Noul`s are
sanitized names (`_sanitize_key`, `[^a-zA-Z0-9_]` -> `_`) prefixed by
dimension (`agent_fit__`, `skill_fit__`, `pipeline_fit__`, `fanout__`), with
an in-memory map back to the original manifest name for parsing.

**Fits check** (`_parse_stage2`, `--fits-threshold`, default 0.30): for each
single-select dimension, the stage-2 `Choice` picks one name from the
shortlist; that SAME name's own per-candidate fit `Noul` is then checked
against `fits_threshold`. Below threshold -> that dimension's pick is
rejected to `null`, regardless of what the `Choice` answer said. This reads
owner's "the BEST-shortlisted candidate's own fit-Noul" as "the candidate the
stage-2 Choice actually selected" (not a separate max-over-shortlist search)
— `Choice` produces the name, `Noul` is the fit veto on that specific name.
`fits_scores` in the result reports this per-dimension value for eval
visibility (`{"agent": x, "skill": y, "pipeline": z_or_null}`).

**Fallback trigger**: `agent` rejected (invalid membership OR sub-threshold
fit) OR `skill` rejected -> the WHOLE decision is `fallback: true` — this
replaces v1's flat `agent_conf < confidence_floor` check. `pipeline` is
NEVER gated into the fallback decision (same as v1: a `null` pipeline is
often the correct answer, most requests are single-phase).

**Multi-select**: the 5 stack signals are independent per-candidate `Noul`s
over the WHOLE request (not per-manifest-candidate), unchanged in mechanism
from v1 — just moved into stage 2's call (they need the same rich context
stage 2 already has, and stage 1's trivial-bypass gate makes them moot when
it fires, so stage 2 is the natural home). Fan-out candidates (`agents`
field) are a NEW per-candidate `Noul` over agents ranked just below the
primary shortlist (the three agents ranked just after it in stage 1),
asking "should this agent ALSO run in parallel, on a distinct independent
subtask" — see "Fan-out selection rule" below for the exact gating heuristic
and why it exists.

## Complexity: dropped as a Jev question, derived in Python

v1 asked Jev a fourth `Choice` question for `complexity`. v2 does not — the
owner's exact stage-1/stage-2 question lists never include a complexity
`Choice`, and asking one would violate the "never proliferating" cost
constraint for no clear benefit once gate_score, the final picks, and the
5 stack signals already exist. `jev-route.py` derives `complexity`
deterministically after stage 2 resolves:

- `pipeline` set OR `agents` (fan-out) non-empty -> `"complex"` (matches
  `/do`'s own "2+ agents... or a genuine multi-phase pipeline" criterion)
- else any stack signal true -> `"medium"` (matches `/do`'s "extra rigor"
  criterion)
- else -> `"simple"`
- trivial-bypass -> `"trivial"` (stage 1 only, no stage 2 needed to know this)

This is a deliberate, documented trade: one fewer Jev question per decision,
a small saved cost, in exchange for a simpler and fully auditable Python rule
instead of a fifth judgment call riding in the same HTTP call.

## Fan-out selection rule

`_select_fanout_candidates`: agents ranked 4-6 in stage 1's probability
ranking (`FANOUT_RANK_START=3`, `FANOUT_MAX_CANDIDATES=3`), asked a
per-candidate fan-out `Noul`, but ONLY when BOTH:

1. `gate_score >= FANOUT_GATE_SCORE_MIN` (0.6) — a heuristic proxy for
   "this is substantive/complex work," well above the 0.30 trivial-bypass
   floor, so borderline-trivial requests never pay for fan-out questions.
2. The top-ranked agent's stage-1 probability is `< FANOUT_DOMINANCE_PROB`
   (0.75) — a heuristic proxy for "more than one plausible domain owner
   exists." When one agent clearly dominates, fan-out questions would almost
   certainly all come back false, so they're skipped rather than spent.

Both thresholds are cost-control heuristics, not precision claims — read
`/do`'s own MULTI-AGENT RULE (`skills/meta/do/SKILL.md` Phase 1: "Parallel
FIRST: 2+ failures / 3+ subtasks -> multiple Agent tools") before changing
the fan-out `Noul`'s instructions text, so the question asked matches what
`/do` actually means by fan-out-worthy.

**Known gap, not wired**: `scripts/build-dispatch.py`'s `--json` schema has
no dedicated fan-out/`agents` field — it dispatches exactly one agent per
call. This is not actually a `/d`-specific gap: `/do`'s own real multi-agent
mechanism is separate parallel `Agent` tool calls issued by the orchestrator
alongside the primary `build-dispatch.py` dispatch, not a `build-dispatch.py`
JSON field. `/d`'s Phase 4 reuses that same mechanism unmodified
(`skills/meta/d/SKILL.md` Phase 3/4) — `JEV_RESULT.agents` is a list to read
at that existing fan-out decision point, not a new contract to invent.

## Cookbook reuse and divergence

TypeSafe's `skill_suggestion` cookbook (`https://docs.typesafe.ai/cookbooks/skill_suggestion.md`)
is the source of the two-stage progressive-disclosure pattern adopted here.
Its own published benchmark (182 skills, 488 requests, `claude-haiku-4-5`):
suggestion-assisted selection cut wrong loads from 16.8% to 7.3% (2.3x fewer)
and needless loads from 9.8% to 4.0% (2.4x fewer), against an oracle floor of
2.5%/1.2%. **This is the cookbook's own benchmark, on its own single-pick
skill-selection task — not a `/d`-specific measurement.** `/d`'s own numbers
(this session's `scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT.md`)
are the ones that actually matter for `/d`'s promotion decision; cite the
cookbook figure only as the stated rationale for trying the pattern at all.

**Reused as-is**:
- The two-stage shape itself: cheap wide `Choice` rank over truncated
  descriptions, then a `Choice` + per-candidate `Noul` rerank over a
  shortlist with full descriptions.
- The gate-then-fits threshold pattern: a cheap up-front gate (mean of
  oriented `Noul`s) deciding whether to do the expensive pass at all, then a
  per-candidate `Noul` "does this genuinely fit" veto on the expensive
  pass's own pick. `/d`'s `GATE_THRESHOLD`/`FITS_THRESHOLD` defaults (0.30
  each) match the cookbook's own defaults.

**Deliberately diverged, and why**:
- **Multi-slot vs. single-pick.** The cookbook selects ONE skill suggestion.
  `/do`'s actual contract (`skills/meta/do/SKILL.md` COMBINATION DOCTRINE) is
  multi-slot: a primary agent plus an independent fan-out `agents` list, a
  primary skill plus an independent `stack` list, and one optional pipeline.
  `/d` runs the cookbook's single-pick shape three times over (once per
  single-select dimension: agent, skill, pipeline), not once.
- **Multi-select via independent Noul, not Choice.** The 5 stack signals and
  the fan-out candidates are "zero or more apply independently," not "pick
  one." A `Choice`'s `probabilities` are a distribution that sums to 1 across
  its options — the wrong shape for "any subset can be true at once." Each
  multi-select dimension is instead an independent per-candidate `Noul`,
  exactly as v1 already did for the 5 stack signals (that part of v1 was
  already right; v2 keeps it and extends the same pattern to fan-out).
- **Pipeline gets a 1-wide, not 3-wide, stage-2 shortlist.** The cookbook
  reranks a fixed top-3. `/d` only has ~29 pipeline candidates total (versus
  182 skills in the cookbook's benchmark), and pipeline is the rarest
  non-null pick across the corpus — a 1-wide "best real candidate vs. none"
  shortlist was judged precise enough without paying for 2 more Choice
  criteria entries and 2 more fit-`Noul`s on every non-trivial request. The
  stage-2 fits-check still always runs for whichever real candidate stage 1
  forwarded — never skipped, only narrower.
- **Complexity dropped as a question entirely** (see above) — the cookbook
  has no complexity-equivalent question to diverge from; this is a `/d`-side
  simplification enabled by already having gate_score, the final picks, and
  the stack signals to derive it from.

## Fallback-to-`/do` behavior

`fallback: true` on any of: `unavailable` (presence check failed), a
sub-`fits_threshold` or invalid-membership agent/skill pick (`source:
"low-confidence"`), or `error` (a stage-1 or stage-2 HTTP/parse/timeout
failure). In every case `/d`'s SKILL.md Phase 1F instructs reading
`skills/meta/do/SKILL.md` in full and running its Phase 1-4 unmodified — not
a degraded in-between state. `jev-trivial-bypass` is NOT a fallback signal —
it is a real terminal state handled by Phase 1T, distinct from Phase 1F.

Measured on `scripts/routing-ab-corpus.json` v1.5 (269 cases,
`scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT.md`): fallback
rate 26.0% (down from v1's 62.1% on the same corpus family, measured on
corpus v1.4) — still common, not a rare edge case, but the fits-threshold
redesign materially reduced how often it fires versus v1's flat confidence
floor.

## Confident-wrong risk (read before trusting this router with real traffic)

Unchanged conclusion from v1, restated because it still applies and the
redesign does not remove it: the fits-threshold catches an uncertain Jev
answer. It does NOT catch a systematically confident-but-wrong classifier —
that failure mode broke the rejected `tiered-v2` manifest experiment (3 new
safety-bucket misses, all confident or null, not low-confidence). The
fits-threshold is a per-request rejection trigger, a better one than v1's
flat confidence floor (it checks "does THIS specific candidate genuinely fit"
rather than "was the classifier confident in general"), but it is still a
**runtime** safety net, not a systematic-confident-wrong-classifier backstop.
That job still belongs to the eval gate: `scripts/routing-ab-corpus.json`'s
`SAFETY_BUCKETS` (`benchmark-force_route`, `false-positive-guard`,
`paraphrase-git`, `paraphrase-security`) are checked individually, per
bucket, before `/d` is trusted with real traffic — a confidently-wrong
pattern fails that gate outright, at any confidence or fits-score level.
`benchmark-force_route`/`paraphrase-git`/`paraphrase-security` are
additionally protected at runtime by construction: they're supposed to be
caught by `pre-route.py` before Jev is ever called (0 HTTP calls, 0 fits
checks in play). `false-positive-guard` has no such runtime backstop, in
`/d` or in `/do` — idiom traps (e.g. "fish out the bug") rely on semantic
judgment catching them, whether that judgment is `/do`'s self-route or
Jev's classification; neither router has a deterministic guard for this
bucket, an existing property of semantic routing generally, not something
`/d` introduced. The v2 redesign measured PASS on this gate (0
critical findings) on the same corpus that measured v1's PASS — the
redesign did not introduce a new safety regression, but it also did not, and
does not claim to, solve the underlying confident-wrong risk structurally.

## Hidden coupling (known limitation, unchanged by v2)

`jev-route.py`'s `instructions`/criteria strings across both stages are a
hand-written paraphrase of `/do`'s prose (Phase 1 Trivial table, Phase 2
SECTION-INTEGRITY/FORCE-ROUTE/SPECIFICITY/COMBINATION DOCTRINE/MULTI-AGENT
RULE, Phase 3 signal table). Nothing automatically keeps these in sync with
`/do`'s prose — if `/do`'s semantics change, `jev-route.py`'s instruction
strings must be updated by hand in the same change. No drift-detection CI
gate exists for this yet.

## Data egress

Stage 1 sends the raw request text and truncated agent/skill/pipeline
names+descriptions to `api.typesafe.ai`; stage 2 (when reached) sends the
request text again plus the shortlisted candidates' full descriptions. Same
kind of call as any other model API this toolkit already talks to. Force-
routed and trivial-bypassed requests send less (trivial: stage 1 only) or
nothing (force-route: Jev isn't called at all).
