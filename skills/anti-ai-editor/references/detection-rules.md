# Detection Rules

Quick-reference for inline detection during editing. For full regex patterns, see `detection-patterns.md`. For complete replacement lists, see `cliche-replacements.md`.

---

## High-Priority Flags (Almost Always Fix)

| Pattern | Issue | Fix |
|---------|-------|-----|
| "delve into" | AI cliche | remove or use "examine", "explore" |
| "In today's [X]" | Empty opener | Remove entire phrase |
| "embark on a journey" | AI cliche | cut entirely |
| "It's important to note" | Throat-clearing | start with the note |
| "robust and comprehensive" | Double fluff | pick ONE specific word |
| "leverage" (non-physics) | Corporate AI | "use" |
| "utilize" | Pompous | "use" |
| "facilitate" | Vague | "help", "enable", or be specific |
| "In this article" | Meta | Remove |
| "As we've discussed" | Meta | Remove |
| "Let me explain" | Meta | Just explain |
| "at the end of the day" | Cliche | cut, or be specific |
| "the failure mode nobody's naming" | Novelty inflation | State the actual pattern |
| "what nobody tells you about" | Engagement bait | Just write the content |

## High-Priority Flags: Copula Avoidance (Almost Always Fix)

| Pattern | Issue | Fix |
|---------|-------|-----|
| "serves as a" | Copula avoidance | "is a" |
| "stands as a" | Copula avoidance | "is a" |
| "functions as a" | Copula avoidance | "is a" |
| "acts as a" | Copula avoidance | "is a" (unless describing actual role) |
| "boasts a/the" | Inflated "has" | "has a/the" |
| "features a/the" | Inflated "has" | "has a/the" |
| "offers a/the" | Inflated "has" | "has a/the" |
| "is a testament to" | Puffery | Rewrite with specific claim |
| "indelible mark" | Puffery | "changed", "influenced" |
| "enduring legacy" | Puffery | Be specific about what endures |
| "the future looks bright" | Generic closer | Remove or state specifics |
| "continues to evolve" | Generic closer | State what actually changed |

## High-Priority Flags: News Article AI Tells (Almost Always Fix)

| Pattern | Issue | Fix |
|---------|-------|-----|
| "worth sitting with" | Pseudo-profound | Remove -- if it's worth sitting with, the reader knows |
| "deserves a closer look" | Pseudo-profound | State what the closer look reveals, or cut |
| "let that sink in" | Pseudo-profound mic-drop | Remove entirely |
| "worth noting" (throat-clearing) | Pseudo-profound | Just state the fact |
| "consequences extend beyond" | Abstract philosophizing | State the specific downstream effect |
| "transcends the event itself" | Abstract philosophizing | Be specific about what it affects |
| "that's the kind of" | Meta-significance | Rewrite with specific stakes |
| "this is exactly why/what/how" | Meta-significance | Remove framing, let facts speak |
| "you'd be hard-pressed" | Meta-significance | Make the claim directly |
| "it's hard to overstate" | Meta-significance | State the specific impact |
| LONG-SHORT-LONG rhythm (3+) | Dramatic AI rhythm | Merge short sentences into surrounding context |

## Medium-Priority Flags (Context-Dependent)

| Pattern | When to Fix | When to Keep |
|---------|-------------|--------------|
| "optimize" | Generic use | Specific technical context |
| "seamless" | Marketing fluff | Describing actual integration |
| "cutting-edge" | Empty hype | Genuinely novel tech |
| Passive voice | General prose | Scientific writing, logs |
| Lists | Prose would be clearer | Actual enumerable items |

---

## Structural Checks

### Sentence Length Monotony
- Check: Are 5+ consecutive sentences within 5 words of each other?
- Fix: Apply short-long-medium pattern. Punch. Develop. Land.
- Target: 5-50 word range across a paragraph

### Missing Extended Metaphor
- Check: Are metaphors decorative one-liners?
- Fix: Develop metaphors across paragraphs, or cut them entirely
- Example: "Think of the crowd as a guitar" -> develop for 3+ sentences

### Preamble Detection
- Check: Does paragraph 1 contain no actual information?
- Fix: Replace with hook (provocative question, news lead, bold claim)

### Summary Closing
- Check: Does ending summarize what was covered?
- Fix: Replace with callback close, implication close, or emotional crescendo

