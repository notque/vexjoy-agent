# OpenSearch detection safety patterns

These are incident-derived constraints.

## Chained-findings index flood

A chained-findings monitor can create `chained_findings_queries_*` indices on every run. Trend `_cat/indices` and inspect monitor configuration. For frequent execution, create one detection-owned query index with an explicit mapping, disable unintended dynamic field creation, point the monitor at it, and verify the index count stabilizes.

## Alias bootstrap conflict

Security Analytics alias bootstrapping can fail against a shared datastream whose field already has a concrete mapping. Do not mutate that stream. Prefer a detection-owned index with the expected mapping and an ingestion/reindex path. If cleaning an existing index:

1. create the replacement mapping;
2. run async `_reindex`;
3. require the task's `status.failures` to be empty;
4. swap aliases atomically.

An existing concrete field cannot be converted to an alias with `PUT _mapping`; reindexing is required.

## Type failures

- aggregation on `text`: use a mapped keyword subfield or reindex;
- malformed hostname in an `ip` field: fix ingestion; `ignore_malformed` is only a temporary containment;
- missing nested path: verify the parent object and actual documents, not only `_mapping/field`;
- alias/text mismatch: inspect `GET {index}/_mapping/field/{name}` and reindex to the intended type.
