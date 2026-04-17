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

<!-- no-pair-required: section-header-only — catalog heading, individual blocks carry the do-framing -->
## Pattern Catalog

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

**Do instead:**
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

**Do instead:**
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

**Do instead:** First sentence states the topic directly.
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

**Do instead:**
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

**Do instead:**
```
The API returns HTTP 429 when you exceed 100 requests per minute. The response
includes a Retry-After header specifying seconds to wait.
```

---

### ❌ Listicle Format

**Detection**:
```bash
grep -c '^[0-9]\+\.' article.md
grep -n '^[0-9]\+\.' article.md | awk -F: 'prev && $1-prev==1{count++} {prev=$1} count>=4{print "Listicle block at line "$1; count=0}'
```

**Do instead:** write prose paragraphs where causation is explicit; full correction follows below.

**What it looks like**:
```
Top 5 Reasons Schema Files Failed

1. Synchronization issues across environments
2. Merge conflicts in large teams
3. No deployment history
4. Difficult rollbacks
5. State drift over time
```

**Why wrong**: Numbered lists atomize related ideas and hide logical relationships. The journalist voice builds arguments in prose where causation is explicit ("X caused Y because Z"), not implied by list adjacency.

**Correction:**
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

## Voice Pattern Quick Reference

### The Direct Opening

The first paragraph states the topic clearly. No preamble.

**Correct opening:**
```
The database migration system changed. The old approach used schema files.
The new one uses versioned migration scripts. This is why it matters.
```

**Incorrect:**
```
Have you ever wondered about the best way to handle database migrations?
It's a fascinating problem that many developers face! Let me share an
exciting new approach that's revolutionizing how we think about...
```

### The Principle-Application-Example Structure

Opinion pieces follow this pattern:

**Principle**: State the core idea clearly
```
Teams should write more documentation.
```

**Application**: Apply to specific context
```
In distributed systems, undocumented service contracts cause integration failures.
The failure happens when Service A assumes behavior that Service B never promised.
```

**Example**: Show concrete scenario
```
Last month, a team deployed a change to the authentication service. They modified
the token format. Three downstream services broke because the token parsing logic
assumed the old format. The integration tests passed because they mocked the auth
service. Documentation would have caught this.
```

### The Matter-of-Fact Tone

This voice states facts without editorial commentary.

**Matter-of-fact:**
```
The system uses PostgreSQL. PostgreSQL handles concurrent writes through MVCC.
This means readers don't block writers. The tradeoff is storage overhead for
old row versions.
```

**Editorial commentary (wrong):**
```
The system brilliantly leverages PostgreSQL's powerful MVCC capabilities!
This elegant solution beautifully solves the reader/writer problem without
compromising performance.
```

### The Knowledgeable Reader Assumption

This voice skips basics, respects reader competence.

**Assumes knowledge:**
```
Horizontal scaling adds more servers. Vertical scaling upgrades existing hardware.
The choice depends on your bottleneck. CPU-bound workloads favor vertical scaling.
I/O-bound workloads favor horizontal scaling with distributed reads.
```

**Condescending (wrong):**
```
As you probably know, scaling means handling more load. There are two types of
scaling (don't worry, I'll explain both!). Horizontal scaling - think of it
like adding more workers to a factory...
```

### Headers Are Descriptive

Headers tell you what's in the section.

**Descriptive:**
```
### Why Schema Files Failed
### How Migration Scripts Solve This
### Rollback Strategy for Failed Migrations
```

**Clickbait (wrong):**
```
The Problem Nobody Saw Coming
The Solution That Changes Everything
What Happens Next Will Surprise You
```

### Topic Sentences Deliver

First sentence states paragraph purpose.

**Delivering topic sentence:**
```
The rollback strategy handles three failure modes. First, syntax errors in
the migration script...
```

**Throat-clearing (wrong):**
```
Rollback strategies are an important consideration when thinking about
migrations. There are several things to keep in mind...
```

## Banned Pattern Reference

### Ban 1: Enthusiasm Markers

This voice omits all of the following:
- Exclamation points for excitement (only for emphasis: "Don't do this!")
- Superlatives ("amazing", "incredible", "revolutionary")
- Persuasive language ("you should definitely", "the best approach")
- Hype ("game-changing", "cutting-edge", "next-generation")

**Correct language:**
```
The new system works. It's faster than the old one. The improvement comes
from caching query results.
```

**Enthusiasm (wrong):**
```
The new system is amazing! It's incredibly fast! You'll love how
revolutionary this cutting-edge approach is!
```

### Ban 2: Vague Abstractions

This voice uses concrete examples, never hand-waves.

**Concrete:**
```
The API returns HTTP 429 when you exceed 100 requests per minute. The response
includes a Retry-After header with the number of seconds to wait.
```

**Vague (wrong):**
```
The API has rate limiting. It returns an error when you make too many requests.
You should implement appropriate backoff strategies to handle this gracefully.
```

### Ban 3: Condescending Explanations

This voice never explains basics to experienced readers.

**Respects knowledge:**
```
The system uses JWT for authentication. The token includes user_id and role
claims. Expiry is 1 hour.
```

**Condescending (wrong):**
```
Now, you might be wondering what JWT means. JWT stands for JSON Web Token,
and it's a way of securely transmitting information between parties. Don't
worry if this sounds complicated - I'll break it down step by step!
```

### Ban 4: Persuasive Framing

This voice informs, doesn't persuade.

**Informative:**
```
Teams write documentation for integration contracts. This prevents breaking
changes. The documentation shows what the service guarantees. Tests verify
the documentation matches implementation.
```

**Persuasive (wrong):**
```
You absolutely must write documentation! It's the single most important thing
you can do to ensure your services work together seamlessly. Trust me,
you'll thank yourself later when you avoid those painful integration bugs!
```

### Ban 5: Listicle Format

This voice writes essays with logical progression, not numbered lists.

**Essay format:**
```
### Why Schema Files Failed

Schema files represented the database state. Each environment had one schema
file. This caused problems during deployment...

The fundamental issue was synchronization...
```

**Listicle (wrong):**
```
Top 5 Reasons Schema Files Failed

1. Synchronization issues across environments
2. Merge conflicts in large teams
3. No deployment history
4. Difficult rollbacks
5. State drift over time
```

## See Also

- `article-structure-patterns.md` — explainer/opinion/analysis article type structures
- `sourcing-and-claims.md` — claim verification and citation patterns
