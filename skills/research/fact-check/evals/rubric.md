# Blind A/B Rubric: fact-check

Maintenance artifact — load when evaluating or modifying the skill, not during ordinary execution.

## Hardening rationale (v2 corpus)

The v1 corpus produced a dead tie (19/19 catches, 0 false alarms in both arms): errors were obvious, fixtures had only two sources, and every claim fell to direct lookup. The v2 corpus makes methodology load-bearing:

- **Distractor sources.** Every fixture includes at least one source that superficially supports a false claim — a secondary outlet misquoting the primary, a pre-vote newsletter with superseded figures, a community wiki with an unsourced valuation. Keyword matching now confirms wrong answers; tier climbing and lateral reading are required to reject them.
- **Subtle errors.** Unit/timeframe drift (annual run rate read as quarterly revenue), meaning-shift paraphrase (association upgraded to causation), and context-stripped quotes (exact words, right speaker, reversed meaning) all pass a words-and-numbers match and fail only under the skill's per-axis checks.
- **Cross-source adjudication.** Claims cite a source that is silent while a different provided source settles them; other claims require combining two sources to compute the asserted figure; two claims pit credible current sources against each other (correct label: Disputed).
- **Label discrimination.** Unverifiable (sources engage, nothing settles — including a claim supported only by a low-tier uncorroborated source) is seeded distinctly from Missing-source (no source addresses it).
- **False-alarm traps.** Several Verified claims look wrong on a shallow read — a figure the distractor contradicts, a growth rate no source states directly — so over-flagging now costs points.

`ground-truth.json` carries per-claim `notes` explaining why direct lookup fails and which method catches the error.

## Setup

- **Arm A**: agent fact-checks each fixture article without the skill.
- **Arm B**: agent reads `SKILL.md` (and references on demand) first, then fact-checks.
- Both arms get the same prompt per fixture: "Fact-check `article.md` against the source documents in this directory. Report your findings per claim." Sources are the files in the fixture dir; the run is closed-book by design.
- Corpus is fixed: 6 fixtures, 46 ground-truth claims (Verified 12, Disputed 22, Unverifiable 6, Missing-source 6), 34 non-Verified claims, all seeded. Seeded-error taxonomy: unit-timeframe-drift ×3, meaning-shift-paraphrase ×2, context-stripped-quote ×4, wrong-source-citation ×3, secondary-source-distortion ×2, stale-stat ×6, source-conflict ×2, uncorroborated-low-tier ×1, no-source-settles ×5, unsupported-claim ×6.
- Run both arms for every fixture in the same session batch; anonymize outputs as Output 1 / Output 2 with arm assignment recorded separately before judging.

## Scoring — deterministic first

Label correctness is deterministic and is scored by matching, not by judge opinion (ground truth is fixed; opinion adds noise). For each arm, walk `ground-truth.json` claim by claim:

| Metric | Definition |
|--------|------------|
| **Catch** | A non-Verified ground-truth claim that the report flags as problematic (any non-Verified label or equivalent wording) |
| **Label match** | The report's label equals the ground-truth label (map free-text verdicts to the nearest of the four labels before comparing; an unmappable verdict counts as no match) |
| **False alarm** | A Verified ground-truth claim that the report flags as problematic |
| **Miss** | A non-Verified ground-truth claim the report treats as fine or omits |

Matching tolerance: claims are matched by content, not ID — an arm that merges or splits claims is scored against the ground-truth claims its text covers. A ground-truth claim the report does not mention at all is a Miss (if non-Verified) or neutral (if Verified).

Report per arm: catch rate (catches / 34), label accuracy (label matches / 46), false-alarm count, misses by seeded-error type.

## Scoring — blind judge second

The judge receives both anonymized reports plus ground-truth.json and scores only what is not deterministic:

1. **Evidence quality** (1–5): does each finding cite the exact source passage?
2. **Report usability** (1–5): verdict-first summary, Warnings section surfaces the serious findings, label meanings readable from the report alone.
3. Winner pick with reasoning.

The judge sees no indication of which output used the skill.

## Promotion bar

Promote (B wins) only when **both** hold:

1. B catches strictly more seeded errors than A (sum across the corpus), and
2. B's false-alarm count is less than or equal to A's.

Ties on catches, or any false-alarm regression, fail to promote — a noisier checker erodes trust in the gate faster than extra catches build it. Label accuracy and judge scores are reported as evidence on the PR but are tiebreakers only, never substitutes for the two conditions.

## Known validation limit

This corpus is closed-book: it exercises extraction, given-source verification, adjudication, and reporting — including distractor rejection, triangulation, and staleness reasoning across provided files. The open-web methods (live lateral reading, tier climbing beyond provided files, live staleness re-checks) are outside what this A/B can confirm and are validated only through live use. State this limit wherever these results are cited.
