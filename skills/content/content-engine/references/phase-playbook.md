# Content Engine Phase Playbook

Detailed platform rules, hype phrase enforcement list, template files, delivery handoff, and error handling. Load when drafting variants or running quality gates.

## Phase 2: `content_ideas.md` Template

```markdown
# Content Ideas — [Source Title or Brief Description]

Generated: [date]
Source: [brief description of source asset]
Goal: [stated goal]
Audience: [stated audience]
Platforms: [target platforms]

## Atomic Ideas

1. [One-sentence statement of idea, specific and standalone]
2. [One-sentence statement of idea]
3. [One-sentence statement of idea]
...

## Primary Idea
[Which idea leads — the strongest for the stated goal]
```

## Phase 3: `content_drafts.md` Template

```markdown
# Content Drafts — [Source Title or Brief Description]

Generated: [date]
Primary Idea: [the idea being adapted]
Status: DRAFT — pending Phase 4 gate

---

## X (Twitter)

[Draft — single tweet or numbered thread]

---

## LinkedIn

[Draft]

---

## TikTok

[Script]

---

## YouTube

[Script or description]

---

## Newsletter

Subject line options:
1. [Option]
2. [Option]
3. [Option]

[Draft]
```

## Phase 3: Platform-Specific Rules (Full Detail)

See also `references/platform-specs.md` for additional character limits and posting norms.

### X (Twitter)

- **Register**: Conversational, direct, opinionated. No corporate voice.
- **Hook**: Open fast. The first tweet carries the entire weight — if it doesn't stop the scroll, the thread dies.
- **Structure for single tweet**: One idea, one sharp claim, optionally one proof point. End with a question or strong assertion, not a CTA.
- **Structure for thread**: Each tweet carries one thought. Segment at natural breaks. Number tweets only if >=5. No cliffhanger tweets that require the next to make sense.
- **Character limit**: 280 per tweet, hard limit. Each tweet must carry exactly one thought — do not split mid-sentence across tweets without a natural break.
- **Hashtags**: 0-2 maximum. Only if they add discoverability, never for decoration.
- **Links**: One link only, at the end of the last tweet if needed. Not in the middle of a thread.
- **CTAs**: Optional. If present, one sentence, at the end, low pressure. Do not reuse the same CTA text used in other platform drafts.

### LinkedIn

- **Register**: Professional but human. Not corporate. Lessons and results framing over announcement framing.
- **Hook**: First line must work standalone before "see more" — it is the only text visible before the fold. If the first line requires the rest of the post to land, rewrite it. It is a promise, not a topic sentence.
- **Structure**: First line → 2-4 short paragraphs of substance → optional takeaway or question at end.
- **Length**: 150-300 words optimal. Can go to 600 if the content earns it. Not longer.
- **Hashtags**: 3-5 at the end. Relevant, not decorative.
- **Links**: Put in comments, not in the post body. LinkedIn suppresses posts with external links. Reference "link in comments" if needed.
- **CTAs**: One soft CTA at end if appropriate (follow for more, drop your take in comments). Match the CTA to LinkedIn norms — "Check out the full article in the comments!" reads differently here than on X.

### TikTok

- **Format**: Short video script (voiceover or talking-head style).
- **First 3 seconds**: Show the result, state the unexpected thing, or interrupt a pattern. Never start with "In this video..." or "Today we're going to..." — preamble kills retention. This is the make-or-break moment.
- **Length**: 30-60 seconds optimal (150-300 words at speaking pace).
- **Structure**: Hook (3s) → one demonstration or explanation → punchline or twist → CTA (5s max).
- **No lists or headers in the script.** Write it to be spoken aloud.

### YouTube

- **Format**: Video script or description (specify which in the draft).
- **Show result early**: Within the first 30 seconds of script, show or state the result. Do not build to it. Same rule as TikTok for the first 3 seconds — interrupt or result, not preamble.
- **Chapter structure**: If script is >3 minutes, include chapter markers.
- **Description**: 2-3 sentences that work as search-discoverable summary, then bullet points of what the video covers, then links/CTA.
- **Thumbnail note**: Include one suggested thumbnail concept (visual + text overlay) with the draft.

