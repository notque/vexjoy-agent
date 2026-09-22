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
- `model`: the shared client calls `jev-latest`. Pin the version when a calibration set or threshold depends on measured behavior. When the model changes, rerun the labeled set and reread the jaggedness page.
- Budget: A request holds 64,000 tokens: the state plus every question. The state plus the longest single question must stay under 32,000. Check the [models page](https://docs.typesafe.ai/models.md) for current limits.
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

Schema strictness: keys outside the documented set (`options`, `min`, `max`, nested `what` at the Choice top level) return HTTP 422 or are ignored. A wrong schema can fall back to defaults silently, and a mocked test passes anyway. Validate against the live API.

## Answers

| Type | Fields | Read it as |
|---|---|---|
| Noul | `noul` | probability of yes. Near 1 yes, near 0 no, 0.5 unsure. No `confidence`; distance from 0.5 is the signal. |
| Choice | `choice`, `probabilities`, `confidence` | `choice` is the argmax. `probabilities` covers every option. `confidence` is how peaked the distribution is. |
| Score | `score`, `legend`, `probabilities`, `confidence` | `score` is the probability-weighted mean of level numbers. `legend` maps level number to description. |

Score example: levels 0, 1, 2 with probabilities 0.0, 0.7, 0.3 give `score` 1.3 and `confidence` 0.54. Level numbers start at 0 and follow array order. The API keys `probabilities` and `legend` by string ("0"); the Python SDK keys them by integer.

Reading `score`:
- It is a position, not a picked level. A 1.0 can be all weight on level 1 or a 0/2 split. Read `probabilities` when the distinction changes the action.
- Threshold it, rank by it, or round it to the nearest level for one outcome. Say in code that rounding is a bucketing step.
- Never interpolate a quantity from it. Levels are weakly calibrated as numbers. "Score 1.3 means 30% of users lack a workaround" is false.
- Scale offsets: adding 1.0 to map a 0-based mean onto labels "1..5" is a bucketing step. Say so in the code, and call the value a mean.

Reading `confidence`:
- A statistic of the distribution, computed for you. Compute your own from `probabilities` when a different measure suits the decision (entropy, top-2 margin).
- It describes the answer, not its correctness. Confidence 1.0 on a wrong answer happens under literal reading.
- Low Choice confidence: options overlap or none fits. Low Score confidence: levels overlap, the question measures two things, or the state says too little.

## Independence and invariants

Every answer is constrained to the options you supplied; code never parses prose. Every answer is independent: adding or removing a question does not change the others. Jev is consistent: similar inputs give similar outputs, so a labeled set stays meaningful across runs.

Structural identities you might expect are not guaranteed:
- A Noul and a yes/no Choice on the same question can return different numbers. Do not carry a threshold from one primitive to the other.
- Do not assume `P(noul)` and `1 - P(not noul)` sum to 1; test the primitive and wording you will deploy.
- A Choice is relative (which option wins); a Noul is absolute (it can be low for every option). Use both on a shortlist: the Choice picks, per-option Nouls decide whether to pick at all.

Validate before acting: `validate_jev_response` checks Noul in [0,1], Choice is a string, Score is numeric, probabilities in [0,1] summing to about 1, confidence in [0,1]. Advisory callers log and continue; safety callers treat an invalid response as unavailable.
