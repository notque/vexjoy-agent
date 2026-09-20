# Relevance-tuning decisions

Start from a versioned judged query set and record per-query results, not only the mean.

- BM25 `k1` controls term-frequency saturation; `b` controls length normalization. Tune per field/corpus, never from a copied constant.
- Damp popularity/freshness signals (for example logarithmic or saturation functions); raw values can overwhelm text relevance.
- Use rescore for expensive proximity, LTR, vector, or script scoring over a bounded first-pass window.
- Move to LTR only with stable labels, multiple useful non-text features, and capacity to maintain feature/model pipelines. Keep a BM25 baseline and inspect feature leakage.
- Hybrid lexical/vector weights require normalization or rank fusion; raw score scales are not comparable.
- Extreme field boosts usually hide query-structure defects. Change one signal, measure held-out nDCG/MRR and important slices, and retain latency as a guardrail.
