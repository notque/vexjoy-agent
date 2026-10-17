# Field learnings

Claims that project sessions sent back, each re-run on synthetic inputs against `jev-1.14.0` unless marked "recorded". Verdicts: VALIDATED, PARTLY, NOT REPRODUCED, NOT TESTABLE HERE. Numbers come from 2026-10-16 runs with small n; re-measure on your data before you set a threshold. Rules that changed practice live in the linked reference; this file keeps the evidence.

Sources: DR = DeepRoute (UI lab: player and images lanes), RTA = road-to-aew, MMR = mmr-ratings.

## Question design

### Compound Noul sits near the middle (MMR)
- Claim: a Noul with several conditions sat near 0.6 on every item (median 0.63); single-condition Nouls split bad 0.97 from good 0.11.
- Repro: 10 UI-copy items (5 good, 5 with one defect each), one 5-condition Noul vs 5 single Nouls. The compound separated them (good 0.67 to 0.88, bad 0.04 to 0.20), so no mid-scale cluster. The singles cross-talked: the "vague" Noul read 0.83 to 0.93 on the jargon, passive, and rude items.
- Verdict: PARTLY. Splitting tells you which condition failed; the "median near 0.6" symptom did not appear on easy items.
- Rule: a Noul whose median sits near 0.5 to 0.7 across all items is probably compound or under-evidenced; split it to locate the failing condition. [question-design.md](question-design.md) (Noul).

### Examples act as a near-exhaustive set (MMR)
- Claim: examples "promotion, era, year, or filter" gave 0.30; "search box, filter, sort, promotion, or date" gave 0.98 on the same state.
- Repro: a list page with one control; question "Does the page give the user a way to change which rows are listed?". Sort dropdown: narrow examples 0.27, broad examples 0.95, no examples 0.73. Search box 0.85 / 0.98 / 0.88. Date picker 0.79 / 0.96 / 0.71. With the narrow examples under `criteria.true`, the sort case read 0.38. A clear control ("Season dropdown", "Week tabs") ignored the examples (0.96 to 0.99 in all three forms).
- Verdict: VALIDATED for borderline forms: examples that omit a form push that form toward no.
- Rule: list every form that should count, or drop the examples; test with and without. [question-design.md](question-design.md) (Noul).

### Design-fork Choices sharpen with measured facts (RTA)
- Claim: measured facts moved one fork from 0.48/0.28/0.24 to 0.78, and a second from 0.53/0.47 to a Noul at 0.84.
- Repro: fork "how should the AI pick each play". Bare: `heuristic_first` 0.82. With facts (550 plays per campaign, 0.7 s budget, no heuristic exists, conditional effects defeat arithmetic): `every_play` 0.70. Fork "surplus gold": bare `carry_over` 0.48; with facts (632 unused, no other use) `shop_buy` 0.48 against `carry_over` 0.47, still split.
- Verdict: VALIDATED, with a correction: a bare answer can be confident and wrong (0.82), so facts change the answer, not only its sharpness. A split that survives the facts needs a narrower second question (a Noul on the leading option), as RTA did.
- Rule: no new rule; it is the "sufficient evidence" rule. Do not trust a confident fork answer that carries no measured facts. [question-design.md](question-design.md).

### One-sided distributions and misleading evidence (MMR, recorded)
- Claims: label capture leaked the options, and jargon was flagged on 60 of 68 items; probe a miss one change at a time (removing one phrase moved 0.77 to 0.54, repeat runs within 0.05); one false claim in state sank an answer (0.20 to 0.67 and 0.77 after the fix); ambiguous names split until state listed who uses them (0.56 to 0.36); an approach Choice over measured facts reached 0.90.
- Source: `/home/feedgen/mmr-ratings-dev/docs`. Not re-run. Consistent with the existing rules.
- Rule: when one answer dominates a whole batch, check the evidence pipeline before the question. Verify every claim you put in state against data. [improve-and-calibrate.md](improve-and-calibrate.md).

### Wrong-field reads fail silently (MMR, recorded)
- Claim: a helper read `choice` on a Score and returned 3 for every item.
- Rule: validate the answer shape per type (`validate_jev_response`) and read `score` from a Score. [primitives.md](primitives.md).

## Evidence and state

