---
name: building-with-jev
description: "Write, compose, integrate, and improve programs that call Jev, TypeSafe's System One judgment model."
user-invocable: false  # default -- router-dispatched, not user-typed
routing:
  force_route: true
  triggers:
    - jev
    - typesafe
    - noul
    - choice question
    - score question
    - system one
    - write a jev question
    - jev answers wrong
    - low confidence
    - jev criteria
    - jev state
    - confidence threshold
    - dissolve skill
    - replace llm with jev
    - three tiers
  not_for: "Running the browser harness end to end (use browser-jev-automation) or routing a request (use do). This skill is for designing and fixing the Jev calls inside a program, and for dissolving skills into Jev programs."
  pairs_with:
    - browser-jev-automation
    - toolkit
    - do
  complexity: Complex
  category: meta
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep
---

# Building with Jev

Jev reads one `state`, answers every question in the request independently and in parallel, and returns a probability distribution over answers you defined. A head cannot read another head's answer: parallel heads share evidence, not reasoning. For one state, maximize independent heads that can change a decision or action, subject to their token cost and the 64,000-token request budget; omit noise heads. Code owns control flow, arithmetic, policy, and every serial dependency; Jev owns the snap judgment. It does not reason in steps, count, do arithmetic, or generate text. Use this skill to design the questions, fit the state, compose answers in code, wire the call into a hook or script, and fix a call that answers wrong.

**Before writing or changing any Jev request, apply [Jev production rules](../../shared-patterns/jev-production-lessons.md) and tick its pre-ship checklist.** It sets request size (2.5–4k tokens via Gateway until measured), per-run budget (~50k tokens), screen-then-detail above ~50 items, sending each stage at once with an instance cap of `floor(0.25 × 250,000 / tokens_per_request)`, retries by status code, eval pacing, caching, logging, and the order to measure failures. The rest of this skill is the method for designing questions; those rules govern how requests are sent. Its four facts come first: use Vercel AI Gateway; too much context is the most common failure, so split an oversized request into as many small requests as it takes (the toolkit transports do this automatically); a small request is the first diagnostic; rate limits are normal, so retry them.

