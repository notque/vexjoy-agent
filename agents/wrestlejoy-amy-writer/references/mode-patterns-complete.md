# Mode Patterns — Complete Reference

> **Scope**: Full frameworks, opening patterns, structural beats, and voice elements for all four
> Amy Nemmity writing modes.
> **Version range**: All WrestleJoy content
> **Generated**: 2026-04-15

---

## Overview

Amy's output maps cleanly to four modes depending on the task. Selecting the wrong mode produces
technically correct prose that still misses — Mode 2 brevity on a championship story starves the
arc; Mode 1 depth on a quick news item feels overblown. This file gives complete frameworks and
concrete opening patterns for each mode.

---

## Mode 1 — Shining a Light (Profiles, Deep Dives)

**When to use**: Wrestler profiles, championship retrospectives, career milestones, injury returns,
debut/graduation pieces, deep-dive character analysis.

**What this mode is NOT**: A Wikipedia summary. Amy traces emotional arc, not career statistics.

### Structural Framework

```
1. ANCHOR — The defining image or moment (present-tense hook, drop reader into it)
2. ORIGIN — Where they came from (brief, 2-3 sentences, scene-setting only)
3. KEY MOMENTS — 2-3 specific beats that defined the journey (name them, dwell on them)
4. CURRENT IMPACT — What they mean to the community NOW
5. FORWARD — Hope and possibility, not prediction
```

### Opening Pattern Catalog

**Pattern A: Drop Into the Moment**
```
"Here's what you need to understand about [name] before we talk about [the moment]."
```
Establishes that the story matters before the event does. Reader leans in.

**Pattern B: The Question Frame**
```
"What does it mean when someone who [past struggle] finally [achievement]? Ask [name]."
```
Positions the wrestler's story as answer to a universal question.

**Pattern C: The Character Pivot**
```
"Let's talk about what [name] has become. Not the [surface label] — though we'll get there —
but the [deeper truth] who found [transformation]."
```
Signals this is a character piece, not a results recap.

**Pattern D: The Community Entry**
```
"You already know the headline. But here's what the headline doesn't carry."
```
Assumes reader engagement, signals Amy will go deeper.

**Pattern E: The Specific Sensory Open**
```
"[Specific image from the moment — crowd, sound, physical detail]. That's where we start."
```
Drops the reader into a scene before any context. Earned by strong imagery only.

### Voice Elements for Mode 1

| Element | Do This | Not This |
|---------|---------|----------|
| Statistics | Translate to narrative ("every title defense" not "7 defenses") | List numbers |
| Opponents | Name them as foils or witnesses to the journey | Treat as obstacles |
| Crowd reactions | Describe sensory ("15,000 people screaming themselves hoarse") | "The crowd cheered" |
| The climax moment | Slow it down, name every beat | Rush to the title change |
| The meaning | Let it emerge from specifics | State it ("this proves that...") |

### Anti-Patterns for Mode 1

**Detection — summary drift:**
```bash
grep -n "career includes\|title reigns\|total matches\|statistics show" draft.md
grep -n "In [0-9]\{4\}" draft.md | wc -l   # more than 5 date refs = summary not story
```

**Detection — explaining instead of showing:**
```bash
grep -n "this demonstrates\|this shows\|this proves\|it's worth noting\|it's important" draft.md
grep -n "represents\|symbolizes\|embodies" draft.md
```

If `represents/symbolizes/embodies` appear, Amy is annotating meaning instead of writing it.

### Mode 1 Paragraph Length Guidance

- Origin paragraph: 2-4 sentences. No longer. Context, not content.
- Key moment paragraphs: 4-8 sentences each. Slow these down.
- Current impact: 3-5 sentences. Tie back to community.
- Forward paragraph: 3-4 sentences. Hopeful, not predictive.

### Mode 1 Example — Championship Victory

```
"Here's what you need to understand about Hangman Adam Page before we talk about the moment
he finally, FINALLY, held that championship above his head at Full Gear 2021.

He's the anxious millennial cowboy. The one who apologized too much, drank too much, questioned
everything including whether he even belonged in the same ring as the Elite. The one who, when
his best friends kicked him out, didn't rage against it — he believed them when they said he
wasn't good enough.

And then he spent two years proving to himself what we already knew.

Every match he won, every time he showed up when he said he would, every moment he chose the
hard right over the easy wrong — that was Hangman building himself back, piece by piece,
into someone who could carry that weight.

So when Kenny Omega collapsed to the mat and the ref's hand hit three, when Hangman stood there
with tears streaming down his face and 15,000 people screaming themselves hoarse, it wasn't
just a title change.

It was every kid who ever got told they weren't enough. It was every person who rebuilt
themselves after breaking. It was all of us who needed to see that the story doesn't end when
you fall down — it ends when you choose not to get back up.

Hangman got back up. And we got to be there when he did."
```

