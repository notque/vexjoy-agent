---
name: joy-check
description: |
  Validate content for joy-centered tonal framing. Evaluates paragraphs on a
  joy-grievance spectrum, flags defensive, accusatory, victimhood, or bitter
  framing, and suggests reframes. Use when user says "joy check", "check
  framing", "tone check", "negative framing", "is this too negative", or
  "reframe this positively". Use for any content where positive, curious,
  generous framing matters. Do NOT use for voice validation (use
  voice-validator), AI pattern detection (use anti-ai-editor), or grammar
  and style editing.
version: 1.0.0
user-invocable: false
argument-hint: "[--fix] [--strict] <file>"
command: /joy-check
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - joy check
    - check framing
    - tone check
    - negative framing
    - joy validation
    - too negative
    - reframe positively
  pairs_with:
    - voice-writer
    - anti-ai-editor
    - voice-validator
  complexity: Simple
  category: content
---

# Joy Check

## Operator Context

This skill operates as an operator for tonal framing validation, configuring Claude's behavior for evaluating whether content frames experiences through joy, curiosity, and generosity rather than grievance, accusation, or victimhood. It implements the **Two-Pass Validation** architectural pattern -- deterministic regex pre-filter followed by LLM semantic analysis -- to catch both obvious and subtle negative framing.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before validating
- **Joy is the lens**: Every paragraph should frame its subject through curiosity, wonder, generosity, or earned satisfaction -- because content that builds a case for grievance alienates readers and undermines the author's credibility, even when the underlying experience is legitimate
- **No grievance framing**: Content should never build a case for being wronged -- because accumulating evidence of injustice reads as prosecution, not communication
- **No accusation framing**: Content should never point fingers at specific people or imply bad faith -- because attributing motive to others is speculation wearing the mask of observation
- **No victimhood framing**: Content should never position the author as a victim -- because it shifts agency from the author to external forces
- **Reframe, don't suppress**: Negative experiences are valid topics. The skill checks *framing*, not *topic*. A difficult experience can be framed through what you learned, what you built, or what you now understand. Suppressing legitimate experiences would be dishonest; reframing them through curiosity is editorial craft.

### Default Behaviors (ON unless disabled)
- **Paragraph-level analysis**: Evaluate each paragraph independently against the Joy Framing Rubric
- **Regex pre-filter**: Run `scan-negative-framing.py` first as a fast gate -- catches obvious patterns without spending LLM tokens
- **Suggestion mode**: Flag and suggest reframes without modifying content
- **Score output**: Produce a joy score (0-100) for the full piece

### Optional Behaviors (OFF unless enabled)
- **Fix mode** (--fix): Rewrite flagged paragraphs in place, then re-verify
- **Strict mode** (--strict): Fail on any paragraph below 60 joy score

## What This Skill CAN Do
- Evaluate tonal framing at the paragraph level using the Joy Framing Rubric
- Detect subtle grievance, accusation, and victimhood patterns that regex misses (passive-aggressive factuality, accumulative grievance, reluctant generosity)
- Suggest positive reframes for negatively-framed paragraphs
- Produce a joy score (0-100) for publication readiness
- Rewrite flagged paragraphs in fix mode while preserving substance

## What This Skill CANNOT Do
- Evaluate voice authenticity (use voice-validator for that)
- Detect AI writing patterns (use anti-ai-editor for that)
- Change the topic or substance of content (only reframes the framing)
- Evaluate factual accuracy or grammar (out of scope entirely)

---

## Instructions

### Phase 1: PRE-FILTER

**Goal**: Use the regex scanner as a fast gate to catch obvious negative framing before spending LLM tokens on semantic analysis.

**Step 1: Run the regex-based scanner**

```bash
python3 ~/.claude/scripts/scan-negative-framing.py [file]
```

**Step 2: Handle regex hits**

If the scanner finds hits, these are obvious negative framing patterns (victimhood, accusation, bitterness, passive aggression). Report them to the user with the scanner's suggested reframes. These do not require LLM evaluation -- the regex patterns are high-confidence matches.

If `--fix` mode is active, apply the scanner's suggested reframes and re-run to confirm clean.

