# Technical Journalist Voice Patterns

> **Scope**: Banned phrases, tone anti-patterns, and structural violations for the matter-of-fact journalism voice. Covers detection commands for auditing generated article content.
> **Version range**: All versions — applies to any technical article output in markdown.
> **Generated**: 2026-04-15

---

## Overview

The technical journalist voice informs without editorial coloring. The most common failure mode is enthusiasm contamination — single words like "amazing" or "seamlessly" break the matter-of-fact register. A second failure mode is persuasive framing ("you should", "you must") that substitutes the author's judgment for evidence. Detection is straightforward because both failure modes are specific lexical items.

---

## Detection Commands Reference

```bash
# Enthusiasm markers — superlatives and hype words
rg -i '\b(amazing|incredible|revolutionary|game-changing|cutting-edge|next-generation|elegant|brilliant|exciting|seamlessly|beautifully|effortlessly|powerful)\b' --type md

# Persuasive language
rg -i '\b(you should definitely|you must|trust me|you will love|you will thank)\b' --type md

# Exclamation points used for enthusiasm (not imperative)
grep -n '!' article.md | grep -v "Don't\|do not\|never\|warning\|STOP\|NOTE"

# Throat-clearing openers
rg -i '^(Have you ever|Did you know|In today|In this article|Welcome to|As we all know|It is worth noting)' --type md -m 5

# Condescending framing
rg -i "\b(don't worry|as you probably know|let me explain|i'll break it down|for those who don't know|in simple terms)\b" --type md

# Vague abstractions — no concrete specification
rg -i '\b(appropriate(ly)?|proper(ly)?|graceful(ly)?|careful(ly)?|thorough(ly)?|effective(ly)?)\b' --type md

# Listicle format (5+ numbered items = likely listicle)
grep -c '^[0-9]\+\.' article.md
```

---

## Anti-Pattern Catalog

### ❌ Enthusiasm Markers

**Detection**:
```bash
rg -i '\b(amazing|incredible|revolutionary|powerful|elegant|game-changing|cutting-edge)\b' --type md
```

**What it looks like**:
```
The system is amazing! It elegantly leverages PostgreSQL's powerful MVCC capabilities
to beautifully solve concurrency without compromising performance.
```

**Why wrong**: Enthusiasm adjectives make claims that can't be verified. "Powerful" compared to what? "Elegantly" by whose standard? These words add editorializing without adding information. Readers tracking the matter-of-fact register notice immediately and discount subsequent factual claims.

**Fix**:
```
The system uses PostgreSQL. PostgreSQL handles concurrent writes through MVCC.
Readers don't block writers. The tradeoff is storage overhead for old row versions.
```

**Replacement rule**: Replace every enthusiasm adjective with a measurement or delete it.
- "powerful" → specific throughput/scale numbers, or delete
- "elegant" → describe the mechanism, not the aesthetic
- "seamlessly" → describe what actually happens at the integration point

---

### ❌ Persuasive Framing

**Detection**:
```bash
rg -i '\b(you should|you must|you need to|you will want to|trust me|make sure to|I recommend)\b' --type md
```

**What it looks like**:
```
You absolutely must write documentation! It's the single most important thing
you can do. Trust me, you'll thank yourself later.
```

**Why wrong**: The journalist voice informs, it doesn't prescribe. "You must" assumes authority over the reader's situation — which the author doesn't have. "Trust me" substitutes author credibility for evidence, which is the opposite of journalism.

**Fix**:
```
Teams write documentation for integration contracts. This prevents breaking
changes by recording what each service guarantees.
```

**Pattern**: Replace "you should X" with an observation about what teams/systems do, and state the consequence.

---

### ❌ Throat-Clearing Openers

**Detection**:
```bash
rg -i '^(Have you ever|Did you know|In today|In this article|Welcome to|As we all know)' --type md
rg '^[A-Z][^.!?]{10,60}\?$' --type md -m 3  # Rhetorical question openers
```