Prefer direct judgments over supplied evidence. Bounded action selection is valid when candidates and decision evidence are supplied. If answering requires an intermediate result that changes later evidence or candidates, code must resolve that dependency before a later Jev request.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| request or response shape, instruction objects, criteria objects, reading `score`/`probabilities`/`confidence` | `references/primitives.md` | Full API shape and answer semantics |
| writing or rewriting instructions, criteria, levels, options, examples | `references/question-design.md` | Question rules with before/after pairs |
| `max_tokens_exceeded`, large inputs, batching, truncation, untrusted text in state | `references/state-and-budget.md` | Fitting stages, batching, bounds, adversarial state |
| any production Jev call: request size, run budget, parallelism, retries, caching, logging, failure diagnosis | `skills/shared-patterns/jev-production-lessons.md` | The concrete rules and checklist; read before shipping |
| 429, 529, Gateway 503, rate limits, tokens per second, concurrency, fan-out size, retries, eval pacing, "works locally but fails in production" | `references/state-and-budget.md` (Rate limits), `references/improve-and-calibrate.md` (Service failure or wrong design) | Per-second pricing, pacing, backoff numbers, and the diagnosis order |
| model alias, `jev-latest`, `jev-preview`, pin a version, deprecation, long context, status codes, retry headers, SDK, official TypeSafe skill | `references/models-and-limits.md` | Aliases, limits, danger-zone headers, errors, retry rules |
| quality or taste goal, hill-climb, Score ladder, before/after rounds, keep/revert, reference anchors, reporting `confidence` or split probabilities | `references/hill-climbing.md` | Owner's hill-climbing method and how to read confidence |
| cookbook technique: beam search, parent fallback, uncertain band, rerank, guardrails, memory gate, entity match, feature discovery, argmax, smoothing | `references/cookbook-techniques.md` | One row per documented technique, with the shape and the numbers |
| fan-out, confidence gates, composite scores, taxonomy walks, cascades, second requests, long horizon, multi-step, agent loop, beam, branching, checkpoint | `references/composition-patterns.md` | Docs patterns plus ours, with script paths as worked examples |
| hooks, reader/storage/action, fail modes, persistence, calibration store | `references/integration-lifecycle.md` | Where a call lives and what happens when Jev is down |
| wrong answers, low confidence, clustered scores, revision discipline, known debt, baseline, OOD, holdout | `references/improve-and-calibrate.md` | Symptom table and labeled-example loop |
| dissolving a skill, replacing an LLM with Jev, three-tier classification | `references/dissolving-a-skill.md` | Method, phase table, worked example |
| decision surface, card, gate design, threshold, what numbers mean, failure behavior, versions | `references/decision-card.md` | Decision card template: fields every gate must define before code ships |
| position of a judgment, operand, gate, post-judge, selector, verifier, logical operators, dissolve a skill phase | `references/composition-positions.md` | 11 positions a judgment can occupy relative to a function, mapped to our scripts, with the walk-the-positions procedure |
| image, screenshot, rendered frame, reference picture, Box question, `JevImage` | `references/images.md` | Send images through the transport: limits, preparation, token cost, visual hill-climb anchors |
| game review, improve a game, per-screen questions, question bank, fun, juice, clarity, flow, session review | `references/game-review-questions.md` | About 60 Noul, Score, and Choice questions per screen, action, flow, and session, with the code checks to run beside them |
| iteratively improve a skill, rubric, prompt, policy, or other artifact with broad Jev feedback | `references/iteration-with-jev.md` | Controlled A/B iteration, wide independent question batteries, variance checks, stopping rules, and avoiding optimization artifacts |
| model limitations, version changes, or a failure-mode audit | `references/question-design.md`, `references/state-and-budget.md`, `references/primitives.md`, `references/improve-and-calibrate.md` | Literal wording, arithmetic and dates, indirection, state filtering, hostile state, structural invariants, generation boundaries, and labeled retesting |
| Jev loop mechanics, Score ladders, answer reading, `evaluate_packed` | `references/jev-loop-mechanics.md` | 9-step Jev development loop, honest answer reading, and transport mechanics |
| 12-step build procedure, fallback/second-opinion modes, escalation, dissolving a skill | `references/build-and-escalation.md` | End-to-end build gates, cost model, alt-model fallback, uncertainty escalation, skill dissolution |
| pre-ship checklist, HTTP 422/429/529/503/401/402 error recovery | `references/checklist-and-errors.md` | Full pre-ship checklist and failure diagnosis/recovery steps |

## Read the live docs

The TypeSafe docs are the source of truth for the API, SDKs, models, limits, and prices. Read them as part of the task; this skill carries our build procedure and measured lessons.

