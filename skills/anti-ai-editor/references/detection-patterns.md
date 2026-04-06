# Detection Patterns

Regex patterns and heuristics for detecting AI writing patterns.

---

## Pattern Matching Rules

### Tier 1: High-Confidence AI Cliches

```regex
# Single word replacements (case insensitive)
\bdelve[sd]?\b
\butilize[sd]?\b
\bleverage[sd]?\b
\bfacilitate[sd]?\b
\bsynerg(y|ies|ize|izing)\b
\bholistic(ally)?\b
\bparadigm\b
\bactionable\b
\bimpactful\b

# Phrase patterns
\bin today'?s\s+\w+\s+world\b
\bin today'?s\s+(fast-paced|modern|digital|competitive)\b
\bembark(s|ed|ing)?\s+on\s+a\s+journey\b
\bat the end of the day\b
\brobust and comprehensive\b
\bcomprehensive and robust\b
\bseamless(ly)?\s+integrat(e|es|ed|ing|ion)\b
\bcutting[- ]edge\b
\bstate[- ]of[- ]the[- ]art\b
\bgame[- ]?changer\b
\bdeep[- ]?dive\b
\bunpack(s|ed|ing)?\s+(this|that|the)\b
```

### Em-Dash and Double-Dash (Tier 1)

Em-dashes (---) and double-dashes (--) are strong AI formatting tells. **WordPress renders both as em-dashes.** This is one of the most reliably detectable AI patterns in news articles. Rewrite every sentence to not need them.
- Regex: `—|--`
- False positive note: YAML frontmatter delimiters (---) are NOT dashes in content
- **Fix strategy**: Rewrite using periods, commas, or parentheses. Never substitute one dash type for another.
  - WRONG: "framing it as historic -- the first woman to pull double duty"
  - RIGHT: "She framed it as historic. The first woman to pull double duty."
  - RIGHT: "She framed it as historic (the first woman to pull double duty)."

### Tier 2: Meta-Commentary

```regex
# Article self-reference
\bin this (article|post|guide|tutorial)\b
\bas (we've|we have) (discussed|seen|mentioned)\b
\blet me explain\b
\blet's (explore|examine|look at|dive into)\b
\bi('d| would) like to\b
\bwithout further ado\b
\bfirst and foremost\b
\blast but not least\b
\bin conclusion\b
\bto sum(marize)? up\b
\ball in all\b
\bhaving said that\b
\bthat being said\b
\bit goes without saying\b
\bneedless to say\b
\bit'?s (important|worth) (to note|noting) that\b
```

### Tier 3: Fluff Phrases

```regex
# Wordy constructions
\ba (wide )?variety of\b
\ba (large )?number of\b
\bdue to the fact that\b
\bin order to\b
\bfor the purpose of\b
\bin the event that\b
\bat this point in time\b
\bin the near future\b
\bon a (daily|regular|weekly) basis\b
\bin the process of\b
\b(is|are) able to\b
\bhas the (ability|capacity) to\b
\bin spite of the fact that\b
\bwith regard to\b
\bin light of\b
\bin terms of\b
\bby means of\b
\bfor all intents and purposes\b
\bthe fact of the matter is\b
\bwhen all is said and done\b
```

### Tier 4: Passive Voice Detection

```regex
# Common passive constructions
\bwas\s+\w+ed\s+by\b
\bwere\s+\w+ed\s+by\b
\bhas been\s+\w+ed\b
\bhave been\s+\w+ed\b
\bwill be\s+\w+ed\b
\bcan be\s+\w+ed\b
\bshould be\s+\w+ed\b
\bmust be\s+\w+ed\b
\bit was\s+\w+ed\s+that\b
\bit has been\s+\w+ed\s+that\b
```

### Tier 1c: False Agency (Inanimate Actors)

AI avoids naming human actors by giving agency to inanimate things. "The decision emerges" means someone decided. "The culture shifts" means people changed behavior. This is distinct from passive voice. The sentence HAS an active subject, but it's the wrong one.

```regex
# Inanimate subjects doing human verbs
\b(the decision|the culture|the conversation|the data|the market|the narrative|the dynamic|the tone)\s+(emerges?|shifts?|moves?|tells us|rewards?|becomes?|changes?|evolves?)\b

# Abstract processes with false autonomy
\b(a bet|the complaint|the problem)\s+(lives or dies|becomes a|turns into)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**The decision emerges** from discussion" | "The team decided after a two-hour meeting" |
| "**The culture shifts** toward openness" | "Engineers started sharing postmortems publicly" |
| "**The data tells us** that churn increased" | "Churn increased 15% in Q3 (we checked)" |
| "**The complaint becomes** a fix" | "The team fixed it within a week of the complaint" |

**False positive note:** "The market rewards" is legitimate in economics writing. "The data shows" is fine in technical contexts (vs "tells us" which anthropomorphizes). Flag only when a specific human actor could replace the inanimate subject.

### Tier 1d: Narrator-from-a-Distance (Observer Perspective)

AI floats above the scene as a detached narrator instead of putting the reader in it. "Nobody designed this" is observation from orbit. "You don't sit down one day and decide to build this" puts you in the chair.

```regex
# Detached observation from nowhere
\bnobody designed this\b
\bthis happens because\b
\bpeople tend to\b
\bone might argue\b
\bobservers note\b
\bcritics point out\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**Nobody designed this.** It emerged over time" | "You don't sit down one day and decide to build this. It accumulates" |
| "**People tend to** underestimate complexity" | "You'll underestimate how long this takes. Everyone does" |
| "**This happens because** teams avoid conflict" | "Your team avoids the hard conversation. Then the debt compounds" |

**Fix strategy:** Replace distant third-person observation with direct second-person address ("you") or specific first-person experience ("I", "we"). Put the reader in the room.

**False positive note:** Technical documentation legitimately uses observer perspective. "This happens because the GC runs during allocation" is fine. Flag only in persuasive, narrative, or opinion writing.