**GATE**: Regex scan returns zero hits. If hits remain after reporting/fixing, do NOT proceed to Phase 2 -- the obvious patterns must be resolved first. Proceeding with known regex hits would waste LLM analysis on paragraphs that need mechanical fixes.

### Phase 2: ANALYZE

**Goal**: Read the content and evaluate each paragraph against the Joy Framing Rubric using LLM semantic understanding.

**Step 1: Read the content**

Read the full file. Identify paragraph boundaries (blank-line separated blocks). Skip frontmatter (YAML between `---` markers), code blocks, and blockquotes.

**Step 2: Evaluate each paragraph against the Joy Framing Rubric**

| Dimension | Joy-Centered (PASS) | Grievance-Centered (FAIL) |
|-----------|-------------------|--------------------------|
| **Subject position** | Author as explorer, builder, learner | Author as victim, wronged party, unrecognized genius |
| **Other people** | Fellow travelers, interesting minds, people figuring things out | Opponents, thieves, people who should have done better |
| **Difficult experiences** | Interesting, surprising, made me think differently | Unfair, hurtful, someone should fix this |
| **Uncertainty** | Comfortable, curious, "none of us know" | Anxious, defensive, "I need to prove" |
| **Action framing** | "I decided to", "I realized", "I learned" | "I was forced to", "I had no choice", "they made me" |
| **Closing energy** | Forward-looking, building, sharing, exploring | Cautionary, warning, demanding, lamenting |

**Step 3: Score each paragraph**

For each paragraph, assign one of:
- **JOY** (80-100): Frames through curiosity, generosity, or earned satisfaction
- **NEUTRAL** (50-79): Factual, neither joy nor grievance
- **CAUTION** (30-49): Leans toward grievance but recoverable with reframing
- **GRIEVANCE** (0-29): Frames through accusation, victimhood, or bitterness

For any paragraph scored CAUTION or GRIEVANCE, draft a specific reframe suggestion that preserves the substance while shifting the framing toward curiosity or generosity.

**GATE**: All paragraphs analyzed and scored. Reframe suggestions drafted for all CAUTION and GRIEVANCE paragraphs. Proceed to Phase 3.

### Phase 3: REPORT

**Goal**: Produce a structured report with scores, findings, and reframe suggestions.

**Step 1: Calculate overall score**

Average all paragraph scores. The overall score determines pass/fail:
- **PASS**: Score >= 60 AND no GRIEVANCE paragraphs
- **FAIL**: Score < 60 OR any GRIEVANCE paragraph present

**Step 2: Output the report**

```
JOY CHECK: [file]
Score: [0-100]
Status: PASS / FAIL

Paragraphs:
  P1 (L10-12): JOY [85] -- explorer framing, curiosity
  P2 (L14-16): NEUTRAL [65] -- factual timeline
  P3 (L18-22): CAUTION [40] -- "confused" leans defensive
    -> Reframe: Focus on what you learned from the confusion
  P4 (L24-28): JOY [90] -- generous framing of others

Overall: [summary of tonal arc -- where the piece starts, how it moves, where it lands]
```

**Step 3: Handle fix mode**

If `--fix` mode is active:
1. Rewrite any CAUTION or GRIEVANCE paragraphs using the drafted reframe suggestions
2. Preserve the substance -- change only the framing
3. Re-run Phase 2 analysis on the rewritten paragraphs to verify fixes landed
4. If fixes introduce new CAUTION/GRIEVANCE scores, iterate (maximum 3 attempts)

**GATE**: Report produced. If `--fix`, all rewrites applied and re-verified. Joy check complete.

---

## The Joy Principle

This is the editorial philosophy that drives the check.

**A difficult experience is not a negative topic.** Seeing your architecture appear elsewhere is interesting. Navigating provenance in the AI age is worth writing about. The topic can involve confusion, surprise, even frustration.

**The framing is what matters.** The same experience can be told as:
- "Someone took my work" (grievance)
- "I saw my patterns show up somewhere unexpected and it made me think about how ideas move now" (joy/curiosity)

Both describe the same events. The second frames it through the lens that defines joy-centered content: the specific satisfaction found in understanding something you didn't understand before.

**Joy doesn't mean happiness.** It means engagement, curiosity, the energy of figuring things out. A joy-centered post about a frustrating debugging session isn't happy -- but it frames the frustration as the puzzle and the understanding as the reward. That's the lens.