**What it looks like**:
```
Have you ever wondered about the best way to handle database migrations?
It's a fascinating problem that many developers face! Let me share an
exciting new approach...
```

**Why wrong**: The first sentence is the highest-value real estate in any article. Rhetorical questions and scene-setting delay the information the reader came for. Technical readers opened the article knowing the topic — delay signals filler.

**Fix**: First sentence states the topic directly.
```
The database migration system changed. The old approach used schema files;
the new one uses versioned migration scripts.
```

---

### ❌ Condescending Explanations

**Detection**:
```bash
rg -i "\b(as you (probably )?know|don't worry|let me explain|i'll break|for those who don't|in simple terms|step by step)\b" --type md
```

**What it looks like**:
```
As you probably know, JWT stands for JSON Web Token. Don't worry if this
sounds complicated — I'll break it down step by step!
```

**Why wrong**: The knowledgeable reader assumption means this audience knows JWT basics. Explaining them signals the author misjudged the audience, eroding trust in the technical claims that follow.

**Fix**:
```
The system uses JWT. The token includes user_id and role claims. Expiry is 1 hour.
```

**Rule**: Skip any explanation the target reader already has. If in doubt about audience level, write for the more experienced reader.

---

### ❌ Vague Abstractions

**Detection**:
```bash
rg -i '\b(appropriate(ly)?|proper(ly)?|correct(ly)?|graceful(ly)?|careful(ly)?|thorough(ly)?)\b' --type md
```

**What it looks like**:
```
The API has rate limiting. It returns an error when you make too many requests.
You should implement appropriate backoff strategies to handle this gracefully.
```

**Why wrong**: "Appropriate" and "gracefully" are placeholders for specific knowledge the author didn't provide. The reader needs the specific behavior: what HTTP status code, which response header, how many seconds.

**Fix**:
```
The API returns HTTP 429 when you exceed 100 requests per minute. The response
includes a Retry-After header specifying seconds to wait.
```

---

### ❌ Listicle Format

**Detection**:
```bash
# Count numbered list items in article
grep -c '^[0-9]\+\.' article.md

# Find consecutive numbered items (listicle blocks)
grep -n '^[0-9]\+\.' article.md | awk -F: 'prev && $1-prev==1{count++} {prev=$1} count>=4{print "Listicle block at line "$1; count=0}'
```

**What it looks like**:
```
### Top 5 Reasons Schema Files Failed

1. Synchronization issues across environments
2. Merge conflicts in large teams
3. No deployment history
4. Difficult rollbacks
5. State drift over time
```

**Why wrong**: Numbered lists atomize related ideas and hide logical relationships. The journalist voice builds arguments in prose where causation is explicit ("X caused Y because Z"), not implied by list adjacency.

**Fix**:
```
### Why Schema Files Failed

Schema files represented a static snapshot of database state. Each environment
maintained one file. Deployment became a synchronization problem: staging and
production diverged because teams edited them independently. Merge conflicts
were frequent. When a migration failed, there was no history of what had been
applied where.
```

---

## Replacement Map

| Banned Pattern | Replacement Strategy |
|----------------|---------------------|
| `amazing`, `incredible` | Delete — if the fact is notable, state it specifically |
| `powerful` | Specific metric: throughput, latency, scale ceiling |
| `seamlessly` | Describe what actually happens at the integration point |
| `elegantly` | Describe the mechanism, not the aesthetic |
| `appropriately` | State the specific required behavior |
| `gracefully` | Describe what the error path does concretely |
| `as you know` | Delete — just state the fact |
| `you should` | "Teams that X find Y" or state the consequence directly |
| `next-generation` | State specifically what changed from the previous approach |
| `cutting-edge` | State the publication date and what was new then |

---

## See Also

- `article-structure-patterns.md` — explainer/opinion/analysis article type structures
- `sourcing-and-claims.md` — claim verification and citation patterns
