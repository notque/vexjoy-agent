# Decision Analysis Anti-Patterns

> **Scope**: Behavioral failure modes that corrupt weighted decision scoring. Covers framing, scoring, and interpretation errors. Does not cover domain-specific criteria selection (see `decision-archetypes.md`).
> **Version range**: All versions of decision-helper skill
> **Generated**: 2026-04-16

---

## Overview

The weighted scoring framework exists to surface hidden reasoning and reduce bias. The anti-patterns below defeat that purpose. Most are invisible to the user doing them — the matrix looks correct but the inputs were already corrupted. The detection signals below are observable language and behavior patterns that indicate an anti-pattern is in progress.

---

## Anti-Pattern Catalog

### ❌ Confirmation Bias via Post-Hoc Weight Adjustment

**Detection signal**: User adjusts weights AFTER seeing the scored matrix, specifically to change the winner.

```
"Actually, I think Familiarity should be weight 4, not 2."  [after seeing their preferred option lost on Familiarity]
"Can we lower Risk? I don't think it's that important here." [after seeing their preferred option scored badly on Risk]
```

**Why wrong**: Weights represent what matters for this decision. If weights were set correctly before scoring, changing them afterward is just math to reach a predetermined conclusion. The matrix now proves nothing — it just launders a gut feeling as structured analysis.

**Fix**: Lock weights before scoring begins (Step 2 gate). If a user wants to change weights after seeing results:
1. Ask why the criterion now seems less important — what changed?
2. If they can give a substantive reason (new constraint discovered, misunderstood criterion), accept it and re-score
3. If the only reason is that their preferred option scored badly: name it directly — "That would be adjusting weights to reach a preferred outcome. Is there a criterion we're missing instead?"

**Re-run protocol**: If weights legitimately need changing, reset: wipe scores, update weights, re-score from scratch with updated weights visible.

---

### ❌ Analysis Paralysis via Option Proliferation

**Detection signal**: User presents 5+ options, or keeps adding options mid-scoring.

```
"We're also considering Option D, and actually Option E is worth looking at..."
"Before we score, what if we added the hybrid approach as Option F?"
```

**Why wrong**: Scoring more than 4 options dilutes focus and invites false precision. A 6-option matrix signals the decision hasn't been framed yet — it's research, not decision-making. The math becomes meaningless when the options haven't been pre-filtered.

**Fix** (Step 1 gate): Before scoring, apply a two-pass filter:
1. **Hard constraint elimination**: any option that fails a hard constraint is removed, not scored
2. **Dominance elimination**: if Option B dominates Option C on ALL criteria at first glance, remove Option C

After filtering, if >4 remain: group similar options or ask the user to identify the top 3-4 worth deep analysis. Name the others as "out of scope for this decision."

**Never score more than 4 options**. The framework says this explicitly. Enforce it.

---

### ❌ Anchoring to the First Option

**Detection signal**: First option stated gets systematically higher scores across criteria, even weak ones, or other options are evaluated relative to the first rather than absolutely.

```
"Option A does X well. Option B doesn't do X as well as A." [A becomes the reference point]
```

**Why wrong**: Scores should be absolute (1-10 on the criterion itself), not relative to another option. When the first option anchors scoring, the matrix measures "distance from Option A," not actual quality.

**Fix**: Score criteria independently per option. When scoring Option B on Maintainability, ask "how maintainable is this, independently?" — not "is it more or less maintainable than A?"

For options where anchoring is suspected: re-score the anchored option last and check for systematic differences.

---

### ❌ False Precision on Tied Scores

**Detection signal**: User treats a 0.1 or 0.2 weighted score difference as a meaningful recommendation.

```
Option A: 6.89
Option B: 6.71
"So we should go with Option A."
```

**Why wrong**: Individual scores are subjective 1-10 estimates. A score of 7 vs 8 on Complexity is not a measurement — it's an opinion. Weighted differences below 0.5 are noise, not signal. Treating them as decisive ignores the uncertainty in every input score.

**Fix**: Apply the close-call rule: any margin within 0.5 is a close call, regardless of which option is numerically higher. Flag it explicitly and identify what additional factor should decide, rather than defaulting to "higher number wins."