### Compare candidates inside one request (MMR)
- Claim: a Score moved with batch context (1.73 in an 11-item batch vs 2.22 alone); a before/after pair in one request agreed within 0.05 over two runs.
- Repro: 12 copy items scored alone and in one 12-question request, same ladder. Mean difference -0.01, largest 0.16. Three before/after pairs in one request, two runs: gaps 2.77/2.78, 1.21/1.03, 1.13/1.03 (alone: 2.69, 1.14, 1.01). The reference copy scored 3.92 and 3.52 in the same form as candidates.
- Verdict: NOT REPRODUCED for batch shift; paired runs agreed within 0.18, not 0.05.
- Rule: keep comparing before and after in one request (it costs nothing and removes any context shift), and score the anchor in the same rubric and state form as the candidates as a calibration check. Do not trust a gap under about 0.2. [iteration-with-jev.md](iteration-with-jev.md).

### Perceptibility thresholds, scale splits, ladders (MMR, recorded)
- Claims: stating "1 px is not noticeable, 2 px or more is" moved an arm Choice 0.50/0.48 to 0.69 and a women group 0.55 to 0.94; 1x and 3x judged apart (0.45 vs 0.82); a fixed 0 to 4 ladder tracked measured luma change at 1x and 3x on text descriptions (about 6.3k tokens); a reference scored 2.02/2.19 as "matches reference" but 3.71/3.16 with observed descriptions.
- Rule: put measured thresholds in state as facts; ask per scale and per group; describe the reference and the candidate in the same form. [improve-and-calibrate.md](improve-and-calibrate.md), [images.md](images.md).

### A judgment can rise while the measured gate worsens (MMR, recorded)
- Claim: an "accurate to the real move" Noul rose from 0.44 to 0.72 while pose distance worsened from 0.715 to 0.760; a text-only Score passed a move the owner rejected because pose names carry no timing.
- Rule: the concrete case for "pair every judgment with a measured number"; when they disagree, stop and find out why. Send frames and measured timings, not names.

### App ground truth beats DOM text and Jev reads (RTA, DR; recorded)
- Claims: a DOM regex missed wins after a UI change while the store state (`runLog result == 'won'`) was true; DR's 5 stuck-Noul reads were all right and all 5 causes were harness bugs (stale element handles after an overlay re-rendered the DOM).
- Rule: read the app's own state first, DOM facts second, a Jev visual read last. A stuck Noul says that you are stuck, not why: check the harness first (press Escape, re-tag by role and name).

## Choice option sets

### Large-N Choices are flat; margin predicts stability (DR player)
- Claim: a Choice over up to 40 near-equal actions had top p 0.2 to 0.4, reversing the order kept the argmax 1 of 5 times, and "top p under 0.5" escalated on 75 of 100 steps.
- Repro, 36 synthetic nav actions on a team page:
  - Specific goal ("see who we play next week"), 6 states: top p 0.45 to 0.99, 4 of 6 stable under reversal, and every pick was in the acceptable set.
  - Vague goal ("look around"), 6 states: top p 0.18 to 0.35 (uniform is 0.03), median margin 1.2, 2 of 6 stable.
  - Gradient over N (3, 5, 8, 14, 28 unvisited options, 10 states each): agreement 8, 8, 6, 8, 9 of 10; median top p 0.66, 0.59, 0.47, 0.46, 0.35. No steady fall with N. Repeats at N 28 to 36: 7 of 10 stable. Pooled at N 28 to 36 with a vague goal: 25 of 36 stable (69%), not 20%.
  - What predicts stability is `p_max / p_second` of the forward answer. Margin 2 or more: 29 of 29 stable; under 2: 10 of 21. Top p 0.5 or more: 22 of 24 stable; under 0.5: 17 of 26. A top p of 0.35 is flat at N 36 and strong at N 3, so a fixed top-p bar misfires; margin does not depend on N.
  - Shortlisting: 10 random unvisited options, and a two-stage group-then-action walk over 7 groups, did not make a vague-goal pick stable (5 of 6 each, margins 1.4 to 1.6). With a specific goal the second stage reached top p 0.7 to 1.0 on 4 to 7 options, at the cost of a second request.
