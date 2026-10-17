# Primitives: API shape and answer semantics

Endpoint: `POST https://api.typesafe.ai/v1/systemone`, bearer auth. Python SDK: `client.system_one(state=..., questions=...)`. Stdlib client: `scripts/jev_router_common.py` (`call_jev`, `validated_call_jev`, `validate_jev_response`, `extract_usage`, `bound_text`).

## Request

```json
{"model": "jev-latest",
 "state": {"request": "...", "diff": "...", "prior": {"scope_flags": 3}},
 "questions": {
   "in_scope":  {"type": "noul",   "instructions": "...", "criteria": {"true": "...", "false": "..."}},
   "category":  {"type": "choice", "instructions": "...", "criteria": {"a": "...", "b": "...", "other": "..."}},
   "severity":  {"type": "score",  "instructions": "...", "criteria": ["level 0", "level 1", "level 2"]}}}
```

- `state`: string or JSON. Every question sees the same state. Structure it so questions can point into it by path.
- Question ID: your key. It is not sent to the model; write the full question in `instructions`.
- `model`: the shared client sends `jev-latest`, an alias that moves (1.13.0 now, 1.14.0 about 2026-10-21). Pin a versioned ID (`jev-1.13.0`) when a calibration set or threshold depends on measured behavior, store the response's `model` with each answer, and rerun the labeled set when the version changes. Aliases, deprecation notice, limits, and the long-context header: `models-and-limits.md`.
- Budget: 64,000 tokens per request (state plus every question); state plus the longest single question under 32,000; no cap on the question count. Limits, status codes, and retry rules: `models-and-limits.md`. `scripts/jev_limits.py` holds our planning constants and `backoff_delay`.
- Rate limits are per organization and shared by every request, retry, user, and eval. Retry 429 and 529 (Gateway 503) with jittered backoff; never retry 401, 402, or 422.
- Response carries `usage.input_tokens` and `usage.output_tokens`; `extract_usage` passes them through.

## Structured fields

`instructions`, Choice option values, Score level entries, and Noul `criteria.true`/`criteria.false` each accept a string, an object, an array, or `null`. Use an object when a question has labeled parts or needs supporting data. Pass a schema, taxonomy, or row as JSON; never serialize it into a string.

Instruction object keys the docs use:

| Key | Meaning |
|---|---|
| `question` | the question text |
| `focus` | what to weigh, what to ignore |
| `inspect` | the state path to judge |
| `note` | a scoping remark ("judge the number of changes, not their size") |
| `compare` | list of state paths to compare |
| `field` | `{name, type, unit, description}` shared by several questions about one field |

```json
"instructions": {"question": "Does `message` ask the recipient to disclose a credential?",
                 "inspect": "message",
                 "focus": "A request to send the credential itself, not to reset it."}
```

Array instructions: use `compare` with an array when two or more state paths must be compared side by side.

```json
"instructions": {
  "question": "Does the claimed sender identity conflict with the sending domain?",
  "compare": ["ticket.sender.display_name", "ticket.sender.email"],
  "focus": "Compare the named organization with the email domain."
}
```

Use an array for `inspect` when the question needs evidence from multiple fields simultaneously. Arrays keep the model's attention on the right fields without requiring you to name every path in the prose.

Choice option object: `{"what": ..., "not_for": ..., "examples": [...]}`. Option value `null` is allowed: a bare candidate list for extraction, where code generated the candidates and Jev picks.

Score level object: `{"summary": ..., "signals": [...]}` or `{"what": ..., "examples": [...]}`. Use the same keys on every level so the model compares like with like.

Noul criteria: optional. Add `true` and `false` sides with `what` and `examples` when the boundary is subtle. Put the neighboring case on the side it belongs to.

Limits on shape: a Choice takes up to 255 options and a Score 2 to 10 levels. Option and field names inside criteria are free (`what`, `not_for`, `examples`, `summary`, `signals` are our conventions, not reserved). A Choice option value may be a nested subtree, which is how a taxonomy walk shows what lives under a branch. Level numbers and neighbors are never shown to the model; a Score with levels "0", "1", "2" and no descriptions splits probability between neighbors.

Schema strictness: keys outside the documented set (`options`, `min`, `max`, nested `what` at the Choice top level) return HTTP 422 or are ignored. A wrong schema can fall back to defaults silently, and a mocked test passes anyway. Validate against the live API.

## Answers

| Type | Fields | Read it as |
|---|---|---|
| Noul | `noul` | probability of yes. Near 1 yes, near 0 no, 0.5 unsure. No `confidence`; distance from 0.5 is the signal. |
| Choice | `choice`, `probabilities`, `confidence` | `choice` is the argmax. `probabilities` covers every option. `confidence` is how peaked the distribution is. |
| Score | `score`, `legend`, `probabilities`, `confidence` | `score` is the probability-weighted mean of level numbers. `legend` maps level number to description. |

