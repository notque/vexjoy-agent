---
name: content-engine
description: |
  Repurpose a source asset (article, demo, launch note, insight) into
  platform-native social content variants. Use when the user provides a
  source asset and wants it adapted for X, LinkedIn, TikTok, YouTube, or
  newsletter. Triggered by: "repurpose this", "adapt for social", "turn
  this into posts", "content from [article/doc/demo]", "write variants
  for", "social content from".

  ROUTING DISAMBIGUATION vs voice-writer:
  - content-engine: user supplies a source asset to adapt → use this skill
  - voice-writer: user wants to write in a specific voice profile with no
    source asset → use voice-writer instead
  - Both specified: content-engine runs Phase 3 DRAFT first, then
    voice-writer applies the voice profile to the resulting drafts

  Do NOT use for: writing original content from scratch with a voice
  profile (use voice-writer), managing a content pipeline (use
  content-calendar), scheduling or publishing posts (use x-api or
  crosspost downstream).
version: 1.0.0
user-invocable: true
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
    - crosspost
  category: content
  disambiguate: voice-writer
---

# Content Engine Skill

## Operator Context

This skill repurposes anchor content into platform-native variants. It is not a summarization tool. Summaries do not work as social content — they lack hooks, carry the wrong register, and read identically across platforms.

**Platform-native means:**
- Different register per platform (conversational on X, professional-but-human on LinkedIn, punchy on TikTok)
- Different structure per platform (thread vs. long-form post vs. short script vs. newsletter section)
- Different hook style per platform (open fast on X, strong first line on LinkedIn, interrupt on TikTok)
- Not the same text made shorter

**This skill produces drafts only.** It does not make API calls or publish content. Posting is handled downstream by `x-api` (single platform) or `crosspost` (multi-platform).

**The quality gate in Phase 4 is not optional.** Generic output with banned hype phrases or duplicated copy across platforms is not deliverable. The skill will rewrite and retry until both script checks pass before proceeding to Phase 5.

### Hardcoded Behaviors (Always Apply)

- **Do not proceed to Phase 2 if source asset AND platform target are both unspecified.** Ask. One missing is acceptable if the other provides clear direction. Both missing means there is nothing to work with.
- **Save artifacts to files.** `content_ideas.md` and `content_drafts.md` must exist as files before Phase 5 executes. Context is not an artifact.
- **No verbatim sentence shared across any two platform drafts.** Each platform variant is written from scratch using the atomic idea as input, not copied and trimmed.
- **Banned phrases are hard rejections.** If `scan-negative-framing.py --mode hype` exits non-zero, rewrite the flagged draft and re-run the check. Do not deliver the batch until exit 0.
- **X character limits are per-tweet.** Each tweet in a thread must be ≤280 characters and carry exactly one thought. Do not split mid-sentence across tweets without a natural break.
- **LinkedIn first line is the hook.** The first line must work standalone — it is the only text visible before "see more". If the first line requires the rest of the post to land, it fails.
- **TikTok/YouTube: result or interrupt first, not preamble.** Never open with "In this video I will..." or "Today we're going to...". Show the result or interrupt the pattern in the first 3 seconds of script.

### Default Behaviors (ON unless disabled)

- **Extract 3-7 atomic ideas from the source asset.** Fewer than 3 means underutilization. More than 7 means the asset lacks coherence and should be split.
- **Primary platform first in delivery.** If a primary platform was stated, that draft leads the delivery.
- **Flag missing details before handoff.** Any draft containing placeholder text (`[URL]`, `[handle]`, `[date]`) must be flagged at delivery with what is needed to finalize it.

### Optional Behaviors (OFF unless enabled)

- **Multi-idea series**: Extract all ideas and schedule as a series (pairs with `content-calendar`)
- **Voice profile application**: After drafting, apply a voice profile via `voice-writer`
- **Immediate publish**: After gate passes, hand off to `x-api` or `crosspost`

---

## Phase 1: GATHER — Collect Inputs Before Writing Anything

**Goal**: Establish everything needed to write platform-native variants. Do not begin writing until this phase is complete.

**Required inputs:**

| Input | Description | If Missing |
|-------|-------------|------------|
| Source asset | The content being adapted (article text, demo description, launch doc, insight, transcript) | Ask — required |
| Target platforms | X, LinkedIn, TikTok, YouTube, newsletter — one or many | Ask if not inferable from context |
| Audience | Builders, investors, customers, operators, general | Infer if a strong signal exists; ask if ambiguous |
| Goal | Awareness, conversion, recruiting, authority, launch support, engagement | Infer from source if obvious; ask otherwise |
| Constraints | Character limits already observed, brand voice notes, phrases to avoid | Skip if none stated |

