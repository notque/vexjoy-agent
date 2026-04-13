# Query Classification Reference

> **Scope**: Classifying incoming research queries into depth-first, breadth-first, or straightforward before any subagent deployment.
> **Version range**: All versions of research-coordinator-engineer
> **Generated**: 2026-04-13 — update decision criteria when new query archetypes emerge

---

## Overview

Query classification is the mandatory first step in every research session. Skipping it causes mismatched subagent strategies: deploying 3 parallel breadth-first subagents for a narrow depth question fragments context, while deploying a single depth-first subagent for a comparison query wastes parallel capacity. The correct type determines subagent count, instruction structure, and synthesis approach.

---

## Pattern Table

| Query Type | Subagent Count | Instruction Style | Synthesis Style |
|-----------|---------------|------------------|----------------|
| Depth-first | 3–5 | Different methodological angles on same topic | Reconcile findings across perspectives |
| Breadth-first | 1 per topic (3–7) | Scoped to exactly one option/entity | Side-by-side comparison |
| Straightforward | 1–2 | Precise target, tight deliverable | Direct extraction, no reconciliation |

---

## Correct Patterns

### Depth-First: Multiple Angles on One Topic

Deploy subagents that investigate the same subject from distinct methodological perspectives — theoretical, empirical, historical, adversarial. Never assign the same angle to two subagents.

```markdown
Research query: "How does transformer attention scaling affect reasoning?"

Subagent 1 — Theoretical: "Explain the mathematical mechanisms linking attention head count
to reasoning capability. Focus on published theoretical work. 300-400 words. Sources: ML
papers, not blog posts."

Subagent 2 — Empirical: "Summarize benchmark results showing reasoning performance vs
attention scaling in GPT/LLM families. Include specific model names and scores. 300-400
words. Sources: leaderboards, ablation studies."

Subagent 3 — Failure modes: "Document known failure cases where more attention does NOT
improve reasoning. Include specific task types and model behaviors. 300-400 words. Sources:
papers on reasoning limitations."
```

**Why**: Different angles produce findings the lead agent can reconcile into a coherent whole. Identical angles produce redundant content.

---

### Breadth-First: One Subagent Per Entity

Each subagent owns exactly one option/entity. Instructions must specify the same deliverable format across all subagents so comparison is clean.

```markdown
Research query: "Compare PostgreSQL, MongoDB, and Cassandra for write-heavy workloads"

Subagent 1 — PostgreSQL: "Research PostgreSQL for write-heavy workloads: write throughput
benchmarks, WAL behavior, partitioning strategies. 250-350 words. Include at least 2
benchmark citations. Sources: official docs, pg performance blogs."

Subagent 2 — MongoDB: "Research MongoDB for write-heavy workloads: write concern levels,
WiredTiger write performance, sharding impact on writes. 250-350 words. Include at least
2 benchmark citations. Sources: official docs, MongoDB blog."

Subagent 3 — Cassandra: "Research Cassandra for write-heavy workloads: LSM-tree write path,
compaction impact, consistency vs write speed tradeoffs. 250-350 words. Include at least
2 benchmark citations. Sources: official docs, DataStax resources."
```

**Why**: Uniform format makes synthesis mechanical — the lead agent slots findings into a comparison matrix rather than re-summarizing.

---

### Straightforward: Tight Target, Single Deliverable

Deploy 1–2 subagents with maximally constrained instructions. State the exact data point or answer format needed.

```markdown
Research query: "What is the current market share of AWS vs Azure vs GCP?"

Subagent 1: "Find the most recent (2024-2025) cloud market share statistics for AWS, Azure,
and GCP. Return exactly: three percentages with source name and date. Do not summarize
other content. Sources: Synergy Research, Gartner, IDC reports."
```

**Why**: Straightforward queries become complex when over-deployed — using 5 subagents to find a single statistic wastes budget and produces conflicting numbers.

---

## Anti-Pattern Catalog

### ❌ Depth-First Instructions Without Angle Differentiation

