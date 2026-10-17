# Question design

A good Jev question is one a knowledgeable person answers in a second given the right context. If the question needs steps, split it and compose in code.

## Instructions

| Rule | Weak | Strong |
|---|---|---|
| State the exact condition | "Is this candidate strong in Python?" | "Does the resume state the candidate used Python at work?" |
| One property per question | "Is the PR small and safe?" | `is_small` Noul and `is_safe` Noul |
| Name the state path | "Does the message ask for a refund?" | "Does `ticket.messages[0].text` ask for a refund?" |
| No double negatives | "Is it not the case that no tests were added?" | "Were tests added for the edited code?" |
| No property of a property | "Is the author of the linked issue senior?" | fetch the author in code; ask about the author record |
| No numerals as levels | "Rate from 0 to 2" | describe each level as a situation |
| Policy stays in code | "A shared address cannot override a name conflict; decide the match" | `same_address` Noul, `name_conflict` Noul; decide in code |
| Full question in `instructions` | ID `refund_requested`, instructions "Refund?" | "Does `ticket_message` request a refund or credit?" |

Jev reads literally. When a wrong answer makes you explain what you really meant, that explanation is the missing half of the instruction. Where interpretation is unavoidable, split it into two literal questions and combine in code.

Give Jev the consequences of a choice as evidence: labeling a link "navigates away to /path" or marking a control "offscreen" moved the right pick's probability without a model change.

## Criteria

Criteria extend the instruction. Both must ask for the same thing in the same direction. A Noul whose `true` side describes "no" performs worse.

Write criteria for the hard cases. Jev already handles "agent rewrote an unrelated README" as scope creep. Criteria exist for "agent fixed a type import in `utils.py` because the edited function depends on it" (justified). Encode each case that was misjudged: false positive goes into `not_for` or the `false` side; a miss goes into `what` or the `true` side. Criteria are a living test suite for judgment.

### Start with sufficient evidence

For an affirmative decision, say what is sufficient before listing what is not. A long catalogue of exclusions teaches a cautious model to reject every imperfect case. Write the observable conjunction that earns `true`, then name the few lookalikes that must remain false. Add clerical equivalence only when labels support it: punctuation, abbreviations, spacing, nicknames, a middle initial, or a suffix present on one record may be equivalent; contradictory given names, incompatible dates, or different house numbers are not silently equivalent.

For example, a candidate-selection question should name the evidence combination sufficient to select one candidate, then list similar-looking but insufficient cases. Formatting differences or a missing optional field may be equivalent when labels support it; a conflicting required field is not. The exact evidence and exceptions belong in the question; the action threshold belongs in code.

Do not collapse distinct decisions into one broad `same` label. Keep classification, linkage, selection, and action authorization as separate questions or choices with separate policies. Preserve source IDs, evidence fields, question version, answer distribution, and policy decision for every action so a later correction can explain and undo it.

### Choice

```json
"billing": {"what": "Charges, invoices, refunds, subscriptions",
            "not_for": "Order tracking or account access",
            "examples": ["I was charged twice", "Where is my refund?"]}
```

