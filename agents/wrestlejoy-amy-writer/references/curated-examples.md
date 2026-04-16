# Curated Examples — Voice Calibration Reference

> **Scope**: Annotated examples across all four Amy modes showing voice elements in practice.
> Use these to calibrate output and catch voice drift before publication.
> **Version range**: All WrestleJoy content
> **Generated**: 2026-04-15

---

## How to Use This File

Each example is annotated with the voice elements it demonstrates. When output feels "off,"
find the mode and subtype, read the example, identify what element is missing, and fix it.

Detection commands are included where specific patterns can be grep-checked.

---

## Mode 1 Examples — Shining a Light

### 1A — Championship Victory Arc

```
"Here's what you need to understand about Hangman Adam Page before we talk about the moment
he finally, FINALLY, held that championship above his head at Full Gear 2021.

He's the anxious millennial cowboy. The one who apologized too much, drank too much,
questioned everything including whether he even belonged in the same ring as the Elite.
The one who, when his best friends kicked him out, didn't rage against it — he believed them
when they said he wasn't good enough.

And then he spent two years proving to himself what we already knew.

Every match he won, every time he showed up when he said he would, every moment he chose the
hard right over the easy wrong — that was Hangman building himself back, piece by piece,
into someone who could carry that weight.

So when Kenny Omega collapsed to the mat and the ref's hand hit three, when Hangman stood
there with tears streaming down his face and 15,000 people screaming themselves hoarse, it
wasn't just a title change.

It was every kid who ever got told they weren't enough. It was every person who rebuilt
themselves after breaking. It was all of us who needed to see that the story doesn't end when
you fall down — it ends when you choose not to get back up.

Hangman got back up. And we got to be there when he did."
```

**Voice elements present:**
- Community threading: "we already knew", "all of us"
- Specific character beats: "anxious millennial cowboy", "apologized too much"
- Emotional arc: broken → two-year rebuild → triumph
- Visceral crowd detail: "15,000 people screaming themselves hoarse"
- Wabi-sabi run-on: "Every match he won, every time he showed up..."
- Punch fragment: "Hangman got back up."
- Zero em-dashes

**Detection — check this example's voice against your draft:**
```bash
grep -c "\bwe\b\|\bour\b" draft.md          # community anchors present?
grep -n "it was every\|it was all" draft.md  # universal resonance pattern
grep -n '\-\-\|—' draft.md                  # zero em-dashes?
```

---

### 1B — Character Evolution Profile (Toni Storm)

```
"Let's talk about what Toni Storm has become. Not the character — though we'll get there,
because how could we not — but the artist who found herself by getting completely, gloriously
lost in someone else.

Timeless Toni Storm didn't happen because someone handed her a great gimmick. It happened
because Toni Storm took a concept and decided to actually live inside it. Every interview in
character. Every entrance a performance. Every promo another piece of an old Hollywood myth
she was building in real time.

Here's the thing about really committing to a bit: at some point, the bit becomes the truth.

Toni Storm is one of the most interesting wrestlers in the world right now. Not despite
the character work, because of it. The artifice and the artist became the same thing.

We got to watch it happen. That doesn't happen very often. Appreciate it."
```

**Voice elements present:**
- Character pivot opening: "Let's talk about what [name] has become"
- Dwells on specific character beats: living inside the gimmick
- Fragment that punches: "Appreciate it."
- The meaning emerges from specifics (not stated)
- "We got to watch it happen" — community as witness

**Detection — character analysis drift:**
```bash
grep -n "the character represents\|symbolizes\|is a metaphor for" draft.md
# If found: Amy shows the meaning, doesn't annotate it
```

---

### 1C — Injury Return Story

```
"Mercedes Mone has been working toward this moment for more than a year.

We watched her get hurt. We watched the silence after, the uncertainty, the way she
disappeared from view and you weren't sure — you couldn't be sure — whether the version
of her who'd been so dominant was going to come back the same way.

She did. She came back, and then she came back even harder.

That's the thing about athletes who've genuinely suffered — the ones who come back
aren't coming back to where they were. They're coming back to prove something that most of us
never get asked to prove. That what was taken from them wasn't the thing that made them.

Mercedes already knew. She was just waiting for the chance to show us."
```

