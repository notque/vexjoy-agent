# Writing Rubric: Joy-Grievance Spectrum

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

These patterns are what the regex scanner cannot catch. They are the primary purpose of LLM analysis:

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

**A difficult experience is not a negative topic.** Failure, confusion, being wrong, losing something. These are all worth writing about. The topic can involve surprise, frustration, even grief.

**The framing is what matters.** The same experience can be told as:
- "The project failed because leadership wouldn't listen" (grievance)
- "The project failed and it changed how I understand what makes a team actually work" (joy/curiosity)

Both describe the same events. The second frames it through the lens that defines joy-centered content: the specific satisfaction found in understanding something you didn't understand before.

**Joy doesn't mean happiness.** It means engagement, curiosity, the energy of figuring things out. A joy-centered post about a frustrating debugging session isn't happy. It frames the frustration as the puzzle and the understanding as the reward. That's the lens.

## Examples

These examples show the same content reframed from grievance to joy. Each covers a different topic to demonstrate that the pattern applies broadly. The substance stays. Only the framing changes.

### Example 1: A Project That Failed

**GRIEVANCE (FAIL):**
```
I spent six months building this and leadership killed it. They never
gave it a real chance. The team was understaffed, the deadline was
impossible, and when it didn't ship on time they blamed engineering.
```

**JOY (PASS):**
```
I spent six months on a project that got cancelled. The team was small,
the deadline was ambitious, and we didn't make it. What I didn't expect
was how much I'd learn about what makes a technical bet actually land
versus just being a good idea on paper.
```

**Why the second works:** The author is a learner extracting insight, not a victim cataloguing injustice. "What I didn't expect" signals curiosity. The failure is acknowledged but framed as the start of understanding.

### Example 2: Finding Someone Solved the Same Problem

**GRIEVANCE (FAIL):**
```
I was halfway through the implementation when I found an open-source
library that does the exact same thing. Six weeks of work, wasted.
If I'd found it earlier none of this would have happened.
```

**JOY (PASS):**
```
Halfway through, I found an open-source library that solved the same
problem. My first reaction was frustration, but then I started reading
their code. They'd made completely different trade-offs than I had,
and comparing the two taught me more about the problem space than
either approach alone.
```

**Why the second works:** "Started reading their code" is an explorer's response. The parallel work becomes a learning opportunity, not wasted effort. Frustration is acknowledged directly, then moved through.

### Example 3: Giving Away Work You Could Have Monetized

**GRIEVANCE (FAIL):**
```
I open-sourced the whole thing and nobody even starred the repo. People
are using it — I can see the clone stats — but nobody bothers to
contribute back or even say thanks. Open source is a thankless grind.
```

**JOY (PASS):**
```
I open-sourced it and the response was mostly quiet. Some clones, a
few issues filed, not much else. But every once in a while someone
emails to say it saved them a week of work, and that's a strange kind
of satisfaction, knowing something you built is just quietly useful
somewhere.
```

**Why the second works:** "Quietly useful" reframes silence as a form of impact. The author finds satisfaction in the work's utility rather than demanding visible reciprocity.

### Example 4: Being Passed Over for Recognition

**GRIEVANCE (FAIL):**
```
I've been thinking about why this bothered me, and it's because the
work speaks for itself. Two years of contributions and they promoted
someone who joined six months ago. Merit clearly doesn't matter here.
```

**JOY (PASS):**
```
I've been thinking about what I actually want from work, and it turns
out "being recognized" is too vague to be useful. What I want is to
work on problems that stretch me, with people who take the craft
seriously. Once I framed it that way, the promotion question got
a lot simpler.
```

**Why the second works:** Locates the feeling in self-knowledge ("what I actually want") not entitlement ("merit should be rewarded"). The author discovers something about themselves rather than building a case against someone else.

### Example 5: Wrapping Up a Career Transition

**GRIEVANCE (FAIL):**
```
I left because the industry stopped valuing the kind of deep work I
do. Everything is about speed now, shipping fast, cutting corners.
I refuse to compromise on quality, and if that means moving on, fine.
```

**JOY (PASS):**
```
I left because I wanted to find out what I'd build if I got to choose
the constraints. Turns out the answer is weirder and more interesting
than what I was building before. I don't know where it leads, but the
not-knowing is part of what makes it fun.
```

**Why the second works:** Ends on what the author is moving toward, not what they're escaping from. "The not-knowing is part of what makes it fun" carries experimental energy. No industry-as-villain framing.

### Example 6: Ambiguous Feedback from a Collaborator

**GRIEVANCE (FAIL):**
```
They said the design "needed more thought" but wouldn't say what was
wrong with it. Classic move — vague enough to block progress without
having to commit to an actual opinion.
```

**JOY (PASS):**
```
They said the design "needed more thought," which is the kind of
feedback that's frustrating in the moment but sometimes means there's
something I'm not seeing yet. I went back and sat with it for a day,
and they were right. There was a whole failure mode I'd been
hand-waving past.
```

**Why the second works:** The author sits with discomfort instead of building a case. "They were right" is generous without being self-deprecating. The frustration is honest but leads to discovery.
