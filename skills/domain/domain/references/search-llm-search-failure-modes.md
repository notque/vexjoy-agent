# Search-engineering failure guardrails

LLM-default advice often fails because it ignores corpus and engine evidence. Reject recommendations that:

- tune boosts, BM25, analyzers, shards, or caches without a measured baseline and target query slice;
- mix Elasticsearch, OpenSearch, Solr, Vespa, or Typesense syntax without naming platform/version;
- infer mapping from documents instead of checking mapping/field capabilities;
- prescribe vector or LTR as an upgrade without labels, operational capacity, and a simpler baseline;
- use click data as unbiased relevance truth;
- change several ranking variables at once;
- copy thresholds, shard sizes, refresh intervals, or “good” nDCG values as universal constants;
- claim success from a valid query alone rather than held-out judgments plus latency/error guardrails.

State assumptions, provide the exact observation that would falsify the diagnosis, and distinguish reversible experiments from reindexing or schema changes.
