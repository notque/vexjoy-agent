# Voice Analysis Methodology

Detailed algorithms for extracting writing patterns from samples.

---

## 1. Sentence Analysis

### Length Calculation

```
Input: Raw markdown text
Output: Sentence length distribution

Algorithm:
1. Remove front matter (--- delimited YAML)
2. Remove code blocks (``` or indented 4 spaces)
3. Remove blockquotes (lines starting with >)
4. Remove markdown links, keep text: [text](url) -> text
5. Remove inline code: `code` -> code
6. Split by sentence terminators: . ! ?
7. Filter out:
   - Sentences < 3 words (likely headers or fragments)
   - Sentences that are just URLs
8. Count words in each remaining sentence
9. Categorize and calculate percentages
```

### Sentence Categories

| Category | Word Range | Typical Usage |
|----------|------------|---------------|
| Short | 3-10 | Impact statements, transitions |
| Medium | 11-20 | Standard explanations |
| Long | 21-30 | Complex ideas, caveats |
| Very Long | 31+ | Dense technical content |

### Fragment Detection

Fragments are intentional incomplete sentences for emphasis:
- Starts with lowercase (after period)
- No main verb
- Often single word or phrase: "Exactly." "Not anymore."

---

## 2. Opening Pattern Classification

### Categories and Detection

**Direct Fact Statement**
- Pattern: `[Subject] [verb] [object/predicate].`
- No hedging words: "In my experience", "It seems"
- No question
- Example: "Docker builds on this project took 8 minutes."

**Question Opener**
- Starts with: What, Why, How, When, Where, Who, Do, Does, Did, Can, Could, Should, Would, Is, Are, Have
- Ends with ?
- Example: "Why does this function take 3 seconds?"

**How/Why Explanation**
- Starts with: "Here's how", "Here's why", "This is how", "This is why"
- Example: "Here's how we cut build times by 80%."

**Story/Anecdote**
- Starts with: "Last [time]", "Yesterday", "Recently", "I was", "We were"
- Sets temporal scene
- Example: "Last week our CI pipeline started failing randomly."

**Preamble/Setup**
- Starts with: "In today's", "When it comes to", "As developers", "In the world of"
- Generic, could apply to many topics
- Example: "In today's fast-paced development environment..."

**Definition**
- Pattern: `[Term] is [definition]` or `[Term] means [definition]`
- Example: "A race condition is when two processes compete..."

### Scoring

For each sample, classify the opening pattern. Calculate distribution across all samples:
- 100% one pattern = highly consistent
- Mixed distribution = less distinctive

---

## 3. Word Frequency Analysis

### Transition Word Categories

```
Additive (adding information):
  also, and, moreover, furthermore, additionally, besides, equally,
  in addition, likewise, similarly, too

Contrast (showing difference):
  but, however, although, nevertheless, yet, whereas, while,
  on the other hand, in contrast, despite, even though

Cause/Effect (showing result):
  because, since, therefore, thus, so, consequently, as a result,
  hence, accordingly, due to

Sequence (showing order):
  first, second, third, then, next, finally, meanwhile, subsequently,
  afterward, before, after, initially

Example (illustrating):
  for example, for instance, specifically, such as, namely, including,
  to illustrate, in particular

Emphasis:
  indeed, in fact, certainly, definitely, absolutely, actually,
  especially, particularly
```

### Frequency Calculation

1. Normalize to per-1000-words rate
2. Compare to baseline frequencies (typical web content)
3. Mark as "preferred" if >150% of baseline
4. Mark as "avoided" if <50% of baseline

### Verb Analysis

Track active vs passive voice ratio:
- Active: Subject performs action ("We fixed the bug")
- Passive: Subject receives action ("The bug was fixed")

High active ratio (>80%) indicates direct style.

---

## 4. Structural Analysis

### Paragraph Metrics

```
1. Split content by double newlines (\n\n)
2. For each paragraph:
   - Count sentences
   - Note if single-sentence (emphatic style)
   - Measure word count
3. Calculate:
   - Average paragraph length (sentences)
   - Single-sentence paragraph frequency
   - Longest/shortest paragraph
```

### Header Frequency

```
1. Count all headers (# through ######)
2. Count total paragraphs
3. Calculate: paragraphs per header

Low ratio (2-3) = frequent headers, scannable
High ratio (8+) = dense prose, fewer breaks
```

### List Usage

```
Categories:
- Rare: <1 list per 1000 words
- Moderate: 1-3 lists per 1000 words
- Frequent: >3 lists per 1000 words

Also note:
- Bullet vs numbered preference
- List item length (word count)
```

---

## 5. Tone Analysis

### Formality Indicators

**Casual markers:**
- Contractions (don't, can't, won't)
- First person singular (I, me, my)
- Colloquialisms (gonna, gotta, kinda)
- Sentence fragments
- Exclamation points

**Formal markers:**
- No contractions
- Third person or passive voice
- Complete sentences only
- Technical terminology without explanation
- Semicolons and colons

**Scoring:**
- Count casual markers per 1000 words
- Count formal markers per 1000 words
- Net score determines formality level

### Humor Detection

Look for:
- Parenthetical asides with irony
- Hyperbole for effect
- Self-deprecation
- Unexpected comparisons

Note: This is subjective. Mark as "detected in X samples" rather than percentage.

### Person Usage

```
First person singular: I, me, my, mine, myself
First person plural: we, us, our, ours, ourselves
Second person: you, your, yours, yourself
Third person: he, she, it, they, one, the user, developers

Calculate distribution across total pronouns.
```

---

## 6. Punctuation Patterns

### Key Punctuation to Track

| Symbol | What It Indicates |
|--------|-------------------|
| , (comma) | Clause complexity, breath pauses |
| ; (semicolon) | Formality, complex sentence linking |
| : (colon) | Elaboration style, list introduction |
| -- (em dash) | Interruption style, emphasis |
| ... (ellipsis) | Trailing thought, informal |
| ! (exclamation) | Enthusiasm, emphasis level |
| ? (question) | Engagement, rhetorical style |
| () (parentheses) | Asides, qualifications |

### Calculations

Per-sentence averages:
- Commas per sentence
- Parenthetical asides frequency

Style indicators:
- Em dash vs colon preference (for elaboration)
- Question frequency in non-intro positions

---

## 7. Distinctive Element Identification

### Deviation Threshold

A pattern is "distinctive" if it deviates >20% from generic baseline:

**Generic Baselines (typical web content):**
- Sentence length: 15-20 words average
- Paragraph length: 3-4 sentences
- Transition frequency: moderate
- Opening style: mixed (25% each major type)
- Formality: neutral
- First person: occasional

### Distinctiveness Scoring

For each pattern:
1. Calculate sample value
2. Compare to baseline
3. Calculate deviation percentage
4. If >20% deviation, mark as distinctive

Rank distinctive elements by:
1. Consistency across samples (appears in all vs some)
2. Deviation magnitude (30% more distinctive than 21%)

---

## 8. Sample Size Considerations

### Minimum Requirements

- 3 samples: Minimum viable analysis
- 5 samples: Recommended for reliable patterns
- 10+ samples: High confidence, can detect subtle patterns

### Handling Variation

If pattern varies significantly across samples:
- Report the range, not just average
- Note which samples deviate
- Consider if variation is intentional (topic-dependent)

### Weighting

Recent samples weighted more heavily if writing style evolves:
- Last 3 months: 100% weight
- 3-12 months: 75% weight
- 12+ months: 50% weight

Weight by word count (longer samples more reliable).
