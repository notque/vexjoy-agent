# Composition patterns

Questions in one request never see each other's answers. Compose in code.

## Pattern index

| Pattern | When to use | Sketch | Dissolve difficulty unlocked |
|---|---|---|---|
| Speculative fan-out | Multiple branches share state | all heads in one call; code ignores unused | multi-branch skills with shared evidence |
| Second request | First answer decides what data to fetch | call 1 picks, call 2 judges the picked data | two-phase skills (detect then act) |
| Confidence-gated routing | Action cost varies by stake | floor, act, confirm, hand-off paths | skills with escalation logic |
| Composite scoring | Multiple quality dimensions | one Score per dimension, weights in code | multi-rubric review skills |
| Intent routing | Classify then route | Choice + complexity Score, both gated | router/dispatcher skills |
| Taxonomy walk | Hierarchical classification | one Choice per tree level, follow in code | category-heavy triage skills |
| Choice + Nouls | Relative pick needs absolute check | Choice picks, per-option Nouls confirm | skills that must reject all options |
| Multi-Noul decomposition | Compound goal check | one Noul per clause, combine in code | phased skills with compound gates |
| Cascade + verification | Wide scan, narrow confirm | cheap pass proposes, second call verifies | review/audit skills |
| Deterministic pre-filter | Obvious ends + ambiguous middle | programs decide extremes, Jev judges rest | skills with regex/grep pre-phases |
| History injection | Sequential actions, loop risk | recent actions as do-not-repeat in state | interactive/browser skills |
| Label over index | DOM or list selection | pick by meaning, not position | UI-driven skills |
| Classify before acting | Unknown initial state | feasibility Noul on first observation | skills that gate on preconditions |

## Speculative fan-out

Ask every question the code might need in one request, including questions that matter only on some branches. Questions run in parallel; extra questions add little latency and few tokens. Code ignores the answers it does not need. Docs measured 13 questions in one call at 11.5x cheaper and 9.6x faster than 13 calls, with identical answers.

```python
answers = call(state, {"category": choice, "bug_severity": score, "refund_requested": noul})
if answers["category"]["choice"] == "bug_report" and answers["bug_severity"]["score"] > 1.5: escalate()
elif answers["category"]["choice"] == "billing" and answers["refund_requested"]["noul"] > 0.7: billing(refund=True)
```

Worked example: `scripts/jev-browser-decide.py` sends one Choice head per operation type (click targets, select values, type destinations) plus `still_loading` and page-quality Nouls in one call; the program executes only the head matching the chosen operation.

## Second request only when the first answer decides the data

Make a second call only when code cannot build it without the first answer: the answer picks what to fetch, what the state is made of, or which options the next Choice offers. Docs examples: rank 182 items in one call, then re-judge the top three against their full text; classify blocks that only exist after a first pass merged lines; hierarchical classification where each answer selects the next options. If the second call's questions could have run against the original state, put them in the first call.

## Confidence-gated routing

The answer says what; confidence says whether to act. Three paths: act, confirm or flag, hand off.

```python
if intent["confidence"] < 0.6: hand_off()                      # floor
elif intent["choice"] == "check_balance": act()                # low stakes
elif intent["choice"] == "approve_transfer":
    act() if intent["confidence"] > 0.85 else confirm()        # high stakes
```

Docs floors: 0.5 to 0.6; 0.85 to 0.9 for high-stakes actions. Start conservative and tune on labeled data. Thresholds scale with the cost of a wrong call, so one system carries several. Gate a Score's confidence too, not only the Choice's. Worked example: `scripts/jev-route.py` (confidence floors per dimension, `FANOUT_DOMINANCE_PROB = 0.75`).

Low confidence on a non-terminal browser action (under 0.45) was a guess in every observed case. Hold the pick, re-observe, and count it toward the stall guard. Terminal claims skip the gate because verification gates them.

## Composite scoring

One Score per dimension, normalized by `len(criteria) - 1`, combined with weights in code.

```python
def normalized(answers, qid): return answers[qid]["score"] / (len(QUESTIONS[qid]["criteria"]) - 1)
priority = 0.6 * normalized(a, "severity") + 0.3 * normalized(a, "frustration") + 0.1 * normalized(a, "report_quality")
```

Change a weight when priorities shift; do not rewrite a question to change policy. Different role profiles are different weight vectors over the same answers.

## Intent routing

