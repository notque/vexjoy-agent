# Decision Analysis Patterns Guide

> **Scope**: Behavioral patterns that protect the integrity of weighted decision scoring. Covers framing, scoring, and interpretation discipline. Does not cover domain-specific criteria selection (see `decision-archetypes.md`).
> **Version range**: All versions of decision-helper skill
> **Generated**: 2026-04-16

---

## Overview

The weighted scoring framework exists to surface hidden reasoning and reduce bias. The patterns below protect that purpose by catching the moments where bias re-enters the process. Most corruption is invisible to the person doing it — the matrix looks correct but the inputs were already compromised. The detection signals below are observable language and behavior patterns.

---

## Pattern Catalog

### Lock Weights Before Scoring Begins

Set all criterion weights in Step 2, then freeze them. If a user wants to change weights after seeing results, require a substantive reason — not just that their preferred option scored badly.

When a user says "Can we lower Risk? I don't think it's that important here" after seeing their preferred option score badly on Risk, name the pattern directly: "That would be adjusting weights to reach a preferred outcome. Is there a criterion we're missing instead?"

**Re-run protocol**: If weights legitimately need changing (new constraint discovered, misunderstood criterion), reset: wipe scores, update weights, re-score from scratch with updated weights visible.

**Why this matters**: Weights represent what matters for this decision. Changing them after seeing the scored matrix is math to reach a predetermined conclusion. The matrix now proves nothing — it launders a gut feeling as structured analysis.

**Detection**: User adjusts weights AFTER seeing the scored matrix, specifically to change the winner.

---

### Filter Options to Four Before Scoring

Apply a two-pass filter before building the scoring matrix. First, eliminate any option that fails a hard constraint. Second, eliminate any option dominated on ALL criteria at first glance. After filtering, if more than 4 remain, group similar options or ask the user to pick the top 3-4 worth deep analysis.

Never score more than 4 options. The framework says this explicitly. Enforce it.

**Why this matters**: Scoring more than 4 options dilutes focus and invites false precision. A 6-option matrix signals the decision has not been framed yet — it is research, not decision-making.

**Detection**: User presents 5+ options, or keeps adding options mid-scoring ("We're also considering Option D, and actually Option E is worth looking at...").

---

### Score Each Option Independently

Evaluate each option on each criterion using absolute scoring (1-10 on the criterion itself), not relative to another option. When scoring Option B on Maintainability, ask "how maintainable is this, independently?" — not "is it more or less maintainable than A?"

For options where anchoring to the first option is suspected: re-score the anchored option last and check for systematic differences.

**Why this matters**: When the first option anchors scoring, the matrix measures "distance from Option A," not actual quality. Scores should reflect each option's absolute performance on the criterion, not its position relative to whichever option was mentioned first.

**Detection**: First option stated gets systematically higher scores across criteria, or other options are evaluated relative to the first ("Option B doesn't do X as well as A").

---

### Apply the Close-Call Rule for Margins Under 0.5

Any weighted score margin within 0.5 is a close call, regardless of which option is numerically higher. Flag it explicitly and identify what additional factor should decide, rather than defaulting to "higher number wins."

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| "A wins 7.0 vs 6.9" stated as clear recommendation | 0.1 margin treated as signal | Flag as close call, ask what additional factor decides |
| Long discussion about whether score should be 7 or 8 | Precision theater | Use the midpoint and move on — these debates add no value |
| Re-scoring same criterion 3+ times | Discomfort with uncertainty | Accept the range, note it as uncertain, proceed |

**Why this matters**: Individual scores are subjective 1-10 estimates. A score of 7 vs 8 on Complexity is an opinion, not a measurement. Treating sub-0.5 differences as decisive ignores the uncertainty in every input score.

**Detection**: User treats a 0.1 or 0.2 weighted score difference as a meaningful recommendation.

---

### Freeze Criteria at the Step 2 Gate

All criteria must be defined before scoring begins. If a genuinely forgotten criterion is discovered mid-scoring: stop scoring, add the criterion, back-fill scores for ALL already-scored options on the new criterion, then continue.

Test for scope creep: "Would you have added this criterion if Option B were winning?" If the user cannot justify the new criterion without referencing a specific option's weakness, it is scope creep.

**Why this matters**: Adding criteria after partial scoring means earlier options were scored on a different basis than later ones. It also creates an opening for sneaking in criteria that reverse an unwanted result.

**Detection**: New criteria added after scoring has started, especially if the new criterion favors a particular option that was losing.

---

### Eliminate Hard-Constraint Failures Before Scoring

Run hard constraint checks before framing options in the matrix. A vendor that does not support the required data residency region, a GPL library for a commercial product, or a framework with no commits in 4 years should be eliminated, not scored.

Document which options were eliminated and why — this is important context for the decision record.

```bash
# Check license before scoring a library
gh repo view {org}/{repo} --json licenseInfo

# Check activity before scoring a framework
gh repo view {org}/{repo} --json pushedAt,isArchived
```

**Why this matters**: Hard constraints are binary eliminators, not scored criteria. Including non-starters in the matrix wastes time and creates noise. A non-starter that scores well on other criteria may appear competitive, forcing re-justification of the constraint.

**Detection**: Options with obvious eliminators (unsupported region, incompatible license, abandoned project) still present in the scoring matrix.

---

### Require Justification for Every Score Change

Every score change requires a one-sentence justification: "I'm changing Risk from 7 to 9 because we just learned the vendor has had three outages this quarter." Without justification, name the pattern: "That would be adjusting a score without new information. What specifically changed your view?"

If many scores feel wrong, the criteria may be mismatched to the decision. Return to Step 2 and check whether the archetype-specific criteria from `decision-archetypes.md` are more appropriate.

**Why this matters**: The framework's value is making implicit reasoning explicit. Unexplained score changes re-obscure the reasoning. Score changes without justification are gut feelings overriding the framework.

**Detection**: User repeatedly adjusts scores without reasoning, or says "something feels off" without specifics.

---

## Error-Fix Mappings

| Signal | Failure Mode | Intervention |
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