- Make descriptions contrastive when options sit close: `not_for` names the neighbor.
- Add `other` or `none` when the list may not cover the input; otherwise probability piles onto the least-wrong option.
- Examples are concrete instances, not descriptions of instances. "I was charged twice" helps; "a message about a billing problem" does not.
- Examples steer only when they resemble real inputs. Test matching and non-matching examples on representative labeled cases; keep examples only when they improve the relevant decision without harming boundary cases.
- Keep specific names and values in `examples`; keep general rules in `what`.
- Option names and descriptions are both sent. The API accepts 255 options and any value shape, including `null` and nested subtrees. The keys `what`, `not_for`, and `examples` are our convention, not API fields: you may pick other names.
- Give the full legitimate option list, not a shortlist: options cost a few tokens each. Code removes options that are illegal or irrelevant for this state before the call. Offered impossible or degenerate options, Jev picks them (a game agent took "1 plate" 25 times in a row when every amount was offered).
- Merge equivalent options (same template, cost, effect) into one before you send, or sum their probability by class before you read the margin. Identical options split the mass and make a flat answer look like a split. When goals are vague the options are near-equal and the Choice is flat by nature: give it a goal that has an answer, and let code break a remaining tie.
- Count distinct options before you ask. Code-enumerated options that collapse to one or none (6 seed salts gave 1 distinct card) mean the generator is broken, not Jev: fail loudly instead of calling.
- Adding an option can flip the pick: a near-duplicate of the winner took it (0.79 to 0.76 for the new option). Rerun after any change to the option set, fold near-duplicates into the option they copy, and reconcile sub-answers that contradict the headline in code. Dedupe code-generated options by label.
- Jev leans toward the first option on some inputs (jaggedness page, "Choice option order"). For a high-stakes pick, ask again with the options reversed in the same request (two questions, same state) and act only when both agree; otherwise treat the answer as unsure.

### Score

- Two to ten levels, low to high, only as many as you can describe distinctly. Three is fine.
- Each level is a standalone situation. Jev sees neither the number nor the neighbors; "worse than the previous level" means nothing. Validate that descriptive levels improve decisions on representative labeled inputs; confidence alone is not evidence.
- One dimension per Score. "Punctual and smart and experienced" cannot place an input that is high on one and low on another.
- Give a rare extreme its own level when code must treat it differently ("abusive or threatening" above "very angry").
- Level objects: `{"summary": ..., "signals": [...]}`; same keys on every level.
- Two wordings of one scale behave differently on your data. Test levels against labeled inputs; higher confidence alone is not evidence.

### Noul

Criteria optional. When the boundary is subtle:

```json
"criteria": {"true":  {"what": "Asks the recipient to send a password, PIN, or one-time code",
                       "examples": ["Reply with your password"]},
             "false": {"what": "No credential is requested",
                       "examples": ["Reset your password from settings"]}}
```

`criteria.true`/`criteria.false` accept JSON objects for complex boundaries.

- Phrase it so a high value means yes: "Does the message contain personal data?", never "Is it free of personal data?". A statement works too ("The customer requests a refund"). Try both phrasings on labeled data.
- "Any" removes the middle ground: "Does the resume show any Python use?" beats "Is the candidate strong in Python?". For degree, use a Score.
- Test with and without `criteria`; keep whichever scores better on labeled cases.
- Examples act as a near-exhaustive set: a form you leave out is pushed toward no (a sort control read 0.27 with narrow examples, 0.95 with broad ones, 0.73 with none). List every form that should count, or drop the examples.
- A Noul whose median sits near 0.5 to 0.7 across all items is probably compound or under-evidenced. Split it into one Noul per condition to see which one fails; do not expect splitting to fix separation on easy items.
- A design fork ("which approach") over bare options can come back confident and wrong; add the measured facts (counts, latencies, what already exists) before you trust it. If it stays split after the facts, ask a narrower Noul on the leading option.
- Several labels that can all apply: one Noul per label, not one Choice.

### Progress comparison

In a multi-step task, "correct" depends on the path, which a snapshot does not show. Compare candidate resulting states against a named, observable subgoal instead. List the current state as an option so "no candidate makes progress" can win.

| Weak | Strong |
|---|---|
| Noul per action: "Is clicking `button:Next` the correct action?" | Choice over `candidates` plus `current`: "Which state in `candidates` is closest to `subgoal` (the shipping form shows a saved address)?" |

Each option's `what` summarizes its resulting state, not the action that produced it. Code maps the winning state back to its action (`composition-patterns.md`, Checkpoint search).

## Choosing the primitive