### Dangling Participial Phrases (-ing Clauses)
- Check: Does sentence end with ", highlighting/underscoring/showcasing..." clause?
- Fix: Remove the trailing clause. If the idea matters, make it its own sentence.
- Example: "Revenue grew 20%, underscoring the significance" -> "Revenue grew 20%"

### Generic Positive Conclusions
- Check: Does ending use "future looks bright", "exciting times", "continues to thrive/evolve/grow"?
- Fix: Replace with specific fact, callback to opener, or cut entirely
- Example: "The future looks bright" -> [state what's actually planned next]

### Boldface Overuse
- Check: Are 30%+ of content lines mechanically bolded? Are 3+ list items `**Term** - desc`?
- Fix: Convert bold-term lists to prose paragraphs. Reduce bold to 1-2 critical items.

### Dramatic Short-Sentence AI Rhythm
- Check: Do 3+ consecutive sentence-pairs alternate between LONG (>15 words) and SHORT (<8 words)?
- Fix: Merge short dramatic sentences into surrounding context, or break the mechanical alternation
- Example: "The conference had eight sessions. Attendees had options. They chose this event." -> "The conference ran eight sessions and the registration rate showed attendees were in"
- Note: Single short-sentence punches are fine. Only flag the *pattern* of alternation.

### List Overuse
- Check: More than 2 bulleted lists in 500 words?
- Fix: Convert some to prose, especially if items need context

### Synonym Cycling
- Check: Do 3+ synonyms for the same concept appear in one paragraph? (e.g., "challenges", "obstacles", "hurdles")
- Fix: Repeat the clearest word. Real writers say "the bug" five times; AI rotates through "the issue", "the defect", "the problem", "the anomaly".
- Example: "We faced challenges. These obstacles required solutions. The hurdles were overcome." -> "We faced challenges. The challenges required solutions. We overcame them."

### False Concession
- Check: Does text use "While X is impressive, Y remains a challenge" where both halves are vague?
- Fix: Make both sides specific. "While the progress is impressive, challenges remain" -> "They shipped 3 features but broke the API twice"
- Note: Legitimate concessions have specific claims on both sides. Flag only when both halves are vague.

### Over-Polishing Warning
Aggressive de-AI editing can paradoxically push human writing TOWARD AI statistical profiles by removing natural disfluency. Per Pangram Labs research (trained on 28M documents), structural regularity is the #1 signal AI detectors weight -- above vocabulary.

Rules:
- Fix rhythm alongside words -- never words alone
- If editing makes every sentence 15-20 words, you've created an AI tell
- Preserve deliberate fragments, uneven pacing, idiosyncratic word choices
- After editing, verify sentence length still varies (5-50 word range)
- The wabi-sabi check exists for this reason: imperfections are features

## Structural Regularity Warning

Structural regularity (sentence/paragraph rhythm uniformity) is the #1 signal AI detectors weight, above vocabulary. This finding comes from Pangram Labs research on 28M documents. Fixing word choices while leaving uniform sentence length untouched leaves text classifiable as AI-generated.

**Implication:** Always fix rhythm alongside or before fixing individual words. Never apply word-level fixes alone and declare content de-AI'd. A document with zero AI cliches but perfectly uniform 18-word sentences will still flag as AI-generated.

---

## Voice Integration

When a voice is specified, also check voice-specific patterns:

### Voice-Specific Checks

Each voice skill defines anti-patterns. Examples from voice profiles:
- Check for monotonous sentence length
- Check for decorative (non-sustained) metaphors
- Check for summary conclusions
- Check for missing callback closes

### Universal Checks (all voices)

These apply regardless of voice:
- Banned words from references/banned-words.md
- AI cliches (delve, robust, comprehensive)
- News AI tells (worth sitting with, consequences extend beyond, that's the kind of, dramatic rhythm)
- Copula avoidance (serves as a, boasts a, features a)
- Dangling -ing clauses (highlighting, underscoring, showcasing)
- Significance puffery (testament to, indelible mark, enduring legacy)
- Generic positive conclusions (future looks bright, continues to evolve)
- Curly quotes in Markdown/plain-text contexts (ChatGPT-specific)
- Empty preambles ("In today's...")
- Meta-commentary ("In this article...")
