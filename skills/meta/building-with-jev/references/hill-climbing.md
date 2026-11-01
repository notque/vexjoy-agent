# Hill-climbing a quality goal with Jev, and reading Jev answers

Moved here verbatim from `~/.claude/CLAUDE.md` on 2026-11-01 (owner request, to cut per-request tokens). Load this before any quality or taste climb, and before reporting Jev confidence numbers.

## Reading the answer: what `confidence` is and is not
Source: https://docs.typesafe.ai/confidence.md and the primitive pages.

- **`confidence` is a shape statistic, not belief or trust.** It is computed
  from the `probabilities` Jev already returned. All mass on one option or level
  gives 1.0; the more evenly the mass spreads, the lower it goes. For a
  three-option Choice it is `(3 × largest probability − 1) / 2`. A Score's
  confidence is ordinal (spread across distant levels lowers it more), so
  that formula does not apply there. Formulas: the `building-with-jev` skill's
  `references/primitives.md`.
- It is **not** "how much Jev believes the answer", "how trustworthy the
  score is", or "how likely the answer is correct". Confidence 1.0 can still be
  wrong. Never write "Jev doesn't believe it", "Jev isn't sure it's right", or
  "the score can't be trusted" because confidence is low.
- **Noul has no `confidence` field.** The `noul` value is itself the
  probability of yes; its distance from 0.5 is the signal.
- **A Score is a probability-weighted mean of levels, not a picked level.** A
  Score of 1.5 on 0–3 can be all weight on 1–2 or a split between 0 and 3.
  Confidence near 0 with mass on both ends means the distribution is split, not
  that the page is "middling".
- **Low confidence tells you about the question, not about Jev's belief.** On a
  Choice: the options overlap or none clearly wins. On a Score: the levels are
  ambiguous, the question measures more than one thing, or the state doesn't
  contain enough evidence.
- **What to do with low confidence:** read `probabilities` and report the
  actual split (for example, "40% level 0, 45% level 3"). Then fix the question:
  split a multi-part judgment into separate questions, sharpen the level or
  option descriptions, or add the missing evidence to the state. Only then
  re-ask. Don't act on the mean of a split distribution as if it were a
  consensus.
- **Gate actions by consequence.** Use a higher bar for costly or irreversible
  actions and a lower one for cheap, reversible ones. When you need a different
  measure (top-2 margin, entropy), compute it from `probabilities`.

## Using Jev as a map: hill-climbing any quality goal
From the owner (notque), 2026-10-08, after this method fixed match-viewer
movement that had resisted months of tuning. Use it for any goal that is a
matter of quality or taste ("look like Fire Pro", "feel like a real GM",
"read clearly on mobile", "match a writing voice"), in any project.

1. **Fix the destination before working.** Write a Score ladder for the goal:
   3–5 levels, each with a `summary` and concrete, observable `signals`
   (sizes, ratios, what is visible, what a player notices), not adjectives.
   Score the current state first; that is the baseline. Don't rewrite the
   ladder mid-climb except as step 8 says.
2. **Find the structural cause before tuning.** Ask Jev (Choice) which
   approach fits before tweaking parameters. The movement fix came from
   changing structure (paired moves), not from tuning the solver.
3. **Show or describe what the user sees, not what the code says.** For a
   visual goal, send the rendered frame or screenshot as an image (long side
   at least 1080 px), with measured numbers beside it: structured context and
   the image together beat either alone. Otherwise the state holds
   observations measured from the actual output: pixel widths from a
   rendered frame, response times from a timed run, text as displayed. Never
   describe settings or intent. (Jev called the arms inflated from the code's
   numbers; on screen they were too skinny.)
4. **Give Jev something real to compare against.** Reference examples
   (screenshots, sketches, prior good output), sent as images for visual
   goals and handled the same way as the candidate. Without them Jev scores against its memory of the target.
5. **Pair every Jev judgment with a measured number.** "Looks grounded" goes
   with the shove distance; "feels faster" goes with p95. When the two
   disagree, stop and find out why before continuing. A metric that agrees
   with Jev only by chance (4 of 8) is not a check; replace it.
