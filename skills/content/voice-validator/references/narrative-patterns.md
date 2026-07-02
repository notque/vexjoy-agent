# Narrative Structure Patterns

The 13-check Narrative rubric. Source: Russell et al. (2026), "StoryScope: Towards Comprehensive Narratological Evaluation of LLM-Generated Stories," arXiv:2604.03136v4, University of Maryland. 61,608 stories, 10,272 prompts, 304 narrative features, 5 AI models. The checks below adapt StoryScope's fiction features to nonfiction: arguments instead of plots, named actors and sources instead of characters, endings instead of resolutions.

**Applicability**: content over 500 words. Skip this checklist for captions, tweets, and short social posts. `voice-validator` runs this rubric as its Narrative category; the private de-AI editor skill runs the same checks as its Narrative Structure category (its own `references/narrative-patterns.md`).

**Why narrative checks matter**: surface tells (word choice, cliches, sentence rhythm) get edited away; narrative structure survives stylistic editing. StoryScope reports 93.9% macro-F1 for human-vs-AI detection after LAMP rewriting stripped every stylistic cue. The structural fingerprint persists when every surface tell is patched.

**Known limit**: StoryScope measured fiction. The nonfiction rephrasing here is an adaptation. Transfer to argumentative prose is assumed, not yet measured. StoryScope's Dream/Vision Avoidance feature (SHAP 0.116) is dropped deliberately: dream and vision sequences are fiction devices with no nonfiction counterpart.

**How to run it**: these are LLM-judgment checks, not regex patterns. Read the whole piece, score each check pass or fail against its test, count the fails, apply the scoring table at the end. Every fail must cite a specific quote or location.

---

## Universal Patterns (Checks 1-8)

Present across all five models StoryScope tested, each with a measured human-vs-AI gap.

### 1. Theme Over-Explanation

**Signal**: The narrator states the takeaway in abstract terms: "the lesson here is", "what this means is", a moral paragraph after the evidence. StoryScope: 77% of AI stories explain their theme vs 52% human (25-point gap).

**Human contrast**: Evidence carries the meaning. Facts, quotes, and moments make the point; the reader is trusted to land on it.

**Pass/fail test**: Find every sentence that restates the piece's point in abstract terms. Pass if the point is stated at most once and the evidence still carries it with that sentence deleted. Fail if the takeaway is spelled out more than once, or if deleting the explanation leaves evidence that no longer makes the point. Fix the evidence, then cut the explanation.

### 2. Single-Track Argument

**Signal**: The piece runs straight from thesis to conclusion. No tangents, counter-examples, or asides. StoryScope: 79% of AI stories have no subplot vs 57% human (22-point gap).

**Human contrast**: Secondary threads. A tangent, a counter-example, an aside that returns to enrich the main argument. Real writers wander productively.

**Pass/fail test**: Count the threads that depart from the main argument and return to feed it. Pass: one or more. Fail: zero.

### 3. Strict-Linear Time

**Signal**: Every section moves forward in strict chronological or logical order. No callbacks, no jumps. StoryScope non-linearity scale: 2.12 AI vs 2.40 human.

**Human contrast**: A callback to an earlier point, a flash-forward, an opening that starts at the outcome and explains how it happened, a "remember when" return.

**Pass/fail test**: Count the moves that break strict order (callback, flash-forward, non-linear opening). Pass: one or more. Fail: zero.

### 4. Tidy-Realization or Epilogue Ending

**Signal**: The piece ends on an internal realization ("and then I understood...") or a future-gesturing wrap-up paragraph that adds no information. Realization endings: 47% AI vs 27% human (20-point gap). The epilogue preference is also a Claude fingerprint (SHAP 0.096).

**Human contrast**: Endings with forward motion: a concrete action, an open question, a dated plan, tension left standing.

**Pass/fail test**: Read the final two paragraphs. Pass if the ending carries new information or forward motion (specific next step, open question, standing tension). Fail if it restates the piece, gestures at "what comes next" in general terms, or settles into a neat realization.

### 5. Resolved Ambiguity

**Signal**: The subject has the answer to every question the piece raises; every judgment is settled by the end. StoryScope: the protagonist's choices drive all resolution in 69% of AI stories vs 46% human (23-point gap).

**Human contrast**: Luck, timing, other people's decisions, loose ends. The piece says "I don't know" somewhere it matters, and a moral or open question is left standing.

**Pass/fail test**: List the questions the piece raises. Pass if at least one stays open, or is resolved by something outside the subject's control. Fail if every question closes and the subject's own choices close them all.

### 6. Single Emotional Register

**Signal**: Emotion arrives through one channel only, usually bodily sensation (tight chest, cold sweat, breath catching). StoryScope: 81% AI vs 38% human (42-point gap, the largest in the set).

**Human contrast**: Mixed registers. Named feelings ("I was afraid"), behavioral cues ("I closed the laptop"), sensation, plain statement.

**Pass/fail test**: Mark each emotional beat by register. Pass: two or more registers across the piece. Fail: one register throughout.

