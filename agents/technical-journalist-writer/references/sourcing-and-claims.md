# Sourcing and Claims Patterns

> **Scope**: How to handle factual claims, mark inferences, cite sources, and avoid unsupported assertions in technical journalism. Covers claim classification and detection commands for validation.
> **Version range**: All versions — applies to any technical article output.
> **Generated**: 2026-04-15

---

## Overview

The journalist voice requires a verifiable basis for every factual claim. The agent body includes a hard STOP rule: before delivering any article, verify every factual claim against its source. This reference operationalizes that rule — covering claim classification, inline citation patterns, how to mark inferences, and how to detect unsupported assertions.

---

## Claim Classification

| Claim Type | Source Required | How to Handle |
|------------|----------------|---------------|
| Statistical claim | Yes — specific source | Cite inline: "X% of Y, per [Source Year]" |
| Version-specific behavior | Yes — release notes or docs | Cite inline: "as of [Framework vX.Y]" |
| Historical event | Yes — dated reference | Cite with date: "in [Month Year], [Organization]..." |
| Architectural observation | If specific — docs or codebase | Mark as inference if derived from reading code |
| General mechanism | No — established knowledge | State directly without citation |
| Reader-facing inference | No source exists — reasoning only | Mark explicitly: "this suggests..." or "the implication is..." |

---

## Correct Sourcing Patterns

### Statistical Claims

State the source inline, not in a footnote. Technical readers verify claims immediately.

```markdown
PostgreSQL handles approximately 10,000 concurrent connections on typical hardware,
per the 2023 PostgreSQL benchmark suite. The limit is configurable via max_connections.
```

```markdown
The study found 73% of production incidents traced to configuration drift,
not code bugs (Puppet State of DevOps Report, 2022).
```

**Why inline**: Footnotes require the reader to interrupt reading to verify. Inline sourcing integrates verification into reading.

---

### Version-Specific Behavior

State the version where behavior applies or changed.

```markdown
Go 1.21 introduced built-in min/max functions. Prior versions required
manual comparison or a third-party package.
```

```markdown
React 18 changed rendering to concurrent by default. Strict Mode behavior
changed as a result — effects run twice in development.
```

**Detection** — version claims without version number:
```bash
# Claims about framework behavior without version qualifier
rg '\b(changed|introduced|deprecated|removed|added)\b' article.md | grep -v '\b[0-9]\+\.[0-9]\+\b'
```

---

### Marking Inferences

When a claim derives from reasoning rather than a direct source, mark it explicitly.

**Marked inference patterns** (acceptable):
```markdown
The latency increase suggests the bottleneck is in the serialization layer,
not the network hop.

This implies that the migration runs before the application starts — otherwise
the schema version check would fail on startup.

The configuration suggests the team chose consistency over availability
in the CAP tradeoff.
```

**Unmarked inference patterns** (wrong — these sound like facts):
```markdown
The bottleneck is in the serialization layer.  # stated as fact, is inference
The migration runs before the application starts.  # stated as fact, is inference
```

---

<!-- no-pair-required: section-header-only — catalog heading, individual blocks carry the do-framing -->
## Anti-Pattern Catalog

### ❌ Statistical Claims Without Source

**Detection**:
```bash
# Percentage claims without citation signal
rg '\b[0-9]+%\b' article.md | grep -v 'per\|according\|source\|report\|survey\|study\|2[0-9][0-9][0-9]'

# Numeric comparative claims ("X times faster", "X% improvement")
rg '\b[0-9]+ times (faster|slower|larger|smaller)\b' article.md
```

**What it looks like**:
```
Studies show that 80% of developers prefer this approach. It's 3x faster
than the alternative in most workloads.
```

**Why wrong**: "Studies show" without a specific study is not a source — it's a rhetorical move. "3x faster" without a benchmark methodology is marketing language. Both patterns erode credibility when readers verify them and find nothing.

**Do instead:**
```
The Redis Labs 2023 benchmark showed 3.2x throughput improvement over
Memcached for workloads with key sizes under 1KB. Results vary with
key distribution and value size.
```

---

### ❌ Fake Certainty for Inferences

**Detection**:
```bash
# Definitive statements about system internals that would require source code to verify
rg '\b(definitely|certainly|always|never|guaranteed|impossible)\b' article.md

# "The reason is..." patterns (often inference stated as fact)
rg '\b(the reason (is|was|for)\b|this is because\b|this happens because\b)' article.md -i
```