**Gate**: Source asset present AND at least one target platform identified. If either is missing, ask before proceeding.

Do not write any content in this phase. Only collect and confirm inputs.

---

## Phase 2: EXTRACT — Identify 3-7 Atomic Ideas

**Goal**: Identify the discrete, postable units inside the source asset. Each atomic idea must be able to stand alone as a post on at least one platform without requiring the reader to know the source.

**Steps:**

1. Read the full source asset
2. Identify ideas that meet the criteria:
   - Specific (concrete claim, result, observation, or instruction — not a vague theme)
   - Standalone (no dependency on other ideas in the list to be understood)
   - Relevant to the stated goal and audience
3. Rank by relevance to the stated goal
4. Write each atomic idea as one sentence maximum

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

**Gate**: 3-7 numbered atomic ideas saved to `content_ideas.md`. Each is specific and standalone. Proceed only when file exists.

---

## Phase 3: DRAFT — Write Platform-Native Variants

**Goal**: Write one draft per target platform, each starting from the primary atomic idea (or specified idea) as raw material. Drafts are written from scratch per platform — not shortened or trimmed from each other.

Apply platform-specific rules (see `references/platform-specs.md` for full detail):

### X (Twitter)

- **Register**: Conversational, direct, opinionated. No corporate voice.
- **Hook**: Open fast. The first tweet carries the entire weight — if it doesn't stop the scroll, the thread dies.
- **Structure for single tweet**: One idea, one sharp claim, optionally one proof point. End with a question or strong assertion, not a CTA.
- **Structure for thread**: Each tweet carries one thought. Segment at natural breaks. Number tweets only if ≥5. No cliffhanger tweets that require the next to make sense.
- **Character limit**: 280 per tweet, hard limit.
- **Hashtags**: 0-2 maximum. Only if they add discoverability, never for decoration.
- **Links**: One link only, at the end of the last tweet if needed. Not in the middle of a thread.
- **CTAs**: Optional. If present, one sentence, at the end, low pressure.

### LinkedIn

- **Register**: Professional but human. Not corporate. Lessons and results framing over announcement framing.
- **Hook**: First line must work standalone before "see more". It is a promise, not a topic sentence.
- **Structure**: First line → 2-4 short paragraphs of substance → optional takeaway or question at end.
- **Length**: 150-300 words optimal. Can go to 600 if the content earns it. Not longer.
- **Hashtags**: 3-5 at the end. Relevant, not decorative.
- **Links**: Put in comments, not in the post body. LinkedIn suppresses posts with external links.
- **CTAs**: One soft CTA at end if appropriate (follow for more, drop your take in comments).

### TikTok

- **Format**: Short video script (voiceover or talking-head style).
- **First 3 seconds**: Show the result, state the unexpected thing, or interrupt a pattern. Never start with "In this video...". This is the make-or-break moment.
- **Hooks matter more than summaries.** A weak hook with great content fails. A strong hook with decent content succeeds.
- **Length**: 30-60 seconds optimal (150-300 words at speaking pace).
- **Structure**: Hook (3s) → one demonstration or explanation → punchline or twist → CTA (5s max).
- **No lists or headers in the script.** Write it to be spoken aloud.

### YouTube

- **Format**: Video script or description (specify which in the draft).
- **Show result early**: Within the first 30 seconds of script, show or state the result. Do not build to it.
- **First 3 seconds**: Same rule as TikTok — interrupt or result, not preamble.
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

**Gate**: One draft per target platform saved to `content_drafts.md`. No two drafts share a verbatim sentence (self-check before running scripts in Phase 4). Proceed only when file exists.

---

## Phase 4: GATE — Quality Check Before Delivery

**Goal**: Mechanically verify drafts before delivery. LLM self-assessment is a secondary check only. Both script checks must exit 0. The gate cannot be bypassed.

### Check 1: Hype Phrase Scan

```bash
python3 scripts/scan-negative-framing.py --mode hype --drafts content_drafts.md
```

This check flags banned hype phrases. Hard-rejected phrases include:

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

**If exit non-zero**: Identify the flagged draft(s), rewrite only the affected sections, save to `content_drafts.md`, re-run the check. Do not proceed to Phase 5 until exit 0.

### Check 2: Cross-Platform Verbatim Check

```bash
python3 scripts/scan-negative-framing.py --mode cross-platform --drafts content_drafts.md
```

