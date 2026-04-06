# Context Profiles

Content type detection and profile-specific tolerance rules. Different content types have different AI-pattern thresholds -- a bulleted list in documentation is normal, in a blog post it's a tell.

---

## Auto-Detection Rules

Detect profile before scanning. Apply in this order (first match wins):

```
1. Under 300 words + hashtags (#topic) or mentions (@name) → linkedin
2. Code blocks (```) + API references + technical architecture terms → technical-blog
3. Salutation ("Hi [name]", "Dear") + investor/fundraising language → investor-email
4. Step-by-step instructions + parameter docs + README structure → docs
5. Explicit user override → whatever they said
6. No strong signals → blog (default)
```

### Signal Patterns

```regex
# LinkedIn signals
\B#\w+\b
\B@\w+\b

# Technical-blog signals (require 2+ matches)
```[\w]*\n
\bAPI\s+(endpoint|reference|call|key|token)\b
\b(microservice|monolith|event[- ]sourc|CQRS|gRPC|REST|GraphQL)\b
\b(p99|p95|latency|throughput|SLA|SLO)\b

# Investor-email signals
^(Hi|Dear|Hello)\s+\w+
\b(raise|fundrais|runway|ARR|MRR|burn rate|Series [A-D]|seed round|valuation)\b

# Docs signals (require 2+ matches)
^#+\s*(Installation|Setup|Configuration|Usage|API Reference|Parameters|Getting Started)
\b(--\w+|`\w+`)\s+(flag|option|parameter|argument)\b
^\d+\.\s+\w+  # numbered steps
```

---

## Profile Definitions

### `linkedin`

Short-form professional content. Relaxed on formatting tells that are native to the platform.

**Relaxations:**
- Em dashes: allow up to 2 per post (platform convention)
- Bold: hooks and key phrases OK (platform convention)
- Emoji: 1-2 end-of-line emoji OK (platform convention)
- Bullets: skip list-overuse check (LinkedIn rewards scannable format)

**Still flag:** All Tier 1 cliches, copula avoidance, significance puffery, engagement bait (Tier 1g)

### `blog` (default)

Standard prose content. All rules apply at normal thresholds.

**Rules:** Full scan, all tiers, all structural checks.

### `technical-blog`

Technical prose with code examples, architecture discussion, and domain terminology.

**Exemptions:** The following words are NOT flagged when used in technical/API context:
- `robust` (describing fault tolerance, error handling)
- `comprehensive` (describing test coverage, documentation scope)
- `seamless` (describing actual integration behavior)
- `ecosystem` (describing software ecosystems, plugin systems)
- `leverage` (describing API capabilities, library features)
- `facilitate` (describing middleware, adapters, bridges)
- `streamline` (describing pipeline optimization, workflow automation)

**Still flag regardless of context:** `delve`, `tapestry`, `game-changer`, `embark`, `testament to`, `indelible mark`, `enduring legacy`, `in today's fast-paced world`

**Structural relaxations:**
- Code-prose-code alternation is normal, not a template monotony tell
- Technical list items (flags, parameters, config keys) skip list-overuse check

### `investor-email`

Fundraising updates, investor communications, board memos.

**Extra strict on:**
- Promotional language (Tier 1 cliches flagged at double weight)
- Significance inflation ("revolutionary", "game-changing", "unprecedented")
- Generic conclusions ("the future looks bright", "exciting times ahead")
- Vague metrics (flag any claim without a number)

**Rationale:** Investors read hundreds of these. AI-generated updates signal low effort and erode trust.

### `docs`

Technical documentation, READMEs, API references, setup guides.

**Relaxations:**
- Lists and bullets are normal -- skip list-overuse check entirely
- Template monotony threshold raised to 5+ consecutive identical sections (from 3)
- Passive voice threshold raised (documentation conventions)

**Still flag:** Platitude injection (CD-3), unearned confidence (CD-2), tour guide transitions (CD-7)

### `casual`

Informal content: Slack messages, forum posts, casual blog posts with conversational tone.

**Rules:** P0/Tier 1 only. Skip most structural checks.

**Flag only:**
- Tier 1 cliches (delve, leverage, utilize, facilitate, synergy, holistic, paradigm)
- Copula avoidance (serves as a, boasts a)
- Engagement bait (Tier 1g)

**Skip:** Structural monotony, list overuse, passive voice, fluff phrases, boldface overuse, contraction rate

---

## Tolerance Matrix

How each rule category applies per profile. `skip` = don't check, `relaxed` = higher threshold, `normal` = standard rules, `strict` = lower threshold, `extra-strict` = flagged at double weight.

| Rule Category | linkedin | blog | technical-blog | investor-email | docs | casual |
|---------------|----------|------|----------------|----------------|------|--------|
| Tier 1 cliches | normal | normal | relaxed (7 exemptions) | extra-strict | normal | normal |
| Copula avoidance | normal | normal | normal | normal | normal | normal |
| Novelty inflation (1g) | strict | normal | normal | strict | normal | normal |
| Synonym cycling (1h) | normal | normal | normal | normal | skip | skip |
| Meta-commentary | normal | normal | normal | normal | relaxed | skip |
| Dangling -ing (2b) | normal | normal | normal | strict | normal | skip |
| Significance puffery (2c) | normal | normal | normal | extra-strict | normal | skip |
| False concession (2e) | normal | normal | normal | strict | normal | skip |
| Emotional flatline (2f) | normal | normal | normal | strict | skip | skip |
| Generic conclusions (2d) | normal | normal | normal | extra-strict | normal | skip |
| Reasoning chains (2g) | normal | normal | normal | normal | normal | skip |
| Parenthetical hedging (3c) | normal | normal | normal | normal | normal | skip |
| Fluff phrases | normal | normal | normal | strict | normal | skip |
| Passive voice | normal | normal | relaxed | normal | relaxed | skip |
| Sentence monotony | relaxed | normal | normal | normal | relaxed | skip |
| List overuse | skip | normal | relaxed | normal | skip | skip |
| Boldface overuse | skip | normal | normal | normal | relaxed | skip |
| Em dashes | relaxed (2 OK) | normal | normal | normal | normal | skip |
| Curly quotes | normal | normal | normal | normal | normal | skip |
| Contraction rate | skip | normal | relaxed | normal | skip | skip |
| Template monotony | skip | normal | normal | normal | relaxed (5+) | skip |

---

## Usage

Apply the detected profile at the start of Phase 1 ASSESS, Step 1. Reference this matrix throughout scanning to skip, relax, or tighten rule application per category.

When a profile exempts a word (e.g., `robust` in `technical-blog`), verify the usage IS technical before exempting. "A robust solution" is still a tell. "Robust error handling with automatic retry and circuit breaking" is legitimate.
