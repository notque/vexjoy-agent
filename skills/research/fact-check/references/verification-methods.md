# Verification Methods

Method detail for Phase 2 of the fact-check skill. Each method states when to use it, the procedure, and what counts as a result.

## Lateral Reading

**When**: judging whether a source is trustworthy for this claim.

Professional checkers read *across* sources rather than *down* one source: they leave the page and ask what independent sources say about the publisher, the author, and the claim. A site's own About page, design polish, and confident tone measure presentation, which anyone can buy.

Procedure:
1. Identify the publisher and author of the source.
2. Search for what independent outlets, databases, or experts say about that publisher and that claim.
3. Weigh the source by its external reputation and track record on this topic, plus any stake it holds in the claim.

Results: a credibility note per source — who runs it, what stake they have in the claim, what independent coverage says. A source with a direct stake (vendor benchmarking its own product, campaign citing its own poll) still counts as evidence; record the stake so adjudication can weigh it.

## Source-Tier Climbing

**When**: the available evidence cites something else.

Every citation chain has an origin. Verify at the highest tier reachable, because each repetition step can introduce paraphrase drift, dropped qualifiers, and unit errors.

| Tier | Examples | Weight |
|------|----------|--------|
| 1 — Primary | Original study, court filing, transcript, raw dataset, the press release itself, financial filing | Strongest — the claim's origin |
| 2 — Direct secondary | Reporting that interviewed the principals or read the primary document | Strong, subject to paraphrase drift |
| 3 — Derived | Aggregators, wire rewrites, summaries of summaries | Weak — count toward volume only after tracing to their origin |

Procedure: follow each citation upward until you reach the origin or the chain breaks. A broken chain (the cited study cannot be found, the linked page no longer states the figure) caps the claim at Unverifiable regardless of how many tier-3 repetitions exist.

## Triangulation

**When**: the claim is contested, surprising, damaging, or load-bearing for the document's argument.

Rule: two independent sources. Independence means separate origins — two outlets republishing the same wire story, or ten pages all citing one press release, count as one source. Trace each candidate source to its origin (see tier climbing) before counting it.

One source suffices for routine, uncontested facts read from a primary document: a date in the minutes, a figure in the filing.

When triangulation finds disagreement between independent sources, that is a Disputed finding, with both sources recorded — agreement was the goal, disagreement is the result.

## Quote Verification

**When**: the document quotes anyone.

Three axes; all must hold for Verified:

| Axis | Check | Failure |
|------|-------|---------|
| Exact words | Quoted text matches the source verbatim, ellipses and brackets disclosed | Altered, trimmed, or invented wording → Disputed |
| Speaker | Source confirms this person said it | Right words, wrong mouth → Disputed (misattribution) |
| Context | Surrounding source text supports the meaning the document assigns | Real quote, contradicted meaning → Disputed (context stripping) |

Procedure: locate the quote in the highest-tier source (transcript beats article), diff the wording character-by-character for numbers and operative words, confirm the speaker in the source's own attribution, then read the paragraph around the quote and compare its point to the document's framing.

Famous-sounding aphorisms attributed to famous people deserve extra suspicion — misattributed aphorisms are the most-recycled quote error, and prior repetition is what makes them feel verified.

## Burden of Proof

The default state of every claim is unproven. The checker's job is to find evidence, and the verdict follows the evidence found:

- Evidence supports → Verified.
- Evidence contradicts → Disputed.
- Evidence engages but settles nothing → Unverifiable.
- No evidence addresses it → Missing-source.

Plausibility, author reputation, and "it sounds right" move nothing — fabrications survive review precisely because they sound right.