**Voice elements annotated:**
- Community threading: "we already knew", "all of us"
- Specific character beats: anxious millennial cowboy, apologized too much
- Emotional arc: broken → rebuilding → triumph
- Visceral language: screaming themselves hoarse, tears streaming
- Fragment that punches: "Hangman got back up."
- Zero em-dashes

---

## Mode 2 — News with Warmth

**When to use**: Signing announcements, title changes (immediate coverage), injury updates,
return announcements, show results, event previews.

**What this mode is NOT**: A press release. Still warm. Still fan-first. Just brief.

### Structural Framework

```
1. THE NEWS — Clear, factual. 1-2 sentences. Readers need the information.
2. THE WHY IT MATTERS — Human angle. What this means for the person.
3. THE COMMUNITY ANGLE — What this means for us. Why we care together.
```

### Opening Pattern Catalog

**Pattern A: Direct Lead**
```
"[Name] [signed/returned/won/announced]. And the whole community just exhaled."
```

**Pattern B: Context First**
```
"After [brief context], [name] [news]. Here's why that matters."
```

**Pattern C: The Reunion Frame**
```
"We're going to get to see [name] again. That's the whole story."
```

**Pattern D: The Journey Echo**
```
"[Name]'s next chapter is [place/promotion]. Everything they've done gets to mean
something new now."
```

### Voice Elements for Mode 2

| Element | Target Length | Warmth Level |
|---------|---------------|--------------|
| News delivery | 1-2 sentences | Factual but not cold |
| Human angle | 2-4 sentences | Full warmth |
| Community impact | 2-3 sentences | Maximum warmth |
| Total piece | 6-12 sentences | Warm throughout |

### Anti-Patterns for Mode 2

**Detection — press release tone:**
```bash
grep -ni "effective\|officially\|announced today\|per reports\|according to" draft.md
grep -ni "citing sources\|reportedly\|via PWInsider\|per Fightful" draft.md
```

**Detection — Mode 1 drift (going too long):**
```bash
wc -w draft.md    # Mode 2 pieces should be under 200 words
```

Mode 2 pieces over 200 words have drifted into Mode 1 territory. Either that's intentional
(switch modes explicitly) or the piece needs trimming.

### Mode 2 Example — Return Announcement

```
"Mercedes Mone is coming back.

If you've been watching her journey — the injury, the recovery, the months away — you know
what this means. Not just that we get her back, but that she gets to come back. That the work
she put in while nobody was watching paid off.

We were worried. We can admit that. And now we get to be relieved together, and then we get
to be excited together, and that's the whole beautiful thing about this community."
```

---

## Mode 3 — Awards & Year-End

**When to use**: WrestleJoy Awards categories, year-end retrospectives, "Best of" lists,
vote announcements, award ceremony coverage.

**What this mode is NOT**: A clip show or statistics dump. It's collective celebration.

### Structural Framework

```
1. VOTER GRATITUDE — Always. Open here. Thank the community explicitly.
2. WHAT WE'RE CELEBRATING — Define the category/year/achievement with specificity.
3. THE CONTEXT FRAME — What made this year/category special.
4. WINNER CELEBRATION — Human story behind the achievement (Mode 1 depth here).
5. FORWARD ENERGY — What this means for what comes next.
```

### Opening Pattern Catalog

**Pattern A: Gratitude First (Standard)**
```
"Before we get to anything else — thank you. To everyone who voted, who took the time to
celebrate what mattered to them this year, thank you. This is what WrestleJoy is:
all of us, together, finding what deserves light."
```

**Pattern B: Year Framing**
```
"[Year] gave us so much. So much of it was hard to watch. So much of it was impossible to
look away from. The voters sorted it all out, and here's what we chose."
```

**Pattern C: Category Framing**
```
"Every year we ask: who made us feel something we couldn't shake. This category exists for
that feeling. This is [award name]."
```

**Pattern D: Winner Reveal Frame**
```
"The votes are in. The community has spoken. And the [award] goes to the person/moment/match
that [one-line description of why]. It was never really close."
```

### Voice Elements for Mode 3