This check identifies any sentence appearing verbatim in two or more platform sections of `content_drafts.md`.

**If exit non-zero**: Rewrite the flagged sentence(s) in one of the two platforms where they appear. The rewrite must be platform-native — not a synonym swap. Re-run the check. Do not proceed to Phase 5 until exit 0.

### Secondary LLM Check (after scripts pass)

Once both scripts exit 0, verify:
- [ ] Each draft reads natively for its platform (register, length, formatting feel right)
- [ ] Every hook is strong and specific — not a topic sentence, not a summary opener
- [ ] CTAs match the stated goal and platform norms
- [ ] No placeholder text that cannot be published as-is (flag these, do not remove them)

**Gate**: Both script checks exit 0. All LLM checklist items confirmed. Update `content_drafts.md` status from `DRAFT — pending Phase 4 gate` to `READY`. Proceed to Phase 5 only when gate passes.

---

## Phase 5: DELIVER — Present Drafts with Posting Guidance

**Goal**: Hand off clean drafts with enough context for the user or a downstream skill to act immediately.

**Delivery order**: Primary platform first (if specified), then remaining platforms alphabetically.

**For each draft, include:**
1. The draft text (from `content_drafts.md`)
2. Optimal posting time if known (platform norms: X/LinkedIn weekdays 8-10am, TikTok evenings, Newsletter Tuesday-Thursday)
3. Any remaining placeholders that must be resolved before publishing (flag clearly)
4. Suggested posting order if multiple platforms (e.g., "post X first to gauge reaction, then LinkedIn 48 hours later")

**Downstream handoff options:**

| If user wants to... | Route to |
|---------------------|----------|
| Publish to X | `x-api` skill |
| Publish to multiple platforms | `crosspost` skill |
| Schedule posts | `content-calendar` skill |
| Apply a voice profile to drafts | `voice-writer` skill (post-process these drafts) |
| Extract more ideas from the same source | Re-run from Phase 2 |

**Artifacts produced:**
- `content_ideas.md` — 3-7 numbered atomic ideas with ranking
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

## Anti-Patterns

### Anti-Pattern 1: Summarizing instead of adapting
**What it looks like**: LinkedIn draft that opens with "This article covers..." or X tweet that says "New post: [title]. Key points: 1, 2, 3. Link in bio."
**Why wrong**: Summaries give readers no reason to stop scrolling. They signal the platform-native content is elsewhere.
**Do instead**: Extract one atomic idea and write a post that delivers value on its own, with the link as optional context.

### Anti-Pattern 2: Copy-paste-shorten across platforms
**What it looks like**: LinkedIn draft is the X thread with hashtags added. TikTok script is the LinkedIn draft read aloud.
**Why wrong**: Fails the cross-platform verbatim check. Also fails the native-read check — audiences on each platform recognize content that was not written for them.
**Do instead**: Start each draft from the atomic idea, not from another platform's draft.

### Anti-Pattern 3: Bypassing the gate with self-assessment
**What it looks like**: "I reviewed the drafts and they look clean" without running the scripts.
**Why wrong**: LLM self-assessment misses hype phrases in context and cannot do verbatim comparison reliably.
**Do instead**: Run both script checks. If scripts are unavailable, use Grep manually and document that the automated gate was not run.

### Anti-Pattern 4: Hype phrasing in hooks
**What it looks like**: "Excited to share our game-changing approach to..."
**Why wrong**: Fails the hype scan. Also reads as corporate noise — the audience stops reading.
**Do instead**: Open with a specific result, number, counterintuitive claim, or observation. "We cut deploy time by 80%. Here is what actually changed."

### Anti-Pattern 5: Identical CTAs across platforms
**What it looks like**: Every draft ends with "Check out the full article in the comments!"
**Why wrong**: LinkedIn suppresses posts with external links. X readers expect links at end of threads. Newsletter readers want a different action than social followers.
**Do instead**: Match CTA to platform norms. For LinkedIn: put link in comments and reference that. For X: link at end of last tweet. For newsletter: inline or button.

### Anti-Pattern 6: Producing all platforms when only one was requested
**What it looks like**: User says "turn this into an X thread" and skill produces X + LinkedIn + TikTok drafts.
**Why wrong**: Wastes effort and signals the skill didn't understand the request.
**Do instead**: Produce exactly what was requested. Offer to expand to other platforms in Phase 5.

---

## References

- `${CLAUDE_SKILL_DIR}/references/platform-specs.md` — Character limits, format rules, and posting norms per platform
- `scripts/scan-negative-framing.py` — Negative framing and hype phrase detection
