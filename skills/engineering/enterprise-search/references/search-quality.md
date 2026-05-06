# Search Quality Reference

Deep reference for search quality metrics, judgment collection, offline evaluation, online testing, and search funnel analysis. Loaded by QUALITY mode.

---

## Metrics Reference

### Ranking Metrics

| Metric | Formula (Simplified) | Measures | Range | Good Value |
|--------|----------------------|----------|-------|------------|
| **nDCG@k** | Normalized discounted cumulative gain at rank k | Graded relevance considering position | 0–1 | > 0.6 (domain-dependent) |
| **MRR** | 1 / rank of first relevant result | How quickly user finds answer | 0–1 | > 0.5 |
| **P@k** | Relevant docs in top k / k | Precision in top results | 0–1 | > 0.4 at k=5 |
| **Recall@k** | Relevant docs in top k / total relevant | Coverage of relevant docs | 0–1 | > 0.7 for recall-critical |
| **MAP** | Mean of average precision per query | Balanced precision-recall | 0–1 | > 0.3 |
| **ERR** | Expected reciprocal rank (cascade model) | Expected user effort to find answer | 0–1 | Higher is better |

### When to Use Which

| Use Case | Primary Metric | Secondary | Why |
|----------|---------------|-----------|-----|
| Web/general search | nDCG@10 | MRR | Multiple relevant results at graded levels |
| Navigational / FAQ | MRR | P@1 | User wants the one right answer fast |
| E-commerce | nDCG@20, P@5 | Revenue per search | Multiple good products, care about top page |
| Legal / compliance | Recall@100 | P@20 | Missing a relevant document has high cost |
| Autocomplete | MRR@5 | Completion rate | User needs the suggestion quickly |
| Knowledge base | nDCG@5 | Click-through rate | First page must be good, few results shown |

### nDCG Deep Dive

Normalized Discounted Cumulative Gain accounts for both relevance grade and position. Higher-ranked positions get more weight (logarithmic discount).

**Relevance grades** (standard 4-point scale):

| Grade | Label | Definition |
|-------|-------|------------|
| 3 | Perfect | Exactly what the user wanted. Would stop searching. |
| 2 | Good | Relevant and useful. Partially addresses the need. |
| 1 | Fair | Marginally relevant. Contains some useful information. |
| 0 | Bad | Not relevant. Does not address the query. |

**Interpretation**:
- nDCG@10 = 0.8+: Strong relevance. Users consistently find good results near the top.
- nDCG@10 = 0.5–0.8: Acceptable. Room for improvement in ranking.
- nDCG@10 < 0.5: Significant relevance issues. Investigate query coverage and ranking.

### Metric Computation Gotchas

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Unjudged documents | Treated as irrelevant (pessimistic) or skipped (optimistic) — changes scores | Use "judged only" nDCG or ensure judgment coverage for top results |
| Position bias in click data | Top results get more clicks regardless of relevance | Apply position debiasing (inverse propensity weighting) |
| Query set selection | Head queries dominate, tail queries under-represented | Stratify by query frequency: head (top 100), torso (100-1000), tail (1000+) |
| Small judgment sets | Noisy metric estimates | Report confidence intervals. Minimum 200 judged queries for stable nDCG. |
| Grade inflation | Annotators tend toward generous grades over time | Periodic calibration sessions. Inter-annotator agreement checks. |

---

## Judgment Collection

### Guidelines Template

Provide annotators with:

1. **Task definition**: "You will be shown a search query and a document. Rate how well the document answers the query."
2. **Grade scale**: Use the 4-point scale above. Define each grade with 2-3 examples from your domain.
3. **Edge case rules**:
   - Partially relevant: Grade 1 (Fair)
   - Relevant but outdated: Grade 1 (Fair) with note
   - Relevant to a different interpretation: Grade 1 or 0 depending on ambiguity
   - Duplicate of a higher-graded result: Grade normally (dedup is a ranking concern)
4. **Query intent**: Annotator should consider what a reasonable user meant by this query.

### Collection Methods

