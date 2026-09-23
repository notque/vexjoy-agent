---
name: building-with-jev
description: "Write, compose, integrate, and improve programs that call Jev, TypeSafe's System One judgment model."
user_invocable: false  # default -- router-dispatched, not user-typed
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
| fan-out, confidence gates, composite scores, taxonomy walks, cascades, second requests, long horizon, multi-step, agent loop, beam, branching, checkpoint | `references/composition-patterns.md` | Docs patterns plus ours, with script paths as worked examples |
| hooks, reader/storage/action, fail modes, persistence, calibration store | `references/integration-lifecycle.md` | Where a call lives and what happens when Jev is down |
| wrong answers, low confidence, clustered scores, revision discipline, known debt, baseline, OOD, holdout | `references/improve-and-calibrate.md` | Symptom table and labeled-example loop |
| dissolving a skill, replacing an LLM with Jev, three-tier classification | `references/dissolving-a-skill.md` | Method, phase table, worked example |
| decision surface, card, gate design, threshold, what numbers mean, failure behavior, versions | `references/decision-card.md` | Decision card template: fields every gate must define before code ships |
| position of a judgment, operand, gate, post-judge, selector, verifier, logical operators, dissolve a skill phase | `references/composition-positions.md` | 11 positions a judgment can occupy relative to a function, mapped to our scripts, with the walk-the-positions procedure |
| iteratively improve a skill, rubric, prompt, policy, or other artifact with broad Jev feedback | `references/iteration-with-jev.md` | Controlled A/B iteration, wide independent question batteries, variance checks, stopping rules, and avoiding optimization artifacts |
| model limitations, version changes, or a failure-mode audit | `references/question-design.md`, `references/state-and-budget.md`, `references/primitives.md`, `references/improve-and-calibrate.md` | Literal wording, arithmetic and dates, indirection, state filtering, hostile state, structural invariants, generation boundaries, and labeled retesting |

## Read the live docs

The TypeSafe docs are the source of truth for the API, SDKs, models, limits, and prices. Read them as part of the task; this skill carries our build procedure and measured lessons.