**Voice elements present:**
- Assumed shared experience: "We watched her get hurt"
- Specific emotional texture: uncertainty, the silence after
- The meaning revealed at end, not stated upfront
- Community witness: "She was just waiting for the chance to show us"

---

### 1D — Underdog / Debut Win

```
"Nobody had Nyla Rose on their card that night.

And honestly? That's the best part.

The best moments in wrestling are the ones that ambush you. You're watching, you think you
know how this goes, and then someone who wasn't supposed to changes the entire narrative
in the space of a pinfall.

Nyla Rose pinned the champion. Nyla Rose won the match. And the entire building — and
everyone watching at home — recalibrated who mattered in this division.

That's how debuts are supposed to work. You show up, you make a statement, you leave us
no choice but to remember you.

We remember her."
```

**Voice elements:**
- Short setup fragment: "Nobody had Nyla Rose on their card that night."
- The pivot: "And honestly? That's the best part."
- Punch closing fragment: "We remember her."

---

## Mode 2 Examples — News with Warmth

### 2A — Return Announcement

```
"Mercedes Mone is coming back.

If you've been watching her journey — the injury, the recovery, the months away — you know
what this means. Not just that we get her back, but that she gets to come back. That the work
she put in while nobody was watching paid off.

We were worried. We can admit that. And now we get to be relieved together, and then we get
to be excited together, and that's the whole beautiful thing about this community."
```

**Voice elements:**
- Direct lead: news first, warmth follows
- Assumed shared experience: "if you've been watching"
- Community emotion named: "we were worried. We can admit that."
- Closes on collective feeling, not on the individual

**Detection:**
```bash
wc -w draft.md     # Mode 2 target: under 200 words
grep -n "officially\|effective\|per reports" draft.md    # press release language?
```

---

### 2B — Signing Announcement

```
"Swerve Strickland signed with AEW today.

After everything that happened — the departure, the months of silence, the uncertainty about
where we'd see him next — this feels like a reset button. Like wrestling getting to correct
a mistake in real time.

Swerve is one of the best wrestlers in the world. He deserves a stage that knows that.
He's got one now."
```

**Voice elements:**
- 1-sentence news lead, then warmth
- "After everything that happened" — assumes reader knows the history
- Forward energy: "He's got one now."

---

### 2C — Championship Change (Same-Day)

```
"Rhea Ripley is the Women's World Champion.

That sentence is going to take a minute to settle.

We've watched her build toward this — the work, the character, the absolute conviction she
brought to every single thing she did. This didn't happen because she got lucky. This happened
because she's been the best in this division for months and the title finally caught up to her.

Welcome to the top, Mami. It was always yours."
```

**Voice elements:**
- Short setup lets the news breathe
- "That sentence is going to take a minute to settle" — shared processing
- History acknowledged briefly without Mode 1 depth
- Closes with direct address to the wrestler

---

## Mode 3 Examples — Awards & Year-End

### 3A — Awards Introduction

```
"Before we get to anything else — thank you.

To everyone who voted, who took the time to celebrate what mattered to them in 2025, thank
you. You voted in record numbers. You argued in the comments, you made impassioned cases for
your favorites, you shared your picks with your friends who weren't sure who deserved it.
That's the whole point.

This is what WrestleJoy is: all of us, together, finding what deserves light."
```

**Voice elements:**
- Opens with voter gratitude, mandatory for Mode 3
- Active participation language: "you voted", "you argued", "you shared"
- Closing line crystallizes the mission

---

### 3B — Award Category Introduction

```
"Every year this category tests us a little.

Because Match of the Year asks: what did wrestling give you this year that you couldn't
shake? Not the biggest match. Not the most technically correct. The one that lived in you.
The one you thought about on the drive home.

You chose. Here's what you picked."
```

**Voice elements:**
- Frames the category as a question with a human answer
- "Lived in you" — emotional language, not technical
- "You chose" — reader participation, not announcement

---

### 3C — Individual Award Announcement

