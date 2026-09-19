# Composition patterns

Questions in one request never see each other's answers. They run independently against the same state; parallelism improves wall time, not the token bill or shared request budget. Maximize independent questions that add decision or action value, subject to their question-token cost and the 64,000-token request budget. Compose in code.

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

Ask every question the code might need in one request, including questions that matter only on some branches. Questions run in parallel, but each question's instructions and criteria still add billed tokens and consume shared request budget. Batch independent heads that can change a decision or action; omit low-value or noise heads. Do not batch a head that requires another answer to select evidence, construct candidates, or define its criterion. Measure the cost, wall time, and answer agreement of batching against serial sends on the target workload before relying on it.

```python
answers = call(state, {"category": choice, "bug_severity": score, "refund_requested": noul})
if answers["category"]["choice"] == "bug_report" and is_actionable_severity(answers["bug_severity"]): escalate()
elif answers["category"]["choice"] == "billing" and passes_refund_policy(answers["refund_requested"]): billing(refund=True)
```

For example, a browser program can send operation-type Choices beside readiness Nouls, then execute only the answers its deterministic policy needs.

## Second request only when the first answer decides the data

Make a second call only when code cannot build it without the first answer: the answer picks what to fetch, what the state is made of, or which options the next Choice offers. Examples include ranking candidates before re-judging a shortlist against full text, classifying blocks produced by a first-pass merge, and hierarchical classification where each answer selects the next options. If the second call's questions could have run against the original state, put them in the first call. The code—not an implied dependency between heads—must build and label the new state.

## Confidence-gated routing

The answer says what; confidence says whether to act. Three paths: act, confirm or flag, hand off.

```python
if intent["confidence"] < HANDOFF_CONFIDENCE: hand_off()      # floor
elif intent["choice"] == "check_balance": act()                # low stakes
elif intent["choice"] == "approve_transfer":
    act() if intent["confidence"] > HIGH_STAKES_CONFIDENCE else confirm()
```

Select thresholds on labeled data and the cost of a wrong call; one system may need several. Gate a Score's confidence too, not only the Choice's. Keep thresholds as named policy constants and report their calibration.

Treat low confidence on a non-terminal browser action as a reason to hold the pick, re-observe, and count it toward the stall guard. Set the cutoff from labeled data and action costs. Terminal claims skip this gate only when an independent verification gate controls them.

## Composite scoring

One Score per dimension, normalized by `len(criteria) - 1`, combined with weights in code.

```python
def normalized(answers, qid): return answers[qid]["score"] / (len(QUESTIONS[qid]["criteria"]) - 1)
priority = 0.6 * normalized(a, "severity") + 0.3 * normalized(a, "frustration") + 0.1 * normalized(a, "report_quality")
```

Change a weight when priorities shift; do not rewrite a question to change policy. Different role profiles are different weight vectors over the same answers.

## Intent routing

A Choice for intent beside a complexity Score can route each intent to deterministic code, a specialist LLM, or a person; send low-confidence classifications and high-complexity edge cases to a person. A wide pass may shortlist candidates for a detailed rerank with `not_for` and per-candidate fit Nouls. Log the full distribution: a near-tie between the winner and runner-up is a close call that the pick alone hides.

## Taxonomy walk

One Choice per tree level; walk in code. Each option's criteria value is its subtree, so Jev sees what lives under a branch before committing. Trim large subtrees to direct children and a sample of leaves. When probabilities are close, follow several branches (beam) and let a later level or a per-leaf Noul settle it. Two calls for a two-level tree, not one call per leaf.

## Choice picks, Nouls decide whether to pick

A Choice is relative: something always wins. Add one Noul per shortlisted option (absolute: "does this genuinely fit?") in the same call. Act on the Choice only when its winner's Noul also passes.

## Multi-Noul decomposition

Split a compound goal into one Noul per clause. Programs split, Jev judges each, programs combine. Compare decomposed and compound forms on labeled cases; keep the decomposition only when it improves the action or quality measure. When an answer looks wrong, the question may be too big.

## Cascade plus verification

One wide request per unit proposes; code thresholds pick the survivors; a second request verifies them and carries only evidence the first lacked. Only confirmed findings reach the report. Add deterministic post-checks beside Jev: does the file exist, does the test pass, does the build succeed. A model's claim of completion is not evidence of completion.

Severity must spread. If findings collapse into a few indistinguishable levels, a ranking is unusable. Define Score levels as distinct situations and, when the evidence requires it, use a verification-stage severity judgment to produce a ranking someone can act on.

## Bounded residual review

Use a stronger reviewer only after code and Jev have handled the obvious units, and only for a declared referral band. This is an exception to the normal rule against LLM review, not a second general-purpose judge. The runner gives the reviewer the immutable, source-bound evidence bundle Jev saw (plus explicitly declared new evidence if one was fetched), pins a fixed answer schema, and keeps the reviewer from drafting explanations or changing the evidence.

Before shipping, compare Jev-only and Jev-plus-review on a held-out split. Report: referral rate, accuracy/recall and false-positive lift on both all units and referred units, incremental cost per input KB and per corrected unit, p50/p95 added wall time, accumulated reviewer call time, timeouts, and declined referrals. Cap per-call spend, output, retries, and deadline in code. Keep the stage only when the marginal lift is worth those limits; otherwise improve Jev evidence or criteria instead.

The decision definition stays model-neutral: code creates evidence bundles and source IDs, the runner selects the model, and downstream policy consumes the same typed answer. Persist each attempt and final decision so a later model swap or audit can replay the exact workload.

## Deterministic pre-filters and per-class thresholds

Programs decide the obvious ends; Jev judges the middle. In compaction, deterministic result classes may always drop or keep when representative evidence supports those rules, and Jev judges the rest. Per-class policy thresholds can differ. A `referenced` Noul ("was this result cited later?") can boost keep probability in code. Missing answers default to keep.

## History injection and stall detection

Put a bounded action history in state as a plain list (`actions_already_taken`). Put the rule ("do not repeat an action listed in `actions_already_taken`") in the instructions: state holds facts, instructions hold the judgment. This keeps Jev from choosing the same action again. Fingerprint each observed state (hash of role:label:value); an unchanged fingerprint after an action means no effect, and repeated fingerprints are a cycle. Both end the loop in code with policy-defined limits. When an action had no effect and confidence was low, retry with the runner-up from `probabilities` rather than the same pick.

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
4. **Keep only with evidence.** A pattern that reads well but does not improve a measured decision, cost, or quality outcome against its baseline is not a pattern. Record the before/after evidence alongside the labeled cases.
