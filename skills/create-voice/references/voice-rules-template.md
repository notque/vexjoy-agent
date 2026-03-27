# Voice Rules Template

Detailed reference for Step 4: RULE of the create-voice pipeline.

---

## What This Voice IS (Positive Identity)

Write 4-6 core traits with examples from the samples. Use probability dampening to avoid caricature:

- **"subtly" skeptical** not "skeptical" -- dampens the trait so it appears naturally, not performatively
- **"generally" conversational** not "conversational" -- allows for variation
- **"slightly" self-deprecating** not "self-deprecating" -- prevents over-application

For each trait, include 2-3 exact quotes from samples that demonstrate it.

Use dampening adverbs because without them the model cranks traits to 100%. "Skeptical" becomes every-sentence-is-a-challenge. "Conversational" becomes aggressively casual.

---

## What This Voice IS NOT (Contrastive Identity)

Build a contrastive table showing THIS voice vs Generic AI for at least 6 aspects:

| Aspect | This Voice | Generic AI |
|--------|-----------|------------|
| Opening | [Example from samples] | "In today's rapidly evolving landscape..." |
| Uncertainty | [How they express doubt] | "It's worth noting that perspectives may vary" |
| Agreement | [How they agree] | "I absolutely agree with your insightful point" |
| Disagreement | [How they disagree] | "While there are valid concerns, I would respectfully suggest..." |
| Conclusion | [How they end] | "In conclusion, we have explored..." |
| Technical | [Technical style] | "This represents a robust paradigm for..." |

---

## Hard Prohibitions

Identify patterns this voice NEVER uses. Apply attention anchoring (**bold**) to all negative constraints because the model pays more attention to bolded text:

Common prohibitions to evaluate:
- **Em-dashes**: Does this person ever use them? If not, FORBIDDEN
- **Formal transitions**: "However", "Furthermore", "Moreover", "Additionally", "Consequently"
- **AI-typical phrases**: "Let's dive in", "Here's the thing", "delve", "robust", "leverage", "ecosystem"
- **The "It's not X. It's Y" pattern**: Signature AI structure. Almost always prohibited
- **Excessive hedging**: "It's worth noting", "One might argue", "At the end of the day"

For each prohibition, explain WHY it's prohibited for this specific voice (not just "because it's AI-sounding").

---

## Wabi-Sabi Rules

Which "errors" MUST be preserved? This is the inversion of typical quality rules. Only include imperfections actually observed in the samples, because manufactured imperfections feel forced and are as detectable as forced perfection:

- If they write run-on sentences: "Allow comma-chain sentences up to {N} words when expressing enthusiasm or building arguments"
- If they use fragments: "Target {X}% fragment rate for emphasis and pacing"
- If punctuation is loose: "Do not standardize comma usage; match the inconsistent pattern from samples"
- If they self-correct: "Include at least one visible direction change per long-form response"

---

## Anti-Essay Patterns

Most voices are NOT essay-writers. Identify the structural anti-patterns:

- Staccato rhythm? (Short sentences dominating)
- No signposting? (No "First... Second... Third...")
- Single-sentence paragraphs? (Common in chat/forum)
- No introduction/conclusion structure? (Just starts talking)
- Abrupt endings? (No wrap-up, just stops)

---

## Architectural Patterns Template

Translate the linguistic architectures discovered in Step 3 into actionable rules for the voice skill. These go in a dedicated `## Architectural Patterns` section in the generated SKILL.md, between the identity rules and banned patterns.

For each documented architecture, write a rule:

```markdown
## Architectural Patterns

### Argument Flow
[Inductive/Deductive/Mixed] — [one-sentence description]
Build arguments by [specific instruction]. The main claim should appear [position].
Example from samples: "[exact quote showing the pattern]"

### Concessions
Structure: [short admission → pivot / long qualification → reversal / never concedes]
Pivot markers: [list of words this voice uses]
Example: "[exact quote]"

### Analogy Domains
Primary: [domain1, domain2]
Deployment: [where analogies appear — openers? mid-section? closers?]
Density: [frequency]
**NEVER draw analogies from**: [domains this voice avoids]
Example: "[exact quote]"

### Bookends
Opening move: [pattern]
Closing move: [pattern]
Symmetry: [yes/no/sometimes]
Example opening: "[quote]"
Example closing: "[quote]"
```

Omit any architecture that wasn't documented in Step 3. A missing section is better than a fabricated one.