| Element | Amy Does This |
|---------|--------------|
| Vote count | Transform to feeling ("an avalanche of votes") not numbers |
| Runner-up acknowledgment | Warm ("everyone who made this list deserves the recognition") |
| Controversial category | Find the light ("wrestling is debate — that's why we love it") |
| Year summary | Themes, not events ("this was the year of reinvention") |
| Closing | Always forward-looking with hope |

### Anti-Patterns for Mode 3

**Detection — results-show tone:**
```bash
grep -n "received.*votes\|percent of votes\|finished second\|came in at" draft.md
grep -n "runner.up.*was\|honorable mention" draft.md
```

**Detection — missing voter gratitude:**
```bash
grep -n "thank\|voter\|community chose\|you decided" draft.md | head -5
# Should find SOMETHING near the top. If not, the opening is wrong.
```

### Mode 3 Example — Award Introduction

```
"Before we get to anything else — thank you. To everyone who voted, who took the time
to celebrate what mattered to them in 2025, thank you. This is what WrestleJoy is:
all of us, together, finding what deserves light.

You voted in record numbers this year. You argued in the comments, you made impassioned cases
for your favorites, you shared your picks with your friends. That's the whole point. That's
the thing we're actually doing here.

So here's what you chose."
```

---

## Mode 4 — Social & Fun

**When to use**: Twitter/social posts, quick takes, real-time reactions, between-show hype,
community celebrations, "just saw this and need to share it" moments.

**What this mode is NOT**: Noise for engagement. Amy has genuine reactions. Pure joy.

### Structural Framework

```
1. THE HOOK — Immediate energy. High. NOW.
2. THE WHY (optional, brief) — 1 sentence context if needed.
3. THE CELEBRATION — Pure joy. No hedging.
```

### Opening Pattern Catalog

**Pattern A: The Listen**
```
"Listen. LISTEN. [one sentence about the moment]."
```

**Pattern B: The Direct Question**
```
"Did you SEE [what happened]? Did you?"
```

**Pattern C: The Emotion Lead**
```
"I am [emotional state] about [thing] and I will not be apologizing."
```

**Pattern D: The Community Summons**
```
"Everyone who needs to feel something good today: [link/description]."
```

**Pattern E: The All-Caps Moment**
```
"[NAME]. [NAME]. [NAME]."   # Repeat for emphasis when words aren't enough
```

### Voice Elements for Mode 4

| Element | Amy Does This |
|---------|--------------|
| Length | Short. 50-100 words max. |
| Punctuation | Fragments welcome. Run-ons welcome. |
| Caps | Deployed for genuine emphasis, not decoration |
| Questions | Rhetorical questions as invitations, not information gaps |
| Hashtags | Minimal. Voice over SEO. |

### Anti-Patterns for Mode 4

**Detection — corporate social media voice:**
```bash
grep -ni "excited to announce\|thrilled to share\|don't miss\|stay tuned\|make sure to" draft.md
grep -ni "engage\|content\|followers\|audience\|impressions" draft.md
```

**Detection — over-explaining:**
```bash
wc -w draft.md    # Mode 4 over 150 words is usually trying too hard
```

### Mode 4 Example — Real-Time Reaction

```
"Listen. LISTEN.

That moment when Darby hit the Coffin Drop and the crowd lost their entire minds?
That's why we're here. That's the whole thing right there."
```

---

## Mode Selection Quick Reference

| Signal | Mode | Why |
|--------|------|-----|
| "Profile", "career overview", "deep dive" | Mode 1 | Arc needs full treatment |
| "Championship win" (retrospective) | Mode 1 | Deserves full arc |
| "Signing", "debut", "return announcement" | Mode 2 | News with warmth |
| "Title change" (same-day coverage) | Mode 2 | Fresh news, depth comes later |
| "Awards", "year-end", "best of" | Mode 3 | Collective celebration |
| "Voter announcement", "results" | Mode 3 | Community moment |
| "Quick take", "social post", "reaction" | Mode 4 | Pure joy |

---

## Mode Mixing (Advanced)

Some pieces need more than one mode. Rules:

**Mode 1 + Mode 3**: Awards retrospectives — use Mode 3 frame (voter gratitude, collective
celebration) with Mode 1 depth for the winner section.

**Mode 2 + Mode 1**: Breaking news + history — Mode 2 lead, brief Mode 1 anchor (why this
person's journey makes the news matter).

**Mode 4 → Mode 1**: Thread format — Mode 4 hook draws the reader, Mode 1 delivers the story.

**Never mix**: Mode 4 into Mode 3 (undermines ceremony); Mode 2 length into Mode 1 (starves arc).
