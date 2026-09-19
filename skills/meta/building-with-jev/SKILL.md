---
name: building-with-jev
description: "Write, compose, integrate, and improve programs that call Jev, TypeSafe's System One judgment model."
user_invocable: false  # default -- router-dispatched, not user-typed
routing:
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
    - skill-creator
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

Jev reads one `state`, answers every question in the request independently and in parallel, and returns a probability distribution over answers you defined. It does not reason in steps, count, do arithmetic, or generate text. Code owns control flow, arithmetic, and policy; Jev owns the snap judgment. Use this skill to design the questions, fit the state, compose answers in code, wire the call into a hook or script, and fix a call that answers wrong.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| request or response shape, instruction objects, criteria objects, reading `score`/`probabilities`/`confidence` | `references/primitives.md` | Full API shape and answer semantics |
| writing or rewriting instructions, criteria, levels, options, examples | `references/question-design.md` | Question rules with before/after pairs |
| `max_tokens_exceeded`, large inputs, batching, truncation, untrusted text in state | `references/state-and-budget.md` | Fitting stages, batching, bounds, adversarial state |
| fan-out, confidence gates, composite scores, taxonomy walks, cascades, second requests | `references/composition-patterns.md` | Docs patterns plus ours, with script paths as worked examples |
| hooks, reader/storage/action, fail modes, persistence, calibration store | `references/integration-lifecycle.md` | Where a call lives and what happens when Jev is down |
| wrong answers, low confidence, clustered scores, revision discipline, known debt | `references/improve-and-calibrate.md` | Symptom table and labeled-example loop |
| dissolving a skill, replacing an LLM with Jev, three-tier classification | `references/dissolving-a-skill.md` | Method, phase table, worked example |
| the number behind a rule | `references/lessons-with-numbers.md` | Each rule with the measurement that supports it |
| decision surface, card, gate design, threshold, what numbers mean, failure behavior, versions | `references/decision-card.md` | Decision card template: fields every gate must define before code ships |
| position of a judgment, operand, gate, post-judge, selector, verifier, logical operators, dissolve a skill phase | `references/composition-positions.md` | 11 positions a judgment can occupy relative to a function, mapped to our scripts, with the walk-the-positions procedure |

## Read the live docs

The TypeSafe docs are the source of truth for the API, SDKs, models, limits, and prices. Read them as part of the task; this skill carries our build procedure and measured lessons.

