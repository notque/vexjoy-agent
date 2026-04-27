# Extraction Validation -- Triple-Validation Gate

Detailed reference for Step 3 (PATTERN) and Step 4 (RULE) of the create-voice
pipeline. This rubric decides which extracted patterns are kept in the voice
profile and which are discarded.

The principle: a voice profile is only as strong as the patterns it captures.
Patterns that survive all three checks below carry real signal about how the
person thinks and writes. Patterns that pass on intuition alone tend to be
generic observations dressed up as voice traits.

---

## The Triple-Validation Rubric

A voice trait, mental model, phrase fingerprint, or thinking pattern is kept
in the profile only when **all three** of the following hold:

1. **Cross-domain recurrence**: the pattern appears in at least two distinct
   sources or domains (e.g. blog posts AND chat replies; technical writing
   AND casual writing; long-form essays AND short-form replies).
2. **Generative power**: the pattern lets you predict, with reasonable
   confidence, how the person would respond to a NEW situation they haven't
   written about. The pattern produces new output, not just descriptions of
   old output.
3. **Distinguishing exclusivity**: the pattern is specific enough to
   distinguish this person from their peers in the same field. It would feel
   wrong attributed to a similar writer in the same genre.

Patterns that satisfy all three checks earn a place in the voice profile.
Patterns that satisfy two earn a footnote ("observed in domain X, weak in
domain Y") so the voice-writer knows to use them with care. Patterns that
satisfy only one are discarded; they're either noise from the corpus or
generic-writer features the model already produces by default.

---

## Apply the Rubric to Each Extracted Pattern

Document each candidate with this template:

```
### Pattern: <short name>
- Recurrence: <list 2+ sources/domains where it appears, with quotes>
- Generative test: <a NEW situation + the predicted response shape>
- Exclusivity: <name 1-2 peers in the same genre + what they do differently>
- Verdict: KEEP / FOOTNOTE / DROP
- If KEEP, where it lives in the profile: <SKILL.md section, profile.json field>
```

The verdict is positive: KEEP a pattern when all three checks pass. FOOTNOTE
a pattern that passes two of three. DROP a pattern that passes one or none --
those slots are better spent on patterns with stronger signal.

---

## Worked Examples

### Example 1: KEEP -- Andy's Calibration Questions

- **Recurrence**: Appears in his blog posts ("So is the answer to just keep
  context windows shorter?"), in his HN comments ("am I missing something
  obvious here?"), and in his chat replies ("does that match your
  experience?"). Three distinct domains, same move.
- **Generative test**: Prompted with "what do you think about the new Claude
  release?", we'd predict an opener like "what's the actual workflow change
  here, am I missing it?" rather than a flat assessment. The pattern
  generates new text that matches voice.
- **Exclusivity**: Other AI-tooling writers state confident takes; Andy
  reliably opens with calibration. Distinguishes him from peers in the same
  genre.
- **Verdict**: KEEP. Lives in `SKILL.md` thinking-patterns and
  fingerprints sections.

### Example 2: KEEP -- Feynman's Mechanism-First Framing

- **Recurrence**: His Caltech lectures, his memos, and his Challenger appendix
  all open by laying out a physical mechanism before assigning blame or
  importance. Cross-domain across teaching, technical writing, and
  investigative work.
- **Generative test**: Asked about a new technology, he'd describe what is
  physically happening before judging it. The pattern predicts new output.
- **Exclusivity**: Other physicists of his generation default to formalism or
  authority-citing. Feynman's mechanism-first move is recognisably his own.
- **Verdict**: KEEP. Documented as a thinking pattern with quotes from each
  domain.

### Example 3: FOOTNOTE -- VexJoy's Household Analogies

- **Recurrence**: Strong in long-form blog posts ("the toolbox", "the filing
  cabinet"), nearly absent in chat replies. One domain, partially.
- **Generative test**: Prompted with a tooling question, the analogy tendency
  predicts new output -- but only in long-form mode.
- **Exclusivity**: Distinguishing within tech-writing peers, who mostly use
  industrial or game analogies.
- **Verdict**: FOOTNOTE -- "applies to long-form mode; do not force in
  short-form chat replies".

### Example 4: DROP -- "Uses contractions"

- **Recurrence**: Yes, contractions appear everywhere in the corpus.
- **Generative test**: Predicts no new output -- every casual writer uses
  contractions.
- **Exclusivity**: Fails. This pattern fits any informal writer in English.
- **Verdict**: DROP from the qualitative pattern list. The contraction RATE
  still belongs in `profile.json` (it's a quantitative metric), but it's not
  a distinctive pattern worth a SKILL.md callout.

### Example 5: DROP -- "Sometimes uses em-dashes"

- **Recurrence**: Sporadic, no clear domain pattern.
- **Generative test**: Doesn't predict new output -- the use is too
  inconsistent to anchor on.
- **Exclusivity**: Em-dashes are common in casual writing and notorious in
  AI-generated text. The pattern would push the voice toward a known AI tell.
- **Verdict**: DROP. Em-dashes belong in the banned-pattern list, not the
  positive pattern list.

---

## How This Wires Into the Pipeline

- **Step 3 (PATTERN)**: every extracted pattern is run through the rubric
  before it's documented. Show the verdict inline with the pattern. The Step 3
  gate requires that documented patterns each carry an explicit KEEP or
  FOOTNOTE verdict with evidence for all three checks.
- **Step 4 (RULE)**: rules are derived only from KEEP and FOOTNOTE patterns.
  Dropped patterns never reach the rules document.
- **Step 5 (GENERATE)**: the generated SKILL.md cites the verdict per
  pattern so future maintainers know what survived the gate and why.

A pattern that can't pass triple-validation is a pattern that will degrade
the voice when the model leans on it. Spending the gate's effort upfront
saves correction work in Step 6 (VALIDATE) and Step 7 (ITERATE).

---

## Citation

The triple-check rubric (cross-domain recurrence + generative power +
exclusivity) originates with the `alchaincyf/nuwa-skill` extraction
framework. We adopted the three checks; the wiring into Step 3 / Step 4
gates, the verdict vocabulary (KEEP / FOOTNOTE / DROP), and the toolkit
examples are ours.
