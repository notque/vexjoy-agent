# Search index decisions

Preserve these action-changing constraints:

- Mapping types cannot generally be changed in place; create a versioned index, reindex, verify failures/counts, then atomically swap an alias.
- Test an analyzer with `_analyze` on representative language before indexing. Search and index analyzers may differ deliberately; synonyms normally belong at search time when updates must not force reindexing.
- Prefer explicit mappings for operational fields. Dynamic mappings can create field explosions and wrong types; watch total field count.
- Use keyword fields for exact filter/sort/aggregation and text fields for analysis. Multi-fields support both; do not aggregate on text.
- ILM rollover conditions and shard count follow measured index growth and recovery needs, not a fixed document-count rule.
- Before destructive reindex/cutover: freeze the source query, record source count, require empty reindex failures, compare destination count/sample queries, and make alias swap atomic.
- Index templates affect newly created indices, not existing mappings. Template priority decides collisions.