- Verdict: PARTLY. Flatness reproduced (vague goal, near-equal options). Order instability reproduced but milder (69% vs 20%). The N gradient is not clean: goal specificity matters more than N, and shortlisting to 10 does not cure flatness by itself.
- Rule: flat means Jev has no preference, so a stronger model has nothing to find. Read margin, not a top-p bar. If the leading options do not differ in cost, take the argmax or let code break the tie (first unvisited, random). Escalate only when consequences differ (see Escalation). Helper: `scripts/jev_choice.py`. [primitives.md](primitives.md).
- Correction for DR: shortlist to remove options that are visited, illegal, or equal, not to reach a size. Give the Choice a goal that has an answer.

### Equivalent options split the mass (RTA)
- Claim: duplicate cards (same template, cost, text) spread mass over 4 to 6 options (top p 0.28 to 0.78); merging them and escalating a split only when consequences differ gave 0 escalations over 55 calls.
- Repro: 8 synthetic hands of 3 to 6 cards with duplicate templates, listed unmerged ("Strike #1", "Strike #2") vs merged ("Strike (x3 in hand)"), forward and reversed. The same template won in both forms 8 of 8. Unmerged: top p median 0.55, option-level margin median 2.56, but 1.76 once mass was summed by template. Merged: top p median 0.56, margin 1.78. Forward/reverse agreement by template: unmerged 7 of 8, merged 5 of 8 (small n; the misses were hands with top p near 0.5).
- Verdict: PARTLY. Merging does not change which play wins; it changes the margin you read. An unmerged list can show a false lead (the copies share mass) or a false split (second place is a copy of first).
- Rule: merge or sum equivalent options before you read the margin: `choice_margin(probs, classes)`. [question-design.md](question-design.md) (Choice).

### Order sensitivity grows as the lead shrinks (RTA, DR)
- Claim: reversed criteria agreed 5 of 6 on combat picks (4 to 6 options) vs 1 of 5 on 40 UI options.
- Repro: see the gradient above. Agreement tracks margin, and option count matters only through margin. Few options with a clear lead are stable; many equal options are not; N alone predicted little in our runs.
- Verdict: VALIDATED as a gradient by margin.
- Rule: with margin 2 or more, act without a reversal check; below that, the pick is arbitrary.

### Adding an option can flip the pick (MMR)
- Claim: one added option flipped a Choice (0.98 to 0.90 for the new option), and sub-Choices in the same request contradicted the headline.
- Repro: 4 nav options, goal "find which starters are hurt" (Injuries 0.79). Adding the near-duplicate "Open Injury Report": the new option won at 0.76. Adding the unrelated "Open News Feed": Injuries 0.79, unchanged. Goal "who plays center field tomorrow": Depth Chart 0.73, then 0.65 and 0.59 with an option added.
- Verdict: VALIDATED for near-equivalent additions (they take the pick); unrelated additions lower top p a little.
- Rule: rerun and re-read after you change an option set; fold a near-duplicate into the option it duplicates; reconcile any sub-answer that disagrees with the headline in code. [question-design.md](question-design.md) (Choice).

### Duplicate labels fail at the Gateway (MMR)
- Claim: options with the same label ("heading: Diana Strong" vs "control: Diana Strong") failed with "did not select a highest-probability option".
- Repro: prefixed labels, and labels that differ only by a trailing space, ran on both the Gateway and the direct API with no error. Two options with identical `what` text returned 0.65/0.35, an arbitrary split. A list of one-key objects as `criteria` fails at the Gateway.
- Verdict: NOT REPRODUCED. The failure needs a condition we did not recreate.
- Rule: unchanged hygiene: dedupe code-generated options by label before you send. A JSON object cannot hold a key twice, so a duplicate means your code overwrote an option.

## Escalation

Unified rule from DR (large-N flatness) and RTA (interchangeable plays), checked above:

1. Merge equivalents (same template, cost, effect) into one option, or sum their mass by class.
2. Drop options the state rules out: visited, illegal, unreachable. Give the question a goal that has an answer.
3. Read the margin, not a top-p bar: `p_max / p_second` below about 2 is unstable.
4. Gate on consequences: escalate only when the leading options differ in outcome cost (death is possible, unblocked incoming damage of 25% HP or more, money, irreversible, owner-visible). Otherwise take the argmax or break the tie in code.
5. Then escalate to a stronger model with the frozen evidence (SKILL.md, "Escalate when Jev is unsure").