### Tier 1e: Dramatic Fragmentation

AI uses performative simplicity. A noun. A period. "That's it." Another period. This pattern announces significance rather than demonstrating it.

```regex
# "That's it. That's the [thing]." pattern
\.\s+That's it\.\s+That's the\b

# Staccato drama: "X. And Y. And Z."
\.\s+And \w+\.\s+And \w+\.

# Artificial revelation
\bThis unlocks something\.\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "Routing. **That's it. That's the** whole system." | "The whole system is routing. Everything else is support." |
| "Fast. **And** reliable. **And** cheap." | "It's fast, reliable, and cheap." |
| "**This unlocks something.** Velocity." | "This gives you velocity." |

**Fix strategy:** Complete sentences. Trust content over presentation. If something is significant, the facts will show it without dramatic formatting.

### Tier 1f: Performative Emphasis

AI tells the reader to feel something instead of presenting facts that create the feeling naturally.

```regex
# Emphasis crutches
\bfull stop\b
\blet that sink in\b
\bmake no mistake\b
\bthis matters because\b
\bhere's why that matters\b
\band that's okay\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "10,000 users in a week. **Let that sink in.**" | "10,000 users in a week, triple their previous best." |
| "Quality matters. **Full stop.**" | "Quality matters." (the period already stops) |
| "**Make no mistake**, this changes everything" | "This changes the deployment model entirely" |
| "It's messy. **And that's okay.**" | "It's messy. It works." |

**Fix strategy:** If you need to tell the reader something matters, the preceding facts didn't do their job. Fix the facts, then delete the emphasis.



```regex
# Absolute adjectives with modifiers
\bvery unique\b
\bcompletely (finished|destroyed|unanimous)\b
\babsolutely (essential|critical|necessary)\b
\btotally (destroyed|unanimous)\b
\bextremely (critical|essential|important)\b
\bhighly (innovative|unique)\b
\btruly (exceptional|unique)\b

# Filler words (context-dependent)
\bquite frankly\b
\bhonestly,?\s
\bbasically,?\s
\bliterally\b
\bactually,?\s
\breally\b
\bjust\b
\bsimply\b
\bobviously\b
\bclearly\b
```

---

## Structural Analysis Heuristics

### Sentence Length Monotony

Algorithm:
```
1. Split content into sentences
2. Calculate word count for each sentence
3. For windows of 5 consecutive sentences:
   - Calculate standard deviation of word counts
   - Flag if std_dev < 3 (too uniform)
4. Report "Monotonous sentence lengths in paragraph N"
```

Threshold: Flag if 5+ consecutive sentences are within 5 words of each other.

### Preamble Detection

Patterns for empty opening paragraphs:
```regex
# Starts with vague opener
^In (today's|our|the) (modern|current|digital|fast-paced)\b
^(As|When) (we|you) (think about|consider|look at)\b
^Have you ever (wondered|thought|considered)\b
^(Everyone|We all) knows?\b
^It's no secret that\b
^There's no doubt that\b
```

Flag first paragraph if:
- Contains 2+ patterns from above
- Contains no specific nouns, dates, or data
- Ends with a question (rhetorical opener pattern)

### Contraction Avoidance (AI Formality Tell)

AI models tend to avoid contractions, producing unnaturally formal text. In news articles and blog posts, humans use contractions at 80%+ rate. Low contraction rates are a strong AI signal.

**Detection heuristic:**
```
1. Count expandable contractions present: don't, can't, won't, isn't, aren't, hasn't, haven't, didn't, doesn't, shouldn't, wouldn't, couldn't, it's, he's, she's, they've, we've, he'd, she'd, they'd, we'd
2. Count missed contraction opportunities: "do not", "can not", "will not", "is not", "are not", "has not", "have not", "did not", "does not", "should not", "would not", "could not", "it is", "he is", "she is", "they have", "we have"
3. Calculate contraction rate: contractions / (contractions + missed opportunities)
4. Flag if rate < 75% (target for news articles: 82%+)
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "She does not plan to stop." | "She doesn't plan to stop." |
| "It is the first time..." | "It's the first time..." |
| "They have been building..." | "They've been building..." |
| "He would not comment." | "He wouldn't comment." |

**False positive note:** Contractions are inappropriate in direct quotes where the speaker used the formal form, and in legal/formal contexts. Skip this check inside blockquotes.

### List Overuse

Heuristic:
```
1. Count bulleted/numbered lists in content
2. Count total words in content
3. Calculate ratio: lists per 500 words
4. Flag if ratio > 2
```

Also flag when:
- List items could form a coherent paragraph
- List has 2 items (should be prose)
- List items are complete sentences (often should be paragraphs)

### Tier 1b: Copula Avoidance (AI Verb Substitution)

AI models avoid simple copulas ("is", "has", "are") by substituting unnecessarily complex verbs. Sourced from Wikipedia's WikiProject AI Cleanup via OpenClaw's Humanizer skill.

```regex
# "Is/are" avoidance — substituting complex verbs for simple copulas
\b(serves|stands|functions|acts)\s+as\s+(a|an|the)\b

# "Has" avoidance — inflated verbs replacing "has"
\b(boasts|features|offers)\s+(a|an|the)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "The library **serves as a** bridge between APIs" | "The library **is a** bridge between APIs" |
| "The framework **stands as a** testament to good design" | "The framework **is** a testament to good design" |
| "The package **functions as a** wrapper" | "The package **is** a wrapper" |
| "The city **boasts a** rich history" | "The city **has a** rich history" |
| "The platform **features a** modern UI" | "The platform **has** a modern UI" |
| "The SDK **offers a** simple interface" | "The SDK **has** a simple interface" |

**False positive note:** "serves as" is legitimate when describing actual service/duty roles (e.g., "She serves as the committee chair"). Flag only when substituting for "is".

### Tier 2b: Superficial -ing Analysis (Dangling Participial Phrases)