- Start at the [documentation index](https://docs.typesafe.ai/llms.txt). Append `.md` to a page path for Markdown.
- Read the jaggedness page for the exact model version you deploy. Pin that version; when it changes, reread the page and rerun the labeled set before reusing thresholds.
- Before you write an integration, read the [API page](https://docs.typesafe.ai/api.md), the page for each primitive you use, and the closest cookbook. A cookbook often shows a better decomposition than a plain classifier.
- The `typesafe:typesafe-ai` skill lists the design patterns the docs cover (route and fill arguments, select instead of generate, rerank, feature discovery, verify and escalate). Load it when you explore what to build.
- Treat thresholds and results in cookbooks as examples to test on your data.
- Read the documented rate limits on the models page, not just the request limits. On 2026-09-22 they were 64,000 tokens per request, 32,000 for state plus the longest question, **250,000 input tokens per second, and 1,200 requests per minute**, "subject to dynamic adjustment". `scripts/jev_limits.py` holds these numbers; update it when the page changes.

## Transports

A program reaches Jev through one of two transports. Use Vercel AI Gateway (`JEV_TRANSPORT=vercel`); the direct API is for measurement only. Benchmark and price on the transport production uses; their latencies and error codes differ.

| Transport | How | Errors to back off on | Notes |
|---|---|---|---|
| Direct API | `POST https://api.typesafe.ai/...` with `TYPESAFE_API_KEY`; `scripts/jev_router_common.py` | 429, 529 | Official SDKs retry with backoff by default. |
| Vercel AI Gateway | AI SDK `experimental_evaluate` with a plain model string, or `scripts/jev_vercel.py`; key is `AI_GATEWAY_API_KEY` (or OIDC on Vercel) | 429, **503**, 529 | The Gateway passes the payload to Jev verbatim. It reports upstream rate limiting or overload as HTTP 503 `GatewayInternalServerError` ("Service temporarily unavailable"), and it uses the same 503 for fast transient failures whose rate grew with tokens per request in our measurements (2026-09-22: ~1.6k tokens 0/8, ~3k 1/8, ~5k 3/8, ~13k 5/8, one request at a time). A 503 is a retry signal, not proof of an outage, a bad payload, or rate limiting; measure which before redesigning. The Gateway question type `"boolean"` is Noul. Read `providerMetadata.gateway.routing` on failures. |

Both transports share the same account-level rate limits. A direct-API probe that succeeds says nothing about the Gateway path, and the reverse; a direct-key 401/402 says nothing about a Gateway-routed app.

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

Build one Jev system at a time. A system is finished when it has labeled cases, a measured score, a measured cost per run, and an action that uses the answer. Start the next system after that.

Evidence of value is a labeled run. Unit tests with fake Jev answers show that the code runs; a labeled run shows that the grading is right.

| Step | Tier | Do | Exit gate |
|---|---|---|---|
| 1. State the decision | - | Write one sentence: the decision, the unit it applies to (a match, a diff hunk, a prompt), and the action code takes on each answer. | A person can label one unit by hand in under a minute. |
| 2. Build the grader | 1 | Collect human-confirmed labeled units `(x, y)` with label provenance. Freeze fixture copies and hash both fixtures and rubric. Split train/dev from an untouched group-disjoint heldout. Provisional or agent labels are diagnostics, never action-promoting ground truth. | `score(predictions)` runs on dev and prints the majority-class baseline; the heldout is sealed. |
| 3. Discover signals | 1 | Run SQL or Python over train. For every computable signal, record accuracy against `y`, count, and the same per slice. Start from existing analytics code. Keep every signal; the table decides. | A correlation table sorted by accuracy, with counts. |
| 4. Write the policy | 1 | Turn the table into rules: `rule(x) -> (action, sure)`. The strongest signal decides; a near-certain signal overrides. Score the rules on dev. | The rules and their dev score are row one of the run log. The residual (every unit where `sure` is false) is counted. |
| 5. Design the request | 1+2 | Build state for residual units only: correlated signals, bounded, labeled, arithmetic done in code, plus the rules' verdict and why it was unsure. Write one atomic question per judgment, worded from the table. Match the primitive to the action. Put every independent question about one state in one request. A question whose evidence/options depend on another answer is a second request after code builds the new state. | The decision card is filled in (`references/decision-card.md`). |
| 6. Price the run | 1 | Run the program on a ten-word input: the billed tokens are the fixed floor, your question text. Compute calls per run = units x calls per unit x rounds, tokens per call, tokens per run, referrals per run, and worst-case retry sends. Then price it per second: dump every request one run sends to JSON and run `python3 scripts/jev-budget-check.py --payload run.json --concurrency C --concurrent-runs N --attempts A`. Pick the request size with `python3 scripts/jev-size-probe.py --payload run.json` on the production transport. Price any eval the same way with `--eval-cases`. State all numbers. | The numbers are ones you would approve and the budget check says `ok`: peak tokens per second and requests per minute stay under 25% of the documented limits with retries and concurrent users counted. When the floor exceeds the typical state, shorten the questions first. When tokens per run exceed about 50,000, redesign as a cascade before tuning anything else. |
| 7. Smoke run | 2 | Run the three-unit set, then the dev sample. | `calls_failed` is zero, every answer parses, and `python3 scripts/jev-cost-report.py --since 1h` matches the step 6 estimate. |
| 8. Score | 1 | On the same dev set, report the rules alone, Jev on the residual, and the combined system, per slice, with Brier and a calibration curve. Count false positives beside recall. Run judge variance once over frozen rows. | The combined score and its cost per run are in the run log. |
| 9. Improve | 1+2 | First separate code errors and service failures (HTTP errors, timeouts) from wrong answers, by reading the exact state, questions, candidates, and answers of each miss. Then classify the wrong answers (`state_lacked_evidence`, `criteria_ambiguous`, `wrong_primitive`, `label_noise`). Change one state, instruction, criterion, or policy lever at a time. State changes must add needed decision evidence, not decorative context. Re-score. Keep the change when the combined score climbs and every slice holds. | Each variant is logged with score and cost. |
| 10. Report | 1 | Score the untouched heldout once after selection. Report p50/p95 wall time, accumulated model call time, throughput, and (when used) referral rate, marginal reviewer lift, cost, and time. Before later tuning, create a new independent heldout. | One heldout number and workload metrics, reported beside the dev number. |
| 11. Integrate | 1+2 | Ship an on-demand command with a reader, storage, and an action. Log whether each answer changed the action. Promote to a hook when four conditions hold: code decides the obvious cases first; the labeled set shows the answers are right; the answer distribution is meaningfully non-constant; something acts on the answer. Run a new hook in shadow mode first, and promote one hook at a time. | A day of use shows the cost report and the action-changed rate you expected. |
| 12. Next system | - | Start step 1 for the next decision. | - |

**Step 9 levers, in search order:** evidence in state; decomposition (one Score into several Nouls); criteria wording; thresholds; few-shot examples in state. Evidence comes first because the other levers work only on a signal that is present. Retune thresholds from stored probabilities, which costs zero calls. Derive a gate threshold from action costs, `t = C_FP / (C_FP + C_FN)`, select it on one split, and report on another.

**Cost model.** Cost = calls x input tokens per call. Input tokens = state + the text of every question, with its criteria and examples. Output is free. Parallel questions reduce wall time relative to serial sends but do not make question text free. Fill a request with independent heads only while each has decision/action value and the total fits its 64,000-token budget; sequence only a head whose evidence or candidates are derived from a prior answer. Measure wall time separately from accumulated model call time (the sum of attempt durations): concurrency can lower the former while leaving the latter high. Throughput is units or KB divided by the chosen clock; label the clock. Three numbers govern a run:

| Number | Target | Reach it by |
|---|---|---|
| Sends per state | one per run | one request per unit; stages as code thresholds; a second request only for new evidence |
| Fixed floor per call | below the typical state size | one- or two-line questions; `what`, `not_for`, and `examples` only where labeled misses call for them |
| Firing rate | matches how often the answer changes an action | on-demand commands first; hooks after step 11's conditions |
| Peak tokens per second | under 25% of the documented 250,000 (about 60,000), with retries and concurrent users counted | fewer tokens per run (a cascade instead of full detail for every unit); an instance-wide in-flight cap sized from the budget so simultaneous runs cannot burst together; jittered backoff for 429/529 |
| Tokens per answer, retries included | request size near the minimum of `size / success_rate(size)` on the production transport | measure the transient failure rate at several request sizes (`references/improve-and-calibrate.md`), then pack requests to that size |

**Per-request fit is not enough.** Every request can sit far under 64,000 tokens while one run still spends the whole per-second limit: 20 requests of 15,000 tokens sent together is 300,000 tokens in about a second. Retries then multiply it, because every failed request resends its full state. A design that works for one test query fails for real users, and an eval of 80 such runs spends millions of tokens in minutes. Price tokens per run and per second in step 6, not only tokens per request.

**Measure repeatability before iterating.** Run repeated frozen requests and measure answer variance and decision flips on the workload. Keep thresholds away from where answers cluster, and establish this noise floor before comparing variants. Treat cache behavior and circuit-breaker behavior as implementation details to verify in the current runner rather than performance guarantees.

**Telemetry is part of the system.** `call_jev` logs every call: script name, session id, input tokens, question count, payload hash, cached or not, error. An evidence-pipeline runner also persists the evidence-bundle ID/version, prompt/question version, model/version, attempt number, retry reason, deadline/cap, response, accounting, and final keep/refer/action outcome. Preserve source rows and provenance through joins: a relationship label is not permission to merge identities. Read the cost report after every multi-call run and compare it with the step 6 estimate.

**Graders see only what you send.** Send the richest available output and the evidence itself: command output, file content, stored answers. Tune on one label set and report on another.

**Action-changing gates stay conservative.** An unavailable, missing, or invalid Jev answer is `unknown`: exclude it from quality scores, retain its failure receipt, and never reinterpret it as `no`, pass, or permission to act. Keep any action-changing selector in shadow mode until human-confirmed, disjoint-heldout results show that its action improves the intended outcome. Confidence measures concentration, not authority: it cannot authorize an action or override source evidence, permissions, or deterministic safety rules. An evidence question needs a supplied source-evidence ledger; plausibility and apparent intent are not source evidence.

Sanity floors (majority class, the single strongest signal) prove the pipeline is wired. The bar is higher: the combined system climbs across iterations, calibration holds on the residual, and the test set agrees once. Spend scales with the residual, so a good policy keeps each round to hundreds of calls.

The grader decides how far the procedure goes. With outcomes that already happened (a result, a merged PR, a finished run), the loop runs unattended. With hand labels, it runs until the labels are used up; then the next step is more labels.

The same procedure replaces a skill: the skill's phases supply the signals and questions, its EVAL.md or hand labels are the grader, and the policy function replaces its gates (see "Dissolving a skill"). Systems compose: one system's decision is another's signal. Deterministic driver: `scripts/jev-harness.py` (`loop`, `variance`, `sweep`).

## Primitives

| Primitive | Ask when | Returns | Code acts with |
|---|---|---|---|
| Noul | clean yes/no; the probability is the signal | `noul` in [0, 1]; no `confidence` | `if noul > t` |
| Choice | one of a known unordered set | `choice`, `probabilities`, `confidence` | a branch per option |
| Score | a position on a spectrum you can describe in steps | `score`, `legend`, `probabilities`, `confidence` | threshold, rank, or round |

`score` is the probability-weighted mean of level numbers (0-based), not a picked level. A 1.0 can be certainty on level 1 or a 0/2 split; read `probabilities` when the distinction matters. Threshold, rank, or round it; never interpolate a quantity from it. A Noul at 0.5 means unsure, not "medium"; distance from 0.5 is its confidence. Do not carry a threshold tuned on one primitive to another, and do not expect `P(noul)` and `1 - P(not noul)` to agree. Full shapes: `references/primitives.md`.

`confidence` on a Choice or Score measures how concentrated the distribution is. It does not say the workflow is right, and it is not permission to act. Several acceptable options also spread probability, so low confidence on a harmless preference choice is fine. Set thresholds from your labeled data and the cost of each action.

## Question rules

- State the exact condition. Jev reads scoping words and negations literally. When you find yourself explaining what you meant after a miss, that explanation is the missing half of the instruction.
- One narrow, coherent judgment per question. Split dimensions that are useful on their own; keep together a relationship that is the thing being judged (does this reply answer this question). Atomic does not mean one sentence: a bounded action choice or a reading in context is one judgment. No double negatives, no multi-hop questions.
- The question ID is your key and is not sent to the model. Put the full meaning in `instructions`.
- When Jev selects from candidates that code produced, check coverage first: Jev cannot pick a value that is not in the list.
- Name the state path in backticks: `` `ticket.messages[0].text` ``.
- Criteria and instruction ask the same thing in the same direction. A Noul whose `true` side describes "no" degrades.
- Criteria encode the hard cases. Jev handles the obvious ones alone. `what`, `not_for`, `examples` per Choice option; `true`/`false` with `what` and `examples` for a subtle Noul.
- Score levels: 2 to 10, each a standalone situation, one dimension, no numerals and no "worse than the previous". Give a rare extreme its own level.
- Choice: add `other` or `none` when the list may not cover the input. Examples are concrete instances ("charged twice"), not descriptions of instances.
- Instructions accept a string or an object (`question`, `focus`, `inspect`, `note`, `compare`, `field`). Pass schemas and rows as JSON, never serialized into a string.
- Ask many specific questions, not one broad one. Put them in one call so the state is billed once. Every question's text is billed too: write each in one or two lines, and add `what`, `not_for`, and `examples` only where labeled misses show the question needs them.

## State rules

- State is evidence, not instructions. No coaching in state; rules go in `instructions` and `criteria`.
- Send only what the questions need. Irrelevant detail lowers accuracy and hides which input caused a miss.
- Bound every field with a named constant; keep the tail; note omitted characters; label sections (`[Request]`, `[Diff]`, `[Prior Assessment]`).
- Convert numbers to words or buckets. Compute dates, durations, counts, and sums in code. Jev does not count: one Noul per item, sum in code.
- A request holds 64,000 tokens: the state plus every question. The state plus the longest single question must stay under 32,000. The account also has a per-second limit (250,000 input tokens per second, 1,200 requests per minute on 2026-09-22) shared by every request, retry, user, and eval. Check the [models page](https://docs.typesafe.ai/models.md) for current limits. The state is billed again in every request, so fill each request with as many questions as fit before you start a second one. Fit state in stages. Every stage that calls Jev needs fitting, not just the first.
- Keep observed facts and inferred values in separate, labeled fields. Check that the state is still current before you act on an answer about it.
- Jev does not treat state as hostile. Text in state can steer answers. Apply `skills/shared-patterns/untrusted-content-handling.md`, name in criteria what counts, and run adversarial and self-describing test cases before deployment.

## Composition patterns

| Pattern | Shape | Worked example |
|---|---|---|
| Speculative fan-out | every branch's questions in one call, each stating its own premise ("if this is a refund request, ..."); heads are independent and cannot see one another's answers; code ignores unused heads and their uncertainty | `scripts/jev-browser-decide.py` |
| Confidence-gated routing | a floor below which nothing acts and a higher bar for high-stakes actions; paths act / confirm / hand off. Select both thresholds from labeled data and action costs | `scripts/jev-route.py` |
| Composite scoring | one Score per dimension, normalize by `len(criteria) - 1`, weights in code. Weighted sums suit preferences that offset one another; an "any serious violation" rule needs its own Noul per condition | `references/composition-patterns.md` |
| Intent routing | Choice for intent plus complexity Score, both confidence-gated | `scripts/jev-route.py` |
| Taxonomy walk | one Choice per level; each option's criteria is its trimmed subtree; follow several branches when close | `references/composition-patterns.md` |
| Multi-Noul decomposition | split a compound goal into one Noul per clause; combine in code | `references/composition-patterns.md` |
| Cascade plus verification | one wide request per unit; code thresholds pick survivors. Send a second request when the first answer is needed to fetch evidence, build new state, or decide the next options; it carries only what the first lacked | `references/composition-patterns.md` |
| Bounded residual review | Jev handles most units, a fixed-answer reviewer checks benchmarked referrals; runner sends the same source-bound bundle with immutable provenance; code accepts only the declared answer schema | `references/composition-patterns.md` |
| Deterministic pre-filter | programs decide the obvious ends; Jev judges the middle | `scripts/jev-compact.py` |
| History injection | recent actions as "already taken, do not repeat" | `scripts/jev-browser-agent.py` |
| Checkpoint search | caller sets subgoals a few steps apart; Jev beam-searches between them with progress-comparison Choices; LLM only on a near-tie, missing answer, or stalled subgoal; a small ledger replaces raw history | `scripts/jev_search.py` |

One screen each, with the code shape: `references/composition-patterns.md`.

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

## Dissolving a skill into a Jev program

A dissolution is the build procedure with the skill as the request. The method:

1. **List phases.** Read the skill's SKILL.md. Write each phase on one row.
2. **Classify each phase** into four columns: deterministic (program), judgment (Jev), generation (LLM), or orchestration (dispatch/coordination).
3. **Convert judgment phases.** Each judgment becomes one or more Jev questions: Noul for gates, Choice for classification/routing, Score for severity/quality. Write criteria for the hard cases.
4. **Keep deterministic phases in code.** Regex scans, file reads, grep, counts, averages, formatting stay as programs.
5. **Isolate generation.** If any phase requires new text (rewrite, diagnosis, plan), that phase keeps an LLM. The LLM receives all prior Jev decisions as `prior_results` and does not re-judge.
6. **Write the policy function.** A pure function `policy(assessment) -> action` with named thresholds is the dissolved skill's contract. It replaces the skill's gates.
7. **Prove agreement.** Run the Jev program on the skill's EVAL.md cases or hand-labeled examples. Match or exceed the skill's accuracy before deleting the SKILL.md.

**Worked example.** `references/dissolving-a-skill.md` walks one skill through the method: phase table, Jev question set, and policy function.

## Checklist

- [ ] This is the only Jev system under construction; the previous one has labeled cases, a score, a cost per run, and an action.
- [ ] The fixed floor, sends per state, and calls per run are measured; each state is sent once per run.
- [ ] The expected call count was computed before launch and matches the cost report after.
- [ ] `scripts/jev-budget-check.py` says `ok` for one run at the planned concurrency, attempts, and concurrent users, and any eval was priced with `--eval-cases` before it ran.
- [ ] A run over about 50 units or 50,000 tokens is a cascade: a cheap wide stage over every unit, full detail only for survivors.
- [ ] Independent requests in a stage are sent together, not in waves; an instance-wide in-flight cap derived from the per-second budget bounds simultaneous runs. Rate answers (429/529, repeated 503s) back off exponentially with jitter (base at least 0.5 s) and honor `Retry-After`; a lone fast Gateway 503 retries after about 100 ms. Every run has a retry budget.
- [ ] A deterministic policy over the signals is written and scored first; Jev receives the residual it leaves undecided.
- [ ] Each question asks one property a person could answer in a second.
- [ ] The primitive matches how code uses the answer.
- [ ] Instructions state the exact condition and name state paths in backticks.
- [ ] Criteria agree with the instruction and point the same way; hard cases are encoded.
- [ ] Score levels are standalone situations with no numerals; Choices that may not cover the input have `other`.
- [ ] Score uses a `criteria` list (2–10 level descriptions), never `min`/`max`. Choice uses a `criteria` map with `what`/`not_for`/`examples`.
- [ ] Code does all counting, arithmetic, and date comparison.
- [ ] State holds only what questions need, every field bounded by a named constant, sections labeled.
- [ ] Every stage that calls Jev fits state and batches questions; `calls_failed` is zero on a labeled run.
- [ ] All independent questions on one state travel in one request; serial dependencies are explicit second requests built by code.
- [ ] Responses are validated; a pure policy function decides; thresholds sit in the policy.
- [ ] Reader, storage, and action all exist; assessments persist with full distributions, prompt/model versions, attempts, and final actions.
- [ ] Entity or linkage systems preserve original rows and provenance; relationship labels and identity merges are separate actions.
- [ ] Workload reports distinguish wall time from accumulated model call time and label throughput's clock.
- [ ] Any non-Jev residual reviewer is fixed-answer, source-bound, capped, and justified by a held-out marginal benchmark.
- [ ] `score` is read as a weighted mean; code that rounds says so.
- [ ] Adversarial and self-describing inputs are in the test set.
- [ ] Labeled examples back every revision; the model version is pinned or the jaggedness page rechecked.
- [ ] Fixtures and rubrics are hashed; labels record human/provisional provenance, and provisional labels never promote an action.
- [ ] An untouched group-disjoint heldout is used once after selection; later tuning starts with a new independent heldout.
- [ ] Missing, invalid, and unavailable answers are stored as `unknown` with separate failure receipts, never scored as pass or no.
- [ ] Any action-changing selector remains shadow-only until human-confirmed, disjoint-heldout evidence shows the action is useful.
- [ ] Evidence questions receive an explicit source-evidence ledger; confidence cannot override evidence or permission constraints.
- [ ] Every script passes a validation probe: imports without error, `--help` exits 0, and a live call with representative input returns valid JSON with `source != "error"`.
- [ ] Hooks that grade agent output read the richest available text (task-notification result, not just the last assistant message).
- [ ] Hooks that check grounding receive verifiable evidence (stored Jev answers, tool output summaries), not just file paths.
- [ ] In development, run on a small representative sample before the full dataset. A bad question wastes every call.
- [ ] Read the cost report after every multi-call run. Investigate scripts with no successful calls, duplicate payload hashes, or any unexpected failures.

## Error handling

**Error: HTTP 422 on the request**
- Cause: wrong schema. Choice needs `criteria` as a map; Noul uses `criteria.true`/`criteria.false`; Score uses a `criteria` list. Keys such as `options`, `min`, `max` are not part of the API.
- Solution: match `references/primitives.md`; validate against the live API, not a mocked test.

**Error: `max_tokens_exceeded`, or a request that fails because it carries too much context**
- Cause: state plus questions exceed a limit at some stage. Through the Gateway this is the most common failure, and it recurs well below the documented 64,000 tokens: large requests fail while small ones return fine.
- Solution: check with a ~100-token request; if that returns, the cause is size. `jev_transport.evaluate` splits oversized requests into as many small ones as it takes, each with the same state; in other code, do the same with `jev_limits.split_and_run`. Shrink the state when it alone passes the target. Fit state in stages, cap items per call, and count failures per stage. See `references/state-and-budget.md` and fact 2 in the production rules.

**Error: HTTP 429 or 529 (direct), or 503 through Vercel AI Gateway**
- Cause: rate limit (tokens per second or requests per minute) or an overloaded service. Through the Gateway these arrive as 503 `GatewayInternalServerError`. The most common cause in our programs is the program itself: one run, or an eval of many runs, sending more tokens per second than the account allows, or requests large enough that transient failures are frequent (through the Gateway, the 503 rate grew with tokens per request).
- Solution: first price the run with `scripts/jev-budget-check.py`. If it is over 25% of a limit, fix the design (cascade, fewer tokens per run, a concurrency cap), not the retry loop. Then retry with exponential backoff and equal jitter (`jev_limits.backoff_delay`: base 0.5 s, doubling, capped, half random) so parallel requests that failed together do not retry together, and treat `Retry-After` as a floor. Cap attempts per request and retries per run; when the budget is spent, stop sending and return what finished. Persist every failed and retried attempt with its reason; retries count in workload cost and latency. Short fixed delays (100 ms, 200 ms) across many parallel requests make a retry storm that keeps the limit tripped.
- Diagnose before blaming the payload or the service: see "Service failure or wrong design" in `references/improve-and-calibrate.md`.

**Error: HTTP 401 or 402**
- Cause: bad key or exhausted credits. A retry never succeeds.
- Solution: the breaker in `call_jev` stops further sends. Code outside `call_jev` (a sandboxed plugin) stops after the first such status. Keep the API key on the server side; never ship it to a browser.

**Error: valid response, wrong decision**
- Cause: policy reads `score` as a level index or thresholds on the wrong primitive.
- Solution: read `probabilities`; keep thresholds in the policy; see the known-debt note in `references/improve-and-calibrate.md`.
