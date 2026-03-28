# Writing Rubric — Joy-Grievance Spectrum

This rubric applies to human-facing content: blog posts, emails, articles, documentation meant to be read by people.

## Joy Framing Rubric

Every paragraph should frame its subject through curiosity, wonder, generosity, or earned satisfaction. Content that builds a case for grievance alienates readers and undermines the author's credibility, even when the underlying experience is legitimate.

| Dimension | Joy-Centered (PASS) | Grievance-Centered (FAIL) |
|-----------|-------------------|--------------------------|
| **Subject position** | Author as explorer, builder, learner | Author as victim, wronged party, unrecognized genius |
| **Other people** | Fellow travelers, interesting minds, people figuring things out | Opponents, thieves, people who should have done better |
| **Difficult experiences** | Interesting, surprising, made me think differently | Unfair, hurtful, someone should fix this |
| **Uncertainty** | Comfortable, curious, "none of us know" | Anxious, defensive, "I need to prove" |
| **Action framing** | "I decided to", "I realized", "I learned" | "I was forced to", "I had no choice", "they made me" |
| **Closing energy** | Forward-looking, building, sharing, exploring | Cautionary, warning, demanding, lamenting |

## Subtle Patterns (LLM-only detection)

These patterns are what the regex scanner cannot catch — the primary purpose of LLM analysis:

- **Defensive disclaimers** ("I'm not accusing anyone", "This isn't about blame"): If the author has to disclaim, the framing is already grievance-adjacent. The disclaimer signals the content that follows is accusatory enough to need a shield. Flag the paragraph and recommend removing both the disclaimer and the accusatory content it shields.
- **Accumulative grievance**: Each paragraph is individually mild, but together they build a case for being wronged. A reader who finishes the piece feeling "that person was wronged" has been led through a prosecution. Flag the accumulation pattern and recommend interspersing observations with what the author learned, built, or found interesting.
- **Passive-aggressive factuality** ("The timeline shows X. The repo was created Y days later. I'll let you draw your own conclusions."): Presenting facts in prosecution order is framing, not neutrality. "I'll let you draw your own conclusions" deputizes the reader as jury. Flag and recommend including facts where relevant to the experience, not as evidence.
- **Reluctant generosity** ("I'm not saying they did anything wrong, BUT..."): The "but" negates the generosity. This is grievance wearing a generous mask. Flag and recommend being generous without qualification, or acknowledging the complexity directly.

## Scoring

| Score | Label | Meaning |
|-------|-------|---------|
| 80-100 | **JOY** | Frames through curiosity, generosity, or earned satisfaction |
| 50-79 | **NEUTRAL** | Factual, neither joy nor grievance |
| 30-49 | **CAUTION** | Leans toward grievance but recoverable with reframing |
| 0-29 | **GRIEVANCE** | Frames through accusation, victimhood, or bitterness |

**Pass criteria**: Score >= 60 AND no GRIEVANCE paragraphs.

## The Joy Principle

**A difficult experience is not a negative topic.** Seeing your architecture appear elsewhere is interesting. Navigating provenance in the AI age is worth writing about. The topic can involve confusion, surprise, even frustration.

**The framing is what matters.** The same experience can be told as:
- "Someone took my work" (grievance)
- "I saw my patterns show up somewhere unexpected and it made me think about how ideas move now" (joy/curiosity)

Both describe the same events. The second frames it through the lens that defines joy-centered content: the specific satisfaction found in understanding something you didn't understand before.

**Joy doesn't mean happiness.** It means engagement, curiosity, the energy of figuring things out. A joy-centered post about a frustrating debugging session isn't happy — but it frames the frustration as the puzzle and the understanding as the reward. That's the lens.

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
people who are unaware of where it came from, then I might as well just
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
I have no answer for the provenance problem. But I'm going to keep
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
come from?" might be "I built it with Claude and I have no way of knowing what
Claude drew on." That's true for everyone using these tools. Including me.
```

**Why the second works:** Includes the author in the same uncertainty. "Including me" is the key phrase. It transforms from "I know and they should know" to "none of us fully know."
