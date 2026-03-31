---
name: content-engine
description: "Repurpose source assets into platform-native social content."
version: 1.0.0
user-invocable: false
model: sonnet
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - repurpose this
    - adapt for social
    - turn this into posts
    - content from article
    - content from demo
    - content from doc
    - write variants for
    - social content from
    - platform variants
    - repurpose for
  pairs_with:
    - x-api
  category: content
  disambiguate: voice-writer
---

# Content Engine Skill

Repurpose anchor content into platform-native variants. This skill produces drafts only — it does not make API calls or publish content. Posting is handled downstream by `x-api` (single platform) or `crosspost` (multi-platform).

Platform-native means each variant is written from scratch for its target platform: different register (conversational on X, professional-but-human on LinkedIn, punchy on TikTok), different structure (thread vs. long-form post vs. short script vs. newsletter section), and different hook style (open fast on X, strong first line on LinkedIn, interrupt on TikTok). Shortening the same text for each platform is not adaptation — it produces content that reads identically everywhere and fails on every platform.

---

## Instructions

### Phase 1: GATHER — Collect Inputs Before Writing Anything

Establish everything needed to write platform-native variants. Do not begin writing until this phase is complete.

**Required inputs:**

| Input | Description | If Missing |
|-------|-------------|------------|
| Source asset | The content being adapted (article text, demo description, launch doc, insight, transcript) | Ask — required |
| Target platforms | X, LinkedIn, TikTok, YouTube, newsletter — one or many | Ask if not inferable from context |
| Audience | Builders, investors, customers, operators, general | Infer if a strong signal exists; ask if ambiguous |
| Goal | Awareness, conversion, recruiting, authority, launch support, engagement | Infer from source if obvious; ask otherwise |
| Constraints | Character limits already observed, brand voice notes, phrases to avoid | Skip if none stated |

**Gate**: Source asset present AND at least one target platform identified. If either is missing, ask before proceeding. Both missing means there is nothing to work with — do not guess.

Produce only the platforms the user requested. If the user says "turn this into an X thread", produce an X thread. Offer to expand to other platforms in Phase 5, but do not produce unrequested variants.

Do not write any content in this phase. Only collect and confirm inputs.

---

### Phase 2: EXTRACT — Identify 3-7 Atomic Ideas

Identify the discrete, postable units inside the source asset. Each atomic idea must stand alone as a post on at least one platform without requiring the reader to know the source.

**Steps:**

1. Read the full source asset
2. Identify ideas that meet the criteria:
   - Specific (concrete claim, result, observation, or instruction — not a vague theme)
   - Standalone (no dependency on other ideas in the list to be understood)
   - Relevant to the stated goal and audience
3. Rank by relevance to the stated goal
4. Write each atomic idea as one sentence maximum

Fewer than 3 ideas means the source is very narrow — proceed with what exists (minimum 1 is sufficient for a single platform) and note in the output file that the source yielded fewer than expected. More than 7 means the asset lacks coherence and should be split; ask the user which section to focus on.

**Output format for `content_ideas.md`:**

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

**Gate**: Numbered atomic ideas saved to `content_ideas.md`. Each is specific and standalone. The file must exist before proceeding — context is not an artifact.

---

### Phase 3: DRAFT — Write Platform-Native Variants

Write one draft per target platform, each starting from the primary atomic idea (or specified idea) as raw material.

Every draft must be written from scratch for its platform. Do not write one version and shorten or trim it for others — audiences on each platform recognize content that was not written for them. No two platform drafts may share a verbatim sentence. If the LinkedIn draft opens with "This article covers..." or the X tweet says "New post: [title]. Key points: 1, 2, 3", that is a summary, not an adaptation. Summaries give readers no reason to stop scrolling.

Apply platform-specific rules (see `references/platform-specs.md` for full detail):

#### X (Twitter)

- **Register**: Conversational, direct, opinionated. No corporate voice.
- **Hook**: Open fast. The first tweet carries the entire weight — if it doesn't stop the scroll, the thread dies.
- **Structure for single tweet**: One idea, one sharp claim, optionally one proof point. End with a question or strong assertion, not a CTA.
- **Structure for thread**: Each tweet carries one thought. Segment at natural breaks. Number tweets only if >=5. No cliffhanger tweets that require the next to make sense.
- **Character limit**: 280 per tweet, hard limit. Each tweet must carry exactly one thought — do not split mid-sentence across tweets without a natural break.
- **Hashtags**: 0-2 maximum. Only if they add discoverability, never for decoration.
- **Links**: One link only, at the end of the last tweet if needed. Not in the middle of a thread.
- **CTAs**: Optional. If present, one sentence, at the end, low pressure. Do not reuse the same CTA text used in other platform drafts.

#### LinkedIn

- **Register**: Professional but human. Not corporate. Lessons and results framing over announcement framing.
- **Hook**: First line must work standalone before "see more" — it is the only text visible before the fold. If the first line requires the rest of the post to land, rewrite it. It is a promise, not a topic sentence.
- **Structure**: First line → 2-4 short paragraphs of substance → optional takeaway or question at end.
- **Length**: 150-300 words optimal. Can go to 600 if the content earns it. Not longer.
- **Hashtags**: 3-5 at the end. Relevant, not decorative.
- **Links**: Put in comments, not in the post body. LinkedIn suppresses posts with external links. Reference "link in comments" if needed.
- **CTAs**: One soft CTA at end if appropriate (follow for more, drop your take in comments). Match the CTA to LinkedIn norms — "Check out the full article in the comments!" reads differently here than on X.

