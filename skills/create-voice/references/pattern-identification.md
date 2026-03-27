# Pattern Identification Guide

Detailed reference for Step 3: PATTERN of the create-voice pipeline.

---

## Phrase Fingerprints (CRITICAL)

Read through ALL samples and identify 10+ distinctive phrases that recur. These are what authorship-matching roasters use to confirm identity.

Look for:
- **Signature openers**: How do they start responses? ("I think the issue is...", "So basically...", "Here's what I've found...")
- **Signature closers**: How do they end? ("but we'll see", "does that help?", "anyway, that's my take")
- **Filler phrases**: Verbal tics that appear across contexts ("For what it's worth", "to be fair", "honestly")
- **Hedging patterns**: How they express uncertainty ("probably", "I suspect", "my guess is")
- **Emphasis patterns**: How they stress a point ("the key thing is", "the part people miss")

Document each fingerprint with 2-3 exact quotes from the samples showing it in context.

---

## Thinking Patterns

How does this person reason? This is deeper than style; it's cognitive architecture.

Common patterns to check for:
- **Concede-then-assert**: "That's fair, but..." (acknowledges opposing view, then states own position)
- **Hypothesis-experiment**: "My theory is... I tried... and found..."
- **Systems framing**: "The way this works is..." (explains mechanisms, not just opinions)
- **Experience-based**: "In my experience..." (grounds claims in personal observation)
- **Question-led**: "The question is..." (frames issues as questions to investigate)
- **Analogy-driven**: Uses metaphors and comparisons from specific domains

---

## Response Length Distribution

From the samples, estimate what percentage of responses fall into each bucket:
- Very short (1 sentence): ____%
- Short (2-3 sentences): ____%
- Medium (4-6 sentences): ____%
- Long (paragraph+): ____%

This distribution is critical because most people write short responses most of the time, and AI tends to generate medium-to-long responses by default.

---

## Natural Typos (Authenticity Markers)

Scan samples for 5+ real typos. Document them with the correct spelling. These become wabi-sabi markers that signal authenticity. Do NOT treat these as errors to correct, because those "imperfections" ARE the voice -- perfection is an AI tell.

Examples of what to look for:
- Missing apostrophes ("dont" instead of "don't")
- Common word swaps ("there" for "their")
- Dropped letters ("probabl" for "probably")
- Double-typed characters ("tthe")
- Missing spaces after punctuation ("works.But")

---

## Wabi-Sabi Markers

Identify which "imperfections" ARE the voice. These are not bugs to fix; they are features to preserve.

- Run-on sentences: Does this person chain clauses with commas?
- Fragments: Do they use sentence fragments for emphasis?
- Loose punctuation: Is comma usage inconsistent? Is that part of the texture?
- Self-corrections: Do they change direction mid-sentence? ("Well, actually..." or "I mean,")
- Tangential asides: Do they go on tangents? (Parenthetical digressions?)

---

## Linguistic Architectures

Beyond sentence-level patterns, identify the **structural moves** that operate across sentences and paragraphs. These are what AI erases most aggressively -- the model defaults to claim -> evidence -> hedged conclusion regardless of the writer's actual architecture.

Analyze ALL samples (not just a few) for each dimension:

### Argument Architecture

How does the writer build a case?
- **Direction**: Inductive (examples -> conclusion) vs deductive (claim -> evidence) vs mixed? Where does the main claim appear relative to supporting evidence?
- **Escalation**: Do stakes increase through the piece? Narrow -> broad? Low -> high severity?
- **Ending reframe**: Does the ending restate the opening, or transform it into something new?

Document with exact quotes: "In {N} of {M} samples, the writer builds inductively -- evidence first, conclusion last. Example from sample X: [quote showing the build]"

### Concession Architecture

How does the writer handle "yes, but"?
- **Structure**: Short admission -> pivot? Long qualification -> reversal? Never concedes?
- **Pivot markers**: Which words signal the turn? ("but", "though", "the thing is", "and yet", "that said")
- **Position**: Where do concessions appear? Opening? Mid-argument? Never at the end?

Document with exact quotes: "Concessions follow a [short admission -> blunt pivot] pattern. Example: [quote showing concession shape]"

### Analogy Architecture

Where do metaphors and references come from?
- **Source domains**: Which fields? (cooking, construction, sports, warfare, nature, machinery, music, software, etc.)
- **Deployment**: Are analogies used to open? To explain mid-section? To close with a memorable image?
- **Density**: Every post? Rarely? Only for technical concepts?

Document with exact quotes: "Analogies cluster around {domains}. Example: [quote showing analogy from that domain]"

### Bookend Architecture

How do pieces open and close?
- **Opening moves**: Question? Declarative claim? Anecdote? Provocation? Scene-setting?
- **Closing moves**: Reframe? Fragment punch? Circle back to opening? Call to action? Open question?
- **Symmetry**: Does the closing echo or answer the opening?

Document with exact quotes: "Opens with [pattern] in {N}/{M} samples. Closes with [pattern]. Opening and closing are [symmetric/independent]."

---

## Architecture Coverage Note

Not all writers exhibit all 4 architectures. Tweet-only writers may not have argument or bookend architecture. The gate requires 2 of 4, not 4 of 4.