| Method | Volume | Quality | Cost | Latency |
|--------|--------|---------|------|---------|
| **Expert annotation** | 50-200 queries, 10-20 docs each | Highest (domain expertise) | $$$ | Days-weeks |
| **Crowdsourced** | 500-5000 queries | Good (with quality controls) | $$ | Days |
| **Click-based** | 10K+ queries (implicit) | Moderate (biased) | $ | Continuous |
| **LLM-assisted** | 1K+ queries | Good for initial pass | $ | Hours |
| **Pairwise preference** | Any scale | High agreement, lower coverage | $$ | Varies |

### Click-Based Judgments (Implicit Feedback)

| Signal | Interpretation | Reliability |
|--------|---------------|-------------|
| Click + long dwell (>30s) | Likely relevant | Moderate-High |
| Click + short dwell (<5s) | Possibly irrelevant (pogo-sticking) | Low |
| No click, high position | Possibly irrelevant (skipped) | Low (snippet may have answered) |
| Last click in session | Likely satisfying result | High |
| Reformulated query | Previous results unsatisfying | Moderate (negative signal) |

**Position debiasing**: Clicks are biased toward higher positions. Use inverse propensity scoring (IPS) to adjust: `weight = 1 / P(click | position)` estimated from randomization experiments.

### LLM-Assisted Judgment Workflow