- Start at the [documentation index](https://docs.typesafe.ai/llms.txt). Append `.md` to a page path for Markdown.
- Before you write an integration, read the [API page](https://docs.typesafe.ai/api.md), the page for each primitive you use, and the closest cookbook. A cookbook often shows a better decomposition than a plain classifier.
- The `typesafe:typesafe-ai` skill lists the design patterns the docs cover (route and fill arguments, select instead of generate, rerank, feature discovery, verify and escalate). Load it when you explore what to build.
- Treat thresholds and results in cookbooks as examples to test on your data.

## The three tiers

Three things run this toolkit: deterministic programs, Jev, and LLMs. Apply the lowest tier that can do the job.

| Tier | When | Examples |
|---|---|---|
| 1. Program | The answer is computable | search, parse, count, diff, validate, run a command, regex, build, test |
| 2. Jev | The answer is a judgment over evidence in hand | classify, gate, score, triage, verify, choose from a fixed set, decide to escalate |
| 3. LLM | The output is a new artifact | write code, draft prose, produce a plan, diagnose a novel problem, synthesize across sources |

An LLM call in a hook, gate, router, or review is a defect unless the output is generative. A Score, a Choice, or a yes/no decision is never generative. When you catch an LLM doing a job Jev can do, replace it.

Jev bills input tokens: the state plus the full text of every question. Output is free. One call is cheap and returns in under 200 ms; the bill comes from call count times tokens per call, so measure both (see "Build procedure"). An LLM costs far more per call, takes seconds, and can rationalize a wrong answer. The toolkit metric is **LLM calls per request**; Jev programs exist to drive it toward zero.

Programs produce the evidence. Jev judges it. The LLM acts on those judgments creatively, receiving tier 1 and 2 findings as `prior_results`, not re-judging them. When all phases of a skill are tier 1 and 2, the skill dissolves into a Jev program and no LLM runs at all.

Tier 1 goes first on every unit; tier 2 receives the residual tier 1 leaves undecided. That is what "program first" means in practice: a rule the data supports is written in code and scored before any question is written.

## Pick the shape

Name the shape of the problem first. The shape decides what code does, what Jev does, and how many requests a run costs.

| Shape | Signs | Build |
|---|---|---|
| Decide from history | labeled outcomes exist; signals are computable from data | Code builds a correlation table and writes rules for the sure units. Jev judges the residual the rules leave undecided. |
| One document, many properties | review a file, grade a draft, check a diff | One request per document: the state once, every question once. Stages are code thresholds over that one answer set. A second request carries only evidence the first lacked. |
| Pick from known options | route a request, classify an error, choose a template | Code produces the candidates. A cheap wide Choice ranks them; a second Choice reranks the shortlist with full detail; a confidence gate decides act, confirm, or hand off. |
| Many items, same question | rank comments, filter tool results, triage files | Code decides the obvious ends. The middle goes in one request as short per-item Nouls. Code counts and sums. |
| Event stream | something to check on every tool call, reply, or commit | Build it as an on-demand command. Promote it to a hook after the four conditions in step 11. |
| Select, then copy | extract a value, pick a source span, recover structure | Code finds the candidate values or spans. Jev selects the intended one. Code copies or normalizes it. No text is generated. |
| New text needed | write, rewrite, plan, diagnose | First check whether "Select, then copy" fits. When it does not, an LLM writes. Jev grades the result against a rubric that has its own labeled set. |

## Build procedure

Build one Jev system at a time. A system is finished when it has labeled cases, a measured score, a measured cost per run, and an action that uses the answer. Start the next system after that.

Evidence of value is a labeled run. Unit tests with fake Jev answers show that the code runs; a labeled run shows that the grading is right.

| Step | Tier | Do | Exit gate |
|---|---|---|---|
| 1. State the decision | - | Write one sentence: the decision, the unit it applies to (a match, a diff hunk, a prompt), and the action code takes on each answer. | A person can label one unit by hand in under a minute. |
| 2. Build the grader | 1 | Collect labeled units `(x, y)`. Split train, dev, and test, by time when time exists. Freeze the inputs as fixture copies. Cut a three-unit smoke set and a dev sample of about 100. | `score(predictions)` runs on dev and prints the majority-class baseline. |
| 3. Discover signals | 1 | Run SQL or Python over train. For every computable signal, record accuracy against `y`, count, and the same per slice. Start from existing analytics code. Keep every signal; the table decides. | A correlation table sorted by accuracy, with counts. |
| 4. Write the policy | 1 | Turn the table into rules: `rule(x) -> (action, sure)`. The strongest signal decides; a near-certain signal overrides. Score the rules on dev. | The rules and their dev score are row one of the run log. The residual (every unit where `sure` is false) is counted. |
| 5. Design the request | 1+2 | Build state for residual units only: correlated signals, bounded, labeled, arithmetic done in code, plus the rules' verdict and why it was unsure. Write one atomic question per judgment, worded from the table. Match the primitive to the action. Put every question about one state in one request. | The decision card is filled in (`references/decision-card.md`). |
| 6. Price the run | 1 | Run the program on a ten-word input: the billed tokens are the fixed floor, your question text. Compute calls per run = units x calls per unit x rounds, and tokens per call. State both numbers. | The numbers are ones you would approve. When the floor exceeds the typical state, shorten the questions first. |
| 7. Smoke run | 2 | Run the three-unit set, then the dev sample. | `calls_failed` is zero, every answer parses, and `python3 scripts/jev-cost-report.py --since 1h` matches the step 6 estimate. |
| 8. Score | 1 | On the same dev set, report the rules alone, Jev on the residual, and the combined system, per slice, with Brier and a calibration curve. Count false positives beside recall. Run judge variance once over frozen rows. | The combined score and its cost per run are in the run log. |
| 9. Improve | 1+2 | First separate code errors and service failures (HTTP errors, timeouts) from wrong answers, by reading the exact state, questions, candidates, and answers of each miss. Then classify the wrong answers (`state_lacked_evidence`, `criteria_ambiguous`, `wrong_primitive`, `label_noise`). Change one lever. Re-score. Keep the change when the combined score climbs and every slice holds. | Each variant is logged with score and cost. |
| 10. Report | 1 | Score the test split once. | One test number, reported beside the dev number. |
| 11. Integrate | 1+2 | Ship an on-demand command with a reader, storage, and an action. Log whether each answer changed the action. Promote to a hook when four conditions hold: code decides the obvious cases first; the labeled set shows the answers are right; under 90% of answers are the same; something acts on the answer. Run a new hook in shadow mode first, and promote one hook at a time. | A day of use shows the cost report and the action-changed rate you expected. |
| 12. Next system | - | Start step 1 for the next decision. | - |

**Step 9 levers, in search order:** evidence in state; decomposition (one Score into several Nouls); criteria wording; thresholds; few-shot examples in state. Evidence comes first because the other levers work only on a signal that is present. Retune thresholds from stored probabilities, which costs zero calls. Derive a gate threshold from action costs, `t = C_FP / (C_FP + C_FN)`, select it on one split, and report on another.

**Cost model.** Cost = calls x input tokens per call. Input tokens = state + the text of every question, with its criteria and examples. Output is free. Three numbers govern a run:

| Number | Target | Reach it by |
|---|---|---|
| Sends per state | one per run | one request per unit; stages as code thresholds; a second request only for new evidence |
| Fixed floor per call | below the typical state size | one- or two-line questions; `what`, `not_for`, and `examples` only where labeled misses call for them |
| Firing rate | matches how often the answer changes an action | on-demand commands first; hooks after step 11's conditions |

**Iteration is cheap when requests repeat.** Identical payloads return identical answers (zero variance across repeated runs of a fixed question set). `call_jev` caches by payload hash for 30 minutes, longer than a loop round, so a round re-bills only the requests whose questions changed. A breaker trips on HTTP 401 and 402, so an auth or billing failure costs one call.

**Telemetry is part of the system.** `call_jev` logs every call: script name, session id, input tokens, question count, payload hash, cached or not, error. Read the cost report after every multi-call run and compare it with the step 6 estimate.

**Graders see only what you send.** Send the richest available output and the evidence itself: command output, file content, stored answers. Tune on one label set and report on another.

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
- A request holds 64,000 tokens: the state plus every question. The state plus the longest single question must stay under 32,000. Check the [models page](https://docs.typesafe.ai/models.md) for current limits. The state is billed again in every request, so fill each request with as many questions as fit before you start a second one. Fit state in stages. Every stage that calls Jev needs fitting, not just the first.
- Keep observed facts and inferred values in separate, labeled fields. Check that the state is still current before you act on an answer about it.
- Jev does not treat state as hostile. Text in state can steer answers. Apply `skills/shared-patterns/untrusted-content-handling.md`, name in criteria what counts, and run adversarial and self-describing test cases before deployment.

## Composition patterns

| Pattern | Shape | Worked example |
|---|---|---|
| Speculative fan-out | every branch's questions in one call, each stating its own premise ("if this is a refund request, ..."); questions cannot see one another's answers; code ignores unused heads and their uncertainty | `scripts/jev-browser-decide.py` |
| Confidence-gated routing | a floor below which nothing acts and a higher bar for high-stakes actions; paths act / confirm / hand off. Start near 0.5-0.6 and 0.85-0.9, then set both from your labeled data and action costs | `scripts/jev-route.py` |
| Composite scoring | one Score per dimension, normalize by `len(criteria) - 1`, weights in code. Weighted sums suit preferences that offset one another; an "any serious violation" rule needs its own Noul per condition | `references/composition-patterns.md` |
| Intent routing | Choice for intent plus complexity Score, both confidence-gated | `scripts/jev-route.py` |
| Taxonomy walk | one Choice per level; each option's criteria is its trimmed subtree; follow several branches when close | `references/composition-patterns.md` |
| Multi-Noul decomposition | split a compound goal into one Noul per clause; combine in code | `references/composition-patterns.md` |
| Cascade plus verification | one wide request per unit; code thresholds pick survivors. Send a second request when the first answer is needed to fetch evidence, build new state, or decide the next options; it carries only what the first lacked | `references/composition-patterns.md` |
| Deterministic pre-filter | programs decide the obvious ends; Jev judges the middle | `scripts/jev-compact.py` |
| History injection | recent actions as "already taken, do not repeat" | `scripts/jev-browser-agent.py` |

One screen each, with the code shape: `references/composition-patterns.md`.

## Integration lifecycle

Start every program as an on-demand command. Promote it to a hook after it meets the four conditions in step 11 of the build procedure. Promote one hook at a time and read the cost report after a day of use.

Every integration has a reader (runs Jev), storage (findings persist somewhere read), and an action (something changes behavior). Missing any part wastes the call. Thread prior assessments into later calls as bounded, labeled evidence. Fail open for advisory checks; fail to warn for safety checks; never fail to block when Jev is unavailable. Validate every response with `validate_jev_response` before acting. Details: `references/integration-lifecycle.md`.

## Improve a program

This is step 9 of the build procedure. Find the failing question on labeled data before changing anything.

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
| Answer follows text in state | state steering | tighten criteria; adversarial tests; confidence gate |
| Rewording trades one error for another | one question, several properties | split into atomic questions |
| Answers right, decision wrong | policy | change weights or thresholds in code, not questions |
| Slow or costly | sequential calls | merge into one request |

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
- [ ] All questions on one state travel in one request.
- [ ] Responses are validated; a pure policy function decides; thresholds sit in the policy.
- [ ] Reader, storage, and action all exist; assessments persist with full distributions.
- [ ] `score` is read as a weighted mean; code that rounds says so.
- [ ] Adversarial and self-describing inputs are in the test set.
- [ ] Labeled examples back every revision; the model version is pinned or the jaggedness page rechecked.
- [ ] Every script passes a validation probe: imports without error, `--help` exits 0, and a live call with representative input returns valid JSON with `source != "error"`.
- [ ] Hooks that grade agent output read the richest available text (task-notification result, not just the last assistant message).
- [ ] Hooks that check grounding receive verifiable evidence (stored Jev answers, tool output summaries), not just file paths.
- [ ] In development, run on a small sample (50–200 rows) before the full dataset. A bad question wastes every call.
- [ ] `jev-cost-report.py --since 1h` after every multi-call run. Watch for: 0-ok scripts, duplicate payload hashes, and failed calls above 1%.

## Error handling

**Error: HTTP 422 on the request**
- Cause: wrong schema. Choice needs `criteria` as a map; Noul uses `criteria.true`/`criteria.false`; Score uses a `criteria` list. Keys such as `options`, `min`, `max` are not part of the API.
- Solution: match `references/primitives.md`; validate against the live API, not a mocked test.

**Error: `max_tokens_exceeded`**
- Cause: state plus questions exceed the budget at some stage.
- Solution: fit state in stages, cap items per call, split large inputs, and count failures per stage. See `references/state-and-budget.md`.

**Error: HTTP 429 or 529**
- Cause: rate limit (tokens per second or requests per minute) or an overloaded service.
- Solution: retry with exponential backoff and honor `retry-after`. The official SDKs do this by default; `call_jev` callers keep the existing retry path. Fewer, fuller requests lower the request rate.

**Error: HTTP 401 or 402**
- Cause: bad key or exhausted credits. A retry never succeeds.
- Solution: the breaker in `call_jev` stops further sends. Code outside `call_jev` (a sandboxed plugin) stops after the first such status. Keep the API key on the server side; never ship it to a browser.

**Error: valid response, wrong decision**
- Cause: policy reads `score` as a level index or thresholds on the wrong primitive.
- Solution: read `probabilities`; keep thresholds in the policy; see the known-debt note in `references/improve-and-calibrate.md`.