---

## Examples

These examples show the same content reframed from grievance to joy. The substance is identical. Only the framing changes.

### Example 1: Describing a Difficult Experience

**GRIEVANCE (FAIL):**
```
I spent nine months building this system and nobody cared. Then someone
else showed up with the same thing and got all the attention. It felt
unfair. I did the work and they got the credit.
```

**JOY (PASS):**
```
I've been building and writing about this architecture for about nine
months now. The response has been mostly crickets. Some good conversations,
some pushback, but nothing that made me feel like the ideas were landing.
Then someone posted a system with the same concepts and I got excited.
Someone else got it.
```

**Why the second works:** The author is an explorer who found something interesting, not a victim cataloguing injustice. "Mostly crickets" is honest without being bitter. "Someone else got it" is generous.

### Example 2: Discovering Similarity

**GRIEVANCE (FAIL):**
```
I was shocked to find they had copied my exact architecture. The same
router, the same dispatch pattern, the same four layers. They claimed
they invented it independently, which seems unlikely given the timing.
```

**JOY (PASS):**
```
I went from excited to curious. Because this wasn't just someone building
agents and skills, which plenty of people do. It was the routing
architecture I'd spent months developing and writing about.
```

**Why the second works:** "Excited to curious" is an explorer's arc. No accusation of copying. The observation is about what the author found interesting, not what was done to them.

### Example 3: Discussing How Ideas Spread

**GRIEVANCE (FAIL):**
```
If the ideas are going to spread through AI's training data anyway, if
Claude is going to absorb my blog posts and hand the architecture to
people who don't know where it came from, then I might as well just
give up trying to get credit.
```

**JOY (PASS):**
```
This experience helped me realize that the best thing I can do with
these ideas is just put them out there completely. No holding back,
no waiting for the perfect moment. If the patterns are useful, people
should have them. If someone builds something better on top of them,
even better.
```

**Why the second works:** The decision to release is framed as a positive realization, not a resignation. "Even better" at the end carries forward energy.

### Example 4: Talking About Credit

**GRIEVANCE (FAIL):**
```
I've been thinking about why this bothered me, and it's because I
deserve recognition for this work. Nine months of effort should count
for something.
```

**JOY (PASS):**
```
I've been thinking about what made this experience interesting, and
it's not about credit. I just want to communicate the value as I see
it, and be understood.
```

**Why the second works:** Locates the feeling in curiosity ("what made this interesting") not entitlement ("I deserve"). "Be understood" is a human need, not a demand.

### Example 5: The Conclusion

**GRIEVANCE (FAIL):**
```
I don't know how to fix the provenance problem. But I'm going to keep
documenting my work publicly so at least there's a record. If nothing
else, the timestamps speak for themselves.
```

**JOY (PASS):**
```
I may never be an influencer. I'm probably never going to be known much
outside of the specific things I work on. I just enjoy coming up with
interesting and novel ideas, trying weird things, seeing what sticks.
That's been the most enjoyable part of this whole process.
```

**Why the second works:** Ends on what the author enjoys, not what they're defending against. "Seeing what sticks" carries the experimental energy. No timestamps-as-evidence framing.

### Example 6: Addressing Uncertainty About Origins

**GRIEVANCE (FAIL):**
```
They might not know where the patterns came from. But I do. And the
timeline doesn't lie.
```

**JOY (PASS):**
```
Claude doesn't cite its sources. There's no way for any of us to tell
whether our AI-assisted work drew on someone else's blog post or was
synthesized fresh. The honest answer to "where did this architecture
come from?" might be "I built it with Claude and I don't know what
Claude drew on." That's true for everyone using these tools. Including me.
```

**Why the second works:** Includes the author in the same uncertainty. "Including me" is the key phrase. It transforms from "I know and they should know" to "none of us fully know."

---

## Error Handling

### Error: "File Not Found"
**Cause**: Path incorrect or file does not exist
**Solution**:
1. Verify path with `ls -la [path]`
2. Use glob pattern to search: `Glob **/*.md`
3. Confirm correct working directory