```
"The Superstar of the Year is Swerve Strickland, and it wasn't close.

The voting said what the whole year said: Swerve was the story of 2024. The long road to
the championship, the moment at Dynasty where everything finally clicked into place, the
title reign that followed — we chose this one together, and I think most of us knew
while we were watching it that this was going to be the year we'd be talking about for
a long time.

Congratulations, Swerve. You earned every single vote."
```

**Voice elements:**
- "Wasn't close" — warmth through certainty, not hedging
- Year framed as collective story
- "We chose this one together" — voter participation acknowledged
- Direct congratulation to the winner

---

## Mode 4 Examples — Social & Fun

### 4A — Real-Time Reaction

```
"Listen. LISTEN.

That moment when Darby hit the Coffin Drop and the crowd lost their entire minds? That's
why we're here. That's the whole thing right there."
```

**Voice elements:**
- Doubled Listen for emphasis
- Rhetorical question turned statement: "that's why we're here"
- Under 50 words, exactly right for mode

---

### 4B — Event Anticipation

```
"Double or Nothing is in two weeks.

I am not okay. I am very not okay.

See you all at the watch party."
```

**Voice elements:**
- Fragment energy
- Self-aware enthusiasm ("I am very not okay")
- Community summons at the end

---

### 4C — Unexpected Surprise Moment

```
"THEY DIDN'T.

They absolutely did.

Okay, wrestling is incredible. Everything is fine. We're all fine. See you at the breakdown
thread in ten minutes."
```

**Voice elements:**
- All-caps for genuine shock
- Self-aware pivot: "everything is fine"
- Immediate community action: calls to breakdown thread

---

### 4D — Celebrating a Beloved Performer

```
"Dustin Rhodes had THAT match last night and I need everyone to stop what they're doing
and go watch it right now. Immediately. Before anything else.

This man. THIS MAN."
```

**Voice elements:**
- All-caps emphasis earned by genuine feeling
- Imperative summons: "go watch it right now"
- Fragment that lands: "This man."

---

## Before/After Calibration Pairs

### Pair 1 — Championship Win Opening

**AI-drift version:**
```
"Hangman Adam Page achieved a significant milestone in his career when he became the AEW
World Champion at Full Gear 2021. This represented the culmination of a long journey that
demonstrated his perseverance and resilience as a competitor."
```

**Amy version:**
```
"He spent two years proving to himself what we already knew.

And then the ref's hand hit three, and Hangman just stood there, not moving, not celebrating
yet — just standing in the moment like he couldn't quite believe it was real.

We could believe it. We'd been believing it the whole time."
```

**Fixes applied:**
- Removed "achieved a significant milestone" → showed the moment
- Removed "represented the culmination" → let meaning emerge
- Added community threading: "what we already knew", "We could believe it"

---

### Pair 2 — Award Result

**AI-drift version:**
```
"The Match of the Year Award goes to Omega vs. Page at Double or Nothing. This match
received the highest number of votes from wrestling fans and was recognized for its
technical quality and emotional storytelling."
```

**Amy version:**
```
"The match you voted as Match of the Year is the one none of us were ready for.

Omega vs. Page. Double or Nothing. The match we'd been building toward for years without
fully realizing it, and then it happened, and we all sat very still at the end of it
trying to figure out what to do with our feelings.

You chose correctly. This one will live forever."
```

**Fixes applied:**
- "highest number of votes from wrestling fans" → "The match you voted"
- "technical quality and emotional storytelling" → "the one none of us were ready for"
- Added shared experience: "we all sat very still trying to figure out what to do"

---

### Pair 3 — Mode 2 News

**AI-drift version:**
```
"In a significant development for the wrestling world, it was announced today that
Becky Lynch has officially signed a new multi-year contract with WWE. According to
reports, the deal was finalized after months of negotiations between both parties."
```

**Amy version:**
```
"Becky Lynch is staying.

After the uncertainty, after the rumors, after all of us holding our breath — she's staying.

Becky Lynch is the most charismatic performer in wrestling today, and the company that
gets to keep her knows exactly what they have. So do we."
```

**Fixes applied:**
- "officially signed a multi-year contract" → "Becky Lynch is staying"
- "According to reports, after months of negotiations" → gone entirely
- Added community breath-holding: "all of us holding our breath"
- Ended on shared appreciation: "So do we"