### 7. Vague References

**Signal**: "Experts say", "as many have noted", "studies show", with no names attached. StoryScope: implicit, unnamed references in 72% of AI stories vs 50% human (22-point gap).

**Human contrast**: Named people, named works, dates, publications. "Russell et al. (2026) measured" carries authority that "researchers found" lacks.

**Pass/fail test**: List every external claim. Pass if each load-bearing claim names its source. Fail if any load-bearing claim rests on an unnamed authority.

### 8. Reader Never Addressed

**Signal**: The piece is written as if no one is reading: purely declarative from first line to last. StoryScope: 93% of AI stories ignore the reader vs 72% human (21-point gap).

**Human contrast**: "You have probably seen this", "if you have tried X, you know". The prose admits a reader exists.

**Pass/fail test**: Search for direct address or an appeal to the reader's likely experience. Pass: present at least once where the target voice allows it. Fail: absent in a piece whose voice profile is conversational. Formal voices that exclude direct address pass on an implied reader (anticipating an objection counts).

---

## Model Fingerprints and Adapted Checks (Checks 9-13)

Checks 9, 10, and 13 are Claude-specific fingerprints (we generate with Claude; these are self-awareness checks). Checks 11 and 12 adapt StoryScope's discourse-structure and character-agency features to nonfiction; they carry no measured percentage gap yet.

### 9. Flat Escalation

**Signal**: Stakes and intensity hold level from start to finish, or climb in one even ramp. Every section sits at the same emotional temperature. The single strongest Claude discriminator (SHAP 0.402).

**Human contrast**: Escalation in bursts. Stakes ratchet at a specific moment, then release. Peaks and valleys.

**Pass/fail test**: Sketch the intensity curve section by section. Pass: at least one identifiable peak and one valley. Fail: a flat line, or a strictly linear ramp with no release.

### 10. Uniform Event Types

**Signal**: Every paragraph makes the same move: explain, evidence, explain, evidence. Narrow range of what happens in the piece (SHAP 0.491, Claude fingerprint).

**Human contrast**: At least one move the reader would not predict from the opening: a surprising data point, an unexpected reaction, a reversal.

**Pass/fail test**: Label each paragraph's move type. Pass: three or more distinct move types and at least one unpredicted turn. Fail: two move types alternating throughout.

### 11. Front-Loaded Conclusion

**Signal**: The full conclusion arrives in the opening and every later section justifies it backward. No claim is ever at risk. Adapted from StoryScope's discourse-structure features.

**Human contrast**: An inductive build. Evidence accumulates, the conclusion forms in front of the reader, and early sections leave the outcome genuinely uncertain. A front-loaded thesis can also pass when later sections test it for real.

**Pass/fail test**: Locate where the piece's main conclusion first appears in full. Pass if it forms after the evidence, or if it is front-loaded and at least one later section runs a test that could have broken it. Fail if the opening states the conclusion and nothing afterward puts it at risk.

### 12. Agentless Action

**Signal**: Things happen with no named actor ("the system was improved", "mistakes were made"), or one actor does everything and is never stuck. Adapted from StoryScope's character-agency features: AI protagonists act decisively; human subjects get stuck, decide partially, and react to forces outside their control.

**Human contrast**: Visible actors with mixed agency. Specific people do specific things, and at least one of them stalls, reverses, or responds to something they did not choose.

**Pass/fail test**: For each major action in the piece, name who did it. Pass: actions have named actors, and at least one moment shows an actor stuck or reacting rather than driving. Fail: actions float without actors, or a single subject acts decisively at every turn.

### 13. Reverent Structure

**Signal**: The piece honors every convention of its genre. Nothing is subverted; everything feels proper. StoryScope: 62% of Claude stories take the reverent/continuist approach.

**Human contrast**: One subverted expectation per piece: a counter-intuitive lead, a challenged convention, a position the reader might push back on.

**Pass/fail test**: Name the expectation the piece subverts. Pass: you can point to one. Fail: you cannot.

---

## Scoring

Count fails across all 13 checks.

| Fails | Assessment | Action |
|-------|-----------|--------|
| 0-2 | Natural narrative structure | No narrative revision needed |
| 3-5 | Narrative revision warranted | Address the flagged checks |
| 6+ | Structural rewrite needed | Rebuild the piece's architecture, not just surface edits |

The percentages above ground the judgment: most measured checks carry a >=20-point gap (or a top SHAP value) between human and AI writing. Checks 11 and 12 are adapted features awaiting their own measurement; weight them as judgment calls, not measured gaps.

---

## Evidence Summary

| Metric | Value |
|--------|-------|
| Narrative features alone (macro-F1) | 93.2% |
| After LAMP stylistic editing (macro-F1) | 93.9% |
| Human structural rarity (mean percentile) | 0.71 |
| AI structural rarity (mean percentile) | 0.49 |
| Rarity effect size (Cohen's d) | 0.83 |
| Core 30 features retain | 84.8% of full model performance |
| Claude 6-way attribution without style features (F1) | 77.1% |