AI appends dangling participial phrases to sentences to add fake analytical depth. These trailing clauses sound insightful but say nothing specific.

```regex
# Trailing participial phrases that add fake depth
,\s*(highlighting|underscoring|emphasizing|showcasing|symbolizing|reflecting|fostering|cultivating|encompassing)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "The team shipped 3 features this quarter, **highlighting its importance** to the roadmap" | "The team shipped 3 features this quarter" |
| "Revenue grew 20%, **underscoring the significance** of the pivot" | "Revenue grew 20% -- the pivot paid off" |
| "The festival draws 50,000 visitors, **showcasing the diversity** of the region" | "The festival draws 50,000 visitors from across the region" |
| "The architecture uses event sourcing, **reflecting** modern design trends" | "The architecture uses event sourcing" |

**Fix strategy:** Usually remove the trailing clause entirely. If the idea matters, make it a standalone sentence with a specific claim.

### Tier 2c: Significance/Legacy Puffery

AI inflates the importance of mundane subjects with grandiose "legacy" and "testament" language. Common in biographical, historical, and organizational content.

```regex
# Testament phrasing
\b(is|stands?\s+as)\s+a\s+testament\s+to\b

# Landscape/evolving language
\b(pivotal|crucial|vital)\s+role\s+in\s+the\s+(evolving|ever-changing|shifting)\s+landscape\b

# Legacy/mark language
\bindelible\s+mark\b
\benduring\s+legacy\b
\blasting\s+(impact|impression|legacy)\b
\bprofound\s+(impact|influence|effect)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "Her career **is a testament to** hard work" | "She built her career through hard work" |
| "The company plays a **pivotal role in the evolving landscape**" | "The company is a major player in the market" |
| "He left an **indelible mark** on the industry" | "He changed how the industry works" |
| "The project's **enduring legacy** continues to inspire" | "The project still influences new work" |
| "This had a **profound impact** on the community" | "This changed the community" |

### Tier 2d: Generic Positive Conclusions

AI closes articles with vague optimism instead of specific forward-looking statements. Mirrors the preamble detection logic but for endings.

```regex
# Bright future closers
\bthe future (looks|is) bright\b
\bexciting times (lie|are) ahead\b
\bonly time will tell\b

# Continues to [vague verb]
\b(continues|continue) to (thrive|evolve|grow|inspire|shape)\b

# Poised/positioned language
\b(poised|positioned|well-positioned) (to|for)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**The future looks bright** for the project" | [Remove -- end with a specific fact or callback] |
| "**Exciting times lie ahead** for the community" | [Remove or state what's actually coming next] |
| "The framework **continues to evolve** and grow" | "The framework added async support in v3.2" |
| "The team is **poised to** deliver results" | "The team ships v2 next month" |
| "The organization **continues to thrive**" | [Be specific about what "thriving" means] |

**Fix strategy:** Replace with a specific fact, a callback to the opening, or simply cut the closing platitude.

### Tier 3b: Curly Quote Detection (ChatGPT-Specific)

ChatGPT outputs curly/smart quotes by default. In code-adjacent, Markdown, and plain-text contexts, humans use straight quotes. Presence of curly quotes in these contexts is a strong ChatGPT signal.

```regex
# Curly double quotes (left and right)
[\u201C\u201D]

# Curly single quotes / apostrophes (left and right)
[\u2018\u2019]
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| \u201CThis is a quote\u201D | "This is a quote" |
| it\u2019s working | it's working |
| \u2018single quoted\u2019 | 'single quoted' |

**False positive note:** Curly quotes ARE correct in typeset documents (books, PDFs, formal publications). Only flag in Markdown, README, code comments, blog posts, and plain-text contexts. Do NOT flag in `.docx`, `.pdf`, or formal publishing formats.

### Tier 1g: Novelty Inflation / Engagement Bait

AI treats established concepts as newly invented or uses "nobody talks about this" clickbait framing. Real writers cite prior art; AI manufactures exclusivity.

```regex
\b(the (failure mode|insight|pattern|problem) nobody'?s (naming|talking about|discussing))\b
\bwhat nobody tells you about\b
\bthe insight everyone'?s missing\b
\b(introduced|coined|invented) a term\b
\bthe thing (most people|nobody|few people) (get|miss|overlook)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**The failure mode nobody's naming**" | "A common failure mode in distributed systems" |
| "**What nobody tells you about** Kubernetes" | "Kubernetes networking trips up most developers" |
| "He **introduced a term** I hadn't heard before" | "He used the term X, which dates back to [origin]" |
| "**The thing most people miss**" | [State what they miss] |
| "**The insight everyone's missing**" | [State the insight directly] |

**Fix strategy:** If the concept is established, cite prior art. If it's genuinely new, let the novelty speak for itself without "nobody's talking about this" framing. Real discoveries don't need engagement bait.

**False positive note:** Legitimate when the writer genuinely coined a term (with evidence) or when referencing a documented gap in coverage. Flag when used as generic clickbait framing.

### Tier 1h: Synonym Cycling

AI rotates synonyms within paragraphs to avoid word repetition. Real writers repeat the clearest word. This is a structural tell -- the fix is counterintuitive.

**Detection heuristic (structural, not regex):**
```
1. Within each paragraph, extract key nouns and verbs
2. Identify synonym clusters (e.g., "challenges", "obstacles", "hurdles")
3. Flag when 3+ synonyms for the same concept appear in one paragraph
4. The fix is counterintuitive: repeat the clearest word
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "We faced **challenges**. These **obstacles** required creative solutions. The **hurdles** were eventually overcome." | "We faced challenges. The challenges required creative solutions. We overcame them." |
| "The system has **issues**. These **problems** cause errors. Such **difficulties** are hard to debug." | "The system has issues. The issues cause errors. The issues are hard to debug." |

**Fix strategy:** Pick the clearest word and repeat it. Real writers say "the bug" five times in a paragraph because "the bug" is what they mean. AI says "the bug", "the issue", "the defect", "the problem", "the anomaly" because it was trained to avoid repetition.