#### TikTok

- **Format**: Short video script (voiceover or talking-head style).
- **First 3 seconds**: Show the result, state the unexpected thing, or interrupt a pattern. Never start with "In this video..." or "Today we're going to..." — preamble kills retention. This is the make-or-break moment.
- **Length**: 30-60 seconds optimal (150-300 words at speaking pace).
- **Structure**: Hook (3s) → one demonstration or explanation → punchline or twist → CTA (5s max).
- **No lists or headers in the script.** Write it to be spoken aloud.

#### YouTube

- **Format**: Video script or description (specify which in the draft).
- **Show result early**: Within the first 30 seconds of script, show or state the result. Do not build to it. Same rule as TikTok for the first 3 seconds — interrupt or result, not preamble.
- **Chapter structure**: If script is >3 minutes, include chapter markers.
- **Description**: 2-3 sentences that work as search-discoverable summary, then bullet points of what the video covers, then links/CTA.
- **Thumbnail note**: Include one suggested thumbnail concept (visual + text overlay) with the draft.

#### Newsletter

- **Register**: One-on-one. Write to one person, not a list.
- **Lens**: One clear angle on the idea. Not a summary — a perspective.
- **Structure**: Skimmable headers (2-4 max), short paragraphs (2-3 sentences max), one CTA at end.
- **Length**: 300-600 words. Long enough to have substance, short enough to be read.
- **Subject line**: Write 3 subject line options with the draft. Short, specific, curiosity-gap or benefit-driven.
- **No generic openers**: Do not start with "This week I want to talk about..." or "I hope this email finds you well."

**Output format for `content_drafts.md`:**

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

**Gate**: One draft per target platform saved to `content_drafts.md`. Self-check that no two drafts share a verbatim sentence before running scripts in Phase 4. The file must exist before proceeding.

---

### Phase 4: GATE — Quality Check Before Delivery

Mechanically verify drafts before delivery. Both script checks must exit 0. The gate cannot be bypassed — LLM self-assessment alone ("I reviewed the drafts and they look clean") misses hype phrases in context and cannot do verbatim comparison reliably. Run the scripts.

#### Check 1: Hype Phrase Scan

```bash
python3 scripts/scan-negative-framing.py --mode hype --drafts content_drafts.md
```

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

**If exit non-zero**: Identify the flagged draft(s), rewrite only the affected sections, save to `content_drafts.md`, re-run the check. Do not proceed to Phase 5 until exit 0.

#### Check 2: Cross-Platform Verbatim Check

```bash
python3 scripts/scan-negative-framing.py --mode cross-platform --drafts content_drafts.md
```

This check identifies any sentence appearing verbatim in two or more platform sections of `content_drafts.md`.

**If exit non-zero**: Rewrite the flagged sentence(s) in one of the two platforms where they appear. The rewrite must be platform-native — not a synonym swap. Re-run the check. Do not proceed to Phase 5 until exit 0.

#### Secondary LLM Check (after scripts pass)

Once both scripts exit 0, verify:
- [ ] Each draft reads natively for its platform (register, length, formatting feel right)
- [ ] Every hook is strong and specific — not a topic sentence, not a summary opener
- [ ] CTAs match the stated goal and platform norms
- [ ] No placeholder text that cannot be published as-is (flag these, do not remove them)

**Gate**: Both script checks exit 0. All LLM checklist items confirmed. Update `content_drafts.md` status from `DRAFT — pending Phase 4 gate` to `READY`. Proceed to Phase 5 only when gate passes.

---

### Phase 5: DELIVER — Present Drafts with Posting Guidance

Hand off clean drafts with enough context for the user or a downstream skill to act immediately.

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

### Error: scan-negative-framing.py --mode hype not recognized
Cause: Script does not yet support `--mode hype` flag.
Solution: Manually scan `content_drafts.md` for banned phrases using Grep. Flag each occurrence, rewrite the affected sentence(s), confirm clean before proceeding. Note in delivery that automated gate was not available.

### Error: scan-negative-framing.py --mode cross-platform not recognized
Cause: Script does not yet support `--mode cross-platform` flag.
Solution: Manually compare platform drafts sentence by sentence using Grep for repeated sentences across sections. Rewrite any matches. Note in delivery that automated gate was not available.

### Error: Platform target not specified and cannot be inferred
Cause: User said "make social posts" with no platform context.
Solution: Ask. Minimum: "Which platforms — X, LinkedIn, TikTok, YouTube, newsletter, or a subset?" Do not proceed with generic drafts that are not platform-native.

### Error: Source asset is ambiguous (no clear ideas emerge)
Cause: Source is a collection of loosely related fragments.
Solution: Ask user to identify the one idea they most want to amplify. Extract around that anchor. Note that less-coherent sources produce fewer high-quality atomic ideas.

### Error: Fewer than 3 atomic ideas extracted
Cause: Source asset is very narrow or very short.
Solution: Proceed with what exists (minimum 1 idea is sufficient for a single platform). Note in `content_ideas.md` that the source yielded fewer than 3 ideas and why.

---

## References

- `${CLAUDE_SKILL_DIR}/references/platform-specs.md` — Character limits, format rules, and posting norms per platform
- `scripts/scan-negative-framing.py` — Negative framing and hype phrase detection