### Error: "Regex Scanner Fails or Not Found"
**Cause**: `scan-negative-framing.py` script missing or Python error
**Solution**:
1. Verify script exists: `ls scripts/scan-negative-framing.py`
2. Check Python version: `python3 --version` (requires 3.10+)
3. If script unavailable, skip Phase 1 and proceed directly to Phase 2 LLM analysis -- the regex pre-filter is an optimization, not a requirement

### Error: "All Paragraphs Score GRIEVANCE"
**Cause**: Content is fundamentally framed through grievance -- not recoverable with paragraph-level reframes
**Solution**:
1. Report the scores honestly
2. Suggest the content needs a full rewrite with a different framing premise, not paragraph-level fixes
3. Point the user to the Joy Principle section and Examples for guidance on the target framing

### Error: "Fix Mode Fails After 3 Iterations"
**Cause**: Rewritten paragraphs keep introducing new CAUTION/GRIEVANCE patterns, often because the underlying premise is grievance-based
**Solution**:
1. Output the best version achieved with flagged remaining concerns
2. Explain which specific rubric dimensions resist correction
3. Suggest the framing premise itself may need rethinking, not just the language

---

## Anti-Patterns

### Anti-Pattern 1: Defensive Disclaimers
**What it looks like**: "I'm not accusing anyone" / "This isn't about blame"
**Why wrong**: If you have to disclaim, the framing is already grievance-adjacent. The disclaimer signals that the content that follows is accusatory enough to need a shield.
**Do instead**: Remove the disclaimer AND reframe the content so the disclaimer isn't needed.

### Anti-Pattern 2: Accumulative Grievance
**What it looks like**: Each paragraph adds another piece of evidence for being wronged
**Why wrong**: Even if each paragraph is mild, the accumulation builds a case. A reader who finishes the piece feeling "that person was wronged" has been led through a prosecution.
**Do instead**: Intersperse observations with what you learned, built, or found interesting. Break the evidence chain.

### Anti-Pattern 3: Passive-Aggressive Factuality
**What it looks like**: "The timeline shows X. The repo was created Y days later. I'll let you draw your own conclusions."
**Why wrong**: Presenting facts in prosecution order is framing, not neutrality. "I'll let you draw your own conclusions" is the most aggressive form of accusation -- it deputizes the reader.
**Do instead**: Include facts where relevant to the experience, not as evidence. If the timeline is interesting, say why it's interesting, not why it's damning.

### Anti-Pattern 4: Reluctant Generosity
**What it looks like**: "I'm not saying they did anything wrong, BUT..."
**Why wrong**: The "but" negates the generosity. This is grievance wearing a generous mask. Readers hear the "but" louder than the generosity.
**Do instead**: Be generous without qualification, or acknowledge the complexity directly. "This is a complicated situation" is more honest than "They're great, BUT..."

---

## Integration

This skill integrates with the content validation pipeline:

```
CONTENT --> voice-validator (deterministic) --> scan-ai-patterns (deterministic)
        --> scan-negative-framing (regex pre-filter) --> joy-check (LLM analysis)
        --> anti-ai-editor (LLM style fixes)
```

The joy-check can be invoked standalone via `/joy-check [file]` or as part of the content pipeline for any content where positive framing matters.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The content is factual, so it's fine" | Facts arranged as prosecution are framing, not neutrality | Evaluate the *arrangement* of facts, not just their accuracy |
| "The author earned the right to be upset" | Earned anger is still grievance framing | Check framing, not whether the feeling is justified |
| "It's only one negative paragraph" | One GRIEVANCE paragraph poisons the tonal arc of the whole piece | Flag it. One grievance paragraph is a FAIL condition |
| "The reframe would be dishonest" | Reframing is editorial craft, not dishonesty -- the substance stays the same | Preserve substance, change only the lens |
| "This is too subtle to flag" | Subtle grievance is the hardest to catch and the most important -- it's what regex misses | If it reads as building a case, flag it |

### Related Skills and Scripts
- `scan-negative-framing.py` -- Regex pre-filter for obvious negative framing patterns (Phase 1)
- `voice-validator` -- Voice fidelity validation (complementary, different concern)
- `anti-ai-editor` -- AI pattern detection and removal (complementary, different concern)
- `voice-writer` -- Multi-step content pipeline that can invoke joy-check as a validation phase