**False positive note:** Legitimate synonym variation exists -- "the API" and "the endpoint" may refer to different things. Flag only when synonyms clearly refer to the same concept within one paragraph.

### Tier 2e: False Concession

AI creates fake balanced analysis: "While X is impressive, Y remains a challenge" where both halves are vague. Real balanced analysis has specific claims on both sides.

```regex
\bwhile .+ (is|are|was|were) (impressive|notable|significant|remarkable|commendable),?\s+.+\s+(remains?|continues?|persists?|presents?)\s+(a )?(challenge|concern|issue|question)\b
\bdespite .+ (achievements?|progress|advances?|successes?),?\s+.+\s+(still|yet|nevertheless)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**While the progress is impressive, challenges remain**" | "They shipped 3 features but broke the API twice" |
| "**Despite notable achievements, concerns persist**" | "Revenue grew 20% but churn doubled" |

**Fix strategy:** Make both sides specific and falsifiable. If you can't name what's impressive or what the challenge is, the sentence contains no information. Replace with concrete claims on both sides of the "but".

**False positive note:** Legitimate concessions exist -- "While latency improved to 12ms, throughput dropped 15%" is real analysis with specific numbers. Flag only when both halves are vague.

### Tier 2f: Emotional Flatline

AI announces emotions instead of conveying them through the writing itself. "What surprised me most" tells; presenting the surprising fact shows.

```regex
\bwhat (surprised|struck|impressed|fascinated) me (most|was)\b
\bi was (fascinated|surprised|impressed|struck) (to discover|to learn|by|that)\b
\bwhat (really )?stands out (is|here)\b
\bthe most (surprising|fascinating|striking|impressive) (thing|part|aspect)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**What surprised me most** was the latency improvement" | "Latency dropped from 200ms to 12ms" |
| "**I was fascinated to discover** the architecture" | "The architecture uses an unusual event-sourcing pattern" |
| "**What really stands out** is the team's dedication" | "The team shipped three weekends in a row to hit the deadline" |
| "**The most surprising thing** was the error rate" | "The error rate was 0.001% -- lower than the monitoring threshold" |

**Fix strategy:** Earn the emotion through specific facts, not by declaring it. If the reader should be surprised, present the surprising fact. The feeling follows. If you need to tell the reader you were fascinated, the facts aren't doing their job.

**False positive note:** First-person emotional language is fine in personal essays and memoirs where the writer's inner experience IS the subject. Flag only in analytical, technical, or news content where facts should do the emotional work.

### Tier 2g: Reasoning Chain Artifacts

LLM scaffolding leaking into published output. Distinct from meta-commentary -- these are specifically chatbot thought-process markers that survive into final copy.

```regex
\blet me (think|break this down|walk through)\b
\bhere'?s my (thought process|reasoning|thinking)\b
\b(step [0-9]+|first,? let'?s)\s+(consider|think about|examine|look at)\b
\bbreaking this down\b
\bto (summarize|recap) (my|the) (thinking|analysis|reasoning)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**Let me think** step by step about this" | [Remove -- state the conclusion] |
| "**Breaking this down**, we can see..." | "The system has three components:" |
| "**Here's my thought process:**" | [Remove -- present the analysis directly] |
| "**To summarize my reasoning**" | [Remove -- the conclusion IS the summary] |

**Fix strategy:** Delete the scaffolding and present the conclusion or analysis directly. If the reasoning matters, structure it as an argument with evidence, not as a narrated thought process. Real writers don't annotate their cognition.

**False positive note:** Legitimate in educational content where showing the thought process IS the point (e.g., "Here's how I debug this kind of issue:"). Flag only when the scaffolding adds no instructional value.

### Tier 3c: Parenthetical Hedging

AI inserts hedge-parentheticals that add false precision or unnecessary qualification. These parenthetical asides create an illusion of nuance without adding information.

```regex
\(and,?\s+(increasingly|crucially|critically|notably),?\s+\w+\)
\(or,?\s+more precisely,?\s+.+?\)
\(and this is (key|important|crucial|critical)\)
\(though,?\s+(admittedly|arguably|perhaps),?\s+.+?\)
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "The API supports JSON **(and, increasingly, Protocol Buffers)**" | "The API supports JSON and Protocol Buffers" |
| "**(or, more precisely, a directed acyclic graph)**" | "-- technically a directed acyclic graph" |
| "**(and this is key)** the latency dropped" | "The latency dropped" |
| "**(though, admittedly, not without trade-offs)**" | "The trade-off: higher memory usage" |

**Fix strategy:** Remove the parenthetical. If the hedged information matters, state it directly as its own clause or sentence. If "increasingly" is meaningful, say when the increase started and how much. If "admittedly" qualifies something, state the specific qualification.

**False positive note:** Parenthetical asides are a legitimate stylistic device. Flag only when the aside contains hedge-words (increasingly, crucially, admittedly, arguably) that substitute for specifics.

### News Article AI Tells (Tier 1)

AI writing in news articles and event recaps produces distinct tells that differ from general prose. These patterns emerge when AI tries to sound like a journalist but lacks actual editorial instinct -- it substitutes pseudo-profundity for analysis and dramatic rhythm for real storytelling.

#### Pseudo-Profound Commentary

AI inserts "worth sitting with", "worth noting", "worth a pause" type phrases that add no information. These create a false sense of significance without any actual insight.

