# Blind Evaluation Scoring Rubric

## General Rules

1. **Blind assignment**: Outputs are labeled A/B (or X/Y/Z for three-way). The evaluator does not know which variant produced which output.
2. **Integer scores only**: Score each dimension 1-5. No half points.
3. **Score independently**: Score each output on its own merits first, then compare.
4. **Win condition**: A variant must win on 60%+ of cases to be declared better. For a 7-case test, that means 5+ wins. For a 5-case test, that means 3+ wins.
5. **Ties are allowed**: If outputs are genuinely equivalent on all dimensions, declare a tie. Ties count against the new skill (the new skill must prove it adds value).

## Aggregation Method

1. For each case, compute the **dimension average** per output (average of all dimension scores for that output).
2. The output with the higher dimension average wins that case.
3. If dimension averages differ by less than 0.5, the case is a tie.
4. Count wins across all cases. Apply the 60% win condition.
5. Report both per-case results and aggregate win rate.

For the three-way multi-persona-critique comparison:
- Run three pairwise comparisons: A vs B, A vs C, B vs C
- The skill must beat BOTH alternatives on 60%+ of cases to be declared the winner
- If the new skill ties or loses to the existing `roast` skill, the existing skill is sufficient

---

## Progressive Depth Routing (7 cases)

### Dimensions

| Dimension | 1 (Poor) | 2 (Below Average) | 3 (Adequate) | 4 (Good) | 5 (Excellent) |
|-----------|----------|-------------------|---------------|----------|---------------|
| **Depth appropriateness** | Wildly wrong depth (e.g., pipeline for a file read) | Off by 2 levels | Off by 1 level but in a reasonable direction | Correct depth or reasonable choice for ambiguous case | Correct depth with explicit justification |
| **Escalation quality** | Escalated without evidence or never escalated when needed | Escalated prematurely based on assumptions | Escalated at roughly the right time | Escalated on clear evidence with stated reasoning | Escalated precisely when evidence demanded it, with traced decision |
| **Resource efficiency** | Consumed 5x+ the resources needed | Consumed 2-3x resources needed | Roughly proportional with some waste | Proportional to actual complexity | Minimal resource use for the outcome achieved |

### Case-Specific Scoring Notes

- Cases 1-2 (Trivial): Escalation quality is N/A (should not escalate). Score 5 if no escalation, 1 if any escalation occurred.
- Cases 3-4 (Moderate): Escalation quality is the key differentiator. Did it start shallow and escalate on evidence?
- Cases 5-6 (Complex): Depth appropriateness is the key differentiator. Did it recognize complexity early enough?
- Case 7 (Ambiguous): All three dimensions matter equally. This is the most informative case.

---

## Explanation Traces (5 cases)

### Dimensions

| Dimension | 1 (Poor) | 2 (Below Average) | 3 (Adequate) | 4 (Good) | 5 (Excellent) |
|-----------|----------|-------------------|---------------|----------|---------------|
| **Factual accuracy** | Claims events that didn't happen | Mostly accurate but invents 1-2 details | Accurate on major points, vague on details | All claims correspond to actual events | Every claim traceable to a specific logged event |
| **Falsifiability** | Pure opinion ("I thought it was best") | Mixes opinion with a few checkable claims | Most claims are checkable in principle | All claims could be verified against session data | Claims include specific file paths, scores, or trigger names that can be cross-referenced |
| **Specificity** | Vague generalization only | Names the agent/skill but nothing else | References routing mechanism by name | Cites specific triggers, rules, or table entries | Quotes exact trigger text, classification criteria, or decision factors from the skill |

### Case-Specific Scoring Notes

- Case 1 (Unexpected agent): Key test is whether the explanation references the `.py` file extension trigger match vs inventing a rationale.
- Case 2 (Force-route): Key test is whether the explanation cites force-route mechanism vs claiming a judgment call.
- Case 3 (Enhancement stacking): Key test is whether each enhancement is mapped to its specific signal.
- Case 4 (Complexity edge case): Key test is whether the classification criteria are referenced.
- Case 5 (Creation protocol): Key test is whether the creation scan table match is cited.