6. **Judge every step as before/after.** Compare the candidate with the last
   kept version on the same state. Set the keep bar before asking. Keep the
   step if it clears the bar, revert it if not, and log both. Reverting is
   progress (two of four paired moves were reverted, and that kept quality).
7. **One judgment per question, split by group.** Ask per trait (face, arms,
   gear) and per group (men/women, singles/tag, mobile/desktop), and always
   add a separate "did anything get worse or block?" Noul. A combined "better"
   of 0.90 hid a women regression of 0.23.
8. **Anchor visual ladders to reality, not to our own versions.** Jev can
   judge images now (2026-10-16; images and Box are TypeSafe "dreamer-ready",
   so they steer work and never solely gate a deploy). Comparing our
   candidate to our previous version still measures relative progress, not
   distance from the real thing. For any look or feel goal:
   - get the owner to rate a few absolute anchors once (for example "this
     reference is 9/10, ours is 1/10") and put those anchor images, with the
     owner's rating, into every state or Score ladder level;
   - ask "how far is this from the reference" as well as "is this better than
     last round";
   - before reporting progress on visuals, show the owner a side-by-side
     with the reference. A climb that Jev scores as progress can still be
     at 1/10. (2026-10-08: Jev preferred our untextured heads to ones the
     owner rated 9/10, because it only ever ranked them against our own
     text descriptions.)
   - How to send images, Box, limits and cost: the `building-with-jev`
     skill's `references/images.md`.
9. **The owner's eyes recalibrate the map.** When the owner disagrees with
   Jev, write the owner's observation into the matching ladder level as a
   signal, re-score the baseline, and carry on from there. Never argue the
   owner out of it with a Jev score.
10. **Report the climb.** For each round: the ladder level before and after
   (with probabilities), the measured numbers, what was kept and reverted,
   and the open gaps ranked by Jev.

**One round, in order:**
1. Produce the output for the kept version and the candidate (render, run, time).
2. Measure both the same way and write the observations into one state, with
   the references and the owner's notes.
3. Send one request:
   - `level`: Score on the ladder, asked for each version;
   - `better`: Noul "candidate reads better than kept", for each trait and group;
   - `worse`: Noul "anything got worse or blocks";
   - `next`: Choice of the next gap to work, from the open gaps.
4. Default keep bar, unless the task sets a stricter one: `better` ≥ 0.7 on
   the target trait, `worse` < 0.4, and no measured guard broken. A Noul in
   0.4–0.6 is not an answer; sharpen the question or the evidence and ask again.
5. Keep or revert, log the JSON, and work on `next`. Stop when the target
   level is reached, or after two rounds with no kept step; then report the
   blocker instead of tuning further.

Minimal question set:
```python
LADDER = [{"summary": "...", "signals": ["observable", "..."]}, ...]  # 3-5 levels
q = {
  "level_kept": {"type": "score", "instructions": "Where does the KEPT version sit?", "criteria": LADDER},
  "level_cand": {"type": "score", "instructions": "Where does the CANDIDATE sit?", "criteria": LADDER},
  "better_face": {"type": "noul", "instructions": "True when the candidate's faces read better than kept at game size. False when same or worse."},
  "worse": {"type": "noul", "instructions": "True when anything in the candidate got worse or would block shipping. False otherwise."},
  "next": {"type": "choice", "instructions": "Which open gap should the next round work on?", "criteria": {"gap_a": "...", "gap_b": "..."}},
}
jev_transport.evaluate_packed(state, q, timeout=90)
```


## Escalating an undecided answer (moved from ~/.claude/CLAUDE.md)
When Jev stays undecided after one sharpening (Noul 0.4–0.6, split Choice or Score), escalate that decision to a stronger model instead of looping, but only when the split options differ in consequence. First merge equivalent options and drop illegal ones, and read the Choice margin (`p_max / p_second`; below 2 is unstable, per `scripts/jev_choice.py`) rather than a fixed top-p bar. A split between harmless, interchangeable options is fine: take the argmax.
