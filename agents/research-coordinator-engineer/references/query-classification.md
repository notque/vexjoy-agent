# Query Classification Reference

> **Scope**: Classifying research queries into depth-first, breadth-first, or straightforward before subagent deployment.
> **Version range**: All versions
> **Generated**: 2026-04-13

---

## Pattern Table

| Query Type | Subagent Count | Instruction Style | Synthesis Style |
|-----------|---------------|------------------|----------------|
| Depth-first | 3–5 | Different methodological angles | Reconcile across perspectives |
| Breadth-first | 1 per topic (3–7) | Scoped to one entity | Side-by-side comparison |
| Straightforward | 1–2 | Precise target, tight deliverable | Direct extraction |

---

## Correct Patterns

### Depth-First: Multiple Angles on One Topic

Distinct methodological perspectives — theoretical, empirical, adversarial. Never same angle twice.

```markdown
Query: "How does transformer attention scaling affect reasoning?"

Subagent 1 — Theoretical: mathematical mechanisms, published theory. 300-400 words.
Subagent 2 — Empirical: benchmark results, specific models and scores. 300-400 words.
Subagent 3 — Failure modes: cases where more attention doesn't help. 300-400 words.
```

---

### Breadth-First: One Subagent Per Entity

Same deliverable format across all for clean comparison.

```markdown
Query: "Compare PostgreSQL, MongoDB, and Cassandra for write-heavy workloads"

Subagent 1 — PostgreSQL: write throughput, WAL, partitioning. 250-350 words. 2+ benchmarks.
Subagent 2 — MongoDB: write concern, WiredTiger, sharding. 250-350 words. 2+ benchmarks.
Subagent 3 — Cassandra: LSM-tree write path, compaction, consistency. 250-350 words. 2+ benchmarks.
```

Uniform format makes synthesis mechanical — slot into comparison matrix.

---

### Straightforward: Tight Target

```markdown
Query: "What is the current market share of AWS vs Azure vs GCP?"

Subagent 1: "Find 2024-2025 cloud market share for AWS, Azure, GCP. Return exactly:
three percentages with source name and date. Sources: Synergy Research, Gartner, IDC."
```

Over-deploying simple queries wastes budget and produces conflicting numbers.

---

## Pattern Catalog

### Assign Distinct Angles to Depth-First Subagents

**Detection**:
```bash
grep "Subagent [0-9]\+:" research/*/plan.md | sort | uniq -d
```

**Signal**: All three subagents have identical scope. Produces redundant content, no reconciliation possible.

**Preferred action**: Distinct methodological angles, geographies, or timeframes.

---

### Use Uniform Deliverable Format Across Parallel Subagents

**Detection**:
```bash
grep -E "words|word count" research/*/plan.md
```

One returns 800 words, another a bullet list — synthesis requires resampling, not comparing.

**Preferred action**: Same word count range, section headings, and required data points.

---

### Use Breadth-First for Comparison Queries

**Detection**:
```bash
grep -i "compare\|vs\.\|versus\|difference between" research/*/report.md
```

Depth-first angles on a comparison query produce framework theory, not actionable comparison.

**Preferred action**: Detect comparison keywords, switch to breadth-first — one subagent per option.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Overlapping content | Depth-first without angle differentiation | Assign distinct perspectives |
| No comparison table possible | Mismatched formats | Enforce uniform format |
| Too broad | Straightforward over-deployed | Reduce to 1-2 subagents, add OUT-OF-SCOPE |
| Meta-analysis instead of data | Missing scope boundary | Add explicit deliverable type |
| Gaps despite many subagents | Wrong query type | Re-classify before deploying |

---

## Detection Commands Reference

```bash
grep -L "Depth-first\|Breadth-first\|Straightforward" research/*/plan.md
grep -L "OUT OF SCOPE\|Focus only" research/*/instructions/*.md
grep -il "compare\|vs\.\|versus" research/*/plan.md
```

---

## See Also

- `delegation-patterns.md` — Instruction writing after classification
- `error-catalog.md` — Failures from misclassification