1. Generate initial judgments with LLM (prompt includes query, document, grading scale with examples)
2. Human-review a 10-20% sample for calibration
3. Measure LLM-human agreement (target: Cohen's kappa > 0.6)
4. Flag low-confidence judgments for human review
5. Use LLM judgments for development evaluation, human judgments for final decisions

---

## Offline Evaluation

### Test Harness Design

```
Evaluation Pipeline:
1. Load judgment set (queries + graded documents)
2. For each configuration to evaluate:
   a. Run each query against the search index
   b. Collect top-k results with scores
   c. Match results to judgments
   d. Compute metrics (nDCG@k, MRR, P@k)
3. Compare configurations
4. Report with confidence intervals
```

### Statistical Significance

Use paired tests when comparing two configurations on the same query set:

| Test | When | Implementation |
|------|------|----------------|
| Paired t-test | Metric differences approximately normal | `scipy.stats.ttest_rel` |
| Wilcoxon signed-rank | Non-normal distribution, ordinal data | `scipy.stats.wilcoxon` |
| Bootstrap confidence interval | Small sample, no distributional assumption | Resample 1000x, compute metric, report 95% CI |

**Minimum detectable effect**: With 200 queries, you can reliably detect ~0.03 nDCG@10 difference at p<0.05. With 500 queries, ~0.02 difference.

### Evaluation Set Management

| Practice | Why |
|----------|-----|
| Stratify by query type | Head/torso/tail queries have different characteristics |
| Version the judgment set | Track changes over time, reproduce evaluations |
| Refresh quarterly | Corpus evolves, old judgments become stale |
| Separate dev/test sets | Prevent overfitting to evaluation queries |
| Include known failure queries | Ensure regressions are caught |

---

## Online Testing

### A/B Testing for Search

| Component | Design Decision |
|-----------|----------------|
| **Randomization unit** | User (not query) — prevents same user seeing inconsistent results |
| **Primary metric** | Engagement: click-through rate, conversion, or task completion |
| **Guardrail metrics** | Latency p50/p99, zero-result rate, error rate |
| **Sample size** | Pre-compute using minimum detectable effect and baseline variance |
| **Duration** | Minimum 1-2 weeks to capture day-of-week effects |

### Interleaving Experiments

More efficient than A/B testing for ranking changes. Show interleaved results from two ranking functions, measure which function's results get more clicks.

| Method | How | Pros |
|--------|-----|------|
| **Team Draft Interleaving** | Alternate results from each ranker (like picking teams) | Simple, well-understood |
| **Balanced Interleaving** | Ensure equal representation from each ranker | Controls for position bias better |
| **Optimized Interleaving** | Choose interleaving that maximizes statistical power | Most efficient, more complex |

**Advantage**: Interleaving detects ranking differences with 10-100x fewer queries than A/B testing because both variants are shown to the same user in the same results page.

### Guardrail Monitoring

| Metric | Alert Threshold | Why |
|--------|----------------|-----|
| Zero-result rate | > 5% increase | Users seeing empty results pages |
| Query latency p99 | > 20% increase | Performance degradation |
| Click-through rate | > 10% decrease | Results not compelling |
| Reformulation rate | > 15% increase | Users not finding what they need |
| Error rate | > 1% absolute | System stability |

---

## Search Funnel Analysis

### The Search Funnel

```
[Query Submitted]
      ↓  (abandonment: user leaves without clicking)
[Results Viewed]
      ↓  (zero-click: snippet answered or nothing relevant)
[Result Clicked]
      ↓  (pogo-stick: quick return to results)
[Content Consumed]  (dwell time > 30s)
      ↓
[Task Completed]  (conversion, resolution, etc.)
```

### Funnel Metrics

| Stage | Metric | Healthy Range | What Bad Looks Like |
|-------|--------|--------------|---------------------|
| Query -> Results | Success rate | > 95% | Errors, timeouts, zero results |
| Results -> Click | Click-through rate | 40-70% | < 30% = results not compelling |
| Click -> Dwell | Dwell rate (>30s) | > 60% | < 40% = misleading snippets or wrong results |
| Click -> Task | Conversion rate | Domain-specific | Declining = relevance or UX issue |
| Query -> Reformulation | Reformulation rate | < 25% | > 35% = users not finding what they need |

### Query Classification for Analysis

Segment funnel metrics by query class to find specific problem areas:

| Segment | Examples | Why Segment |
|---------|---------|-------------|
| Head / torso / tail | Top 100 / 100-1K / 1K+ | Tail queries often have worse relevance |
| By intent | Navigational / informational / transactional | Different intents have different success patterns |
| By result count | Zero / few (1-3) / normal / many (100+) | Too few or too many results = different problems |
| By query length | 1 word / 2-3 words / 4+ words | Short queries are more ambiguous |
| New vs returning | First query / refined query | Reformulation patterns reveal gaps |

---

## Continuous Quality Monitoring

### Dashboard Components

| Component | Shows | Refresh |
|-----------|-------|---------|
| nDCG@10 trend | Relevance over time (weekly evaluation runs) | Weekly |
| Zero-result rate by day | Queries returning no results | Daily |
| CTR by query segment | Click-through by query type/category | Daily |
| p50/p99 latency | Search performance | Real-time |
| Top zero-result queries | Specific queries that need coverage | Daily |
| Top reformulated queries | Queries users refine = relevance gap | Weekly |
| Judgment freshness | How old is the evaluation set | Monthly |

### Alerting Rules

| Condition | Alert Level | Action |
|-----------|-------------|--------|
| nDCG@10 drops > 5% week-over-week | High | Investigate recent config/data changes |
| Zero-result rate > 10% | High | Check index health, query pipeline |
| p99 latency > 2x baseline | Medium | Profile slow queries |
| CTR drops > 10% for a segment | Medium | Compare ranking for that segment |
| Judgment set > 6 months old | Low | Schedule refresh |

---

## Common Pitfalls and Positive Alternatives

| Pitfall | What to Do Instead |
|---------|-------------------|
| Using only click data for relevance | Combine click signals with expert judgments. Clicks are biased by position and snippet quality. |
| Reporting metrics without confidence intervals | Always include confidence intervals or standard deviation. A 0.02 nDCG improvement may be noise. |
| Tuning on the full evaluation set | Split into dev and test. Tune on dev, report on test. Prevents overfitting to the evaluation set. |
| Measuring only nDCG without engagement metrics | nDCG measures ranking quality. Engagement (CTR, dwell, conversion) measures user satisfaction. Track both. |
| Running A/B tests for less than a week | Day-of-week effects are real. Run for at least 1-2 full weeks. |
| Ignoring tail queries in evaluation | Tail queries are 50%+ of volume. Include them in judgment sets proportionally. |