| Need | Primitive | Example |
|---|---|---|
| gate (proceed/block) | Noul | `is_safe`, `has_tests`, `addresses_request` |
| classify, route, pick | Choice | `error_type`, `next_action`, `merge_strategy` |
| rate quality, severity, risk | Score | `readiness`, `risk_level` |
| multi-aspect check | many Nouls | scope-creep dimensions in one call |
| taxonomy walk | chained Choices | category, subcategory, type |
| prioritize a list | Score each item | rank findings |
| ambiguous threshold | Noul plus Score | is it bad, how bad |

Scores calibrate magnitude; Nouls decide. Do not use a Score as a boolean proxy. When the answer has no in-between, use a Choice or several Nouls. If two types fit, prefer the one code acts on directly.

Use all three where they fit and ask them in the same call: "is the commit ready" (Noul), designated readiness dimensions (Nouls), "overall readiness" (Score), "what happens next: commit, cleanup, block" (Choice).

## Do not ask Jev about facts the code can check

A Noul that stays undecided in both option orders (0.42 each) on a code fact ("is the Strategy chip gated on the same capability as the Game Plan screen?") is not a judgment question. Settle it in code with a test. Keep Jev for what code cannot measure or compare.

## Which one: Choice, not a Noul per candidate

When the answer is "which of these", ask one Choice over the candidates. A game agent that read an item's identity measured 0.92 to 1.00 on a Choice and 0.44 to 0.70 on a Noul per candidate for the same input, and a "does it say X?" Noul gave 0.60 for a wrong item. A Noul judges one proposition with no rival to compare, so a loose match scores high. This agrees with the docs: a Choice picks among a set; a Noul measures a single claim.

- Add a `none` option so absence can win. A Choice always puts its probability somewhere, so its top option can win with nothing true.
- When an absolute check also matters, add a Noul beside the Choice ("does the document contain an answer at all?") and act on the pick only when both pass (`composition-patterns.md`, Choice picks, Nouls decide whether to pick).
- Read a printed number with a Choice whose options are the numbers ("1" to "N"). Do not use that to count objects: Jev does not count, so count in code and keep Jev for reading one value.

## Known model edges (jev-1.13)

From the [jaggedness page](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) (reviewed by TypeSafe 2026-10-02). Check the page for the version you deploy.

| Edge | What happens | Do |
|---|---|---|
| Literal reading | Scoping words and negations read at face value | State the exact condition; put the boundary case in criteria |
| Counting and math | No reliable counts, sums, or magnitudes | Code does it; one Noul per item, sum in code; never interpolate a quantity from `score` |
| Numeric forms | Hex colors, RGB triples, assembly, and binary do worse than names and high-level code | Convert in code to a name or bucket |
| Dates | Ordering, spans, and windows are unreliable | Choice per date part with a "not stated" option; code builds the date |
| Indirection | Double negatives and multi-hop questions lose accuracy | Ask directly; name the path |
| Large state | Unrelated detail distracts ("context rot") | Filter first; use a relevance Noul per passage when code cannot |
| Adversarial text | Injected or self-arguing text can move the answer | Name what counts in criteria; test hostile cases |
| Contradiction | Instructions and criteria that disagree confuse it | Make criteria an extension of the instruction |
| Option order | Leans to the first option | Reorder and compare |
| Generation | Not trained to write text | Choose among candidates code or an LLM produced |

Also avoid asking what code can compute, hiding several judgments in one question, and multi-layer reasoning questions.

## Ask many specific questions

One Noul "did the agent expand scope?" can return a vague probability. Separate Nouls isolating relevant dimensions (files outside the import chain, reformatting of read-only code, unrequested features, unrelated error handling, new abstractions, unrelated tests, unrelated docs, extra dependencies, unrelated config, debug artifacts) plus a severity Score can tell a richer story. Add only heads that improve an action or decision on labeled cases; each one is billed as input text.

Replace every heuristic that encodes a judgment with a question: label-substring matching for a secret field became a Choice over configured names plus `NONE`; a DOM-mutation timer for "page still loading" became a `still_loading` Noul with the timer kept only as a settle mechanism. Keep deterministic code for policy, safety, and measurement.