A Choice for intent beside a complexity Score. Route each intent to deterministic code, a specialist LLM, or a person; send low-confidence classifications and high-complexity edge cases to a person. Worked example: `scripts/jev-route.py`, two-stage: stage 1 is a cheap wide pass with truncated criteria; stage 2 reranks the top three with full descriptions and `not_for`, adds per-candidate fit Nouls, and skips entirely when a trivial-bypass gate fires. Log the full distribution: `python-general-engineer@0.51` with `testing-automation-engineer@0.48` as runner-up is a close call the pick alone hides.

## Taxonomy walk

One Choice per tree level; walk in code. Each option's criteria value is its subtree, so Jev sees what lives under a branch before committing. Trim large subtrees to direct children and a sample of leaves. When probabilities are close, follow several branches (beam) and let a later level or a per-leaf Noul settle it. Two calls for a two-level tree, not one call per leaf.

## Choice picks, Nouls decide whether to pick

A Choice is relative: something always wins. Add one Noul per shortlisted option (absolute: "does this genuinely fit?") in the same call. Act on the Choice only when its winner's Noul also passes. `scripts/jev-route.py` stage 2 does this for agents.

## Multi-Noul decomposition

Split a compound goal into one Noul per clause. A five-clause goal scored 0.23 as one "is the goal met?" Noul; the same end state scored 0.74 when each clause was asked cleanly. Programs split, Jev judges each, programs combine. When an answer looks wrong, the question is usually too big.

## Cascade plus verification

One wide request per unit proposes; code thresholds pick the survivors; a second request verifies them and carries only evidence the first lacked. Only confirmed findings reach the report. Add deterministic post-checks beside Jev: does the file exist, does the test pass, does the build succeed. A model's claim of completion is not evidence of completion.

Severity must spread. A run that produced 255 medium and 95 low findings was unusable. A Score whose levels are distinct situations, plus a second-opinion severity Score in the verification call, produces a ranking someone can act on.

## Deterministic pre-filters and per-class thresholds

Programs decide the obvious ends; Jev judges the middle. In compaction, Glob and `ls` results always drop, Edit results always keep, Jev judges the rest. Per-tool thresholds let one 0.5 default behave differently per class: Edit/Write keep at 0.35 (higher bar to drop), Glob at 0.0. A `referenced` Noul ("was this result cited later?") boosts keep probability in code. Missing answers default to keep. Worked example: `scripts/jev-compact.py` (`TOOL_THRESHOLDS`, `referenced` boost).

## History injection and stall detection

Include the last N actions as "ACTIONS ALREADY TAKEN (do NOT repeat these)" in state. This keeps Jev from choosing the same action again. Fingerprint each observed state (hash of role:label:value); a fingerprint unchanged after an action means no effect, a fingerprint revisited three times means a cycle. Both end the loop in code with no Jev cost. When an action had no effect and confidence was low, retry with the runner-up from `probabilities` rather than the same pick. Worked example: `scripts/jev-browser-agent.py` (`STALL_LIMIT`, `CYCLE_VISIT_LIMIT`, `_compute_fingerprint`).

## Label over index

Jev picks by meaning. `link:Dashboard` is stable across re-renders; `element_3` breaks when the DOM shifts. Expand each `<select>` option as its own Choice entry (`select_option:Region:US-East`) and map back in code.

## Classify before the first action

A `goal_feasibility` Noul on the first observation catches error pages, login walls, wrong domains, and empty states before the loop spends steps. Informational Nouls (`has_real_content`, `interactive_elements_work`) run in the same verify call and let the program abort early.

## Decision and generation are different tiers

When a Jev decision needs generated text (commit message, field value), Jev decides what; the cheapest adequate model writes the text. Reserve large models for diagnosis and synthesis.

## Inventing a new pattern

Start from the failure: what did Jev get wrong, or what could it not see?

1. **Name the failure.** Wrong answer, low confidence, missed case, loop, or latency.
2. **Change one of four levers.** State shape (what evidence Jev sees), question decomposition (how many questions and of what type), call sequencing (one call vs. chained calls), or policy (thresholds and weights in code).
3. **Measure against labeled cases.** Run the new pattern on the same labeled set. Compare accuracy, confidence distribution, and false-positive rate.
4. **Keep only with numbers.** A pattern that reads well but does not improve the numbers is not a pattern. Record the before/after measurements in `references/lessons-with-numbers.md`.