Score example: levels 0, 1, 2 with probabilities 0.0, 0.7, 0.3 give `score` 1.3 and `confidence` 0.55. Level numbers start at 0 and follow array order. The API keys `probabilities` and `legend` by string ("0"); the Python SDK keys them by integer.

Reading `score`:
- It is a position, not a picked level. A 1.0 can be all weight on level 1 or a 0/2 split. Read `probabilities` when the distinction changes the action.
- Threshold it, rank by it, or round it to the nearest level for one outcome. Say in code that rounding is a bucketing step.
- Never interpolate a quantity from it. Levels are weakly calibrated as numbers. "Score 1.3 means 30% of users lack a workaround" is false.
- Scale offsets: adding 1.0 to map a 0-based mean onto labels "1..5" is a bucketing step. Say so in the code, and call the value a mean.

Reading `confidence`:
- A statistic of the distribution, computed for you. The formulas are exact, so you can reproduce them or compute another measure from `probabilities`.
- It describes the answer, not its correctness. Confidence 1.0 on a wrong answer happens under literal reading.
- Low Choice confidence: options overlap or none fits. Low Score confidence: levels overlap, the question measures two things, or the state says too little.
- Several acceptable alternatives also spread probability. Do not gate a harmless preference on confidence. When you only want the best option, take `choice`; a threshold on every answer is a smell.

| Type | Formula | Note |
|---|---|---|
| Noul | none returned; `abs(2p - 1)` if you want one | 0.5 means the model gives yes and no equal probability, not "medium" |
| Choice, `n` options | `(p_max - 1/n) / (1 - 1/n)` | Only the top probability counts: (0.6, 0.3, 0.1) and (0.6, 0.2, 0.2) both give 0.4 |
| Score, `n` levels, `m` the most likely level | `max(0, 1 - sum(p_i * abs(i - m)) / mad_unif)`, `mad_unif = sum(abs(i - (n-1)/2)) / n` | Ordinal: (0, 0.5, 0.5) gives 0.25 (adjacent levels), (0.5, 0, 0.5) gives 0 (opposite ends) |

Two measures from the same `probabilities` often work better for a Choice: the top probability `p_max` (set its threshold per question, since 0.5 is weak among two options and strong among ten) and the top-to-second ratio `p_max / p_second` (a clear win over the runner-up; many decisions come down to two candidates). Try them beside `confidence` on labeled data. Margin predicts argmax stability better than top p: on synthetic nav Choices (2026-10-16, n=50) a margin of 2 or more kept the pick under reversed option order 29 of 29 times, and under 2 only 10 of 21; a fixed top-p bar misfires as N grows. Sum the probability of equivalent options first. `scripts/jev_choice.py` has `choice_margin(probabilities, classes)`, a per-arity bar (`margin_min_for`: 1.5 for two options, 2.0 otherwise), and a consequence-gated `should_escalate`. Margin 2.0 on a binary is p_max 0.667, which many valid picks miss; evidence in `field-learnings.md`. The CLAUDE.md formula `(3 * p_max - 1) / 2` is the Choice formula for three options, not the Score formula.

## Independence and invariants

Every answer is constrained to the options you supplied; code never parses prose. Every answer is independent: adding or removing a question does not change the others. Jev is consistent: similar inputs give similar outputs, so a labeled set stays meaningful across runs.

Structural identities you might expect are not guaranteed:
- A Noul and a yes/no Choice on the same question can return different numbers. Do not carry a threshold from one primitive to the other.
- Do not assume `P(noul)` and `1 - P(not noul)` sum to 1; test the primitive and wording you will deploy.
- A Choice is relative (which option wins); a Noul is absolute (it can be low for every option). Use both on a shortlist: the Choice picks, per-option Nouls decide whether to pick at all.

Validate before acting: `validate_jev_response` checks Noul in [0,1], Choice is a string, Score is numeric, probabilities in [0,1] summing to about 1, confidence in [0,1]. Advisory callers log and continue; safety callers treat an invalid response as unavailable.

## Box

A question with `type` `box` and `instructions` such as "the next-turn button in `page`" returns `box` (`top`, `bottom`, `left`, `right`, each 0 to 1 of the image, from the top-left) and `confidence`. It takes `instructions` only, needs an image and Jev 1.14, and mixes with other question types in one request. Multiply the fractions by the image size for pixels.

Rules for the question:

- A Box always returns edges, never "not found". Pair it with a presence Noul and ignore the box when the Noul is low.
- Ask one target per Box. Name several targets with one Box each.
- If the image may hold several look-alikes, add a Choice `none` / `one` / `several`.
- A target can be a picture: reference a second image in the instructions.

`scripts/jev_box.py` wraps these patterns: `locate(image, target)` runs the presence, count, refine, tile, and edge-check steps and returns one box in fractions of your original image. Box is experimental: treat it as one signal beside app data, a presence Choice, and edge checks. On images a present/absent Choice reads more decisively than a Noul. Patterns, escalation, and measured numbers: `images.md`.