```regex
# "Worth" phrases that add no substance
\b(worth|deserves?)\s+(sitting with|a (second|moment|pause)|noting|a closer look)\b

# "Let that sink in" -- AI mic-drop that says nothing
\blet that sink in\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "That's **worth sitting with for a second**" | [Remove entirely -- if it's worth sitting with, the reader will do it without being told] |
| "That number **deserves a closer look**" | [State what the closer look reveals, or cut] |
| "The event drew 10,000 fans. **Let that sink in.**" | "The event drew 10,000 fans, their biggest gate since 2022" |
| "It's **worth noting** that this was her first product launch" | "This was her first product launch" |

**False positive note:** "Worth noting" is acceptable in genuinely parenthetical asides where the information IS the note (e.g., "Worth noting: the contract expires in June"). Flag when it's throat-clearing before stating a fact that should just be stated.

#### Abstract Philosophizing About Consequences

AI inflates the significance of events with abstract language about "consequences" and "beyond". Instead of stating what actually happened next, it gestures vaguely at importance.

```regex
# "Consequences extend beyond" -- abstract inflation
\b(consequences|implications)\s+(extend|go|reach)\s+(beyond|past|further than)\b

# "Beyond the night itself" -- vague significance gesture
\b(beyond|transcends?)\s+(the night|this moment|the keynote|the event)\s+itself\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "The **consequences extend beyond the night itself**" | "The loss means they drop out of the leadership track heading into the finals" |
| "The **implications go beyond** just this match" | "A loss here means they miss the tournament entirely" |
| "This **transcends the event itself**" | [State the specific downstream effect, or cut] |

**False positive note:** Legitimate when the sentence then immediately specifies what those consequences are (e.g., "The consequences extend beyond the roster -- it affects the entire promotion's TV deal"). Flag only when the abstraction IS the entire thought.

#### Dramatic Short-Sentence AI Rhythm

AI creates a pattern of: long sentence. Short dramatic sentence. Long sentence. This "mic drop" rhythm is a structural tell. Real journalists vary rhythm organically; AI alternates mechanically.

```
Detection heuristic:
1. Split into sentences, count words per sentence
2. For each consecutive pair, classify as LONG (>15 words) or SHORT (<8 words)
3. Flag when 3+ consecutive sentence-pairs alternate LONG-SHORT-LONG or SHORT-LONG-SHORT
4. This is a structural check, not a regex pattern
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "The conference featured eight sessions across four hours of content. **Attendees had options.** They could attend the flagship conference or catch the free pre-conference workshop. **They chose this event.** The registration rate reflected a hungry audience ready for something different." | "The conference ran eight sessions across four hours. Attendees who signed up -- and most did, given the registration rate -- got a packed agenda from start to finish." |

**Fix strategy:** Merge the short dramatic sentences into their surrounding context, or rewrite to break the mechanical alternation. Real writers use short sentences too, but not in a predictable pattern.

**False positive note:** A single short-sentence punch is fine and natural. Only flag the *pattern* of alternation -- three or more consecutive pairs switching between long and short. Also skip this check inside quoted speech.

#### Event/Review Commentary Clichés (Tier 2)

Domain-specific AI patterns that emerge when AI tries to sound enthusiastic but falls into generic prediction commentary instead of reporting.

```regex
# Prediction commentary -- editorial, not news
\bshould be a (must-see|intense one|highlight|instant classic|showdown)\b

# Explaining motivation -- telling instead of showing
\bthat's what \w+ does when\b