- Start at the [documentation index](https://docs.typesafe.ai/llms.txt). Append `.md` to a page path for Markdown.
- Read the jaggedness page for the exact model version you deploy. Pin that version; when it changes, reread the page and rerun the labeled set before reusing thresholds. `jev-latest` is an alias that moves between versions (TypeSafe said it would reach 1.14.0 about a week after the 2026-10-14 release), so this toolkit pins `jev-1.14.0` and never sends the alias; `jev-preview` moves first (`references/models-and-limits.md`).
- Before you write an integration, read the [API page](https://docs.typesafe.ai/api.md), the page for each primitive you use, and the closest cookbook. A cookbook often shows a better decomposition than a plain classifier (`references/cookbook-techniques.md`).
- TypeSafe's own agent skill (`typesafe-ai`; install with `claude plugin marketplace add typesafe-ai/skills` then `claude plugin install typesafe@typesafe-ai`) is the better source for API shapes, the pattern catalog (route and fill arguments, select instead of generate, rerank, feature discovery, verify and escalate), and what to build. Load it when you explore a design or write against the API. Use this skill for the build procedure, the labeled run, per-second budgeting, Gateway sizing, shadow mode, and our scripts. Where they differ on request size or transport, our measured rules win; on API or pattern facts, the docs win.
- Treat thresholds and results in cookbooks as examples to test on your data.
- Rate limits are per organization and shown in the developer console; the models page no longer prints numbers. Our planning constants (`scripts/jev_limits.py`: 64,000 tokens per request, 32,000 for state plus the longest question, 250,000 input tokens per second, 1,200 requests per minute) are the 2026-09-22 reading. Update them when the console says otherwise.
- Images, Box, and long context are "danger zone" (dreamer-ready) features behind request headers. TypeSafe does not vouch for them in production, and says every model is worse on images than on text: split image questions into the simplest parts. Never make one the only deploy gate.

## Transports

A program reaches Jev through one of two transports. Use Vercel AI Gateway (`JEV_TRANSPORT=vercel`); the direct API is for measurement only. Benchmark and price on the transport production uses; their latencies and error codes differ.

| Transport | How | Errors to back off on | Notes |
|---|---|---|---|
| Direct API | `POST https://api.typesafe.ai/...` with `TYPESAFE_API_KEY`; `scripts/jev_router_common.py` | 429, 529 | Official SDKs retry with backoff by default. |
| Vercel AI Gateway | AI SDK `experimental_evaluate` with a plain model string, or `scripts/jev_vercel.py`; key is `AI_GATEWAY_API_KEY` (or OIDC on Vercel) | 429, **503**, 529 | The Gateway passes the payload to Jev verbatim. It reports upstream rate limiting or overload as HTTP 503 `GatewayInternalServerError` ("Service temporarily unavailable"), and it uses the same 503 for fast transient failures whose rate grew with tokens per request in our measurements (2026-09-22: ~1.6k tokens 0/8, ~3k 1/8, ~5k 3/8, ~13k 5/8, one request at a time). A 503 is a retry signal, not proof of an outage, a bad payload, or rate limiting; measure which before redesigning. The Gateway question type `"boolean"` is Noul. Read `providerMetadata.gateway.routing` on failures. |

Both transports share the same account-level rate limits. A direct-API probe that succeeds says nothing about the Gateway path, and the reverse; a direct-key 401/402 says nothing about a Gateway-routed app.

## Fallback and second-opinion modes

Plain `evaluate`/`evaluate_packed` raises `JevTransportError` with no alt model. Opt into `jev_transport.evaluate_with_fallback(...)` or `jev_transport.evaluate_second_opinion(...)` only when needed; load `references/build-and-escalation.md` for return shapes, provenance rules, and constraints.

## The three tiers

Three things run this toolkit: deterministic programs, Jev, and LLMs. Apply the lowest tier that can do the job.

| Tier | When | Examples |
|---|---|---|
| 1. Program | The answer is computable | search, parse, count, diff, validate, run a command, regex, build, test |
| 2. Jev | The answer is a judgment over evidence in hand | classify, gate, score, triage, verify, choose from a fixed set, decide to escalate |
| 3. LLM | The output is a new artifact | write code, draft prose, produce a plan, diagnose a novel problem, synthesize across sources |

An LLM call in a hook, gate, router, or review is a defect unless the output is generative. A Score, a Choice, or a yes/no decision is never generative. The narrow exception is a bounded review of Jev-referred residuals: the reviewer receives a frozen, source-bound evidence bundle and returns a fixed answer, never new prose or a replacement pipeline. Use it only when a held-out benchmark shows its marginal quality lift justifies its referral rate, marginal cost, and added wall time. When you catch an LLM doing a job Jev can do, replace it.

Jev bills input tokens: the state plus the full text of every question. Output is free. Questions in one request run concurrently, so batching avoids serial call latency, but every question still consumes tokens and shared request budget. Measure actual p50/p95 wall time and accumulated model call time on the workload; do not rely on a universal latency promise. An LLM costs far more per call, takes seconds, and can rationalize a wrong answer. The toolkit metric is **LLM calls per request**; Jev programs exist to drive it toward zero, with benchmarked residual review as the stated exception.

Programs produce the evidence. Jev judges it. The LLM acts on those judgments creatively, receiving tier 1 and 2 findings as `prior_results`, not re-judging them. The only exception is the bounded residual-review stage above. When all phases of a skill are tier 1 and 2, the skill dissolves into a Jev program and no LLM runs at all.

Tier 1 goes first on every unit; tier 2 receives the residual tier 1 leaves undecided. That is what "program first" means in practice: a rule the data supports is written in code and scored before any question is written.

## Pick the shape

Name the shape of the problem first. The shape decides what code does, what Jev does, and how many requests a run costs.

| Shape | Signs | Build |
|---|---|---|
| Decide from history | labeled outcomes exist; signals are computable from data | Code builds a correlation table and writes rules for the sure units. Jev judges the residual the rules leave undecided. |
| One document, many properties | review a file, grade a draft, check a diff | One request per document: the state once, every independent, action-changing question once. Stages are code thresholds over that one answer set. A second request carries only evidence the first lacked. |
| Pick from known options | route a request, classify an error, choose a template | Code produces the candidates. A cheap wide Choice ranks them; a second Choice reranks the shortlist with full detail; a confidence gate decides act, confirm, or hand off. |
| Many items, same question | rank comments, filter tool results, triage files | Code decides the obvious ends. The middle goes in one request as short per-item Nouls. Code counts and sums. Past about 50 items, or when one run would spend more than about 50,000 tokens, build a cascade instead: stage 1 asks one short fit Noul per item over compact state; stage 2 asks the full question set for the top survivors only. Do not fan the full question set out over every item in parallel. |
| Event stream | something to check on every tool call, reply, or commit | Build it as an on-demand command. Promote it to a hook after the four conditions in step 11. |
| Select, then copy | extract a value, pick a source span, recover structure | Code finds the candidate values or spans. Jev selects the intended one. Code copies or normalizes it. No text is generated. |
| New text needed | write, rewrite, plan, diagnose | First check whether "Select, then copy" fits. When it does not, an LLM writes. Jev grades the result against a rubric that has its own labeled set. |

## Build procedure

Build one Jev system at a time: labeled cases, deterministic rules first, Jev on the undecided residual, budgeted per-second pricing (`scripts/jev-budget-check.py`), heldout verification, and shadow-first hook integration. Load `references/build-and-escalation.md` for the full 12-step table, Step 9 levers, cost model, and `scripts/jev-harness.py` workflow.

## Primitives

| Primitive | Ask when | Returns | Code acts with |
|---|---|---|---|
| Noul | clean yes/no; the probability is the signal | `noul` in [0, 1]; no `confidence` | `if noul > t` |
| Choice | one of a known unordered set | `choice`, `probabilities`, `confidence` | a branch per option |
| Score | a position on a spectrum you can describe in steps | `score`, `legend`, `probabilities`, `confidence` | threshold, rank, or round |

`score` is the probability-weighted mean of level numbers (0-based), not a picked level. A 1.0 can be certainty on level 1 or a 0/2 split; read `probabilities` when the distinction matters. Threshold, rank, or round it; never interpolate a quantity from it. A Noul at 0.5 means unsure, not "medium"; distance from 0.5 is its confidence. Do not carry a threshold tuned on one primitive to another, and do not expect `P(noul)` and `1 - P(not noul)` to agree. Full shapes: `references/primitives.md`.

`confidence` on a Choice or Score measures how concentrated the distribution is. It does not say the workflow is right, and it is not permission to act. Several acceptable options also spread probability, so low confidence on a harmless preference choice is fine. Set thresholds from your labeled data and the cost of each action. A Score's confidence is ordinal (adjacent levels split costs less than opposite ends); a Choice's is not. For a Choice, also try the top probability and the top-to-second ratio. Exact formulas: `references/primitives.md`. When you only need the best option, take `choice`: do not gate every answer on confidence.

## Images

When the goal is visual (a render, a screenshot, a frame, a reference picture), send the picture. A text description lets Jev judge the description. Describe pixels in text only when no image exists, and always add the measured numbers beside the image. Images are dreamer-ready: use them to steer hill-climbs and reviews, never as the only deploy gate. API, limits, routing, and token cost: `references/images.md`.

| Put the image in | When | Example |
|---|---|---|
| `state` | Several questions judge the same picture. It is billed once per request. | The candidate render, the rated reference. |
| `instructions` | One question needs it. Only that question pays. | "Does `candidate` match this picture: `{img:ref}`?" |
| `criteria` | An answer is defined by example pictures. | Choice options, Score levels, or Noul `true`/`false` each carrying a `JevImage` example. |

- **Box** (`"type": "box"`) returns where a target is, as `top`, `bottom`, `left`, `right` fractions of the image. It always returns a box, so ask a Noul "is it visible?" beside it and read `confidence`.
- One trait per question, as for text. Add a separate "anything worse?" Noul.
- Each use of an image bills its tokens again (about 1 per 390 px). Put a shared image in state, not in every question.
- Skills with their own image section: `jev-design` (review renders), `browser-jev-automation` (locate with Box), `grill-jev` (visual plans).

## Question rules

- State the exact condition. Jev reads scoping words and negations literally. When you find yourself explaining what you meant after a miss, that explanation is the missing half of the instruction.
- One narrow, coherent judgment per question. Split dimensions that are useful on their own; keep together a relationship that is the thing being judged (does this reply answer this question). Atomic does not mean one sentence: a bounded action choice or a reading in context is one judgment. No double negatives, no multi-hop questions.
- The question ID is your key and is not sent to the model. Put the full meaning in `instructions`.
- When Jev selects from candidates that code produced, check coverage first: Jev cannot pick a value that is not in the list.
- Name the state path in backticks: `` `ticket.messages[0].text` ``.
- Criteria and instruction ask the same thing in the same direction. A Noul whose `true` side describes "no" degrades.
- Criteria encode the hard cases. Jev handles the obvious ones alone. `what`, `not_for`, `examples` per Choice option; `true`/`false` with `what` and `examples` for a subtle Noul.
- Score levels: 2 to 10, each a standalone situation, one dimension, no numerals and no "worse than the previous". Give a rare extreme its own level.
- "Which one" is a Choice over the candidates with a `none` option, not a Noul per candidate. Read a printed value with a Choice over its possible values; never ask Jev to count (`references/question-design.md`).
- A Choice leans to its first option on some inputs: for a high-stakes pick, compare the answer with the options reordered. Give the whole legitimate option list (up to 255) and let code remove illegal options first.
- Phrase a Noul so a high value means yes. Take the argmax of `probabilities` as the decision; do not sample.
- Choice: add `other` or `none` when the list may not cover the input. Examples are concrete instances ("charged twice"), not descriptions of instances.
- Instructions accept a string or an object (`question`, `focus`, `inspect`, `note`, `compare`, `field`). Pass schemas and rows as JSON, never serialized into a string.
- Ask many specific questions, not one broad one. Put them in one call so the state is billed once. Every question's text is billed too: write each in one or two lines, and add `what`, `not_for`, and `examples` only where labeled misses show the question needs them.

## State rules

- State is evidence, not instructions. No coaching in state; rules go in `instructions` and `criteria`.
- Send only what the questions need. Irrelevant detail lowers accuracy and hides which input caused a miss.
- Bound every field with a named constant; keep the tail; note omitted characters; label sections (`[Request]`, `[Diff]`, `[Prior Assessment]`).
- For visual evidence, put the image in state (see Images). Do not replace a rendered output with a description of it.
- Convert numbers to words or buckets. Compute dates, durations, counts, and sums in code. Jev does not count: one Noul per item, sum in code.
- A request holds 64,000 tokens: the state plus every question. The state plus the longest single question must stay under 32,000. The account also has a per-second limit (250,000 input tokens per second, 1,200 requests per minute on 2026-09-22; the console holds the current numbers) shared by every request, retry, user, and eval. The state is billed again in every request, so fill each request with as many questions as fit before you start a second one. Fit state in stages. Every stage that calls Jev needs fitting, not just the first.
- Give as much structured context as you can, not one signal alone (TypeSafe engineer): when a picture is part of the evidence, send the structured state JSON beside it, such as measured numbers, element tables, and field legends.
- Name fields so they explain themselves; add a one-line legend for any opaque field (`hud.slots`: item counts in the toolbar, left to right). For a state that changes between reads, averaging a Choice's probabilities over about three reads can steady the pick (`references/cookbook-techniques.md`).
- Keep observed facts and inferred values in separate, labeled fields. Check that the state is still current before you act on an answer about it.
- Jev does not treat state as hostile. Text in state can steer answers. Apply `skills/shared-patterns/untrusted-content-handling.md`, name in criteria what counts, and run adversarial and self-describing test cases before deployment.

## Composition patterns

| Pattern | Shape | Worked example |
|---|---|---|
| Speculative fan-out | every branch's questions in one call, each stating its own premise ("if this is a refund request, ..."); heads are independent and cannot see one another's answers; code ignores unused heads and their uncertainty | `scripts/jev-browser-decide.py` |
| Confidence-gated routing | a floor below which nothing acts and a higher bar for high-stakes actions; paths act / confirm / hand off. Select both thresholds from labeled data and action costs | `scripts/jev-route.py` |
| Composite scoring | one Score per dimension, normalize by `len(criteria) - 1`, weights in code. Weighted sums suit preferences that offset one another; an "any serious violation" rule needs its own Noul per condition | `references/composition-patterns.md` |
| Domain attachment | one Noul per domain, attach above a 0.6 floor, code caps the count; Jev supplies evidence, code decides | `scripts/jev-route.py` |
| Taxonomy walk | one Choice per level; each option's criteria is its trimmed subtree; follow several branches when close | `references/composition-patterns.md` |
| Multi-Noul decomposition | split a compound goal into one Noul per clause; combine in code | `references/composition-patterns.md` |
| Cascade plus verification | one wide request per unit; code thresholds pick survivors. Send a second request when the first answer is needed to fetch evidence, build new state, or decide the next options; it carries only what the first lacked | `references/composition-patterns.md` |
| Bounded residual review | Jev handles most units, a fixed-answer reviewer checks benchmarked referrals; runner sends the same source-bound bundle with immutable provenance; code accepts only the declared answer schema | `references/composition-patterns.md` |
| Deterministic pre-filter | programs decide the obvious ends; Jev judges the middle | `scripts/jev-compact.py` |
| History injection | recent actions as "already taken, do not repeat" | `scripts/jev-browser-agent.py` |
| Beam over Choices | keep the best `K` paths by `prod(edge_p) ** (1 / decisions)`; one more question per path in the same request | `references/cookbook-techniques.md` |
| Parent fallback | below a confidence cutoff, report the broader parent label; no second call | `references/cookbook-techniques.md` |
| Uncertain band | a top probability under a cutoff (or a Noul in 0.30 to 0.70) becomes `uncertain` and goes to a person | `references/cookbook-techniques.md` |
| Checkpoint search | caller sets subgoals a few steps apart; Jev beam-searches between them with progress-comparison Choices; LLM only on a near-tie, missing answer, or stalled subgoal; a small ledger replaces raw history | `scripts/jev_search.py` |

One screen each, with the code shape: `references/composition-patterns.md`.

## Escalate when Jev is unsure

When a Noul sits in 0.4–0.6 or a Choice/Score is split, run one sharpening pass (split question, add evidence, tighten criteria) and check Choice margin via `scripts/jev_choice.py`; if still flat on a consequential decision, escalate once to a stronger model on the same frozen evidence (`references/build-and-escalation.md`).

## Integration lifecycle

Start every program as an on-demand command. Promote it to a hook after it meets the four conditions in step 11 of the build procedure. Promote one hook at a time and read the cost report after a day of use.

Every integration has a reader (runs Jev), storage (findings persist somewhere read), and an action (something changes behavior). Missing any part wastes the call. Thread prior assessments into later calls as bounded, labeled evidence. Fail open for advisory checks; fail to warn for safety checks; never fail to block when Jev is unavailable. Validate every response with `validate_jev_response` before acting. Details: `references/integration-lifecycle.md`.

## Improve a program

This is step 9 of the build procedure. Find the failing question on labeled data before changing anything.

**Promote lessons deliberately.** Experimental Jevmaxxing is hypothesis discovery, not guidance. Add a durable rule only when it has a clear mechanism, representative labeled evidence, a stated boundary or counterexample, and a measured improvement to an action, cost, or quality decision against a baseline. Otherwise leave the observation out; prune copied lore that cannot meet this standard.

| Symptom | Likely cause | Fix |
|---|---|---|
| Wrong with high confidence | literal reading | state the exact condition; put the boundary case in criteria |
| Low-confidence Choice | options overlap or none fits | add `what`, `not_for`, `examples`; add `other` |
| Low-confidence Score | levels overlap, two dimensions, thin state | rewrite levels as situations; split; add the missing field |
| Scores cluster mid-scale | levels are degrees or numerals | describe a situation per level; drop numerals |
| Extremes look alike | no level for the extreme | add one |
| Noul near 0.5 | vague condition | define it; add `true`/`false` examples |
| Accuracy falls with input size | irrelevant state | filter in code; send fields, not blobs |
| Count, sum, date errors | Jev doing arithmetic | move it to code; per-item Nouls |
| Nested or negated questions fail | indirection | ask directly; split into two literal questions |
| Answer follows text in state | state steering | separate trusted policy from untrusted text; require source evidence in code; adversarial tests; thresholds may abstain or refer, not authorize |
| Rewording trades one error for another | one question, several properties | split into atomic questions |
| Answers right, decision wrong | policy | change weights or thresholds in code, not questions |
| Slow or costly | sequential calls | merge into one request |
| One query works; real use or an eval fails with 429/529/503 | one run spends too much of the per-second limit; retries multiply it | price with `jev-budget-check.py`; cascade; cap concurrency; jittered backoff |

Operational rules:

- Store every answer's probabilities with the payload hash; retune thresholds from stored answers, which costs zero calls.
- Measure judge variance over frozen rows before trusting a judge; gate only on a judge whose answers hold steady between runs.
- Derive a gate threshold from action costs `t = C_FP/(C_FP+C_FN)`, select on one split, report on another, re-measure when the data shifts.
- Run a new gate in shadow mode (log the action it would take) until replayed fixtures pass, then enforce.
- Let a domain rule veto an action regardless of model confidence (permit != confidence).
- Grant "done" only to a post-execution probe (test, build, exit code); the probe result is what decides.

Rules: change one or two questions per revision; judge on labeled data, not confidence alone; keep the answer space stable once code depends on it; general rules in criteria, specific names only in `examples`. Full table and the known-debt note: `references/improve-and-calibrate.md`.

## Dissolving a skill, pre-ship checklist, and error handling

- **Dissolving a skill into a Jev program:** classify phases (program, Jev, LLM, orchestration), isolate generation behind `prior_results`, write a pure `policy(assessment) -> action`, and match accuracy on labeled examples (`references/build-and-escalation.md` and `references/dissolving-a-skill.md`).
- **Pre-ship checklist & HTTP 422 / 429 / 529 / 503 / 401 / 402 recovery:** load `references/checklist-and-errors.md` before shipping or debugging API failures.