### Newsletter

- **Register**: One-on-one. Write to one person, not a list.
- **Lens**: One clear angle on the idea. Not a summary — a perspective.
- **Structure**: Skimmable headers (2-4 max), short paragraphs (2-3 sentences max), one CTA at end.
- **Length**: 300-600 words. Long enough to have substance, short enough to be read.
- **Subject line**: Write 3 subject line options with the draft. Short, specific, curiosity-gap or benefit-driven.
- **No generic openers**: Do not start with "This week I want to talk about..." or "I hope this email finds you well."

---

## Phase 4: Banned Hype Phrases

This check flags banned hype phrases — they are hard rejections, not suggestions. Banned phrases include:

- "excited to share"
- "thrilled to announce"
- "game-changing"
- "revolutionary"
- "groundbreaking"
- "don't miss out"
- "limited time"
- "unlock your potential"
- "dive into"
- "leverage"
- "synergy"
- "best-in-class"
- "world-class"
- "transformative"
- "disruptive"

Opening with hype ("Excited to share our game-changing approach to...") reads as corporate noise. Replace with a specific result, number, counterintuitive claim, or observation: "We cut deploy time by 80%. Here is what actually changed."

---

## Phase 5: Delivery Details

**Delivery order**: Primary platform first (if specified), then remaining platforms alphabetically.

**For each draft, include:**
1. The draft text (from `content_drafts.md`)
2. Optimal posting time if known (platform norms: X/LinkedIn weekdays 8-10am, TikTok evenings, Newsletter Tuesday-Thursday)
3. Any remaining placeholders that must be resolved before publishing — flag clearly with what is needed to finalize (e.g., `[URL]` needs the published article link, `[handle]` needs the company X handle)
4. Suggested posting order if multiple platforms (e.g., "post X first to gauge reaction, then LinkedIn 48 hours later")

**Downstream handoff options:**

| If user wants to... | Route to |
|---------------------|----------|
| Publish to X | `x-api` skill |
| Publish to multiple platforms | `crosspost` skill |
| Schedule posts | `content-calendar` skill |
| Apply a voice profile to drafts | `voice-writer` skill (post-process these drafts) |
| Extract more ideas from the same source | Re-run from Phase 2 |

**Optional behaviors** (off unless enabled by user):
- **Multi-idea series**: Extract all ideas and schedule as a series (pairs with `content-calendar`)
- **Voice profile application**: After drafting, apply a voice profile via `voice-writer`
- **Immediate publish**: After gate passes, hand off to `x-api` or `crosspost`

**Artifacts produced:**
- `content_ideas.md` — numbered atomic ideas with ranking
- `content_drafts.md` — platform-native drafts, gate-verified, status: READY

---

## Error Handling

### Error: Source asset is too long to process in one pass
Cause: Article or transcript exceeds practical working length.
Solution: Ask user to identify the section to adapt, or extract section headers first and confirm which section(s) to use.

### Error: scan-negative-framing.py not found
Cause: Script lives in private-skills, not in this repo.
Solution: Run `python3 ~/private-skills/scripts/scan-negative-framing.py content_drafts.md`. If private-skills is not installed, use the manual grep fallback in `error-handling.md`.

### Error: Platform target not specified and cannot be inferred
Cause: User said "make social posts" with no platform context.
Solution: Ask. Minimum: "Which platforms — X, LinkedIn, TikTok, YouTube, newsletter, or a subset?" Do not proceed with generic drafts that are not platform-native.

### Error: Source asset is ambiguous (no clear ideas emerge)
Cause: Source is a collection of loosely related fragments.
Solution: Ask user to identify the one idea they most want to amplify. Extract around that anchor. Note that less-coherent sources produce fewer high-quality atomic ideas.

### Error: Fewer than 3 atomic ideas extracted
Cause: Source asset is very narrow or very short.
Solution: Proceed with what exists (minimum 1 idea is sufficient for a single platform). Note in `content_ideas.md` that the source yielded fewer than 3 ideas and why.