**Detection**:
```bash
# In subagent instruction files or research plans — look for identical scope descriptions
grep -A5 "Subagent [0-9]" research/*/report.md | grep -c "same topic"
# Manual check: are all subagent subjects identical?
grep "Subagent [0-9]\+:" research/*/plan.md | sort | uniq -d
```

**What it looks like**:
```markdown
Subagent 1: "Research AI regulation trends"
Subagent 2: "Research AI regulation trends"
Subagent 3: "Research AI regulation trends"
```

**Why wrong**: All three subagents converge on the same sources and produce redundant content. The lead agent has nothing to reconcile — just three copies of similar findings. Synthesis produces an averaged summary, not an integrated analysis.

**Fix**: Assign distinct methodological angles (theoretical / empirical / critical), distinct geographies (US / EU / China), or distinct timeframes (historical / current / projected).

---

### ❌ Breadth-First With Mismatched Deliverable Formats

**Detection**:
```bash
# Check for inconsistent word count specifications across parallel instructions
grep -E "words|word count|[0-9]+-[0-9]+ word" research/*/plan.md
```

**What it looks like**:
```markdown
Subagent 1 (PostgreSQL): "Write a detailed technical analysis, include all relevant benchmarks,
historical context, and community adoption trends."

Subagent 2 (MongoDB): "Provide a 200-word overview of write performance."

Subagent 3 (Cassandra): "List the pros and cons."
```

**Why wrong**: Lead agent cannot compare findings — one subagent returned 800 words of technical depth, another returned a bullet list. Synthesis requires resampling, not comparing.

**Fix**: Specify identical format constraints across all parallel instructions: same word count range, same section headings, same required data points.

---

### ❌ Using Depth-First Strategy for a Comparison Query

**Detection**:
```bash
# Queries containing "compare", "vs", "versus", "difference between" should use breadth-first
grep -i "compare\|vs\.\|versus\|difference between" research/*/report.md | head -20
```

**What it looks like**:
```markdown
# Query: "Compare React vs Vue for enterprise apps"
# Wrong strategy applied:
Subagent 1: "Theoretical foundations of frontend frameworks"
Subagent 2: "Historical evolution of JavaScript frameworks"
Subagent 3: "Performance characteristics of SPAs"
```

**Why wrong**: Angles don't map to options. The lead agent now has generic framework theory but cannot answer "which should I choose for enterprise apps?"

**Fix**: Detect comparison keywords and switch to breadth-first — one subagent per option.

---

## Error-Fix Mappings

| Error Symptom | Root Cause | Fix |
|---------------|------------|-----|
| Subagents return overlapping content | Depth-first with no angle differentiation | Assign distinct methodological perspectives before dispatching |
| Synthesis cannot produce comparison table | Breadth-first with mismatched formats | Enforce uniform word count + section headings across all parallel instructions |
| Research is too broad, covers adjacent topics | Straightforward query over-deployed with 4+ subagents | Reduce to 1–2 subagents, add explicit OUT-OF-SCOPE clause to instructions |
| Subagent returns meta-analysis instead of data | Scope boundary missing from instruction | Add explicit "Do NOT summarize other research — focus only on [specific topic]" |
| Final report has gaps despite many subagents | Wrong query type selected | Re-classify before deploying — depth-first ≠ breadth-first ≠ straightforward |

---

## Detection Commands Reference

```bash
# Check for unclassified research plans (missing query type header)
grep -L "Depth-first\|Breadth-first\|Straightforward" research/*/plan.md

# Find parallel subagent instructions with no scope boundaries
grep -L "OUT OF SCOPE\|Do NOT\|Focus only" research/*/instructions/*.md

# Detect comparison queries that should use breadth-first
grep -il "compare\|vs\.\|versus\|difference between" research/*/plan.md
```

---

## See Also

- `delegation-patterns.md` — How to write subagent instructions once query type is classified
- `error-catalog.md` — Common failures when query type is misclassified