**Error-fix mapping**:

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| "A wins 7.0 vs 6.9" stated as clear recommendation | 0.1 margin treated as signal | Flag as close call, ask what additional factor decides |
| Long discussion about whether score should be 7 or 8 | Precision theater | Use the midpoint and move on — these debates add no value |
| Re-scoring same criterion 3+ times | Discomfort with uncertainty | Accept the range, note it as uncertain, proceed |

---

### ❌ Criteria Scope Creep Mid-Scoring

**Detection signal**: New criteria added after scoring has started, especially if the new criterion favors a particular option that was losing.

```
"Actually, we should add 'Vendor Support' as a criterion."  [halfway through scoring]
"I forgot to include 'Team Learning Opportunity.'"  [after Option A is clearly losing]
```

**Why wrong**: Adding criteria after partial scoring means earlier options were scored on a different basis than later ones. The matrix is now comparing apples and partially-scored oranges. It also creates an opening for sneaking in criteria that reverse an unwanted result.

**Fix**: Criteria are frozen at the Step 2 gate. If a genuinely forgotten criterion is discovered mid-scoring:
1. Stop scoring
2. Add the criterion to the table
3. Back-fill scores for ALL already-scored options on the new criterion
4. Continue

If the user can't justify the new criterion without referencing a specific option's weakness, it's probably scope creep. Ask: "Would you have added this criterion if Option B were winning?"

---

### ❌ Skipping Hard Constraint Elimination

**Detection signal**: Options with obvious eliminators still make it into the scoring matrix.

```
Scoring a vendor that doesn't support the required data residency region.
Scoring an open-source library with a GPL license for a commercial product.
Scoring a framework whose last commit was 4 years ago.
```

**Why wrong**: Hard constraints are binary eliminators, not scored criteria. Including non-starters in the matrix wastes time and creates noise. Worse, a non-starter that scores well on other criteria may appear competitive and require re-justifying the constraint.

**Detection commands**:
```bash
# Check license before scoring a library
gh repo view {org}/{repo} --json licenseInfo

# Check activity before scoring a framework
gh repo view {org}/{repo} --json pushedAt,isArchived

# Check compliance before scoring a cloud provider
# (manual — verify against provider's compliance documentation)
```

**Fix**: Run hard constraint checks before framing options in the matrix. Document which options were eliminated and why — this is important context for the decision record.

---

### ❌ No Hard Criteria for "Scores Feel Wrong"

**Detection signal**: User repeatedly adjusts scores without reasoning, or says "something feels off."

```
"I think Risk should be 9, not 7." [no explanation]
"Let's change Maintainability to 5." [changing a score without new information]
```

**Why wrong**: Score changes without justification are gut feelings overriding the framework. The framework's value is making implicit reasoning explicit. Unexplained score changes re-obscure the reasoning.

**Fix**: Every score change requires a one-sentence justification: "I'm changing Risk from 7 to 9 because we just learned the vendor has had three outages this quarter." Without justification, name the pattern: "That would be adjusting a score without new information. What specifically changed your view?"

If many scores feel wrong: the criteria may be mismatched to the decision. Return to Step 2 and check whether the archetype-specific criteria from `decision-archetypes.md` are more appropriate.

---

## Error-Fix Mappings

| Signal | Anti-Pattern | Intervention |
|--------|-------------|-------------|
| "Can we lower that weight?" after matrix shown | Confirmation bias | Lock weights; ask for substantive reason |
| 5+ options presented | Analysis paralysis | Filter to 4 before scoring |
| All scores relative to Option A | Anchoring | Re-score independently; re-score A last |
| Margin <0.5 called a winner | False precision | Flag as close call |
| New criterion added mid-matrix | Scope creep | Back-fill all options or defer to next decision |
| GPL library in commercial matrix | Missing hard constraint | Eliminate before scoring |
| Score changed with no reason | Gut override | Require one-sentence justification |

---

## See Also

- `decision-archetypes.md` — Domain-specific criteria weight adjustments by decision type