RTA's merge plus consequence gate: 0 escalations over 55 calls and 88k tokens, down from 2 of 9 at about $0.07 and 7 s each. DR's 75% escalation rate was flat Choices with nothing at stake.

## Images and Box

### A broad "is something broken" Noul over-flags; one Noul per defect kind does not (DR)
- Claim: a broad Noul flagged 54 of 100 real screens (3 real defects); intentional tab strips and silhouette avatars read 0.7 to 0.9; the companion kind Choice was wrong on 2 of 3.
- Repro: 10 Pillow-rendered 1280x900 team pages: 4 clean (each with a horizontally scrolling tab strip cut at the right edge, a cut-off fourth card, and gray silhouette avatars) and 6 defective (2 each: broken-image icon, overlapping text, red error banner). State held DOM facts (errors and failed requests on the broken-image and error pages).

| Method | Clean flagged at 0.6 or more | Defects found |
|---|---|---|
| Broad Noul | 2 of 4 (0.85, 0.80; a third at 0.54) | 6 of 6 (0.84 to 0.99) |
| Broad Noul plus an `intentional_patterns` list in state | 0 of 4 (0.49, 0.14, 0.11, 0.27) | 4 of 6: broken-image fell to 0.47 and 0.25 |
| One Noul per defect kind (4 kinds) | 0 of 4 (all 0.15 or lower) | 6 of 6; the matching kind read 0.90 to 1.00 and was the top kind each time |
| One Noul per kind plus the list | 0 of 4 | 6 of 6; broken-image fell to 0.61 and 0.57 |

- The kind Noul "text cut off mid-glyph where the content is not meant to scroll" ignored the intentional tab strip (0.04 to 0.09). The error-banner pages read 0.59 to 0.61 on it (cross-talk).
- Verdict: VALIDATED. The listed patterns cut false positives but also suppressed a real defect that resembled a listed pattern (a broken-image glyph where "silhouette avatars are designed" sat).
- Rule: ask one Noul per defect kind, with the intent in the wording ("not meant to scroll"), and read the kind from which Noul fires, not from a second Choice. List intentional patterns narrowly and check that real defects of that kind still fire. Pair with the DOM fault count. [images.md](images.md) (Defect checks).

### Box with vague defect targets (DR)
- Claim: 55 `locate` calls with targets like "the clipped text" and "the broken image" on real pages returned 0 found (24 several, 17 low_confidence, 14 absent).
- Repro: 6 defective synthetic pages and 2 clean ones. Vague "the broken image": found 2 of 2, IoU 0.88 and 0.93. "The error message": found 2 of 2, IoU 0.74. "The clipped text" aimed at overlapping text: `several` 2 of 2 (the wrong word; the page has other cut-off text). Concrete targets ("the orange text that overlaps the name in the third card of the top row"): found 2 of 2, IoU 0.33 to 0.42 (the box covered one line of a wide target); the error bar IoU 0.78 to 0.83. On clean pages the vague target returned `absent` 2 of 2 (present 0.14 and 0.16, count none).
- Verdict: NOT REPRODUCED as stated. DR ran `locate` only on screens where the Noul had fired at 0.6 or more, and 52 of 54 of those had no defect, so `absent`, `several`, and `low_confidence` there were mostly correct. Box disagreed with the Noul, not with the page. A target word that fits a single defect ("broken image") works; one that does not ("clipped" for overlap) gives `several`.
- Rule: name the defect in words the page can match, one instance per call; treat `absent` on a Noul-flagged screen as evidence against the flag. [images.md](images.md) (Locate a target with Box).

### Contact grid of tiles (DR images)
- Claim: one 1228x924 grid of 24 numbered tiles with 24 six-way Choices found 16 of 16 planted defects and labeled 15 exactly; 6 of 56 clean tiles were false positives at p 0.47 to 0.80; the real run flagged 69 of 494 tiles (25 false positives); 18.7k tokens per grid, mostly repeated criteria.
- Repro: synthetic 1228x925 grid of 24 numbered tiles (blue helmet on a plain background); defects: blank, corrupt (noise streaks), wrong crop, wrong colors, not a photo; 8 planted.

