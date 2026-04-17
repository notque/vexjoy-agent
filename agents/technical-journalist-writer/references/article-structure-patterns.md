# Article Structure Patterns

> **Scope**: Structure templates and anti-patterns for the three article types this agent produces: explainer, opinion, and analysis. Covers header patterns, topic sentences, and structural detection commands.
> **Version range**: All versions — applies to markdown article output.
> **Generated**: 2026-04-15

---

## Overview

The journalist voice produces three distinct article types, each with a specific structure. Explainers build from mechanism to implication. Opinion pieces follow principle-application-example. Analysis pieces state findings first, then evidence. The most common failure is applying the wrong structure to the wrong article type, or using clickbait headers that describe drama instead of content.

---

## Article Type Pattern Table

| Article Type | Opening | Body Structure | Closing |
|--------------|---------|----------------|---------|
| Explainer | State what changed or how it works | Mechanism → consequence → implication | What this means for the reader's context |
| Opinion | State the core claim directly | Principle → application → concrete example | Restate claim with evidence accumulated |
| Analysis | State the finding | Evidence → why it matters → what's missing | What question remains open |

---

## Explainer Structure

Explainers answer "how does this work" or "what changed." The structure builds from the mechanism to its implications.

```markdown
## [Descriptive Header: What the System Does]

[Opening: One sentence stating what the system does or what changed.]

[Mechanism paragraph: How it works, specifically.]

[Consequence paragraph: What this means operationally.]

### [Sub-component or Edge Case]

[Topic sentence stating this section's specific focus.]

[Detail with concrete example — a real scenario, not "for example, imagine you..."]

### [Comparison or Context, if relevant]

[How this differs from the previous approach, if applicable.]
```

**Structural rule**: Each section adds one new piece of information. No section exists to create suspense or withhold information for impact.

---

## Opinion Structure: Principle-Application-Example

Opinion pieces make an argument. The journalist voice makes arguments through logic and evidence, not through appeals to authority or enthusiasm.

```markdown
## [Descriptive Header: The Claim]

[Opening: State the core claim directly. One sentence.]

### [Why This Claim Holds]

[Principle: The underlying mechanism that makes the claim true.]

[Application: Apply that principle to the specific context under discussion.]

[Example: A concrete, specific scenario — real system, real behavior, real outcome.]

### [Where This Breaks Down]

[The edge case or counter-argument — acknowledge it directly.]

[Why the main claim still holds despite this.]
```

**Detection** — missing principle-application-example structure:
```bash
# Check if opinion article has concrete example (a date or system name is a strong signal)
grep -i '\b(last month\|last year\|in [0-9]\{4\}\|[A-Z][a-z]* [Ss]ystem\|[A-Z][a-z]* [Ss]ervice)\b' article.md

# Check for specific numbers or metrics (makes it concrete)
grep -E '\b[0-9]+(%|ms|MB|GB|req|rpm|RPS)\b' article.md
```

---

## Analysis Structure

Analysis pieces examine existing data, behavior, or systems. The finding comes first.

```markdown
## [Descriptive Header: The Finding]

[Opening: State the finding. What the analysis shows.]

### [Evidence]

[Topic sentence: This section presents the specific evidence.]

[The data, behavior, or system characteristic that supports the finding.]

### [Why It Matters]

[Operational or architectural consequence of this finding.]

### [What's Not Known]

[The open question — what the analysis can't answer from available data.]
```

---

<!-- no-pair-required: section-header-only — catalog heading, individual blocks carry the do-framing -->
## Anti-Pattern Catalog

### ❌ Clickbait Headers

**Detection**:
```bash
rg '^#{1,3} .*(Nobody|Everything|Changes Everything|Will Surprise|You Won.t Believe|Shocking|Secret|Hidden)' --type md -i
rg '^#{1,3} (The Problem|The Solution|Why This Matters|What Comes Next|The Future)$' --type md
```

**What it looks like**:
```
The Problem Nobody Saw Coming
The Solution That Changes Everything
What Happens Next Will Surprise You
```

**Why wrong**: Clickbait headers delay information by making the reader read the section to find out what it covers. Descriptive headers function as navigation — the reader scans headers to find relevant sections.

**Do instead:**
```markdown
### Why Schema Files Failed at Scale
### How Migration Scripts Fix Deployment Ordering
### Rollback Strategy for Failed Migrations
```

**Rule**: Headers state the section's content. "The Problem" is not content — "Why the Mutex Implementation Is Wrong" is.

---

### ❌ Missing Topic Sentences

**Detection**:
```bash
grep -n '^This \|^It ' article.md | head -10
grep -n '^However,\|^Additionally,\|^Furthermore,\|^Also,' article.md
```

**What it looks like**:
```
Rollback strategies are an important consideration when thinking about
migrations. There are several things to keep in mind when approaching
this problem...
```

**Why wrong**: The first sentence doesn't state what the paragraph covers. "Important consideration" is a label, not information. The reader can't tell from the first sentence whether to keep reading this paragraph.

**Do instead:**
```
The rollback strategy handles three failure modes. Syntax errors abort before
any rows change. Partial constraint violations require row-level rollback.
Lock timeout failures leave the schema unchanged but require manual state verification.
```

---

### ❌ Burying the Lead

**Detection**:
```bash
awk '/^$/{para++} para>=3 && /[0-9]%|[0-9]ms|[A-Z][a-z]+ (changed|failed|broke)/{print NR": first concrete claim at paragraph "para; exit}' article.md
```

**What it looks like**:
```
[3 paragraphs of context and background]
[Paragraph 4: "The system failed because the lock timeout was 30 seconds."]
```

**Why wrong**: The reader has to read through context to find the information they came for. Technical readers skim; burying the lead means many readers miss the core point.

**Do instead:** State the core finding in the first paragraph. Use subsequent paragraphs to support, not to build up to.

---

### ❌ Unsupported Section Length

**Detection**:
```bash
awk '/^#{1,3}/{section=$0} /^$/{if(para==1) print "Single-para section: "section; para=0} /^[^#]/{para++}' article.md
```

**What it looks like**:
```
Why This Matters

This is important because it affects system reliability.

What To Do
```

**Why wrong**: A section with one short paragraph is either padding (can be deleted) or incomplete (the idea wasn't developed). The journalist voice covers each point thoroughly or cuts it.

**Do instead:** Either develop the section with specific examples, data, or mechanisms — or remove the section header and fold the content into an adjacent paragraph.

---

## Structure Detection Commands Reference

```bash
rg '^#{1,3} .*(Nobody|Changes Everything|Will Surprise|Shocking|Secret)' --type md -i
rg '^#{1,3} (The Problem|The Solution|Why This Matters|What Comes Next)$' --type md
grep -n '^This \|^It \|^There ' article.md | head -10
grep -cE '\b[0-9]+(%|ms|MB|GB|req)\b' article.md
rg '^(How can|What if|Why do|Can we)' --type md -m 5
```

---

## See Also

- `voice-patterns.md` — banned phrases and tone anti-patterns with detection
- `sourcing-and-claims.md` — claim verification and citation patterns