# Overused event descriptors
\b(blockbuster|stacked|loaded)\s+(card|lineup|show|event)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "This **should be a must-see**" | "Every time these two present, the event delivers" |
| "**That's what they do when** pushed" | "They delivered their best presentation of the year" |
| "A **blockbuster lineup** from top to bottom" | "Six headline acts. The organizers are not messing around" |
| "This **stacked lineup** has something for everyone" | [State what's in the lineup; let the reader decide] |

#### Bibliography Format Tell (Tier 1)

AI (especially ChatGPT) appends academic-style bibliography sections to news articles. Real news articles cite inline. A "Sources:" or "References:" section at the end of a news article is a strong AI tell.

```regex
# Bibliography headers at article end
^#+\s*(Sources|References)\s*:?\s*$
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| `## Sources:\n- Source A\n- Source B` | [No section — cite inline where the source IS the value] |
| `### References\n1. [Source A](url)\n2. [Source C](url)` | "The CEO told Bloomberg they first met their co-founder at a conference" — inline citation |

**Fix strategy:** Remove the bibliography section entirely. If any source in it represents original reporting worth linking (an interview, an exclusive), move that citation inline to where the information appears in the article. Public knowledge facts (session results, schedule announcements) need no citation at all.

#### Meta-Commentary on Significance

AI tells the reader HOW to feel about facts instead of just presenting them. It editorializes about why something matters rather than letting the facts speak.

```regex
# "That's the kind of" -- telling reader how to categorize
\bthat's the kind of\b

# "This is what/why/how" -- editorial significance framing
\b(this|that) is (exactly )?(what|why|how|where)\b

# "You'd be hard-pressed" / "hard to overstate" -- fake superlatives
\b(you'd be hard-pressed|it's hard to overstate)\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**That's the kind of** stakes that make an event feel like it actually matters" | "With the title and a promotion on the line, both teams had reason to compete" |
| "**This is exactly why** fans tune in every week" | [Remove -- let the preceding facts be the reason] |
| "**You'd be hard-pressed** to find a better closing keynote this year" | "Best closing keynote of the year so far" |
| "**It's hard to overstate** how important this win was" | "This win puts them in line for a shot at the title" |

**False positive note:** "This is what/why/how" is fine in factual explanations (e.g., "This is how the scoring works"). Flag only when used as editorial commentary framing significance, not when explaining mechanics. The test: does removing the phrase lose any factual information? If no, it's a tell.

---

## Structural Analysis Heuristics — Additional Checks

### Boldface Overuse (Mechanical Emphasis)

AI mechanically bolds key terms in lists and explanations, creating a pattern of `**term** -- explanation` that looks like a glossary rather than natural prose. This is a structural check, not a regex pattern.

**Detection heuristic:**
```
1. Count lines containing markdown bold (**text**)
2. Calculate ratio: bold lines per 10 content lines
3. Flag if ratio > 3 (more than 30% of lines have bold)
4. Also flag if 3+ consecutive list items follow the pattern: **Term** - description
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "- **Scalability** -- handles millions of requests" | "It handles millions of requests (scalability was the main goal)" |
| "- **Performance** -- optimized for speed" | "Speed was the priority, so we optimized the hot path" |
| "- **Reliability** -- 99.9% uptime guarantee" | "We guarantee 99.9% uptime" |

**Fix strategy:** Convert mechanical bold-term lists into prose paragraphs. If a list is genuinely needed, reduce bolding to only the most critical 1-2 items.

---

## Scoring System

Each issue type has a severity weight:

| Category | Weight | Description |
|----------|--------|-------------|
| AI Cliche (Tier 1) | 3 | Obvious AI tell |
| News AI Tell (Tier 1-News) | 3 | Pseudo-profound commentary, abstract philosophizing, meta-significance |
| Copula Avoidance (Tier 1b) | 3 | "Serves as a" replacing "is a" |
| Meta-commentary | 2 | Usually removable |
| Dangling -ing clause (Tier 2b) | 2 | Fake-depth trailing phrases |
| Significance puffery (Tier 2c) | 2 | "Testament to", "indelible mark" |
| Generic positive conclusion (Tier 2d) | 2 | "Future looks bright" closers |
| Dramatic AI rhythm (Tier 1-News) | 2 | Mechanical long-short-long alternation |
| Fluff phrase | 1 | Makes text wordy |
| Passive voice | 1 | Context-dependent |
| Redundant modifier | 1 | Easy fix |
| Curly quotes (Tier 3b) | 1 | ChatGPT-specific typography |
| Novelty inflation (Tier 1g) | 3 | Engagement bait / clickbait framing |
| Synonym cycling (Tier 1h) | 2 | Structural tell, counterintuitive fix |
| False concession (Tier 2e) | 2 | Fake balanced analysis |
| Emotional flatline (Tier 2f) | 2 | Declared vs demonstrated emotion |
| Reasoning chain artifact (Tier 2g) | 2 | LLM scaffolding in output |
| Parenthetical hedging (Tier 3c) | 1 | Unnecessary qualification |
| Structural issue | 2 | Affects readability |
| Boldface overuse (structural) | 2 | Mechanical emphasis patterns |

**Total Score Thresholds:**
- 0-5: Content appears natural
- 6-15: Light editing recommended
- 16-30: Significant editing needed
- 30+: Consider paragraph-by-paragraph review

---

## False Positive Prevention

### Technical Context Exceptions

Do NOT flag these in technical content:

```regex
# Legitimate technical uses
\boptimize[sd]?\s+(for|the)\s+(performance|memory|speed|latency)\b
\bleverage\s+(point|ratio|mechanical)\b
\bfacilitate\s+(communication|transfer)\s+between\b
\bscalable\s+(architecture|system|solution)\b
\becosystem\b  # When discussing software ecosystems
```

### Quote Preservation

Skip pattern matching inside:
- Code blocks (``` ... ```)
- Inline code (` ... `)
- Blockquotes (> ...)
- Quoted text ("...")

### Frontmatter Skip

Always skip content between:
```
---
[YAML frontmatter]
---
```

Parse frontmatter separately, do not apply style rules.

---

## Detection Order

Run detection in this order for best results:

1. **Identify skip zones** (code, quotes, frontmatter)
2. **Tier 1 scan** (high-confidence AI tells)
3. **Tier 1-News scan** (news article AI tells -- pseudo-profound, philosophizing, meta-significance)
4. **Tier 1b scan** (copula avoidance -- "serves as a", "boasts a")
5. **Meta-commentary scan** (usually at start/end)
5b. **Novelty inflation / engagement bait scan** (Tier 1g)
6. **Tier 2b-2g scan** (dangling -ing, puffery, generic closers, false concession, emotional flatline, reasoning chains)
7. **Structural analysis** (requires full document, includes boldface overuse, dramatic AI rhythm, synonym cycling)
8. **Tier 3-5 scan** (lower priority, includes curly quote detection)
8b. **Tier 3c scan** (parenthetical hedging)
9. **Passive voice analysis** (context-dependent)

Report issues grouped by paragraph for easier review.

---

## Pattern Testing

Test patterns against known AI text:

```
In today's fast-paced world of software development, it's important
to note that leveraging cutting-edge technologies can help facilitate
seamless integration. This robust and comprehensive solution utilizes
state-of-the-art algorithms to optimize performance.

Expected detections:
- "In today's fast-paced world" (Tier 1)
- "it's important to note that" (Tier 2)
- "leveraging" (Tier 1)
- "cutting-edge" (Tier 1)
- "facilitate" (Tier 1)
- "seamless integration" (Tier 1)
- "robust and comprehensive" (Tier 1)
- "utilizes" (Tier 1)
- "state-of-the-art" (Tier 1)
- "optimize performance" (check context)
```

Test patterns against known AI text (copula avoidance + puffery):

```
The framework serves as a bridge between frontend and backend systems,
highlighting its importance in the evolving landscape. It boasts a
modern API that continues to evolve and grow. The project stands as
a testament to the team's enduring legacy, and the future looks bright
for its continued development.

Expected detections:
- "serves as a" (Tier 1b -- copula avoidance)
- "highlighting its importance" (Tier 2b -- dangling -ing)
- "evolving landscape" (Tier 2c -- puffery)
- "boasts a" (Tier 1b -- copula avoidance)
- "continues to evolve and grow" (Tier 2d -- generic positive conclusion)
- "stands as a testament to" (Tier 2c -- puffery)
- "enduring legacy" (Tier 2c -- puffery)
- "the future looks bright" (Tier 2d -- generic positive conclusion)
```

Test patterns against known AI text (news article tells):

```
The closing keynote delivered a career-defining performance from both
people. That's worth sitting with for a second. The consequences
extend beyond the night itself, reshaping the leadership track heading
into the summer. Attendees had options. They chose this event. That's the
kind of stakes that make an event feel like it actually matters.
It's hard to overstate how much this win changes things.

Expected detections:
- "worth sitting with for a second" (Tier 1-News -- pseudo-profound)
- "consequences extend beyond the night itself" (Tier 1-News -- abstract philosophizing)
- "Attendees had options. They chose this event." (Tier 1-News -- dramatic AI rhythm, check context)
- "That's the kind of" (Tier 1-News -- meta-significance)
- "It's hard to overstate" (Tier 1-News -- meta-significance)
```

Test against natural human text:

```
The cache was stale. I spent three hours debugging before realizing
the CDN had a 24-hour TTL. Changed it to 5 minutes and the problem
went away. Sometimes the simplest fix is the right one.

Expected detections: 0
(Natural, direct, specific, varied sentence lengths)
```

---

## Code & Documentation AI Patterns (Tier CD)

AI patterns specific to code comments, docstrings, READMEs, architecture docs, and technical blog posts. These are distinct from prose AI tells — they emerge when AI generates technical content rather than narrative.

### Tier CD-1: Redundant Explanation

The single most AI-identifiable pattern in prose, equally common in code. AI generates comments that restate what the code already says. Docstrings that merely reword the function signature. Paragraphs that explain what a code block just demonstrated.

**Detection heuristic for code comments:**
```
1. Parse each comment and its associated code statement
2. Extract verbs and nouns from both
3. If comment verbs/nouns overlap >80% with code verbs/nouns → flag
4. Common pattern: "// increment X by Y" above "x += y"
```

**Detection heuristic for docstrings:**
```
1. Parse function/method signature: name, parameters, return type
2. Parse docstring first sentence
3. If docstring merely restates signature in natural language → flag
4. Pattern: "Gets the user by ID" docstring on getUserById(id: string): User
```

```regex
# Code comments that restate the code (high-confidence subset)
//\s*(increment|add|subtract|set|get|return|initialize|update|delete|remove|create|check|validate)\s
#\s*(increment|add|subtract|set|get|return|initialize|update|delete|remove|create|check|validate)\s

# Docstrings that restate the function name
("""|\*\*|///)\s*(Gets?|Sets?|Creates?|Deletes?|Updates?|Returns?|Checks?|Validates?)\s+the\s+\w+
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| `// increment counter by 1` above `counter++` | [Delete — the code is clear] |
| `"""Gets the user by ID."""` on `get_user_by_id()` | `"""Fetches from cache first, falls back to DB. Returns None if soft-deleted."""` |
| `// Check if the value is valid` above `if is_valid(value):` | [Delete — or explain what "valid" means in this context] |
| `// Create a new instance of the service` above `svc := NewService(cfg)` | [Delete — or explain WHY a new instance is needed here] |

**Fix strategy:** Delete the comment if the code is self-explanatory. If a comment is needed, explain WHY or WHEN, not WHAT. A comment that a senior engineer would find insulting is a comment that should be deleted.

### Tier CD-2: Unearned Confidence

AI describes systems with encyclopedic confidence and zero uncertainty. Real documentation acknowledges limitations, edge cases, and known issues. "Handles all edge cases gracefully" is never true. "Works seamlessly" is never honest.

```regex
# Absolute claims about system behavior
\bhandles all .+ gracefully\b
\bhandles all edge cases\b
\bworks seamlessly\b
\bfully reliable\b
\bfully tested\b
\bcompletely secure\b
\bbulletproof\b
\bhandles any .+ you throw at it\b
\bjust works\b
\bno (downsides|trade-?offs)\b
\bnever fails\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**Handles all edge cases gracefully**" | "Handles UTF-8 input up to 10MB. Rejects oversized payloads with 413." |
| "**Works seamlessly** with any database" | "Tested with PostgreSQL 14+ and SQLite 3.35+. MySQL support is experimental." |
| "**Fully tested** and production-ready" | "86% line coverage. Integration tests cover the happy path. Error injection tests are TODO." |
| "**Completely secure** authentication" | "Uses bcrypt with cost 12. Rate-limits to 5 attempts/minute. No MFA yet." |

**Fix strategy:** Replace absolute claims with specific, falsifiable statements. If you can't state what it actually handles, you don't know enough to claim it handles everything.

### Tier CD-3: Platitude Injection

AI inserts universal truths that add zero information. "At its core, software engineering is about managing complexity" wastes the reader's time. If a truism is needed to introduce a point, the point isn't strong enough to stand alone.

```regex
\bat its core,?\s+software\b
\bat the end of the day,?\s+.+\s+is about\b
\bat its heart,?\s+.+\s+is about\b
\bthe beauty of .+ is that\b
\bthe power of .+ lies in\b
\bthe magic of .+ is\b
\bin the world of software\b
\bin the realm of\b
\bin the landscape of\b
\bgood code is .+ about\b
\bgreat software .+ about\b
\bprogramming is .+ about\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**At its core, software engineering is about** managing complexity" | "This module has three responsibilities. Splitting it reduces coupling." |
| "**The beauty of** this architecture **is that** it scales" | "This architecture scales horizontally because each node is stateless." |
| "**In the world of** microservices, communication is key" | "Services communicate via gRPC. Timeouts are set to 5s." |
| "**Good code is ultimately about** readability" | [Delete — start with the specific readability improvement you're making] |

**Fix strategy:** Delete the platitude and start with the concrete claim that follows it. The concrete claim is always there — the platitude is just throat-clearing before it.

### Tier CD-4: False Precision

AI inserts suspiciously specific numbers to sound authoritative. "Reduces latency by 47.3%" when no benchmark was run. "Processes 1,247 requests per second" when the number was invented. Real precision comes with methodology; AI precision comes with confidence.

```regex
\breduces .+ by exactly \d+\b
\bimproves .+ by precisely \d+\b
\btakes exactly \d+ (ms|seconds|minutes)\b
\d+\.\d{2,}x (faster|slower|better|improvement)
\bsaves exactly \d+\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "Reduces latency by **exactly 47.3%**" | "Roughly halves latency (benchmarked on M2 with 10K requests)" |
| "Processes **1,247** requests per second" | "Handles ~1K req/s on a single core (see benchmarks/)" |
| "Saves **exactly 23 minutes** per deployment" | "Cuts deploy time from ~30min to ~10min" |

**False positive note:** Precision is legitimate when citing actual measurements with methodology. "p99 latency: 12.4ms (measured over 1M requests)" is real data, not a tell. Flag only when precision appears without a citation or benchmark reference.

### Tier CD-5: Template Monotony

AI-generated documentation follows identical structure for every section: intro paragraph, bullet list, code example, summary sentence. Every function doc follows: description, parameters, returns, example. This structural repetition is a tell even when no individual section is bad.

**Detection heuristic (structural, not regex):**
```
1. For each H2 or H3 section in a document:
   a. Classify the section structure:
      - INTRO-LIST-CODE-SUMMARY
      - INTRO-CODE-EXPLANATION
      - QUESTION-ANSWER
      - NARRATIVE
      - etc.
   b. Record the structure type
2. Count consecutive sections with identical structure type
3. Flag if 3+ consecutive sections use the same structure
4. Also flag if >60% of sections in a document use the same structure
```

**Before (monotonous):**
```markdown
## Authentication
Authentication is a critical part of any application. Here are the key features:
- JWT tokens
- Session management
- OAuth2 support

## Authorization
Authorization controls what users can access. Here are the key features:
- Role-based access
- Permission groups
- Resource-level policies

## Rate Limiting
Rate limiting protects your API from abuse. Here are the key features:
- Per-user limits
- Global limits
- Burst allowance
```

**After (varied):**
```markdown
## Authentication
Uses JWT with 15-minute expiry. Refresh tokens rotate on use.

## Authorization
Three levels: role → permission group → resource policy. Checked in that order.
See `middleware/authz.go` for the chain.

## Rate Limiting
| Scope | Default | Burst |
|-------|---------|-------|
| Per-user | 100/min | 20 |
| Global | 10K/min | 2K |

Override per-route with `@RateLimit(n)`.
```

**Fix strategy:** Vary section structures deliberately. Use tables where data is tabular. Use code-first where the code IS the explanation. Use narrative where context matters. No two consecutive sections should have the same structure.

### Tier CD-6: Dead Technical Metaphors

Code/docs-specific metaphors that AI overuses to the point of meaninglessness. Different from prose metaphors — these are engineering clichés.

```regex
\borchestrat(e|es|ed|ing) a (ballet|dance|symphony)\b
\bsymphony of (services|systems|components)\b
\btapestry of (services|systems|code)\b
\bunder the hood\b
\bswiss army knife\b
\bsilver bullet\b
\bheavy lifting\b
\bmagic happens\b
\bthe secret sauce\b
\bbehind the scenes\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**Under the hood**, it uses goroutines" | "Implementation: goroutines with a shared channel" |
| "The **secret sauce** is the caching layer" | "The caching layer is the reason it's fast" |
| "This module does the **heavy lifting**" | "This module handles parsing, validation, and storage" |
| "**Behind the scenes**, React reconciles the DOM" | "React reconciles the DOM on each render" |

**False positive note:** "Under the hood" is so ubiquitous in tech writing that it's borderline acceptable. Flag at info severity, not error.

### Tier CD-7: Tour Guide Transitions

AI connects every section with a transition sentence that reads like a museum audio guide. Real technical docs let sections stand independently — readers jump between sections, they don't read linearly.

```regex
\bwith that (in place|established|covered)\b
\bhaving established\b
\bnow that we('ve| have) (covered|established|set up|configured)\b
\bbuilding on (this|the previous|what we)\b
\blet's (now )?turn (our attention )?to\b
\bthis (brings|leads) us to\b
\bwith (this|that) (foundation|understanding|context)\b
\bnow we're ready to\b
```

**Before/After Examples:**

| AI Pattern | Human Version |
|-----------|---------------|
| "**With that in place**, let's configure the database" | "## Database Configuration" |
| "**Now that we've covered** authentication, let's turn to authorization" | "## Authorization" |
| "**Building on the previous** section, we can now..." | [Start with what this section does, not what the previous one did] |

**Fix strategy:** Delete the transition entirely. Start each section with its own content. If sections must be read in order, a numbered list in the overview is better than inline tour-guiding.

---

## Code/Docs Pattern Testing

Test against AI-generated README:

```
At its core, this library is about making API calls simple. It handles
all edge cases gracefully and works seamlessly with any HTTP client.
The beauty of the architecture is that it reduces boilerplate by exactly
47.3%, saving developers hours of work.

With that in place, let's turn to configuration. Configuration is a
critical part of any application. Here are the key options:
- **Timeout** -- sets the request timeout
- **Retries** -- configures retry behavior
- **Auth** -- handles authentication

Under the hood, the secret sauce is the middleware pipeline that
orchestrates a symphony of interceptors.

Expected detections:
- "At its core" (CD-3 -- platitude)
- "handles all edge cases gracefully" (CD-2 -- unearned confidence)
- "works seamlessly" (CD-2 -- unearned confidence)
- "The beauty of" (CD-3 -- platitude)
- "by exactly 47.3%" (CD-4 -- false precision)
- "With that in place, let's turn to" (CD-7 -- tour guide)
- "Under the hood" (CD-6 -- dead metaphor)
- "the secret sauce" (CD-6 -- dead metaphor)
- "orchestrates a symphony of" (CD-6 -- dead metaphor)
```

Test against natural technical writing:

```
The client retries failed requests up to 3 times with exponential
backoff (100ms, 200ms, 400ms). Timeouts default to 5s. Override
per-request with WithTimeout(d).

Known limitation: connection pooling doesn't work with HTTP/2 proxies.
See issue #247.

Expected detections: 0
(Specific, qualified, acknowledges limitations)
```