| Shape | Input tokens | Result |
|---|---|---|
| 24 six-way Choices, short criteria | 6,634 | 8 of 8 found, 8 of 8 labeled exactly, 0 false positives |
| 24 per-tile Noul "is this a normal helmet?" | 3,897 | 8 of 8 found (ok-p under 0.2), 0 false positives |
| 5 per-kind Choices over tile numbers plus `none` | 4,324 | one tile per kind: 5 of 8 defects; the second blank, corrupt, and wrong-colors tile missed |
| 1 grid-level Noul "is every tile normal?" | 3,345 | 8 defects 0.00; clean grids 0.79 and 0.78 |

- Three grids with one planted defect (tile 16; dark and light tiles alternating): grid-level Noul 0.01 to 0.02; per-tile Noul 0.00 to 0.01 on tile 16 and 0.89 or more elsewhere. A grid of good tiles, half dark and half light, had 0 false positives in every shape.
- Verdict: PARTLY. The per-tile Noul cost 41% less than the six-way Choice with the same recall here. Per-kind Choices find one tile per kind. The grid-level Noul caught gross synthetic defects but never read high on a clean grid and does not locate; DR saw 0.0 to 0.8 on 22 real grids. Our tiles are far easier than real photos, so the false-positive rates did not appear.
- Rule: number the tiles, add a legend, keep criteria to a few words, use a per-tile Noul for "is it normal", ask the six-way Choice only on flagged tiles, and gate on `p >= 0.9` of the chosen option. Never use a grid-level Noul as the only check. [images.md](images.md) (Contact grids).

### Judge the strip, not the poster frame (RTA, recorded)
- Claim: the poster frame is the impact instant with a damage badge; `anatomy_broken` read 0.83 to 0.86 on all 4 cards on the static frame and 0.34 to 0.44 on the time-ordered key-pose strip; named-move read 0.07 to 0.64 on the strip against 0.29 to 0.46 on the static frame (n=4).
- Source: road-to-aew `scripts/pictogram_jev_qa.py eval`. Not re-run.
- Rule: send the frames that show the property you judge and remove overlays (badges, HUD) that are not part of it. [images.md](images.md) (Defect checks).

### Fine pose identity in stylised art is at chance (RTA, recorded, scoped negative)
- Claim: near-miss pose identity for stylised flat SVG two-figure poses does not work on jev-1.14.0, even with the card name hidden. State: a key-pose strip (about 1.5 to 2k px wide) and `body_part_targeted`; options: the true move, 3 hard same-family near-misses from the move mechanics, and `none_of_these`, seeded shuffle. Result: 20 of 36 correct (56%), AUC 0.554, about 2.0k tokens per request (n=36). Errors were confident (0.86 to 0.94); strikes collapsed to "haymaker"; Jev did not read whether a rope launch or landing is present from the strips. Earlier round (card name in state, Noul and Choice): Noul AUC 0.574, Choice AUC 0.517 with a name prior; `action_hidden`, anatomy, and the readability Score were identical across classes.
- Per-option reference images were infeasible: they leak the answer.
- Scope: stylised flat SVG poses. Untested: one panel per request at higher resolution, Box on the contact point, photo references.
- Source: road-to-aew `scripts/pictogram_jev_qa.py eval` and `scripts/data/pictogram_qa_labeled.json`, shipped as an experimental tool for re-testing future Jev versions. Not re-run here.
- Verdict: scoped negative (replaces the earlier "PARTLY").
- Rule: do not use Jev to judge fine pose or near-miss identity in stylised art on 1.14. Use the labeled set only as a re-test benchmark when the model version changes. A Choice that picks the named move is a name prior, not identity evidence. [images.md](images.md) (Defect checks).

### Not-a-photo mixes unexpected-but-real with defective; bias (DR images, recorded)
- Claims: 37 of 69 flags were real logos or other legitimate content; false positives skewed toward dark-skinned faces (flagged wrong team colors) and dark helmets (flagged corrupt).
- Source: `/home/feedgen/deeproute-jevlab/research/jev-ui-lab-2026-10-16/images/REPORT.md`. Not re-run on people photos. Flat dark and light synthetic tiles showed no skew (0 false positives).
- Rule: use a deterministic allow-list or a separate "was this intended?" step; audit the false-positive rate by subgroup; never auto-act on a Jev flag of a person's photo. [images.md](images.md).

