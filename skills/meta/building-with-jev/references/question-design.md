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

## Ask many specific questions

One Noul "did the agent expand scope?" can return a vague probability. Separate Nouls isolating relevant dimensions (files outside the import chain, reformatting of read-only code, unrequested features, unrelated error handling, new abstractions, unrelated tests, unrelated docs, extra dependencies, unrelated config, debug artifacts) plus a severity Score can tell a richer story. Add only heads that improve an action or decision on labeled cases; each one is billed as input text.

Replace every heuristic that encodes a judgment with a question: label-substring matching for a secret field became a Choice over configured names plus `NONE`; a DOM-mutation timer for "page still loading" became a `still_loading` Noul with the timer kept only as a settle mechanism. Keep deterministic code for policy, safety, and measurement.