**What it looks like**:
```
The reason the system is slow is definitely the database. The query
always takes 200ms because of missing indexes.
```

**Why wrong**: Without profiling data or execution plans, this is inference stated as fact. If the reader checks and the database isn't the bottleneck, the article loses all credibility.

**Do instead:**
```
Profiling showed the database at 73% of request time. The slow_query_log
identified three queries averaging 200ms — all on the users table without
an index on created_at.
```

Or, if no profiling data is available:
```
The symptoms suggest database contention — high response time with low CPU
usage typically indicates waiting on I/O or locks, not compute.
```

---

### ❌ Historical Claims Without Date

**Detection**:
```bash
# Historical claims without a year
rg '\b(originally|previously|historically|in the early days|back when|used to)\b' article.md | grep -v '\b(19|20)[0-9][0-9]\b'

# "When X was released/launched/introduced" without year
rg 'when .* (was released|launched|introduced|shipped)' article.md -i | grep -v '\b(19|20)[0-9][0-9]\b'
```

**What it looks like**:
```
When Kubernetes was first released, the networking model was much simpler.
Originally, services used flat networks without namespace isolation.
```

**Why wrong**: "When Kubernetes was first released" is vague — Kubernetes 1.0 shipped July 2015. Without the date, the reader can't evaluate how much the ecosystem has changed since then.

**Do instead:**
```
Kubernetes 1.0 shipped in July 2015 with a flat networking model.
NetworkPolicy resources, which enable namespace isolation, arrived in
Kubernetes 1.3 (July 2016).
```

---

### ❌ Unsourced Comparative Claims

**Detection**:
```bash
# Comparative claims that require a baseline to be meaningful
rg '\b(better than|worse than|faster than|more reliable than|superior to|more popular than)\b' article.md -i

# "Widely adopted", "commonly used", "most teams" — popularity claims need data
rg '\b(widely|commonly|most teams|most developers|industry standard|best practice)\b' article.md -i
```

**What it looks like**:
```
PostgreSQL is more reliable than MySQL for write-heavy workloads.
Most teams have moved away from monolithic architectures.
```

**Why wrong**: "More reliable" requires a specific reliability metric and measured workload. "Most teams" requires a survey. Without these, the claims are opinions presented as facts.

**Do instead:**
```
In TPC-C benchmarks on write-heavy workloads, PostgreSQL's MVCC implementation
shows lower lock contention than MySQL's row-level locking under high concurrency
(PostgreSQL vs MySQL Benchmark, 2023).

The CNCF 2023 Annual Survey found 44% of respondents running microservices
in production, up from 38% in 2022.
```

---

## Inference Marking Cheat Sheet

Use these phrasings to mark inferences explicitly:

| Inference Strength | Phrasing |
|-------------------|----------|
| Strong (high confidence) | "This suggests..." / "The data implies..." |
| Medium | "One explanation is..." / "This may indicate..." |
| Weak (speculative) | "It's possible that..." / "If [assumption] holds, then..." |
| Acknowledged gap | "Without profiling data, the root cause is unclear." |

**Rule**: When you can't point to a source for a claim, either mark it as inference using the above phrasings, or remove it. The third option — stating inference as fact — is not available in this voice.

---

## Detection Commands Reference

```bash
# Unsourced percentage claims
rg '\b[0-9]+%\b' --type md | grep -v 'per\|according\|source\|report\|survey\|study\|2[0-9][0-9][0-9]'

# Version claims without version numbers
rg '\b(changed|introduced|deprecated|removed|added)\b' --type md | grep -v '\b[0-9]\+\.[0-9]\+\b'

# Certainty words on inference statements
rg '\b(definitely|certainly|always|never|guaranteed|impossible)\b' --type md

# Historical claims without year
rg '\b(originally|previously|historically|back when|used to)\b' --type md | grep -v '\b(19|20)[0-9][0-9]\b'

# Comparative claims without baseline
rg '\b(better than|faster than|more reliable than|superior to)\b' --type md -i
```

---

## See Also

- `voice-patterns.md` — banned phrases and tone anti-patterns
- `article-structure-patterns.md` — structural patterns for explainer/opinion/analysis