### Code measures, Jev confirms colors (DR images, recorded)
- Claim: a colour-mismatch Choice was reliable when code pre-filtered candidates and supplied the expected hex and measured dominant colours: 9 of 9 mismatches at 0.79 to 0.97, matches at 0.00 to 0.42.
- Rule: send the measured numbers beside the picture.

### Check references on disk before asking Jev (DR images, recorded)
- Claim: the one real image bug (DB rows pointing at `.gif` files that do not exist; only a same-stem `.jpg` does, so the app serves 404s and renders near-black helmets) was missed by the deterministic checks and by the Jev grids; the game player's DOM fault counter found it.
- Rule: for image QA, check references against disk and fetch status first. Jev adds little over Pillow for corruption and is best for semantic checks (wrong content, colours, crop).

### Public-screen image-bug Noul plus Box (DR images, recorded)
- Claim: 4 of 45 flags, all false positives from carousels and fixed bars in full-page shots; Box absent every time.
- Rule: hide fixed-position bars before a full-page capture, capture viewport slices, list intentional clipping in state. Consistent with the defect-Noul entry.

### State images are resent in every split part (DR images)
- Claim: image slices in state reached 152k tokens; "every question sees every state image".
- Repro: billing is not per question. Three 1280x900 state images with 1, 6, and 24 questions cost 9,614, 10,190, and 12,258 input tokens (about 115 per question). The multiplier is our splitter: 7 state images (21.9k tokens) with 230 questions split into 7 requests of 38 questions, each carrying all 7 images: 179,022 input tokens, against 37,898 for 140 questions in one request. The estimator undercounts (37.9k billed for an estimate under the 32k limit), so splits start later than the estimate says.
- Verdict: VALIDATED, caused by our transport. `evaluate()` now records `_meta.split.state_image_tokens_resent` and emits a `UserWarning` when a split resends state images.
- Rule: keep state images few and questions per image modest; send one request per image, or per 3 or 4 images, rather than one state with many images and hundreds of questions. [images.md](images.md) (Token cost and splitting).

## Transport and ops

### Cost and latency (DR)
- Claim: 194 calls, about 1M input tokens, $0.042; 0.1 to 0.4 s per call; wall time dominated by page loads.
- Repro: 3 trivial Noul calls took 0.40 to 0.44 s wall and 395 to 414 ms receipt time through the Gateway (275 input tokens each). This validation run used about 0.85M input tokens, about $0.036.
- Verdict: VALIDATED on cost; Gateway latency (about 0.4 s) is at the top of DR's range.
- Rule: budget by input tokens; Jev latency is not the bottleneck in a browser loop.

### Billed tokens exceed `len(json) / 4` (MMR)
- Claim: billed tokens were about 1.4x the estimate.
- Repro: a Choice with 6, 18, and 36 options billed 345, 441, and 586 tokens against `len/4` of 80, 156, and 272 (marginal ratio 1.25; fixed overhead about 275 per request). Eight Score questions with a 5-level ladder each billed 1,334 against 562 (1.9x after the overhead).
- Verdict: PARTLY. The estimate runs about 1.25x low per token plus about 275 fixed per request, and worse on repetitive structured text. `CHARS_PER_TOKEN` is unchanged: the limits keep a wide margin under the API's 64,000.
- Rule: read `usage.input_tokens` for the real cost; plan with about 30% headroom.

### Failure modes (MMR, recorded)
- A direct key once returned 402 (billing). Do not retry; tell the owner ([models-and-limits.md](models-and-limits.md)).
- Cache keys must include the item name. Poll for stuck detection instead of a fixed sleep.
- Source: `/home/feedgen/mmr-ratings-dev/docs`.

### Run our Jev client without `-I` (RTA)
- `python3 -I` ignores the user site, so Pillow installed there is hidden and `jev_images` and `jev_box` fail to import. The `-I` rule is for Python that reads untrusted downloads; run the Jev client without it, or use a venv that has Pillow. [images.md](images.md).

### `jev-latest` was 1.13 for non-Box calls (DR)
- Fixed by pinning `jev-1.14.0` (PR #1071). Responses report `typesafe-ai/jev-1.14.0`. Nothing to add.