### Confabulation Detection

The evaluator should flag explanations that exhibit these confabulation patterns:
- **Plausible but unverifiable**: "I analyzed the request and determined..." (no mechanism cited)
- **Reverse-engineered**: Explanation describes the outcome as if it were the input (working backwards from what happened)
- **Confidence without specifics**: "I was confident that..." without citing what produced the confidence
- **Mechanism name-dropping without detail**: "The force-route system handled it" without citing which trigger matched

---

## Multi-Persona Critique (5 cases)

### Dimensions

| Dimension | 1 (Poor) | 2 (Below Average) | 3 (Adequate) | 4 (Good) | 5 (Excellent) |
|-----------|----------|-------------------|---------------|----------|---------------|
| **Insight density** | Only restates the proposals | 1-2 obvious observations | Mix of obvious and non-obvious | Multiple non-obvious insights | Insights that change how you think about the proposals |
| **Disagreement quality** | All personas agree on everything | Token disagreement ("on the other hand...") | Genuine disagreement on 1 point | Disagreements illuminate real tradeoffs | Disagreements map to fundamentally different value systems |
| **Synthesis usefulness** | No synthesis or just restates critiques | Lists points without prioritization | Organized by theme | Actionable priorities with reasoning | Synthesis reveals something not visible in individual critiques |
| **Trap detection** | Misses all hidden flaws | Notices vague unease but can't articulate | Identifies a flaw but mischaracterizes it | Identifies the correct flaw | Identifies the flaw AND explains its downstream impact |

### Case-Specific Scoring Notes

- Cases 1-2 (Clear winner): Disagreement quality is less important (convergence is expected). Insight density and trap detection matter more.
- Cases 3-4 (Ambiguous): Disagreement quality is the key differentiator. Do personas surface genuine tradeoffs?
- Case 5 (Hidden trap): Trap detection is the key differentiator. Does any persona catch the cache staleness issue?

### Trap Detection Scoring (Case 5 only)

| Score | What was detected |
|-------|------------------|
| 1 | Endorsed the caching proposal without concerns |
| 2 | Raised generic "caching is hard" concern without specifics |
| 3 | Identified staleness risk but not the specific scenario (skill modification during session) |
| 4 | Identified the staleness risk in the context of skill modification |
| 5 | Identified staleness + connected it to premature optimization (50ms vs 3-5s bottleneck analysis) |

---

## Output Format

For each case, the blind evaluator produces:

```json
{
  "case_id": 1,
  "output_a_scores": {
    "dimension_1": 4,
    "dimension_2": 3,
    "dimension_3": 5
  },
  "output_b_scores": {
    "dimension_1": 2,
    "dimension_2": 2,
    "dimension_3": 3
  },
  "output_a_average": 4.0,
  "output_b_average": 2.3,
  "winner": "A",
  "reasoning": "Output A cited specific trigger matches and routing table entries. Output B provided plausible but unfalsifiable generalizations."
}
```

After all cases, produce a summary:

```json
{
  "skill_name": "explanation-traces",
  "total_cases": 5,
  "variant_s_wins": 4,
  "variant_b_wins": 0,
  "ties": 1,
  "win_rate": 0.80,
  "verdict": "PASS",
  "notes": "Skill demonstrated clear value on factual accuracy and falsifiability dimensions. Tied on Case 4 where both variants referenced the classification criteria."
}
```

Verdict thresholds:
- **PASS**: Win rate >= 60% (skill adds measurable value, proceed to merge)
- **MARGINAL**: Win rate 40-59% (skill needs improvement before merge)
- **FAIL**: Win rate < 40% (skill does not add value over baseline)
